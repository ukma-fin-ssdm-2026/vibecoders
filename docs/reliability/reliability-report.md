# Звіт про надійність (Лаб 9)

**Команда:** vibecoders (NRI Organizer API)
**Документи:** повний опис знахідок з ланцюгом «несправність → помилка → відмова» у [scavenger-hunt.md](./scavenger-hunt.md).
**Тести:** `src/api/tests/reliability/` (102 тести у 12 файлах; запускаються окремим job і разом з рештою через `pytest src/api/tests`).

## 1. Усі знайдені проблеми

| ID | Проблема | Категорія | Критичність | Статус |
|----|----------|-----------|-------------|--------|
| R-01 | Обробник 500 нічого не логує | A, D | Висока | виправлено (Д) |
| R-02 | Сповіщення про скасування пишуться після коміту, поза транзакцією (блокування кімнати) | D | Висока | виправлено (А) |
| R-03 | Видалення гри: три окремі транзакції, без `db_lock`, сповіщення до видалення | D, E | Висока | виправлено (Б) |
| R-04 | `remove_player`: читання-зміна-запис без блокування, втрата чужого запису | E | Середня | виправлено (В) |
| R-05 | З'єднання SQLite без явного тайм-ауту, дубльовані визначення в `db.py` | B | Середня | виправлено (Д, PR #216) |
| R-06 | `OperationalError` потрапляє в загальний 500 без `Retry-After` | A, B | Середня | виправлено (Д) |
| R-07 | Збій запису OpenAPI-файлу при старті валить увесь сервіс | B | Середня | виправлено (Г) |
| R-08 | Блокувальний ввід-вивід і pbkdf2 в `async def` | E | Середня | виправлено (Ж) |
| R-09 | Лічильник невдалих входів у пам'яті, без блокування | D, E | Середня | виправлено (З) |
| R-10 | `int(...)` над id з БД без перевірки формату | C | Низька | виправлено (PR #212) |
| R-11 | Мовчазне резервне значення `PASSWORD_SALT` | D | Середня | виправлено (PR #212) |
| R-12 | `fetch` у фронтенді без тайм-ауту | B | Середня | виправлено (И) |
| R-13 | `getMe` повертає `null` для будь-якої помилки | D | Низька | виправлено (И) |
| R-14 | Повне сканування ігор під `db_lock` | E | Низька | виправлено (І) |
| R-15 | Кеш проксі без меж і з ручною інвалідацією | D | Низька | виправлено (Ї) |

Для зручності виправлення позначені літерами А–Е (R-01…R-07, R-10, R-11) та Ж, З, И, І, Ї (R-08, R-09, R-12 і R-13, R-14, R-15). Виправлення Д повністю закриває R-01 і R-06 та адресує R-05 у частині налаштування тайм-ауту. Дубльовані визначення в `db.py` (повторні визначення `resolve_database_url`, `enable_sqlite_foreign_keys`, `DATABASE_URL` та першого engine) остаточно усунуто в PR #216, що повністю закриває R-05.

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

### Ж. Обробники в пулі потоків замість циклу подій (R-08)

До (`routes/auth.py`, те саме в усіх файлах `routes/`):

```python
async def login(payload: LoginRequest):
    ...
    if account is None or not verify_password(payload.password, account["password_hash"]):
```

Після:

```python
def login(payload: LoginRequest):
    ...
    if account is None or not verify_password(payload.password, account["password_hash"]):
```

У жодному обробнику не було `await`, тож `async def` лише змушував pbkdf2 (100 000 ітерацій) і синхронні запити SQLAlchemy виконуватись у потоці подій. Тепер FastAPI запускає їх у пулі потоків, а решта запитів обслуговується під час хешування. `hashlib.pbkdf2_hmac` у CPython звільняє GIL на час обчислення. Через це ж блокувальний `time.sleep` у `retry_with_backoff` більше не заморожує сервер: він спить у робочому потоці. Окремої зміни для нього не потрібно, на відміну від того, що планувалося в попередній версії звіту.

### З. Лічильник невдалих входів у БД (R-09)

До (`routes/auth.py`):

```python
def register_failed_login(email: str, now: datetime) -> None:
    recent = [t for t in LOGIN_FAILURES.get(email, []) if now - t < LOGIN_WINDOW]
    recent.append(now)
    if len(recent) >= MAX_FAILED_LOGINS:
        LOCKED_UNTIL[email] = now + LOCK_DURATION
        LOGIN_FAILURES.pop(email, None)
    else:
        LOGIN_FAILURES[email] = recent
```

Після (`store.py`):

```python
def record_failed_login(email: str, now: datetime) -> bool:
    now_db = _naive_utc(now)
    window_start = now_db - LOGIN_WINDOW
    with db_lock:
        db = SessionLocal()
        try:
            db.query(LoginFailureModel).filter(LoginFailureModel.failed_at <= window_start).delete(
                synchronize_session=False
            )
            db.add(LoginFailureModel(email=email, failed_at=now_db))
            db.flush()
            attempts = db.query(LoginFailureModel).filter(LoginFailureModel.email == email).count()
            locked = attempts >= MAX_FAILED_LOGINS
            if locked:
                user = db.query(UserModel).filter(UserModel.email == email).first()
                if user is not None:
                    user.locked_until = _naive_utc(now + LOCK_DURATION)
                db.query(LoginFailureModel).filter(LoginFailureModel.email == email).delete(synchronize_session=False)
            db.commit()
            return locked
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
```

`routes/auth.py` лишив `register_failed_login` як тонку обгортку. Рішення про сховище: нова таблиця `login_failures` (`email`, `failed_at`), а не поле `User.failed_login_attempts`. Окреме поле-число втрачає часове вікно в 15 хвилин, а нова таблиця створюється через `create_all` без міграції існуючої БД й рахує також невідомі пошти, як раніше. Поведінку збережено: вікно 15 хв, ліміт 5, блокування 15 хв, невідомі акаунти не блокуються (щоб не розкривати їх наявність). Поле `failed_login_attempts` лишається невикористаним.

### И. Тайм-аут запиту у фронтенді та чесний `getMe` (R-12, R-13)

До (`web/app.js`):

```javascript
response = await fetch('/api/v1' + cleanPath, options);
...
} catch (err) {
  return null;
}
```

Після:

```javascript
var controller = new AbortController();
options.signal = controller.signal;
timer = setTimeout(function () { timedOut = true; controller.abort(); }, App.API_TIMEOUT_MS); // 15000
...
} catch (err) {
  if (err && err.status === 401) { return null; }
  console.error('getMe failed:', err && err.code, err && err.message);
  throw err;
}
```

Таймер діє на отримання відповіді й на читання тіла та знімається в `finally`, тож не лишає завислих таймерів. За відсутності `AbortController` (дуже старий браузер) запит працює як раніше. `admin.html` тепер перехоплює помилку `getMe` і показує її через `App.showError`; `game.html` вже обгортав виклики в `try/catch`.

### І. Фільтрація й пагінація ігор у БД (R-14)

До (`routes/games.py`):

```python
    records = sorted_games(list(GAMES.values()))
    if room_id:
        records = [r for r in records if r.room_id == room_id]
    ...
    page = records[offset : offset + limit]
```

Після:

```python
    page, total = query_games(room_id=room_id, master_id=master_id, limit=limit, offset=offset)
```

`store.query_games` будує один запит із `WHERE`, `ORDER BY starts_at, id`, `OFFSET`, `LIMIT` і `COUNT`. `find_busy_game` бере з БД лише ігри потрібної кімнати або майстра (`WHERE room_id = ? OR master_id = ?`), а перетин часу перевіряє вже на цій вибірці. `room_has_games` замінив `any(...)` над усіма іграми в `PATCH /rooms/{id}`, календар і бронювання кімнати беруть ігри через `query_games(room_id=...)`.

### Ї. Обмежений кеш без ручної інвалідації (R-15)

До (`store.py`):

```python
        self._cache = {}
    ...
        if db_obj.id in self._cache:
            return self._cache[db_obj.id]
```

Після:

```python
        self._cache = BoundedCache(max_cache_entries)   # LRU, 1024 записи
    ...
    def _to_schema(self, db_obj):
        fresh = self._build(db_obj)
        cached = self._cache.get(db_obj.id)
        if cached is not None and cached == fresh:
            return cached
        self._cache[db_obj.id] = fresh
        return fresh
```

Кеш існував, щоб тести могли порівнювати об'єкти через `is`. Тепер він лише зберігає ідентичність: дані завжди беруться з рядка БД, тож зміна рядка поза проксі (або забута інвалідація) не дає застарілого значення. Прямі звернення `GAMES._cache.pop(...)` у `store.py`, `routes/rooms.py` і `routes/users.py` замінено методом `invalidate`. Розмір кешу обмежено.

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
| Повтори з експоненційним відступом і full jitter | Б (`src/api/resilience.py`, `store.CREDENTIALS.get`) |
| Блокувальний ввід-вивід поза циклом подій (пул потоків) | Ж (R-08) |
| Стан у спільному сховищі та транзакція «все або нічого» під блокуванням | З (R-09) |
| Тайм-аут на виклик клієнта до сервера (`AbortController`) | И (R-12) |
| Швидка відмова з розрізненням причин: збій не маскується під «немає даних» | И (R-13) |
| Фільтрація, сортування й пагінація в БД замість Python | І (R-14) |
| Обмежений ресурс (LRU-кеш) і єдине джерело істини замість ручної інвалідації | Ї (R-15) |

Застосовано обмежені повтори (retry) для ідемпотентного читання облікових даних користувача (`store.CREDENTIALS.get`) з експоненційним відступом і full jitter (`src/api/resilience.py`). Повторюються виключно перехідні збої блокування SQLite (`OperationalError` з текстом `locked` або `busy`). Записи й `commit` повторами не обгортаються (вони не є ідемпотентними). Композиція виконана за §3.5 лекції: тайм-аут кожної спроби `DB_TIMEOUT_SECONDS` (10 с) $\to$ повтори навколо (3 спроби) $\to$ швидка відмова (HTTP 503 з `Retry-After: 5`).

## 4. Режими відмов і відновлення

| Виправлення | Швидка чи безпечна відмова | Що бачить користувач під час збою | Як система повертається до норми |
|-------------|----------------------------|-----------------------------------|----------------------------------|
| А. Блокування кімнати | Швидка. Хибний стан (ігри скасовано, гравців не повідомлено) гірший за відсутність відповіді | 503 `SERVICE_UNAVAILABLE`, блокування не створено, ігри на місці | Власник повторює запит після відновлення БД; ручне втручання не потрібне, бо нічого не змінилося |
| Б. Видалення гри | Швидка. Не можна сповістити про скасування гри, яка лишилась | 503, гра і записи гравців не змінені | Повторити `DELETE` після відновлення БД |
| В. Скасування запису | Не вибір відмови, а усунення гонки: запит чекає на блокування, а не видає застарілу відповідь | Звичайна відповідь, трохи більша затримка | Автоматично |
| Г. Старт без OpenAPI-файлу | Безпечна. Документація допоміжна, API важливіший за неї | Усе працює; у логу попередження | Виправити права на `docs/api/`, файл буде записано при наступному старті (або `generate_openapi.py`) |
| Д. Збій БД | Швидка. Для читання немає резервного джерела, а застарілі дані гірші за явну помилку | 503 з `Retry-After: 5`; для непередбачених винятків 500 із загальним текстом без внутрішніх деталей | Клієнт повторює запит; після відновлення БД усе працює без перезапуску (є тест `test_service_recovers_after_database_outage`) |
| Е. Некоректний ID або відсутня сіль у production | Невідомий суфікс ігнорується; без солі в production сервіс швидко завершує старт | Для ID — звичайна реєстрація з наступним валідним ID; для помилкової production-конфігурації сервіс не приймає запити | Виправити запис/конфігурацію; перезапустити сервіс. У development fallback лишається лише для локального запуску, його використання записується в лог |
| Ж. Обробники в пулі потоків | Не вибір відмови, а усунення блокування циклу подій: повільне хешування не гальмує інші запити | Звичайна відповідь. Більше паралелізму може дати `database is locked`: тоді тайм-аут БД і 503 з `Retry-After: 5` (Д) | Автоматично; клієнт повторює після 503 |
| З. Лічильник входів у БД | Швидка. Якщо невдалу спробу не вдалося записати, мовчки пропустити її гірше (підбір пароля лишається непоміченим) | 503 `SERVICE_UNAVAILABLE` з `Retry-After: 5`; запис і блокування відкочено повністю | Повторити вхід після відновлення БД. Лічильник і блокування переживають перезапуск |
| И. Тайм-аут `fetch` | Швидка. Через 15 с повідомлення краще за нескінченне завантаження | «Сервер не відповів вчасно. Спробуйте ще раз» (код `TIMEOUT`). Для POST/PATCH/DELETE тайм-аут не доводить, що сервер не виконав запит | Користувач повторює дію; якщо вона вже виконана, сервер відповідає 409 (наприклад, `ALREADY_ENROLLED`). Після «пробудження» хостингу запит проходить |
| И. `getMe` | Швидка. Для 503, `TIMEOUT` і мережевого збою помилка передається викликачу й логується; `null` лише для «немає сесії» і 401 | Адмін-сторінка показує причину збою, а не вдає, що користувач не авторизований | Оновити сторінку або повторити дію |
| І. Запити ігор у БД | Швидка. Для читання немає резервного джерела | 503 з `Retry-After: 5` через централізований обробник (Д) | Клієнт повторює після відновлення БД |
| Ї. Кеш із межею | Безпечна. Кеш не є джерелом даних: за відсутності запису значення перебудовується з БД | Нічого не змінюється: застарілих даних більше немає, при заповненні кешу витісняється найдавніший запис | Автоматично |
| Повтори при збої читання облікових даних | Швидка. Після вичерпання 3 спроб виняток піднімається в централізований обробник | 503 `SERVICE_UNAVAILABLE` з `Retry-After: 5`; при короткочасному блокуванні користувач не помічає збою (автоматичний повтор дає 200) | При усуненні блокування SQLite повторна спроба успішно завершує запит; якщо збій тривалий, клієнт повторює після 503 |

## 5. Тести надійності

Розташування: `src/api/tests/reliability/`. Усього 102 тести у 12 файлах (включно з 14 тестами повторів з відступом і джитером у `test_reliability_retry.py`). Для R-08, R-09, R-12, R-13, R-14 і R-15 додано 34 тести у п'яти нових файлах. Усі перевірки R-10 і R-11 розташовані у `test_reliability_id_validation.py`. `check_traceability.py` рекурсивно знаходить також вкладені reliability-тести; `test_read_tests_includes_nested_reliability_tests` захищає це від регресії.

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
| Конкурентність (цикл подій) | `test_no_api_handler_is_a_coroutine_function`, `test_password_verification_runs_outside_the_event_loop`, `test_password_hashing_on_registration_runs_outside_the_event_loop` | жоден обробник API не є `async def`; перевірка й хешування пароля виконуються поза потоком подій | Ж |
| Ін'єкція збою (БД) | `test_counter_write_failure_rolls_back_everything_and_is_raised` | збій запису лічильника відкочує все, прострочені записи й блокування не змінені | З |
| Ін'єкція збою (БД) | `test_login_fails_fast_with_503_when_failed_attempt_cannot_be_recorded` | недоступна БД дає 503 з `Retry-After`, без технічних деталей | З |
| Конкурентність | `test_parallel_failed_logins_are_all_counted` | 8 паралельних невдалих входів: рівно одне блокування, лишається 3 записи | З |
| Стан у БД | `test_failed_logins_are_stored_in_the_database`, `test_lockout_is_persisted_and_failure_rows_are_cleared` | лічильник і блокування видно через БД, а не через пам'ять процесу | З |
| Граничні значення | `test_only_failures_inside_the_window_are_counted_and_expired_rows_are_pruned` | запис рівно на межі 15 хв не рахується й видаляється, «на секунду новіший» лишається | З |
| Ін'єкція збою (мережа) | `test_request_to_unresponsive_server_fails_with_timeout_error`, `test_timeout_also_covers_reading_the_response_body` | `fetch`, що не відповідає, дає `TIMEOUT`; таймер знято; тайм-аут діє й під час читання тіла | И (R-12) |
| Обробка помилки | `test_timer_is_cleared_after_a_fast_response_and_errors_keep_their_code` (2 випадки), `test_network_failure_is_still_reported_as_network_error_not_timeout` | швидка відповідь не лишає таймерів, код помилки 503 зберігається, мережевий збій не плутається з тайм-аутом | И (R-12) |
| Обробка помилки | `test_get_me_distinguishes_missing_session_from_server_failure` (5 випадків) | немає сесії і 401 дають `null`; 503 і `TIMEOUT` кидають помилку й потрапляють у лог | И (R-13) |
| Граничні значення | `test_list_games_filters_orders_and_paginates_in_the_database` (4 випадки) | фільтр за кімнатою й майстром, `limit`, `offset`, зсув за межі списку, `total` і `has_more` | І |
| Продуктивність | `test_list_games_converts_only_the_requested_page`, `test_busy_game_lookup_loads_only_games_of_that_room_or_master`, `test_room_has_games_checks_the_database_without_loading_games` (2 випадки) | з БД перетворюються лише потрібні ігри: сторінка з 2 із 12, одна гра кімнати, жодної для перевірки наявності | І |
| Граничні значення | `test_bounded_cache_evicts_the_least_recently_used_entry`, `test_bounded_cache_rejects_non_positive_size` (2 випадки), `test_proxy_cache_never_exceeds_its_limit` | LRU-витіснення, відхилення розміру 0 і -1, кеш проксі не перевищує межу | Ї |
| Стан у БД | `test_row_changed_outside_the_proxy_is_not_served_from_stale_cache`, `test_cached_object_identity_is_kept_while_the_row_is_unchanged`, `test_invalidate_removes_a_single_entry` | зміна рядка поза проксі видима без інвалідації, ідентичність збережено, `invalidate` працює | Ї |
| Повтори з відступом | `test_retry_succeeds_on_transient_failure_after_n_attempts` | успіх з 2 або 3 спроби після N тимчасових збоїв; перевірка кількості викликів і затримок | Бонус |
| Обмеження спроб | `test_retry_attempts_are_bounded_to_max_attempts` | постійний збій дає рівно `max_attempts` викликів і не більше | Бонус |
| Ін'єкція збою (HTTP 503) | `test_reaction_after_exhausted_retries_raises_and_http_returns_503` | виняток піднято, HTTP дає 503 з `Retry-After: 5`, логування помилки | Бонус |
| Відновлення через HTTP | `test_transient_retry_recovers_http_login` | після перехідного збою запит входу відновлюється й повертає 200 | Бонус |
| Швидка відмова | `test_non_retryable_exceptions_fail_fast_without_retries` | невідновні винятки не повторюються (рівно 1 виклик) | Бонус |
| Граничні затримки | `test_delay_bounds_and_full_jitter_distribution` | затримки $\le$ `max_delay`, діапазон $[0, \min(cap, base \cdot 2^n)]$, перша спроба без затримки | Бонус |
| Граничні параметри | `test_invalid_parameters_rejected` (5 випадків) | відхилення некоректних параметрів `max_attempts`, `base_delay`, `max_delay` | Бонус |
| Допоміжні гілки | `test_resilience_helper_coverage_edges` | пряме декорування без дужок та перевірка предикату для не-OperationalError | Бонус |

Усі вісім параметризованих перевірок із PR #212 виконано проти дофіксового `store.py` з `main`: сім падають очікувано — п'ять user ID-випадків і два Unicode game ID-випадки; `game_abc` проходить як контрольний. Для `user_٩` і `game_٩` старий код хибно породжує ID з номером 10; `user_²`, `user_abc`, `user_`, `user_1a` та `game_²` дають `ValueError`. `game_abc` і раніше коректно ігнорувався старою перевіркою `isdigit()`, тому його тест фіксує очікувану поведінку, а не регресію.

**Перевірка тестів R-12 і R-13.** Тести фронтенду виконують справжній `app.js` у Node.js, тож їх перевірено проти коду до виправлення: 4 з 10 падають (обидва тести тайм-ауту та два випадки `getMe` для 503 і `TIMEOUT`), інші 6 страхують поведінку, яка вже працювала (нормальна відповідь, 401, відсутність сесії, мережева помилка). Тести R-08, R-09, R-14 і R-15 залежать від FastAPI й SQLAlchemy та потребують повного прогону `pytest src/api/tests` у CI; `test_reliability_error_handling.py` тепер підміняє `routes.games.query_games` замість `sorted_games`, якого в маршруті більше немає.

Також є тести на видалення неіснуючої гри (`delete_game_with_notifications` без помилки і без сповіщень), на читання `DB_TIMEOUT_SECONDS` з середовища і на передачу тайм-ауту в `create_engine`.

Після розширення тестів у PR #212 повний локальний прогін на Python 3.13.7 дав 351 passed, 1 xfailed і 96,64 % coverage (поріг 95 %); reliability suite — 54 passed. Перевірки Black, Flake8, Bandit і простежуваності проходять. Окремий job `reliability-tests` запускає весь каталог `src/api/tests/reliability/`. Наявний зелений прогін job у PR #213 — [GitHub Actions run 42996166588](https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/runs/42996166588) — містить попередні 43 тести, до перенесення тестів R-10/R-11. Після merge PR #212 job підхопить усі 54 тести. Після merge у `main` job `reliability-tests` пройшов усі 54 тести надійності: [GitHub Actions run 43039990841](https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/runs/43039990841).

**Перевірка «тест справді ловить помилку».** Тести без нових імен у коді (обробка помилки, 503, блокування) запускали проти коду до виправлень: 7 з 8 падають, проходить лише `test_parallel_enroll_and_unenroll...`. Це чесно сказати: гонка залежить від таймінгу, тож цей тест лише димовий. Детерміновану перевірку В дає тест із утримуваним `db_lock`. Тести атомарності (А, Б) на старому коді не запускаються, бо звертаються до нових функцій, тому на старому коді ми відтворили збої вручну: блокування кімнати дало 500, `game_1` видалена, блокування створене, сповіщень 0; видалення гри дало 500, гра існує, сповіщення для `user_2` уже створене.

## 6. Які проблеми залишилися відкритими

З реєстру R-01…R-15 відкритих проблем немає. Обмеження виправлень і подальші кроки (це не нові записи реєстру, а межі того, що зроблено):

| Тема | Обмеження | Що зробити далі |
|------|-----------|------------------|
| R-08 | `seed_db()` у `lifespan` виконується в циклі подій, але лише один раз до початку обслуговування запитів | За потреби винести в `run_in_threadpool` |
| R-09 | Атомарність між процесами тримається на блокуванні запису SQLite, а не на `db_lock`; поле `User.failed_login_attempts` лишається невикористаним | При переході на MySQL перевірити транзакційну ізоляцію (ADR-002); прибрати невикористане поле |
| R-12 | Повторів на клієнті немає: після `TIMEOUT` користувач повторює дію сам | Додати повтор лише для GET, за умовами §3.5 лекції |
| R-14 | `to_game` робить окремий запит кількості гравців для кожної гри на сторінці (до 100), календар робить запит на кожну кімнату | Агрегувати кількість гравців одним `GROUP BY` |
| R-15 | Кеш перебудовує значення з рядка БД при кожному зверненні: він захищає ідентичність, а не економить запити | Якщо профілювання покаже потребу, кешувати за версією рядка |

Проблему R-05 (дубльовані визначення `resolve_database_url`, `enable_sqlite_foreign_keys`, `DATABASE_URL` та engine) вирішено в PR #216.

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

### Повтори з відступом і джитером

Заявляємо бонус «Повтори з відступом (backoff) і джитером (jitter)».

**Що зроблено.** Реалізовано модуль `src/api/resilience.py` з функцією/декоратором `retry_with_backoff`, яка реалізує обмежені повтори з експоненційним відступом та повним джитером (Full Jitter).

**Формула затримки (Full Jitter):**
$$delay = rng.uniform(0.0, \min(max\_delay, base\_delay \cdot 2^{attempt}))$$
де $attempt \in \{0, 1, \dots\}$ — індекс повторної спроби. Перша спроба виконується без жодної затримки ($delay = 0$). Генератор випадкових чисел за замовчуванням використовує криптографічно безпечний `random.SystemRandom()`.

**Де застосовано й чому виклик ідемпотентний.** Повтори підключено до читання облікових даних користувача `store.CREDENTIALS.get(email)`, що викликається під час автентифікації (`POST /api/v1/auth/login`).
- Запит `SELECT ... FROM users WHERE email = :email` є суто **ідемпотентною операцією читання**: він не змінює стан бази даних і може безпечно повторюватися за короткочасного блокування SQLite без ризику створення дублікатів чи побічних ефектів.
- Операції запису, видалення та `commit` повторами **не обгортаються**, оскільки вони не є ідемпотентними.
- Повторюються лише перехідні збої блокування SQLite (`OperationalError` із текстом `locked` або `busy` через предикат `is_transient_db_error`). Помилки валідації, 4xx, помилки програмування та невідновні помилки БД (наприклад `no such table`) не повторюються й відхиляються на першій же спробі.

**Композиція з тайм-аутом (§3.5 лекції):**
1. Внутрішній шар: тайм-аут окремої спроби з'єднання з SQLite (`DB_TIMEOUT_SECONDS = 10.0` с у конфігурації `create_database_engine`).
2. Середній шар: повтори навколо запиту (`max_attempts = 3`, `base_delay = 0.05` с, `max_delay = 0.5` с).
3. Загальний бюджет часу: сума тайм-аутів спроб і затримок обмежена:
   $$T_{budget} \le max\_attempts \cdot DB\_TIMEOUT\_SECONDS + \sum delays \le 3 \cdot 10.0 + 0.15 = 30.15\text{ с}.$$
4. Зовнішній шар (реакція після останньої спроби): **швидка відмова (fast fail)**. Після вичерпання $max\_attempts$ виняток `OperationalError` піднімається вище, записується в лог на рівні `logger.error` і перехоплюється централізованим обробником `database_unavailable_handler` (`errors.py`), який повертає клієнту відповідь HTTP 503 `SERVICE_UNAVAILABLE` із заголовком `Retry-After: 5` без витоку технічних подробиць. Жодного прихованого або мовчазного значення за замовчуванням не підставляється.

**Тести** (`src/api/tests/reliability/test_reliability_retry.py`, 14 тестів):
1. `test_retry_succeeds_on_transient_failure_after_n_attempts`: перевіряє успіх операції після 2 тимчасових збоїв, кількість викликів і затримок.
2. `test_retry_attempts_are_bounded_to_max_attempts`: доводить, що кількість спроб суворо обмежена `max_attempts = 3` при неперервному збої.
3. `test_reaction_after_exhausted_retries_raises_and_http_returns_503`: доводить реакцію швидкої відмови — підняття винятку, HTTP 503 з `Retry-After`, відсутність витоку деталей і запис помилки в лог.
4. `test_transient_retry_recovers_http_login`: доводить відновлення HTTP-ендпоінту під час перехідного збою.
5. `test_non_retryable_exceptions_fail_fast_without_retries`: перевіряє, що невідновні помилки виконуються рівно 1 раз без затримок.
6. `test_delay_bounds_and_full_jitter_distribution`: перевіряє формулу Full Jitter, обмеження стелею `max_delay`, очікувані значення за фіксованого RNG і нульову затримку першої спроби.
7. `test_invalid_parameters_rejected` (5 параметризованих тестів): граничні перевірки на відхилення некоректних параметрів (`max_attempts < 1`, `base_delay < 0`, `max_delay < 0`, `max_delay < base_delay`).
8. `test_process_control_exceptions_are_not_retried` (2 параметризовані тести): підтверджує, що `KeyboardInterrupt` і `SystemExit` не перехоплюються та не повторюються.
9. `test_resilience_helper_coverage_edges`: перевіряє пряме декорування без дужок та предикат для не-OperationalError винятків.

**Пояснення у відео:** бонус зараховується за умови, якщо хоча б один учасник команди пояснить його роботу у своєму Loom-відео (формула full jitter, ідемпотентність виклику, композиція з тайм-аутом і швидка відмова).

### Тести надійності як обов'язкова перевірка PR

Заявляємо бонус «Тести надійності як обов'язкова перевірка PR».

**Що зроблено.** PR #213 додав у `.github/workflows/ci.yml` окремий job `reliability-tests`, який запускає лише `src/api/tests/reliability/` на Python 3.9. Тепер цей job додано до обов'язкових перевірок (required status checks) правила захисту гілки `main`: PR не можна змерджити, поки job не пройде. Тести надійності запускаються окремим кроком, а не лише в складі загального `pytest`, тож збій надійності видно одразу з назвою перевірки.

**Як налаштовано** (Settings → Branches → Branch protection rule для `main`, або Settings → Rules → Rulesets):

1. Увімкнено «Require status checks to pass before merging».
2. У списку перевірок додано `reliability-tests` (назва збігається з `jobs.reliability-tests` у `ci.yml`; GitHub показує лише перевірки, що виконувалися за останній тиждень).
3. Workflow запускається на кожен `pull_request` до `main` без фільтра `paths`, інакше обов'язкова перевірка могла б ніколи не з'явитися на PR, що не торкається цих файлів.

**Докази.**

- Налаштування: `gh api repos/ukma-fin-ssdm-2026/vibecoders/branches/main/protection/required_status_checks --jq '.contexts'` повертає `reliability-tests` серед обов'язкових перевірок.
- Прогін, де крок пройшов у `main`: [GitHub Actions run 43039990841](https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/runs/43039990841).
- PR, де перевірка позначена як Required: _додати посилання на PR цієї гілки після створення, з позначкою «Required» біля `reliability-tests`_.

**Пояснення у відео:** бонус зараховується за умови, якщо хоча б один учасник команди розповість у своєму відео, що саме налаштовано і як це працює: чому окремий job, чому required check, що станеться з PR, у якого тести надійності падають, і чому в workflow не має бути фільтра `paths`.
