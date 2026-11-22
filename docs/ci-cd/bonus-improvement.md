# Бонус: покращення CI з виміряним ефектом

## Дія та першопричина

У `validate-and-test` та `reliability-tests` увімкнено кеш pip через `actions/setup-python@v5`. Кожен job має окремий `cache-dependency-path`, щоб зміна відповідного файлу залежностей створювала новий кеш. Для reliability-тестів залежності винесені в `src/api/requirements-reliability.in` і скомпільовані у `src/api/requirements-reliability.txt` з транзитивними версіями й хешами; CI встановлює їх із `--require-hashes`. `greenlet` зафіксовано окремо, оскільки SQLAlchemy оголошує для нього лише нижню межу версії, якої недостатньо для hash-checking. При зміні прямих залежностей потрібно оновити lock-файл через `pip-compile --generate-hashes --allow-unsafe --output-file=src/api/requirements-reliability.txt src/api/requirements-reliability.in`.

Дані п'яти запусків `main` у таблиці «ДО» показують, що крок `Install dependencies` у `validate-and-test` тривав 11–12 с (середнє 11,2 с), а `Install reliability-test dependencies` — 9 с у кожному запуску. Крок `Set up Python` тривав 8–10 с у кожному job. Кеш має скоротити насамперед повторне отримання пакетів; час job вимірюється повністю, тож можливі витрати на відновлення кешу теж залишаються у вимірі.

PR #228 із фільтром Markdown-only PR — допоміжна, окрема зміна: вона пропускає CI jobs лише для документаційних pull request, не впливає на push у `main` і тому не бере участі у наведеному порівнянні job-time на `main`.

## Метрика

Порівнюється повна тривалість jobs `validate-and-test` і `reliability-tests` у секундах на завершених запусках `main`, породжених злитими PR зі змінами коду, тестів або CI-конфігурації. Черга вказана окремо в секундах: від `createdAt` запуску до старту першого job. Тривалість кожного job — від його `startedAt` до `completedAt`.

До: `validate-and-test` — середнє **91,8 с**, медіана **91 с**; `reliability-tests` — середнє **38,2 с**, медіана **38 с**. У поточному вимірюванні після злиття є лише два придатні запуски; цільова вибірка у 3–5 запусків ще не набрана.

## ДО: запуски на main до кешування

Усі п'ять записів — успішні запуски `main` після злиття відповідних PR. Для кожного PR перевірено перелік файлів через `git diff --name-only` між першим батьком merge-коміту та merge-комітом; усі містять зміни коду, тестів або CI-конфігурації, а не лише Markdown.

