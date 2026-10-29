# План тестування

## Обсяг

Тестуємо `src/api`: `store.py` , `schemas.py` , `routes/games.py` , `routes/rooms.py` , `routes/auth.py` , `security.py`.

Свідомо не тестуємо те, що ще не має реалізації: UI та календар, сповіщення, блокування користувачів і БД.

## Критерії виходу

- усі тести плану зелені в CI;
- покриття не нижче 95%;
- немає відкритих критичних дефектів;
- кожен рядок плану має ID вимоги з `docs/requirements/rtm.md`.

## Ризики

1. Контроль доступу: у двох місцях код розходиться з RTM.
2. Гонитва при одночасних бронюваннях і записах. Зараз сховище в пам'яті, тож справжній ризик з'явиться разом з БД.

## Таблиця тест-кейсів

| № | Компонент/функція | Рівень тесту | Тип (позитивний/негативний) | Очікуваний результат / критерій прийняття | Власник | Вимога (ID з rtm.md) |
|---|---|---|---|---|---|---|
| 1 | `store.time_overlap` | модульний | позитивний | Слоти з перетином навіть на 1 хв → `True`; слот, що починається рівно в момент закінчення попереднього → `False`; результат симетричний | Спис | US-002 |
| 2 | `store.find_busy_game` | модульний | негативний | Та сама кімната з перетином → повертає гру-конфлікт; той самий майстер в іншій кімнаті з перетином → конфлікт; `exclude_game_id` пропускає редаговану гру, але знаходить пізніший конфлікт; вільний слот → `None` | Спис | US-002 (REL-002) |
| 3 | `POST /api/v1/games` | інтеграційний | позитивний | Майстер, вільна кімната, `max_players` ≤ місткості → 201, заголовок `Location`, `master_id` = автор, `current_players` = 0, слот видно в `/rooms/{id}/bookings` | Спис | US-002 (Test-03) |
| 4 | `POST /api/v1/games` | інтеграційний | негативний | Зайнята кімната → 409 `ROOM_BUSY`; майстер уже веде гру → 409 `MASTER_BUSY`; `max_players` > місткості → 409 `ROOM_CAPACITY_EXCEEDED`; роль player → 403 | Спис | US-002 (Test-04, Test-15) |
| 5 | `GameBase` (schemas) | модульний | позитивний | Межі приймаються: `duration_minutes` 30 і 720, `max_players` 2 і 8, `title` 3 і 100 символів | Хамаза | US-002 |
| 6 | `GameBase` (schemas) | модульний | негативний | Поза межами відхиляються: тривалість 29 і 721, гравців 1 і 9, `title` 2 і 101 символ, `room_id` не за шаблоном `room_N` | Хамаза | US-002 |
| 7 | `store.to_game` | модульний | позитивний | `current_players` = кількість записів у `ENROLLMENTS`; гра без запису → 0 | Голдинська | US-001 |
| 8 | `POST /games/{id}/players` | інтеграційний | позитивний | Гравець записується на гру з вільним місцем → 201, `Location`; `GET /games/{id}` показує `current_players` + 1 | Голдинська | US-001 (Test-01) |
| 9 | `POST /games/{id}/players` | інтеграційний | негативний | Місць немає → 409 `GAME_FULL`; повторний запис → 409 `ALREADY_ENROLLED`; кількість гравців не змінилась | Голдинська | US-001 (Test-02) |
| 10 | `DELETE /games/{id}/players/{user_id}` | інтеграційний | позитивний | Гравець скасовує власний запис → 204; `current_players` − 1; той самий гравець може записатися знову (місце звільнено) | Голдинська | US-005 (Test-09, Test-16) |
| 11 | `DELETE /games/{id}/players/{user_id}` | інтеграційний | негативний | Сторонній користувач → 403 `FORBIDDEN`; гравець без запису → 404 `ENROLLMENT_NOT_FOUND`; без токена → 401 | Голдинська | US-005 |
| 12 | `DELETE /games/{id}` | інтеграційний | позитивний | Майстер видаляє свою гру → 204; `GET` → 404; слот зник з `/rooms/{id}/bookings`; записи гравців видалено; у цій кімнаті можна створити нову гру на той самий час | Хамаза | US-008 (Test-12) |
| 13 | `security.get_current_user`, `require_roles` | модульний | негативний | Роль не зі списку → `ApiError` 403; відсутній або недійсний токен → 401 із `WWW-Authenticate: Bearer` | Захарук | SEC-002 |
| 14 | `PATCH /rooms/{id}` | інтеграційний | позитивний | Власник блокує кімнату без ігор → 200, `is_blocked=true`; наступний `POST /games` у цю кімнату → 409 `ROOM_BLOCKED` | Захарук | US-003 (Test-05) |
| 15 | `PATCH /rooms/{id}` | інтеграційний | негативний | Кімната з іграми → 409 `ROOM_HAS_GAMES`, `is_blocked` не змінився; майстер або гравець → 403 | Захарук | US-003 (Test-06) |
| 16 | `GET /games/{id}/players` | інтеграційний | негативний | Гравець, який не є майстром цієї гри чи власником → 403; майстер гри → 200 зі списком, `current_players`, `max_players` | Хамаза | US-007 (Test-17, SEC-002) |
| 17 | `POST /games/{id}/players` + `GET /games/{id}` (нефункціональний) | інтеграційний | позитивний | Запис гравця й наступне читання `current_players` разом тривають менше 1 с (найповільніший із 50 прогонів) | Голдинська | PERF-001 |
| 18 | `POST /auth/login` | інтеграційний | негативний | 5 невдалих входів за 15 хв → наступна спроба, навіть із правильним паролем, повертає 429 `ACCOUNT_LOCKED` із `Retry-After`; невідома пошта блокується так само; інші акаунти не блокуються | Голдинська | SEC-003 |
| 19 | `POST /auth/login` | інтеграційний | позитивний | 4 невдалі входи не блокують, а успішний вхід скидає лічильник; невдачі старші за 15 хв не рахуються; блокування знімається рівно через 15 хв, спроби під час нього його не подовжують | Голдинська | SEC-003 |
| 20 | `store.hash_password`, `store.verify_password` | модульний | позитивний | Хеш детермінований і є hex-рядком; різні паролі дають різні хеші; `verify_password` приймає правильний пароль і відхиляє хибний | Спис | SEC-001 |
| 21 | `POST /api/v1/games` (таблиця рішень) | інтеграційний | негативний | Кожне з 9 правил таблиці рішень (див. «Бонуси») дає очікуваний статус і код помилки; при будь-якій відмові нова гра не з'являється; при кількох порушеннях діє пріоритет перевірок | Спис | US-002 (REL-002) |
| 22 | `GET /games`, `GET /games/{id}` | інтеграційний | позитивний | Список відсортований за часом початку, потім за id; пагінація на межах 1 і 100; фільтри за кімнатою та майстром; недійсні параметри → 400; невідомий id → 404 | Спис | US-006 (Test-10) |

