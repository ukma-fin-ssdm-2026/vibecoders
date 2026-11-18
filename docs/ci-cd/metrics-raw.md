# Сирі метрики CI/CD (гілка main)

Період: 29.10.2026 01:32 – 19.11.2026 01:32 (Europe/Kyiv); ковзне вікно 21 день до збору.
Джерело main: `gh run list --branch main --limit 1000 --json databaseId,headSha,workflowName,conclusion,attempt,createdAt,updatedAt`.
Сирі дані цього звіту: `docs/ci-cd/evidence/snapshots/20261118T233201440011Z`.
За період знайдено 108 запусків на `main` (завершених: 107, незавершених: 1); рядків-комітів у таблиці: 74; комітів із незавершеними запусками пропущено: 1.
Час у таблиці — `Europe/Kyiv`, формат `ДД.ММ ГГ:ХХ`; тривалості в хвилинах округлено до 0,1.

| № | Коміт | PR | Перший коміт PR | Запуск завершено | Черга, хв | Виконання, хв | Статус | Примітка |
|---:|---|---|---|---|---:|---:|:---:|---|
| 1 | `abf8823` | #230 | 18.11 15:37 | 19.11 01:19 | 0.0 | 1.9 | ✅ | workflow: CI Pipeline; час змін: 581.9 хв від #230 |
| 2 | `48a060f` | #228 | 18.11 15:16 | 18.11 15:38 | 0.0 | 1.8 | ✅ | workflow: CI Pipeline; час змін: 21.7 хв від #228 |
| 3 | `6626244` | #227 | 18.11 14:40 | 18.11 15:35 | 0.1 | 2.3 | ✅ | workflow: CI Pipeline; час змін: 55.1 хв від #227 |
| 4 | `ae00a67` | #225 | 13.11 14:39 | 18.11 14:44 | 0.1 | 1.6 | ✅ | workflow: CI Pipeline; час змін: 7205.4 хв від #225 |
| 5 | `7d2da4c` | #224 | 13.11 14:21 | 13.11 14:24 | 0.0 | 1.6 | ✅ | workflow: CI Pipeline; час змін: 3.5 хв від #224 |
| 6 | `e177a64` | #223 | 13.11 14:10 | 13.11 14:14 | 0.0 | 1.6 | ✅ | workflow: CI Pipeline; час змін: 4.5 хв від #223 |
| 7 | `15aa6ad` | #222 | 12.11 09:37 | 12.11 10:56 | 0.0 | 1.6 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 79.4 хв від #222 |
| 8 | `072b18b` | #220 | 11.11 22:33 | 12.11 09:08 | 0.0 | 1.5 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 635.4 хв від #220 |
| 9 | `617f7fb` | #221 | 11.11 23:36 | 12.11 09:04 | 0.0 | 1.6 | ✅ | workflow: CI Pipeline; час змін: 568.0 хв від #221 |
| 10 | `22a87ab` | #219 | 11.11 19:28 | 11.11 22:02 | 0.1 | 3.2 | ✅ | workflow: CI Pipeline; час змін: 153.6 хв від #219 |
| 11 | `aafefb3` | #218 | 11.11 16:47 | 11.11 17:17 | 0.0 | 1.5 | ✅ | workflow: CI Pipeline; час змін: 29.6 хв від #218 |
| 12 | `4089edc` | #217 | 11.11 16:03 | 11.11 16:45 | 0.1 | 1.4 | ✅ | workflow: CI Pipeline; час змін: 42.7 хв від #217 |
| 13 | `9c40497` | #216 | 11.11 15:58 | 11.11 16:43 | 0.1 | 1.6 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 44.8 хв від #216 |
| 14 | `adb601a` | #215 | 11.11 15:54 | 11.11 16:27 | 0.0 | 1.5 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 33.0 хв від #215 |
| 15 | `837b4ea` | #214 | 11.11 11:29 | 11.11 13:37 | 0.1 | 3.0 | ✅ | workflow: CI Pipeline; час змін: 127.8 хв від #214 |
| 16 | `95675e7` | #213 | 11.11 11:22 | 11.11 13:31 | 0.1 | 1.5 | ✅ | workflow: CI Pipeline; час змін: 129.4 хв від #213 |
| 17 | `3edee06` | #212 | 11.11 11:20 | 11.11 13:27 | 0.1 | 1.5 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 127.1 хв від #212 |
| 18 | `cb77fbb` | #211 | 11.11 11:15 | 11.11 13:22 | 0.0 | 1.4 | ✅ | workflow: CI Pipeline; час змін: 127.2 хв від #211 |
| 19 | `8a8009a` | #210 | 10.11 22:38 | 10.11 23:44 | 0.1 | 1.4 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 65.7 хв від #210 |
| 20 | `cfc140e` | #209 | 06.11 14:14 | 06.11 14:42 | 0.1 | 1.4 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 27.4 хв від #209 |
| 21 | `734cf9b` | #208 | 06.11 14:03 | 06.11 14:21 | 0.0 | 1.3 | ✅ | workflow: CI Pipeline; час змін: 17.2 хв від #208 |
| 22 | `e5a4954` | #206 | 05.11 12:46 | 05.11 13:03 | 0.1 | 1.2 | ✅ | workflow: CI Pipeline; час змін: 17.3 хв від #206 |
| 23 | `f2aef4d` | #205 | 05.11 12:34 | 05.11 12:44 | 0.0 | 1.3 | ✅ | workflow: CI Pipeline; час змін: 10.8 хв від #205 |
| 24 | `c8b61ce` | #204 | 05.11 12:03 | 05.11 12:11 | 0.1 | 1.3 | ✅ | workflow: CI Pipeline; час змін: 8.0 хв від #204 |
| 25 | `69126f9` | #203 | 05.11 11:58 | 05.11 12:08 | 0.1 | 1.3 | ✅ | workflow: CI Pipeline; час змін: 10.2 хв від #203 |
| 26 | `d1fdd8b` | #202 | 05.11 11:36 | 05.11 12:02 | 0.1 | 1.2 | ✅ | workflow: CI Pipeline; час змін: 26.0 хв від #202 |
| 27 | `fb8cdfa` | #201 | 05.11 10:46 | 05.11 10:54 | 0.1 | 1.4 | ✅ | workflow: CI Pipeline; час змін: 7.7 хв від #201 |
| 28 | `d7e8439` | #200 | 04.11 22:21 | 05.11 10:12 | 0.1 | 1.3 | ✅ | workflow: CI Pipeline; час змін: 710.7 хв від #200 |
| 29 | `eeb1c03` | #199 | 04.11 19:47 | 04.11 21:30 | 0.0 | 1.4 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 103.3 хв від #199 |
| 30 | `ab38a8d` | #198 | 04.11 17:50 | 04.11 19:50 | 0.5 | 1.3 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 119.6 хв від #198 |
| 31 | `47aa3b3` | #197 | 03.11 20:29 | 04.11 17:40 | 0.1 | 1.3 | ✅ | workflow: CI Pipeline; час змін: 1271.4 хв від #197 |
| 32 | `348af65` | #196 | 03.11 19:45 | 03.11 20:20 | 0.1 | 1.3 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 35.2 хв від #196 |
| 33 | `bdd8e9f` | #195 | 03.11 18:21 | 03.11 20:18 | 0.0 | 1.3 | ✅ | workflow: CI Pipeline; час змін: 117.4 хв від #195 |
| 34 | `9c36df6` | #193 | 01.11 22:17 | 02.11 08:56 | 0.1 | 2.6 | ✅ | workflow: CI Pipeline; час змін: 639.9 хв від #193 |
| 35 | `59c9fec` | #192 | 01.11 22:03 | 02.11 03:02 | 82.1 | 4.2 | ✅ | workflow: CI Pipeline; час змін: 299.5 хв від #192 |
| 36 | `d4bc5cd` | #191 | 01.11 20:56 | 02.11 01:32 | 149.8 | 4.2 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 275.5 хв від #191 |
| 37 | `e4c28bb` | #190 | 01.11 20:49 | 01.11 22:37 | 83.7 | 4.4 | ✅ | workflow: CI Pipeline; час змін: 107.6 хв від #190 |
| 38 | `c85cb41` | #189 | 01.11 20:08 | 01.11 20:42 | 4.9 | 1.7 | ✅ | workflow: CI Pipeline; час змін: 34.1 хв від #189 |
| 39 | `c3de26c` | #188 | 01.11 19:46 | 01.11 20:05 | 4.5 | 1.5 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 18.3 хв від #188 |
| 40 | `b3d7c12` | #187 | 01.11 17:46 | 01.11 19:50 | 15.9 | 0.5 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 123.3 хв від #187 |
| 41 | `e5243e3` | #185 | 31.10 22:23 | 01.11 13:03 | 1.3 | 1.4 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 879.5 хв від #185 |
| 42 | `35c5d44` | #164 | 30.10 14:20 | 01.11 11:59 | 0.1 | 1.2 | ✅ | workflow: CI Pipeline; час змін: 2739.2 хв від #164 |
| 43 | `5802fb5` | #184 | 31.10 23:48 | 01.11 11:56 | 0.0 | 1.3 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 727.5 хв від #184 |
| 44 | `bc5bdd7` | #182 | 31.10 22:14 | 31.10 22:22 | 1.9 | 1.4 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 8.4 хв від #182 |
| 45 | `55a6ccd` | #181 | 31.10 21:04 | 31.10 21:11 | 0.0 | 1.3 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 6.3 хв від #181 |
| 46 | `9f06cdb` | #179 | 31.10 20:26 | 31.10 20:45 | 0.8 | 1.3 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 18.7 хв від #179 |
| 47 | `df16c8d` | #180 | 31.10 20:32 | 31.10 20:40 | 2.8 | 0.6 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 8.0 хв від #180 |
| 48 | `3c5692e` | #178 | 31.10 17:01 | 31.10 19:51 | 0.9 | 1.2 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 170.4 хв від #178 |
| 49 | `40d595f` | #177 | 31.10 17:01 | 31.10 19:51 | 0.8 | 1.2 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 169.8 хв від #177 |
| 50 | `7c134d0` | #176 | 31.10 17:01 | 31.10 19:50 | 0.3 | 1.3 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 169.0 хв від #176 |
| 51 | `baae26e` | #175 | 31.10 15:51 | 31.10 16:37 | 0.1 | 0.7 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 45.2 хв від #175 |
| 52 | `18b286d` | #174 | 31.10 15:51 | 31.10 16:36 | 0.0 | 0.7 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 44.8 хв від #174 |
| 53 | `90fe3f1` | #173 | 31.10 14:14 | 31.10 15:33 | 0.1 | 0.7 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 78.6 хв від #173 |
| 54 | `b503f99` | #172 | 30.10 23:18 | 31.10 13:48 | 3.7 | 0.5 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 869.3 хв від #172 |
| 55 | `75c97d4` | #171 | 30.10 23:06 | 31.10 13:39 | 6.0 | 0.5 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 873.0 хв від #171 |
| 56 | `0f314f1` | #170 | 30.10 22:15 | 31.10 13:18 | 1.0 | 0.5 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 903.2 хв від #170 |
| 57 | `30fa8dc` | #169 | 30.10 21:49 | 31.10 13:15 | 0.0 | 0.7 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 925.7 хв від #169 |
| 58 | `5e8f0a5` | #166 | 30.10 15:49 | 31.10 13:12 | 0.1 | 0.6 | ✅ | workflow: CI Pipeline; час змін: 1283.8 хв від #166 |
| 59 | `ea3c41e` | #165 | 30.10 14:38 | 30.10 16:58 | 87.5 | 0.5 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 139.2 хв від #165 |
| 60 | `45ff0bb` | #163 | 29.10 16:18 | 30.10 12:51 | 0.0 | 0.7 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 1232.5 хв від #163 |
| 61 | `6d932c0` | #162 | 29.10 15:56 | 30.10 12:50 | 0.1 | 0.7 | ✅ | workflow: CI Pipeline; час змін: 1253.1 хв від #162 |
| 62 | `68d8ce3` | #161 | 29.10 13:24 | 29.10 13:27 | 1.0 | 0.7 | ✅ | workflow: CI Pipeline; час змін: 2.8 хв від #161 |
| 63 | `044a5cb` | #160 | 29.10 13:01 | 29.10 13:03 | 0.1 | 0.6 | ✅ | workflow: CI Pipeline; час змін: 2.2 хв від #160 |
| 64 | `1b20015` | #159 | 29.10 12:45 | 29.10 12:50 | 0.0 | 0.7 | ✅ | workflow: CI Pipeline; час змін: 4.8 хв від #159 |
| 65 | `df9e8c1` | #158 | 29.10 12:15 | 29.10 12:42 | 0.3 | 0.8 | ✅ | workflow: CI Pipeline; час змін: 27.0 хв від #158 |
| 66 | `b829348` | #156 | 29.10 12:10 | 29.10 12:40 | 3.5 | 0.8 | ✅ | workflow: CI Pipeline; час змін: 30.0 хв від #156 |
| 67 | `d28ed3c` | #157 | 29.10 12:12 | 29.10 12:39 | 7.0 | 0.7 | ✅ | workflow: CI Pipeline; час змін: 26.7 хв від #157 |
| 68 | `e93cf3e` | #155 | 29.10 12:09 | 29.10 12:34 | 7.6 | 0.8 | ✅ | workflow: CI Pipeline; час змін: 25.3 хв від #155 |
| 69 | `c6881cc` | #154 | 29.10 12:07 | 29.10 12:24 | 0.1 | 0.8 | ✅ | workflow: CI Pipeline, Generate and Deploy API Docs; час змін: 17.0 хв від #154 |
| 70 | `e753bac` | #153 | 29.10 12:04 | 29.10 12:23 | 0.1 | 0.7 | ✅ | workflow: CI Pipeline; час змін: 18.4 хв від #153 |
| 71 | `c5730ca` | #152 | 29.10 11:23 | 29.10 12:21 | 0.1 | 0.8 | ✅ | workflow: CI Pipeline; час змін: 57.6 хв від #152 |
| 72 | `d066ff4` | #150 | 29.10 11:53 | 29.10 12:19 | 0.0 | 0.8 | ✅ | workflow: CI Pipeline; час змін: 25.6 хв від #150 |
| 73 | `fe17f7d` | #151 | 29.10 11:55 | 29.10 12:05 | 0.0 | 0.7 | ✅ | workflow: CI Pipeline; час змін: 9.4 хв від #151 |
| 74 | `f9d3b56` | #149 | 29.10 11:26 | 29.10 12:03 | 0.1 | 0.7 | ✅ | workflow: CI Pipeline; час змін: 36.5 хв від #149 |