| Коміт | PR | Черга, с | `validate-and-test`, с | `reliability-tests`, с | Запуск |
|---|---:|---:|---:|---:|---|
| `15aa6ad` | [#222](https://github.com/ukma-fin-ssdm-2026/vibecoders/pull/222) | 2 | 97 | 42 | [CI run 43186886864](https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/runs/43186886864) |
| `072b18b` | [#220](https://github.com/ukma-fin-ssdm-2026/vibecoders/pull/220) | 2 | 89 | 38 | [CI run 43172879686](https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/runs/43172879686) |
| `9c40497` | [#216](https://github.com/ukma-fin-ssdm-2026/vibecoders/pull/216) | 3 | 93 | 38 | [CI run 43041008763](https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/runs/43041008763) |
| `adb601a` | [#215](https://github.com/ukma-fin-ssdm-2026/vibecoders/pull/215) | 2 | 89 | 39 | [CI run 43038460501](https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/runs/43038460501) |
| `95675e7` | [#213](https://github.com/ukma-fin-ssdm-2026/vibecoders/pull/213) | 3 | 91 | 34 | [CI run 43012489921](https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/runs/43012489921) |

## ПІСЛЯ: запуски на main після злиття PR #233

Перевірено файли кожного PR через `git diff --name-only <merge>^1 <merge>`. PR #233 містить зміну CI та файли залежностей; PR #232 містить workflow, скрипт і тест; PR #237 змінює `.github/workflows/ci.yml`. Їхні запуски враховано. PR #234 виключено: хоча в ньому є JSON evidence, усі змінені файли належать до `docs/ci-cd/`, тобто це документаційний PR без змін коду, тестів чи CI-конфігурації.

Перший запуск після злиття (#233) був із холодним кешем: у логах немає повідомлення про cache hit, а кеш збережено наприкінці jobs. У наступних запусках (#232 і #237) кеш відновлено в обох jobs. Черга порахована від `createdAt` до `startedAt` першого job, який фактично виконувався; пропущений `docs_filter` не враховано, оскільки для нього GitHub повертає суперечливі timestamps (`startedAt` пізніше за `completedAt`).

| Коміт | PR | Черга, с | `validate-and-test`, с | `reliability-tests`, с | Примітка | Запуск |
|---|---:|---:|---:|---:|---|---|
| `f3f0005` | [#233](https://github.com/ukma-fin-ssdm-2026/vibecoders/pull/233) | 3 | 102 | 45 | Холодний кеш; cache miss, кеш збережено | [CI run 44476010874](https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/runs/44476010874) |
| `90eccce` | [#232](https://github.com/ukma-fin-ssdm-2026/vibecoders/pull/232) | 3 | 99 | 43 | Теплий кеш; cache hit у двох jobs | [CI run 44482522699](https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/runs/44482522699) |
| `c6f6cde` | [#237](https://github.com/ukma-fin-ssdm-2026/vibecoders/pull/237) | 3 | 102 | 41 | Теплий кеш; cache hit у двох jobs | [CI run 44508270589](https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/runs/44508270589) |

Сирі дані збережено в `evidence/runs-after-pr237-20261119.json`, `evidence/jobs/44508270589-attempt-1.json` та `evidence/prs/pr-237.json`; раніші виміри й PR-дані залишаються у файлах, перелічених у попередньому абзаці документації.

### Висновок після вимірювання

У таблиці наведені середнє та медіана для трьох придатних запусків разом із холодним першим запуском і окремо для двох теплих. Різниця для середнього зіставлена з базовим середнім, а для медіани — з базовою медіаною.

| Job | ДО: середнє / медіана, с | ПІСЛЯ з холодним кешем: середнє / медіана, с | Різниця середнього від ДО | Різниця медіани від ДО | ПІСЛЯ без холодного запуску: середнє / медіана, с | Різниця середнього від ДО | Різниця медіани від ДО |
|---|---:|---:|---:|---:|---:|---:|---:|
| `validate-and-test` | 91,8 / 91 | 101 / 102 | +9,2 с (+10,0%) | +11 с (+12,1%) | 100,5 / 100,5 | +8,7 с (+9,5%) | +9,5 с (+10,4%) |
| `reliability-tests` | 38,2 / 38 | 43 / 43 | +4,8 с (+12,6%) | +5 с (+13,2%) | 42 / 42 | +3,8 с (+9,9%) | +4 с (+10,5%) |

Після трьох запусків виграшу за повною тривалістю jobs відносно бази не видно: обидва jobs повільніші як у вибірці з холодним кешем, так і в підвибірці з двома теплими запусками. Крок встановлення залежностей на теплому запуску PR #237 тривав 9 с у `validate-and-test` і 7 с у `reliability-tests`; це менше базових 11 с і 9 с, але скорочення кроку не зменшило загальну тривалість job. Результат не можна приписати лише кешу: у PR #233 разом із кешуванням змінено спосіб встановлення залежностей reliability-тестів — додано lock-файл із хешами та `--require-hashes`. Вибірка тепер становить два теплі запуски, але загальні job-часи включають інші етапи, тому ці результати не доводять, що саме кеш спричинив зміну повної тривалості.