## Трасування

У тестах ми пишемо мітку `@pytest.mark.requirement("ID")`, щоб було видно, яку вимогу з `rtm.md` перевіряє тест. Скрипт `scripts/check_traceability.py` перевіряє це в CI. Якщо в тесту немає прямої вимоги (формат помилок, OpenAPI, звичайний вхід), він має мітку `@pytest.mark.technical`.

| Рядок плану | Тести | Результат |
|---|---|---|
| 1 | `test_store.py`: `test_time_overlap_*`; `test_properties.py`: `test_time_overlap_is_symmetric_for_any_slots`, `test_back_to_back_slots_never_overlap` | зелений |
| 2 | `test_store.py`: `test_find_busy_game_*` | зелений |
| 3 | `test_games_routes.py`: `test_create_game_success_sets_master_and_location`; `test_scenarios.py`: `test_scenario_master_books_free_room_and_slot_appears_in_calendar` | зелений |
| 4 | `test_games_routes.py`: `test_create_game_room_busy_returns_409`, `test_create_game_master_busy_returns_409`, `test_create_game_capacity_boundary`, `test_create_game_forbidden_for_player` | зелений |
| 5, 6 | `test_schemas.py`: `test_duration_*`, `test_max_players_*`, `test_title_length_*`, `test_room_id_pattern_rejects_malformed_values` | зелений |
| 7 | `test_store.py`: `test_to_game_*` | зелений |
| 8 | `test_games_routes.py`: `test_enroll_player_uses_current_time_from_stubbed_clock`, `test_enroll_last_free_seat_succeeds_then_game_is_full` | зелений |
| 9 | `test_games_routes.py`: `test_enroll_player_twice_returns_409`, `test_enroll_player_in_full_game_returns_409` | зелений |
| 10 | `test_games_routes.py`: `test_remove_player_allowed_for_self_master_and_owner`, `test_player_can_enroll_again_after_cancelling` | зелений |
| 11 | `test_games_routes.py`: `test_remove_player_by_stranger_is_forbidden`, `test_remove_player_not_enrolled_returns_404`, `test_remove_player_without_token_returns_401_and_keeps_enrollment` | зелений |
| 12 | `test_games_routes.py`: `test_delete_game_removes_game_and_enrollments`; `test_scenarios.py`: `test_scenario_deleting_game_frees_its_slot_for_a_new_booking` | зелений |
| 13 | `test_security.py` | зелений |
| 14 | `test_rooms_routes.py`: `test_block_room_without_games_succeeds`; `test_scenarios.py`: `test_scenario_blocked_room_rejects_new_games` | зелений |
| 15 | `test_rooms_routes.py`: `test_block_room_with_games_returns_409`, `test_block_room_requires_owner` | зелений |
| 16 | `test_list_players_access.py`: `test_list_players_forbidden_for_player_who_does_not_run_the_game` (xfail, D-1), `test_list_players_allowed_for_master_of_the_game`; `test_games_routes.py`: `test_list_players_requires_authentication` | частково: 403 для стороннього гравця не виконується (xfail) |
| 17 | `test_performance.py` | зелений |
| 18, 19 | `test_auth_routes.py`: тести блокування (8 тестів) | зелений |
| 20 | `test_store.py`: `test_hash_password_*`, `test_verify_password_*`; `test_properties.py`: `test_password_hash_verifies_only_original` | зелений |
| 21 | `test_decision_table.py`: `test_create_game_decision_table[DT-1…DT-9]` | зелений |
| 22 | `test_games_routes.py`: `test_list_games_*`, `test_get_game_*`; `test_api.py`: `test_get_games_public`, `test_get_games_authorized` | зелений |