## Методика і вибірка

- Враховані workflow: CI Pipeline, Generate and Deploy API Docs.
- Один рядок на коміт: коміт зелений, лише якщо всі завершені враховані workflow успішні.
- Критичний workflow коміту — той, що завершився останнім. Черга: від `createdAt` саме цього workflow до старту його першого job; виконання: від старту першого job до завершення останнього job цього самого workflow.
- Час виконання змін у примітці: від `authoredDate` першого коміту PR до завершення останнього зеленого запуску; для прямого коміту в `main` — від authored date самого коміту.
- У таблиці лише завершені запуски у вікні 21 день; незавершені не класифікуються. `main`: 107 success, 0 failure; attempts завершених запусків: 1.
- PR-запуски отримані через `gh run list --event pull_request --limit 1000`; у тому самому періоді 187 запусків, з них 28 невдалих. Невдачі PR не рахуються як невдалі зміни на `main` у DORA.

## Розподіл у часі виконання змін

Розраховано за 74 комітами з обома вимірюваннями; суми охоплюють лише критичний workflow кожного коміту.

| Вимір | Сума, хв | Частка суми черги + виконання | Середнє, хв/коміт | Медіана, хв/коміт |
|---|---:|---:|---:|---:|
| Черга | 470.0 | 82.6% | 6.4 | 0.1 |
| Виконання | 99.1 | 17.4% | 1.3 | 1.3 |

