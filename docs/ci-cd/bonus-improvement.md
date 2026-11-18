# Бонус: покращення CI з виміряним ефектом

## Дія та першопричина

У `validate-and-test` та `reliability-tests` увімкнено кеш pip через `actions/setup-python@v5`. Кожен job має окремий `cache-dependency-path`, щоб зміна відповідного файлу залежностей створювала новий кеш. Для reliability-тестів залежності винесені в `src/api/requirements-reliability.txt`; файл використовується і як ключ кешу, і для встановлення тих самих зафіксованих версій пакетів.

Дані п'яти запусків `main` у таблиці «ДО» показують, що крок `Install dependencies` у `validate-and-test` тривав 11–12 с (середнє 11,2 с), а `Install reliability-test dependencies` — 9 с у кожному запуску. Крок `Set up Python` тривав 8–10 с у кожному job. Кеш має скоротити насамперед повторне отримання пакетів; час job вимірюється повністю, тож можливі витрати на відновлення кешу теж залишаються у вимірі.

PR #228 із фільтром Markdown-only PR — допоміжна, окрема зміна: вона пропускає CI jobs лише для документаційних pull request, не впливає на push у `main` і тому не бере участі у наведеному порівнянні job-time на `main`.

## Метрика

Порівнюється повна тривалість jobs `validate-and-test` і `reliability-tests` у секундах на завершених запусках `main`, породжених злитими PR зі змінами коду, тестів або CI-конфігурації. Черга вказана окремо в секундах: від `createdAt` запуску до старту першого job. Тривалість кожного job — від його `startedAt` до `completedAt`.

До: `validate-and-test` — середнє **91,8 с**, медіана **91 с**; `reliability-tests` — середнє **38,2 с**, медіана **38 с**. Після накопичення 3–5 придатних запусків треба порахувати ті самі середні й медіани та різницю відносно цих базових значень.

## ДО: запуски на main до кешування

Усі п'ять записів — успішні запуски `main` після злиття відповідних PR. Для кожного PR перевірено перелік файлів через `git diff --name-only` між першим батьком merge-коміту та merge-комітом; усі містять зміни коду, тестів або CI-конфігурації, а не лише Markdown.

| Коміт | PR | Черга, с | `validate-and-test`, с | `reliability-tests`, с | Запуск |
|---|---:|---:|---:|---:|---|
| `15aa6ad` | [#222](https://github.com/ukma-fin-ssdm-2026/vibecoders/pull/222) | 2 | 97 | 42 | [CI run 43186886864](https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/runs/43186886864) |
| `072b18b` | [#220](https://github.com/ukma-fin-ssdm-2026/vibecoders/pull/220) | 2 | 89 | 38 | [CI run 43172879686](https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/runs/43172879686) |
| `9c40497` | [#216](https://github.com/ukma-fin-ssdm-2026/vibecoders/pull/216) | 3 | 93 | 38 | [CI run 43041008763](https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/runs/43041008763) |
| `adb601a` | [#215](https://github.com/ukma-fin-ssdm-2026/vibecoders/pull/215) | 2 | 89 | 39 | [CI run 43038460501](https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/runs/43038460501) |
| `95675e7` | [#213](https://github.com/ukma-fin-ssdm-2026/vibecoders/pull/213) | 3 | 91 | 34 | [CI run 43012489921](https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/runs/43012489921) |

## ПІСЛЯ: заповнити після злиття та нових запусків

Додати 3–5 завершених запусків `main` від злитих PR, у яких є зміни коду, тестів або конфігурації. Для кожного PR перевірити зміни командою `git diff --name-only`. Не включати docs-only PR.

| Коміт | PR | Черга, с | `validate-and-test`, с | `reliability-tests`, с | Запуск |
|---|---:|---:|---:|---:|---|
|  |  |  |  |  |  |
|  |  |  |  |  |  |
|  |  |  |  |  |  |
|  |  |  |  |  |  |
|  |  |  |  |  |  |

### Висновок після вимірювання

Заповнити після появи даних: середнє й медіана тривалості обох jobs до/після, абсолютна та відсоткова різниця. Якщо кеш не скоротив час або збільшив його через накладні витрати, вказати це прямо.