Останній прогін локально (Python 3.12): 230 тестів, 229 пройшли, 1 xfailed (D-1), покриття 99,53%. Скрипт простежуваності: кожна вимога з `rtm.md` має хоча б один тест, окрім US-004, яку ми відклали.

## Примітки

- **Рядок 15.** В RTM (Test-06) і FR-007 написано, що зайнятий слот блокується «з підтвердженням» і ігри скасовуються автоматично, а API просто повертає 409. В таблиці очікування записані за API. Треба або змінити RTM, або код.
- **Рядок 16, дефект D-1.** У Test-17 і SEC-002 сказано, що список гравців бачить лише майстер гри (і власник), а `list_players` у `routes/games.py` перевіряє тільки те, що користувач увійшов. Очікуваний результат в таблиці записаний за вимогою. Тест позначений `xfail(strict=True)`: коли ми виправимо код, тест пройде, CI впаде з XPASS, і позначку треба буде прибрати. Тест `test_list_players_requires_authentication` теж доведеться змінити.
- **Не реалізовано в API:** US-004 (FR-008), SEC-004, FR-011. Їх немає в обсязі, а скрипт простежуваності позначає їх як відкладені.
- **Не покрито тестами:** REL-001 (20 одночасних бронювань), REL-003, USAB-001, MAINT-001. Для REL-001 потрібна база даних або справжня багатопотоковість.

## Примітки

- **Рядок 15.** RTM (Test-06) і FR-007 вимагають блокувати зайнятий слот «з підтвердженням» і автоматично скасовувати ігри, а API повертає 409. Очікування в таблиці записано за API. Треба або виправити RTM, або змінити код.
- **Не реалізовано в API:** US-004 (FR-008), SEC-004, FR-011. Хеш паролів (SEC-001) є в коді й тестах, але в колонці NFR у RTM його немає.


## Бонуси

### Виконуваний нефункціональний тест (PERF-001)
- Рядок плану: 17. Файл: `src/api/tests/test_performance.py`.
- Поріг із вимоги PERF-001: 1,0 с. Вимога описує клієнта, тому на рівні API перевіряється серверна частина: запис гравця й наступне читання лічильника.
- Виміряно: найповільніший з 50 прогонів 8,06 мс (середній 4,67 мс).
- Команда: `python -m pytest src/api/tests/test_performance.py --benchmark-columns=min,mean,max`

