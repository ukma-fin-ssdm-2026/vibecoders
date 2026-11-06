# Звіт про надійність (Лаб 9)

**Команда:** vibecoders (NRI Organizer API)
**Документи:** повний опис знахідок з ланцюгом «несправність → помилка → відмова» у [scavenger-hunt.md](./scavenger-hunt.md).
**Тести:** `src/api/tests/reliability/` (37 тестів, запускаються разом з рештою через `pytest src/api/tests`).

## 1. Усі знайдені проблеми

| ID | Проблема | Категорія | Критичність | Статус |
|----|----------|-----------|-------------|--------|
| R-01 | Обробник 500 нічого не логує | A, D | Висока | виправлено (Д) |
| R-02 | Сповіщення про скасування пишуться після коміту, поза транзакцією (блокування кімнати) | D | Висока | виправлено (А) |
| R-03 | Видалення гри: три окремі транзакції, без `db_lock`, сповіщення до видалення | D, E | Висока | виправлено (Б) |
| R-04 | `remove_player`: читання-зміна-запис без блокування, втрата чужого запису | E | Середня | виправлено (В) |
| R-05 | З'єднання SQLite без явного тайм-ауту, дубльовані визначення в `db.py` | B | Середня | виправлено (Д) |
| R-06 | `OperationalError` потрапляє в загальний 500 без `Retry-After` | A, B | Середня | виправлено (Д) |
| R-07 | Збій запису OpenAPI-файлу при старті валить увесь сервіс | B | Середня | виправлено (Г) |
| R-08 | Блокувальний ввід-вивід і pbkdf2 в `async def` | E | Середня | відкрито |
| R-09 | Лічильник невдалих входів у пам'яті, без блокування | D, E | Середня | відкрито |
| R-10 | `int(...)` над id з БД без перевірки формату | C | Низька | відкрито |
| R-11 | Мовчазне резервне значення `PASSWORD_SALT` | D | Середня | відкрито |
| R-12 | `fetch` у фронтенді без тайм-ауту | B | Середня | відкрито |
| R-13 | `getMe` повертає `null` для будь-якої помилки | D | Низька | відкрито |
| R-14 | Повне сканування ігор під `db_lock` | E | Низька | відкрито |
| R-15 | Кеш проксі без меж і з ручною інвалідацією | D | Низька | відкрито |

Для зручності виправлення позначені літерами А, Б, В, Г, Д. Виправлення Д закриває три знахідки (R-01, R-05, R-06), бо всі вони стосуються одного шару: як система поводиться, коли БД не відповідає.

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

Повторів (retry) не додавали. Шлях збою БД короткий і повертає 503 з `Retry-After`, тож повтор лишається на клієнті. Бонус «повтори з відступом і джитером» не заявляємо.

## 4. Режими відмов і відновлення

| Виправлення | Швидка чи безпечна відмова | Що бачить користувач під час збою | Як система повертається до норми |
|-------------|----------------------------|-----------------------------------|----------------------------------|
| А. Блокування кімнати | Швидка. Хибний стан (ігри скасовано, гравців не повідомлено) гірший за відсутність відповіді | 503 `SERVICE_UNAVAILABLE`, блокування не створено, ігри на місці | Власник повторює запит після відновлення БД; ручне втручання не потрібне, бо нічого не змінилося |
| Б. Видалення гри | Швидка. Не можна сповістити про скасування гри, яка лишилась | 503, гра і записи гравців не змінені | Повторити `DELETE` після відновлення БД |
| В. Скасування запису | Не вибір відмови, а усунення гонки: запит чекає на блокування, а не видає застарілу відповідь | Звичайна відповідь, трохи більша затримка | Автоматично |
| Г. Старт без OpenAPI-файлу | Безпечна. Документація допоміжна, API важливіший за неї | Усе працює; у логу попередження | Виправити права на `docs/api/`, файл буде записано при наступному старті (або `generate_openapi.py`) |
| Д. Збій БД | Швидка. Для читання немає резервного джерела, а застарілі дані гірші за явну помилку | 503 з `Retry-After: 5`; для непередбачених винятків 500 із загальним текстом без внутрішніх деталей | Клієнт повторює запит; після відновлення БД усе працює без перезапуску (є тест `test_service_recovers_after_database_outage`) |

## 5. Тести надійності

Розташування: `src/api/tests/reliability/`. Усього 37 тестів у 4 файлах; повний набір проєкту: 333 пройдено, 1 xfail (раніше 296 пройдено), покриття 97 % (поріг CI 95 %), `black`, `flake8`, `bandit` і перевірка простежуваності проходять.

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

Також є тести на видалення неіснуючої гри (`delete_game_with_notifications` без помилки і без сповіщень), на читання `DB_TIMEOUT_SECONDS` з середовища і на передачу тайм-ауту в `create_engine`.

**Перевірка «тест справді ловить помилку».** Тести без нових імен у коді (обробка помилки, 503, блокування) запускали проти коду до виправлень: 7 з 8 падають, проходить лише `test_parallel_enroll_and_unenroll...`. Це чесно сказати: гонка залежить від таймінгу, тож цей тест лише димовий. Детерміновану перевірку В дає тест із утримуваним `db_lock`. Тести атомарності (А, Б) на старому коді не запускаються, бо звертаються до нових функцій, тому на старому коді ми відтворили збої вручну: блокування кімнати дало 500, `game_1` видалена, блокування створене, сповіщень 0; видалення гри дало 500, гра існує, сповіщення для `user_2` уже створене.

## 6. Які проблеми залишилися відкритими

| ID | Чому не виправлено зараз | Що зробити далі |
|----|--------------------------|------------------|
| R-08 | Заміна `async def` на `def` у всіх обробниках змінює модель виконання й потребує повного регресу | Перевести обробники з синхронним ввідом-виводом на `def` (FastAPI запускає їх у пулі потоків); хешування паролів винести окремо |
| R-09 | Потрібне рішення про спільне сховище лічильника (колонка `failed_login_attempts` у `User` уже є, але не використовується) | Перенести лічильник у БД і оновлювати під блокуванням |
| R-10 | Потребує вимог до формату id | Перевіряти `isdigit()` як у `_highest_game_number` |
| R-11 | Зміна поведінки при відсутній змінній ламає локальний запуск | У продакшні падати на старті без `PASSWORD_SALT`, у розробці лише логувати попередження; нагадати, що зміна солі інвалідує наявні хеші |
| R-12 | Зачіпає всі сторінки фронтенду | `AbortController` з тайм-аутом у `App.api` і повідомлення «сервер прокидається» |
| R-13 | Залежить від R-12 | Розрізняти 401 і мережеву помилку/503 |
| R-14 | Не критично за поточного обсягу даних | Фільтрувати ігри запитом у БД по кімнаті та інтервалу |
| R-15 | Низький ризик | Прибрати ручну інвалідацію або обмежити розмір кешу |

## 7. Бонуси

Бонусні пункти цього разу не заявляємо.
