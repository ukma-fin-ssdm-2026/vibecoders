# Бонус: покращення CI з виміряним ефектом

## Дія та першопричина

Для `pull_request` окремий легкий job визначає, чи містить PR файли крім Markdown (`**/*.md`). Якщо ні, два self-hosted jobs, що перевіряють Python-код і тести, пропускаються; PR із будь-яким не-Markdown файлом, зокрема кодом, тестами або конфігурацією, запускає їх як раніше. Workflow не використовує trigger-level `paths-ignore`: пропущені jobs мають успішний статус, тож required checks `validate-and-test` і `reliability-tests` не зависають у Pending. Перейменування файлів рахується як зміна старого й нового шляху, тому переміщення коду в Markdown не пропустить CI.

У PR #223 і #224 змінювалися лише Markdown-файли, але кожен запускав обидва self-hosted jobs: разом вони використали **4 хв 24 с job-time** (`validate-and-test`: 1:32 і 1:33; `reliability-tests`: 0:40 і 0:39). На `main` також спостерігалися черги 82,1 хв для `59c9fec`, 73,6 хв для `d4bc5cd` і 83,7 хв для `e4c28bb`, тож раннерний час має цінність для спільного пулу з чотирьох машин. Черга не доводить, що її спричинили docs-only PR, але приклади PR #223 і #224 прямо показують зайві перевірки коду й тестів для змін лише документації. Тому обрано фільтрацію Markdown-only змін на рівні jobs, а не workflow trigger, щоб звільнити self-hosted раннери й водночас зберегти required-check статуси.

## Метрика

Очікуване покращення: **кількість self-hosted job minutes**, витрачених CI Pipeline на Markdown-only pull request. Це не обіцяє скорочення черги для кожного запуску; фактичний ефект слід оцінити після кількох PR із Markdown-only змінами та порівняти витрачений runner time.

## ДО: запуски на main до зміни

Нижче — п'ять зелених запусків на `main` для злитих PR зі змінами коду, тестів або CI-конфігурації. Чергу й виконання взято з фактичних `createdAt`/job `startedAt`/`completedAt`; час змін — від `authoredDate` першого коміту PR до завершення останнього врахованого workflow. Посилання у стовпці «Запуски main» ведуть до сирих GitHub Actions job-даних.

| Коміт | PR | Черга, хв | Виконання, хв | Час виконання змін, хв | Запуски main |
|---|---:|---:|---:|---:|---|
| `15aa6ad` | #222 | 0.0 | 1.6 | 79.4 | [CI](https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/runs/43186886864), [API docs](https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/runs/43186886697) |
| `072b18b` | #220 | 0.0 | 1.5 | 635.4 | [CI](https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/runs/43172879686), [API docs](https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/runs/43172879699) |
| `9c40497` | #216 | 0.1 | 1.6 | 44.8 | [CI](https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/runs/43041008763), [API docs](https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/runs/43041008526) |
| `adb601a` | #215 | 0.0 | 1.5 | 33.0 | [CI](https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/runs/43038460501), [API docs](https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/runs/43038460890) |
| `95675e7` | #213 | 0.1 | 1.5 | 129.4 | [CI](https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/runs/43012489921) |

## ПІСЛЯ: заповнити після злиття та нових запусків

Заповнити після злиття цієї зміни та накопичення 3–5 наступних запусків на `main`. Не враховувати PR лише з Markdown у цьому порівнянні main-раннерів, бо для них очікується, що CI Pipeline не стартуватиме.

| Коміт | PR | Черга, хв | Виконання, хв | Час виконання змін, хв |
|---|---:|---:|---:|---:|
|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |

### Висновок після вимірювання

Заповнити після появи даних: скільки Markdown-only PR пропустили CI Pipeline, скільки self-hosted job minutes зекономлено та чи змінилися черга або виконання звичайних перевірок на `main`.