### Тести як специфікація для агента (SEC-003)
- Рядки плану: 18, 19. Тести: `src/api/tests/test_auth_routes.py`. Реалізація: `routes/auth.py`, `store.py`, `errors.py`.
- Коміт із червоними тестами: 179512d (6 із 18 тестів файлу падали). Коміт із реалізацією: fa1708d. PR: [#140](https://github.com/ukma-fin-ssdm-2026/vibecoders/pull/140).
- Використання ШІ: тести-специфікацію (8 тестів SEC-003) і реалізацію згенеровано Claude; вручну перевірено тести і  запущено (6 червоних, 12 зелених). Реалізація: store.py, routes/auth.py, errors.py.
  
### Автоматична перевірка простежуваності
- Скрипт: `scripts/check_traceability.py`. У `.github/workflows/ci.yml` додано крок «Check requirement traceability», він іде перед pytest.
- Як це працює: ID вимог скрипт бере з першого стовпця `docs/requirements/rtm.md`. У тестах ID задаються мітками `@pytest.mark.requirement("US-001", ...)`, їх зареєстровано в `pytest.ini`. Тест без прямої вимоги має мітку `@pytest.mark.technical`.
- Збірка падає, якщо: вимога не має жодного тесту; тест не має ні вимоги, ні мітки `technical`; тест посилається на ID, якого немає в `rtm.md`. Відкладені вимоги (поки тільки US-004) записані в `DEFERRED` разом з причиною.
- Команда: `python scripts/check_traceability.py`. Тести самого скрипта: `src/api/tests/test_traceability_script.py`.
- Червоний прогін (дірку знайдено): (https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/runs/40686995490/job/122811803714)
- Зелений прогін (дірку закрито): (https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/runs/40690922480/job/122825189878)
- Що скрипт знайшов у нашому проєкті: в RTM не було рядків SEC-001, SEC-002, PERF-001, REL-002, хоча тести на них є (додали); для US-006 не було рядка в плані (додали рядок 22); для US-007 був лише один тест, який не перевіряє обмеження доступу (це дефект D-1, рядок 16).

### Тести з техніки тест-дизайну: таблиця рішень
- Що беремо: створення гри, `POST /api/v1/games` (функція `ensure_schedule_is_valid` у `routes/games.py`). Рядок плану: 21. Тести: `src/api/tests/test_decision_table.py`.
- Умови: C1 - роль може створювати гру (master або owner), C2 - кімната існує, C3 - кімната не заблокована, C4 - `max_players` не більше місткості, C5 - кімната вільна на цей час, C6 - майстер вільний на цей час. Прочерк означає, що умова вже не важлива, бо перевірки йдуть одна за одною.

| Правило | C1 роль | C2 існує | C3 не заблокована | C4 місткість | C5 кімната вільна | C6 майстер вільний | Результат | Тест |
|---|---|---|---|---|---|---|---|---|
| R1 | ні | — | — | — | — | — | 403 `FORBIDDEN` | `DT-1` |
| R2 | так | ні | — | — | — | — | 404 `ROOM_NOT_FOUND` | `DT-2` |
| R3 | так | так | ні | — | — | — | 409 `ROOM_BLOCKED` | `DT-3`, `DT-9` |
| R4 | так | так | так | ні | — | — | 409 `ROOM_CAPACITY_EXCEEDED` | `DT-4` |
| R5 | так | так | так | так | ні | — | 409 `ROOM_BUSY` | `DT-5`, `DT-8` |
| R6 | так | так | так | так | так | ні | 409 `MASTER_BUSY` | `DT-6` |
| R7 | так | так | так | так | так | так | 201, гру створено | `DT-7` |

- `DT-8` перевіряє, що R5 важливіше за R6: якщо зайняті і кімната, і майстер, відповідь `ROOM_BUSY`. `DT-9` перевіряє, що R3 важливіше за R4 і R5: кімната заблокована, замала і зайнята, а відповідь `ROOM_BLOCKED`.
- Тести параметризовані: одне правило або перевірка пріоритету - один випадок з `id` `DT-N`. Після кожної відмови тест перевіряє, що нова гра не з'явилася в `GAMES`.
- Команда: `python -m pytest src/api/tests/test_decision_table.py -v`

### Використання ШІ 
Скрипт простежуваності, мітки в тестах, таблицю рішень і нові тести (`test_decision_table.py`, `test_scenarios.py`, `test_list_players_access.py`, `test_traceability_script.py`) виконано з допомогою Claude. Перевірено: весь набір тестів, `black`, `flake8` і скрипт простежуваності запущено локально, очікування в таблиці рішень звірено з `routes/games.py`.


