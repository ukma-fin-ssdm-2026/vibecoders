# Звіт про надійність (Лаб 9)

**Команда:** vibecoders (NRI Organizer API)
**Документи:** повний опис знахідок з ланцюгом «несправність → помилка → відмова» у [scavenger-hunt.md](./scavenger-hunt.md).
**Тести:** `src/api/tests/reliability/` (54 тести у 6 файлах; запускаються окремим job і разом з рештою через `pytest src/api/tests`).

## 1. Усі знайдені проблеми

| ID | Проблема | Категорія | Критичність | Статус |
|----|----------|-----------|-------------|--------|
| R-01 | Обробник 500 нічого не логує | A, D | Висока | виправлено (Д) |
| R-02 | Сповіщення про скасування пишуться після коміту, поза транзакцією (блокування кімнати) | D | Висока | виправлено (А) |
| R-03 | Видалення гри: три окремі транзакції, без `db_lock`, сповіщення до видалення | D, E | Висока | виправлено (Б) |
| R-04 | `remove_player`: читання-зміна-запис без блокування, втрата чужого запису | E | Середня | виправлено (В) |
| R-05 | З'єднання SQLite без явного тайм-ауту, дубльовані визначення в `db.py` | B | Середня | частково виправлено (Д) |
| R-06 | `OperationalError` потрапляє в загальний 500 без `Retry-After` | A, B | Середня | виправлено (Д) |
| R-07 | Збій запису OpenAPI-файлу при старті валить увесь сервіс | B | Середня | виправлено (Г) |
| R-08 | Блокувальний ввід-вивід і pbkdf2 в `async def` | E | Середня | відкрито |
| R-09 | Лічильник невдалих входів у пам'яті, без блокування | D, E | Середня | відкрито |
| R-10 | `int(...)` над id з БД без перевірки формату | C | Низька | виправлено (PR #212) |
| R-11 | Мовчазне резервне значення `PASSWORD_SALT` | D | Середня | виправлено (PR #212) |
| R-12 | `fetch` у фронтенді без тайм-ауту | B | Середня | відкрито |
| R-13 | `getMe` повертає `null` для будь-якої помилки | D | Низька | відкрито |
| R-14 | Повне сканування ігор під `db_lock` | E | Низька | відкрито |
| R-15 | Кеш проксі без меж і з ручною інвалідацією | D | Низька | відкрито |

Для зручності виправлення позначені літерами А, Б, В, Г, Д. Виправлення Д повністю закриває R-01 і R-06 та частково адресує R-05: усі три стосуються шару роботи з БД, але дубльовані визначення з R-05 залишилися.

R-05 виправлено частково: активний SQLite engine тепер має явний `DB_TIMEOUT_SECONDS`, але `src/api/db.py` усе ще повторно визначає `resolve_database_url`, `enable_sqlite_foreign_keys`, `DATABASE_URL` та `engine` (перший engine з timeout 30 с замінюється нижче). Прибирання дубльованих визначень не входило до цієї роботи; це варто винести в окрему зміну.

## 2. Виправлення: до і після

### А. Блокування кімнати: скасування ігор і сповіщення в одній транзакції (R-02)

До (`routes/rooms.py`):

```python
            db.commit()
        finally:
            db.close()

    for game_id, title, players in notifications:
        GAMES._cache.pop(game_id, None)
        notify_game_cancelled(game_id, title, players)
```

Після:

```python
            for game in overlapping_games:
                player_ids = [
                    player_id
                    for (player_id,) in db.query(EnrollmentModel.player_id)
                    .filter(EnrollmentModel.game_id == game.id)
                    .all()
                ]
                db.add_all(build_cancellation_rows(game.id, game.title, player_ids))
                cancelled_game_ids.append(game.id)
                db.delete(game)
```

Рядки сповіщень створює нова функція `build_cancellation_rows` у `notifications.py`, її ж використовує `notify_game_cancelled`. Після коміту залишається лише скидання кешу.

### Б. Видалення гри: одна транзакція під блокуванням (R-03)

До (`routes/games.py`):

```python
    record = get_game_or_404(game_id)
    ensure_can_manage(record, user.id, user.role)
    notify_game_cancelled(game_id, record.title, ENROLLMENTS.get(game_id, []))
    del GAMES[game_id]
    ENROLLMENTS.pop(game_id, None)
    return Response(status_code=204)
```

Після:

```python
    with db_lock:
        record = get_game_or_404(game_id)
        ensure_can_manage(record, user.id, user.role)
        delete_game_with_notifications(game_id)
    return Response(status_code=204)
```

Нова `store.delete_game_with_notifications` у одній сесії читає записаних гравців, додає сповіщення, видаляє гру і робить один `commit`; при будь-якому винятку виконується `rollback`.

### В. Скасування запису гравця під `db_lock` (R-04)

До:

```python
    record = get_game_or_404(game_id)
    ...
    players = ENROLLMENTS.get(game_id, [])
    remaining = [p for p in players if p.user_id != user_id]
    ...
    ENROLLMENTS[game_id] = remaining
    return Response(status_code=204)
```

Після: те саме тіло функції обгорнуте в `with db_lock:`, тобто взаємно виключається з `enroll_player`, `replace_game`, `patch_game`, `delete_game`.

### Г. Стійкий старт без запису OpenAPI-файлу (R-07)

До (`main.py`):

```python
    seed_db()
    save_openapi_spec(app)
    yield
```

Після:

```python
    seed_db()
    try:
        save_openapi_spec(app)
    except OSError as exc:
        logger.warning("OpenAPI specification was not saved, API starts without it: %s", exc)
    yield
```

### Д. Збій БД: явний тайм-аут, відповідь 503, логування (R-01, R-05, R-06)

До (`errors.py`, `db.py`):

```python
    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception):
        return error_response(500, "INTERNAL_ERROR", "Внутрішня помилка сервера")
```

```python
        connect_args={"check_same_thread": False} if url.get_backend_name() == "sqlite" else {},
```

Після:

```python
    @app.exception_handler(OperationalError)
    async def database_unavailable_handler(request: Request, exc: OperationalError):
        logger.error("Database unavailable during %s %s", request.method, request.url.path, exc_info=exc)
        return error_response(
            503,
            "SERVICE_UNAVAILABLE",
            "Сервіс тимчасово недоступний, повторіть запит пізніше",
            headers={"Retry-After": str(RETRY_AFTER_SECONDS)},
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception):
        logger.error("Unhandled error during %s %s", request.method, request.url.path, exc_info=exc)
        return error_response(500, "INTERNAL_ERROR", "Внутрішня помилка сервера")
```

```python
    connect_args = {"check_same_thread": False, "timeout": read_db_timeout()} if url.get_backend_name() == "sqlite" else {}
```

`read_db_timeout()` читає `DB_TIMEOUT_SECONDS`; для порожнього, нечислового, нульового, від'ємного, `nan` і `inf` значення логує попередження і повертає 10 с. Раніше діяв вбудований тайм-аут `sqlite3` у 5 с.

### Е. Валідація ID і налаштування солі пароля (R-10, R-11)

До (`store.py`):

```python
int(user_id.removeprefix("user_"))
PASSWORD_SALT = os.getenv("PASSWORD_SALT", "default-insecure-salt-for-dev").encode("utf-8")
```

Після:

```python
def _numeric_id_suffix(identifier: str, prefix: str) -> Optional[int]:
    if not identifier.startswith(prefix):
        return None
    suffix = identifier[len(prefix) :]
    if not suffix.isascii() or not suffix.isdecimal():
        return None
    return int(suffix)


def _load_password_salt() -> bytes:
    configured_salt = os.getenv("PASSWORD_SALT")
    if configured_salt and configured_salt.strip():
        return configured_salt.encode("utf-8")
    if os.getenv("APP_ENV", "development").strip().lower() == "production":
        raise RuntimeError("PASSWORD_SALT must be configured in production")
    logger.warning("PASSWORD_SALT is not set; using the insecure development salt")
    return b"default-insecure-salt-for-dev"
```

`_numeric_id_suffix` використовується і для `user_...`, і для `game_...`: пошкоджений суфікс і Unicode-цифри не ламають реєстрацію чи генерацію ID. У Render задано `APP_ENV=production` і генерується `PASSWORD_SALT`. У development відсутня сіль дає явне попередження та зберігає локальний запуск. Зміну солі треба узгоджувати з наявними хешами: хеші, створені з іншою сіллю, більше не перевіряться.

**Відхилення від початкового обсягу R-11:** початково просилося лише логувати попередження за відсутності солі. PR #212 додав ще й fail-fast запуску в production без `PASSWORD_SALT`. Це додаткове посилення конфігурації, а не лише логування; у Render встановлено `APP_ENV=production` і секрет генерується автоматично. Команді слід врахувати та узгодити цю зміну поведінки перед розгортанням інших середовищ.

## 3. Застосовані патерни надійності

| Патерн | Де |
|--------|----|
| Транзакція «все або нічого» | А, Б |
| Взаємне виключення (блокування) | Б, В |
| Тайм-аут на зовнішню залежність | Д (`DB_TIMEOUT_SECONDS`) |
| Вузький `catch` (`OSError`, `OperationalError`) | Г, Д |
| Захисна перевірка входу | Д (`read_db_timeout`) |
| Логування замість мовчазного збою | Г, Д |
| Резервне значення, явне й залоговане | Д (10 с за замовчуванням) |
| Контрольована відповідь замість падіння | Д (503 з `Retry-After`) |
| Перевірка префікса й ASCII-цифр до `int()` | Е (R-10) |
| Fail-fast для конфігурації production, залогований dev fallback | Е (R-11) |

Повторів (retry) не додавали. Шлях збою БД короткий і повертає 503 з `Retry-After`, тож повтор лишається на клієнті. Бонус «повтори з відступом і джитером» не заявляємо.

## 4. Режими відмов і відновлення

| Виправлення | Швидка чи безпечна відмова | Що бачить користувач під час збою | Як система повертається до норми |
|-------------|----------------------------|-----------------------------------|----------------------------------|
| А. Блокування кімнати | Швидка. Хибний стан (ігри скасовано, гравців не повідомлено) гірший за відсутність відповіді | 503 `SERVICE_UNAVAILABLE`, блокування не створено, ігри на місці | Власник повторює запит після відновлення БД; ручне втручання не потрібне, бо нічого не змінилося |
| Б. Видалення гри | Швидка. Не можна сповістити про скасування гри, яка лишилась | 503, гра і записи гравців не змінені | Повторити `DELETE` після відновлення БД |
| В. Скасування запису | Не вибір відмови, а усунення гонки: запит чекає на блокування, а не видає застарілу відповідь | Звичайна відповідь, трохи більша затримка | Автоматично |
| Г. Старт без OpenAPI-файлу | Безпечна. Документація допоміжна, API важливіший за неї | Усе працює; у логу попередження | Виправити права на `docs/api/`, файл буде записано при наступному старті (або `generate_openapi.py`) |
| Д. Збій БД | Швидка. Для читання немає резервного джерела, а застарілі дані гірші за явну помилку | 503 з `Retry-After: 5`; для непередбачених винятків 500 із загальним текстом без внутрішніх деталей | Клієнт повторює запит; після відновлення БД усе працює без перезапуску (є тест `test_service_recovers_after_database_outage`) |
| Е. Некоректний ID або відсутня сіль у production | Невідомий суфікс ігнорується; без солі в production сервіс швидко завершує старт | Для ID — звичайна реєстрація з наступним валідним ID; для помилкової production-конфігурації сервіс не приймає запити | Виправити запис/конфігурацію; перезапустити сервіс. У development fallback лишається лише для локального запуску, його використання записується в лог |

## 5. Тести надійності

Розташування: `src/api/tests/reliability/`. Усього 54 тести у 6 файлах. Усі перевірки R-10 і R-11 розташовані у `test_reliability_id_validation.py`. `check_traceability.py` рекурсивно знаходить також вкладені reliability-тести; `test_read_tests_includes_nested_reliability_tests` захищає це від регресії.

| Тип | Тест | Що перевіряє | Виправлення |
|-----|------|--------------|-------------|
| Обробка помилки | `test_unexpected_exception_gives_generic_500_and_is_logged` | 500 із загальним текстом; причина є в логу, але не у відповіді | Д |
| Ін'єкція збою (БД) | `test_database_outage_gives_503_with_retry_after_and_no_internals` (3 ендпоїнти) | `OperationalError` дає 503 + `Retry-After`, без технічних деталей | Д |
| Ін'єкція збою (БД) | `test_service_recovers_after_database_outage` | після зникнення збою сервіс знову відповідає 200 | Д |
| Ін'єкція збою (запис сповіщень) | `test_room_block_is_rolled_back_when_notification_write_fails` | гра, блокування, записи гравців не змінені | А |
| Ін'єкція збою (запис сповіщень) | `test_room_block_succeeds_again_after_the_fault_is_gone` | повтор після збою працює і створює сповіщення | А |
| Ін'єкція збою (запис сповіщень) | `test_delete_game_keeps_game_and_players_when_notification_write_fails` | гра й гравці лишаються | Б |
| Ін'єкція збою (файлова система) | `test_application_starts_when_openapi_file_cannot_be_written` | `PermissionError` не заважає старту, є попередження в логу | Г |
| Конкурентність | `test_state_changing_requests_wait_for_the_global_lock` (2 ендпоїнти) | `remove_player` і `delete_game` чекають на `db_lock` | Б, В |
| Конкурентність | `test_parallel_enroll_and_unenroll_do_not_lose_enrollments` | запис і скасування запису паралельно не гублять запис | В |
| Граничні значення | `test_db_timeout_setting_falls_back_to_default_on_bad_input` (10 значень) | `None`, порожнє, `abc`, `0`, `-3`, `nan`, `inf`, `0.5`, `30` | Д |
| Граничні значення | `test_last_free_seat_can_be_taken_and_the_next_player_is_rejected` | остання вільна позиція проходить, наступна дає 409 `GAME_FULL` | |
| Граничні значення | `test_list_pagination_boundaries` (8 значень) | `limit` 0/1/100/101/-1, від'ємний `offset`, нечислове значення, величезний `offset` | |
| Граничні значення | `test_registration_ignores_malformed_id_suffixes` (5 випадків) | `user_abc`, `user_`, `user_1a` і Unicode-суфікси не переривають реєстрацію; створюється наступний ASCII ID | Е |
| Граничні значення | `test_next_game_id_ignores_malformed_id_suffixes` (3 випадки) | `game_abc` та Unicode-суфікси не спричиняють некоректний наступний ID | Е |
| Конфігурація | `test_missing_password_salt_warns_and_uses_development_default`, `test_missing_password_salt_fails_in_production`, `test_configured_password_salt_is_used` | використання dev fallback записується в лог; production без солі завершується з помилкою; задана сіль використовується | Е |

Усі вісім параметризованих перевірок із PR #212 виконано проти дофіксового `store.py` з `main`: сім падають очікувано — п'ять user ID-випадків і два Unicode game ID-випадки; `game_abc` проходить як контрольний. Для `user_٩` і `game_٩` старий код хибно породжує ID з номером 10; `user_²`, `user_abc`, `user_`, `user_1a` та `game_²` дають `ValueError`. `game_abc` і раніше коректно ігнорувався старою перевіркою `isdigit()`, тому його тест фіксує очікувану поведінку, а не регресію.

Також є тести на видалення неіснуючої гри (`delete_game_with_notifications` без помилки і без сповіщень), на читання `DB_TIMEOUT_SECONDS` з середовища і на передачу тайм-ауту в `create_engine`.

Після розширення тестів у PR #212 повний локальний прогін на Python 3.13.7 дав 351 passed, 1 xfailed і 96,64 % coverage (поріг 95 %); reliability suite — 54 passed. Перевірки Black, Flake8, Bandit і простежуваності проходять. Окремий job `reliability-tests` запускає весь каталог `src/api/tests/reliability/`. Наявний зелений прогін job у PR #213 — [GitHub Actions run 42996166588](https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/runs/42996166588) — містить попередні 43 тести, до перенесення тестів R-10/R-11. Після merge PR #212 job підхопить усі 54 тести. PR #213 ще не змерджений, тому пост-мерджевого прогону поки немає; посилання на нього треба оновити після merge і нового зеленого запуску.

**Перевірка «тест справді ловить помилку».** Тести без нових імен у коді (обробка помилки, 503, блокування) запускали проти коду до виправлень: 7 з 8 падають, проходить лише `test_parallel_enroll_and_unenroll...`. Це чесно сказати: гонка залежить від таймінгу, тож цей тест лише димовий. Детерміновану перевірку В дає тест із утримуваним `db_lock`. Тести атомарності (А, Б) на старому коді не запускаються, бо звертаються до нових функцій, тому на старому коді ми відтворили збої вручну: блокування кімнати дало 500, `game_1` видалена, блокування створене, сповіщень 0; видалення гри дало 500, гра існує, сповіщення для `user_2` уже створене.

## 6. Які проблеми залишилися відкритими

| ID | Чому не виправлено зараз | Що зробити далі |
|----|--------------------------|------------------|
| R-08 | Заміна `async def` на `def` у всіх обробниках змінює модель виконання й потребує повного регресу | Перевести обробники з синхронним ввідом-виводом на `def` (FastAPI запускає їх у пулі потоків); хешування паролів винести окремо |
| R-09 | Потрібне рішення про спільне сховище лічильника (колонка `failed_login_attempts` у `User` уже є, але не використовується) | Перенести лічильник у БД і оновлювати під блокуванням |
| R-12 | Зачіпає всі сторінки фронтенду | `AbortController` з тайм-аутом у `App.api` і повідомлення «сервер прокидається» |
| R-13 | Залежить від R-12 | Розрізняти 401 і мережеву помилку/503 |
| R-14 | Не критично за поточного обсягу даних | Фільтрувати ігри запитом у БД по кімнаті та інтервалу |
| R-15 | Низький ризик | Прибрати ручну інвалідацію або обмежити розмір кешу |

## 7. Бонуси

### Перевірка здоров'я (health check) сервісу

Заявляємо бонус «Перевірка здоров'я сервісу».

**Що зроблено.** Додано ендпоінт `GET /api/v1/health` (`src/api/routes/health.py`). Він не потребує авторизації й перевіряє критичну залежність сервісу, базу даних, читанням `users` через ту саму фабрику сесій, що й решта API. Простий `SELECT 1` міг би успішно виконатися без фактичного читання БД і дати хибний стан `healthy`. Окремого зовнішнього API сервіс не викликає, тому в перевірці лише база даних.

| Стан | Код | Тіло відповіді |
|------|-----|----------------|
| БД відповідає | 200 | `{"status": "healthy", "checks": {"database": "ok"}}` |
| БД недоступна | 503 + `Retry-After: 5` | `{"status": "unhealthy", "checks": {"database": "unavailable"}}` |

**Як це працює.** Функція `check_database` відкриває сесію, виконує `SELECT 1 FROM users LIMIT 1` і завжди закриває сесію в `finally`. Вузький `except SQLAlchemyError` перетворює збій БД на статус `unavailable` і пише запис в лог (лише назва типу винятку, без технічних деталей у відповіді). Інші винятки (помилки програмування) не ховаємо: вони йдуть у загальний обробник і дають 500. Обробник `get_health` синхронний (`def`), щоб запит до БД не блокував потік подій (див. R-08). Ендпоінт приховано зі схеми OpenAPI (`include_in_schema=False`), бо він службовий і не має описаного 4xx, якого вимагає `test_every_operation_has_summary_description_and_documented_4xx`.

**Тести** (`src/api/tests/reliability/test_reliability_health.py`, 6 тестів):

| Тест | Що перевіряє |
|------|--------------|
| `test_health_is_healthy_when_database_responds` | 200 і статус `healthy`, коли БД працює |
| `test_health_needs_no_authorization` | відповідь без заголовка `Authorization` |
| `test_health_is_unhealthy_when_database_connection_fails` | ін'єкція збою: фабрика сесій кидає `OperationalError`, відповідь 503, `Retry-After`, статус `unhealthy`, у відповіді немає технічних деталей, збій залоговано |
| `test_health_is_unhealthy_when_query_fails_and_session_is_closed` | ін'єкція збою: падає сам запит, статус `unhealthy`, сесію закрито |
| `test_health_recovers_after_database_outage` | після зникнення збою статус знову `healthy` без перезапуску |
| `test_health_does_not_hide_programming_errors` | непередбачений виняток не маскується під «нездоровий» стан, а дає 500 |

Без підключеного маршруту всі 6 тестів падають. Повний набір після розширення PR #212: 351 пройдено, 1 xfail, покриття 96,64 % (поріг CI 95 %), `black`, `flake8`, `bandit` і перевірка простежуваності проходять.

**Пояснення у відео:** потрібно, щоб хоча б один учасник команди розповів у своєму відео, що саме зроблено і як воно працює (за умовою бонуса).

### Окремий CI job

PR #213 додає job `reliability-tests`, який окремо запускає `src/api/tests/reliability/` на Python 3.9. Branch protection rules не змінювалися, тому цей check ще не є required status і бонус про обов'язкову перевірку PR не заявляємо.