## Червоні запуски на main

Завершених червоних запусків на `main` у вибраному періоді немає.

## Невдалі запуски pull request

Причини взято з `gh run view <id> --log-failed`. Ці запуски наведені окремо й не входять у DORA main-метрики.

- Run 43180020077 (`fix/reliability-open-issues`, `CI Pipeline`): Black: would reformat /home/runner/actions-runner/_work/vibecoders/vibecoders/src/api/tests/reliability/test_reliability_frontend.py
- Run 43179453678 (`fix/reliability-open-issues`, `CI Pipeline`): Black: would reformat /home/runner/actions-runner/_work/vibecoders/vibecoders/src/api/tests/reliability/test_reliability_frontend.py
- Run 43178068207 (`fix/reliability-open-issues`, `CI Pipeline`): Black: would reformat /home/runner/actions-runner/_work/vibecoders/vibecoders/src/api/tests/reliability/test_reliability_frontend.py
- Run 42994482801 (`feature/lab09-r10-r11`, `CI Pipeline`): Black: would reformat /home/runner/actions-runner/_work/vibecoders/vibecoders/src/api/store.py
- Run 41312406555 (`Docs_Update`, `CI Pipeline`): Pytest: FAILED src/api/tests/test_notification.py::test_notifications_endpoint_returns_only_current_users_notifications - assert 404 == 200
- Run 41299477773 (`fix/users`, `CI Pipeline`): CI command `python -m flake8` failed; no specific diagnostic was emitted.
- Run 41298765369 (`fix/users`, `CI Pipeline`): Pytest: FAILED src/api/tests/test_notification.py::test_notifications_endpoint_returns_only_current_users_notifications - assert 404 == 200
- Run 41297713728 (`feature/user-profiles-notifications`, `CI Pipeline`): CI command `python -m flake8` failed; no specific diagnostic was emitted.
- Run 41248953230 (`feature/notification-bd-fix`, `CI Pipeline`): CI command `python -m flake8` failed; no specific diagnostic was emitted.
- Run 41248740679 (`feature/notification-bd-fix`, `CI Pipeline`): Black: would reformat /home/runner/actions-runner/_work/vibecoders/vibecoders/src/api/db.py
- Run 41229770669 (`feature/midterm-backend-update`, `CI Pipeline`): Black: would reformat /home/runner/actions-runner/_work/vibecoders/vibecoders/src/api/tests/test_auth_routes.py
- Run 41220079482 (`feature/concurrency-test`, `CI Pipeline`): CI command `python scripts/check_traceability.py` failed; no specific diagnostic was emitted.
- Run 41209105705 (`feature/db-skeleton`, `CI Pipeline`): Black: would reformat /home/runner/actions-runner/_work/vibecoders/vibecoders/src/api/tests/test_db_models.py
- Run 41208529777 (`feature/db-skeleton`, `CI Pipeline`): ERROR: Coverage failure: total of 85 is less than fail-under=95
- Run 41208181879 (`feature/db-skeleton`, `CI Pipeline`): CI command `python -m flake8` failed; no specific diagnostic was emitted.
- Run 41200384058 (`feature/ui-manage-games`, `CI Pipeline`): Pytest: FAILED src/api/tests/test_web.py::test_web_create_game_html_served - assert 404 == 200
- Run 41058657732 (`feature/refactoring-sonar`, `CI Pipeline`): Pytest: FAILED src/api/tests/test_store.py::test_hash_password_is_deterministic_and_hex - AssertionError: assert '519d825ea0e1...6ee795d4bb010' == 'e70b03133044...65afba1978fa4'
- Run 41057721447 (`feature/refactoring-sonar`, `CI Pipeline`): Black: would reformat /home/runner/actions-runner/_work/vibecoders/vibecoders/src/api/store.py
- Run 40953087892 (`docs/fix-documentation`, `CI Pipeline`): CI command `python scripts/check_traceability.py` failed; no specific diagnostic was emitted.
- Run 40952335412 (`docs/fix-documentation`, `CI Pipeline`): CI command `python scripts/check_traceability.py` failed; no specific diagnostic was emitted.
- Run 40950648918 (`docs/fix-documentation`, `CI Pipeline`): CI command `python scripts/check_traceability.py` failed; no specific diagnostic was emitted.
- Run 40949780294 (`docs/fix-documentation`, `CI Pipeline`): CI command `python scripts/check_traceability.py` failed; no specific diagnostic was emitted.
- Run 40948011545 (`docs/fix-documentation`, `CI Pipeline`): CI command `python scripts/check_traceability.py` failed; no specific diagnostic was emitted.
- Run 40946729338 (`docs/fix-documentation`, `CI Pipeline`): Black: would reformat /home/runner/actions-runner/_work/vibecoders/vibecoders/src/api/tests/test_quality_goals.py
- Run 40946453510 (`docs/fix-documentation`, `CI Pipeline`): Black: would reformat /home/runner/actions-runner/_work/vibecoders/vibecoders/src/api/tests/test_quality_goals.py
- Run 40945321993 (`docs/fix-documentation`, `CI Pipeline`): CI command `python scripts/check_traceability.py` failed; no specific diagnostic was emitted.
- Run 40892280607 (`docs/fix-documentation`, `CI Pipeline`): CI command `python scripts/check_traceability.py` failed; no specific diagnostic was emitted.
- Run 40853393454 (`update/lab7_test-plan`, `CI Pipeline`): CI command `python scripts/check_traceability.py` failed; no specific diagnostic was emitted.
