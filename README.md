# 🎲 Організатор Настільних Рольових Ігор (НРІ)

[![CI Test](https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/workflows/ci.yml/badge.svg)](https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/workflows/ci.yml)

Вітаємо у репозиторії команди **VIBECODERS**! 
Цей проєкт розробляється в рамках курсу "Методи розробки програмних систем". 
Наша система дозволяє майстрам організовувати ігри та бронювати кімнати в ігровому клубі, а гравцям — записуватися на сесії через зручний календар.

## Наша команда

Проєкт виконується командою з 4 осіб. Ролі взято з розділу 2 [Командного статуту](./TeamCharter.md#2-ролі-та-відповідальності).

| Учасник | GitHub | Ролі за статутом |
|---|---|---|
| Катерина Спис | @katespys2006 | Керівник вимог; Керівник архітектури; Супроводжувач репозиторію; Backend Lead; Рецензент коду; Стратег тестування |
| Захарук Софія | @Sonafi3 | Керівник якості (Quality Lead); Супроводжувач CI; Керівник моделі даних і загроз; Аналітик безпеки; Керівник інтеграції |
| Голдинська Ірина | @iraholdynska | Керівник трекера завдань; Керівник простежуваності; Керівник інтеграції (Integration Lead) |
| Хамаза Ігор | @reonor | Керівник документації |

## Поточний стан реалізації

- **REST API** на FastAPI: 24 операції під `/api/v1` (вхід і реєстрація, ігри, запис гравців, кімнати, календар і блокування кімнат, користувачі: профіль, список і блокування акаунтів, сповіщення). Специфікація: [openapi-generated.yaml](./docs/api/openapi-generated.yaml).
- **Веб-інтерфейс** на `/app/`: 8 сторінок (головна, вхід, реєстрація, список ігор, сторінка гри, створення гри, календар кімнат, адміністрування). Це статичні HTML і JavaScript, що звертаються до API.
- **Дані** зберігаються в SQLite (`club.db`, SQLAlchemy). При старті сервер додає демо-кімнати, користувачів і ігри. Рішення задокументовано в [ADR-004](./docs/architecture/decisions/ADR-004.md); перехід на MySQL лишається цільовою архітектурою ([ADR-002](./docs/architecture/decisions/ADR-002.md)).
- **Тести**: 291 пройшли, 1 xfailed (відомий дефект D-1), покриття 96,39% (поріг у CI 95%).
- **Не реалізовано**: відправка листів (SMTP), завантаження аватара, окрема міграція на MySQL. Повний перелік обмежень: [progress.md](./docs/code-quality/progress.md), розділ 5.

## Запуск

### Вимоги до середовища

- **Python 3.9 або новіший.** CI працює на Python 3.9. Мутаційне тестування (`mutmut`) потребує Python 3.10+ і ставиться лише там автоматично. Docker-образ збирається на Python 3.13, публікація документації API на Pages працює на 3.12.
- Git і доступ до інтернету для `pip install`.

### Кроки

Усі команди виконуються з кореня репозиторію.

1. Клонуйте репозиторій і створіть віртуальне середовище:

   ```
   git clone https://github.com/ukma-fin-ssdm-2026/vibecoders.git
   cd vibecoders
   python -m venv .venv
   ```

2. Активуйте його:

   ```
   # Linux або macOS
   source .venv/bin/activate

   # Windows (PowerShell)
   .venv\Scripts\Activate.ps1
   ```

3. Встановіть залежності:

   ```
   python -m pip install --upgrade pip
   pip install -r src/api/requirements.txt
   ```

4. Запустіть сервер:

   ```
   cd src/api
   python main.py
   ```

Сервер стартує на `http://127.0.0.1:3000`:

| Що | Адреса |
|---|---|
| Веб-інтерфейс | `http://127.0.0.1:3000/app/` |
| Swagger UI | `http://127.0.0.1:3000/api-docs` |
| ReDoc | `http://127.0.0.1:3000/redoc` |

У Swagger UI для захищених операцій натисніть Authorize і введіть демо-токен. Щоб слухати не лише localhost, задайте змінну середовища `API_HOST`.

При кожному запуску сервер перезаписує `docs/api/openapi-generated.yaml`. Специфікацію можна згенерувати й окремо: `python generate_openapi.py` (з `src/api`).

### Демо-акаунти

| Роль | Пошта | Пароль | Токен для Swagger UI |
|---|---|---|---|
| Майстер | `master@club.test` | `master-pass-1` | `master-token` |
| Гравець | `player@club.test` | `player-pass-1` | `player-token` |
| Власник клубу | `owner@club.test` | `owner-pass-1` | `owner-token` |

Це навчальні дані. Нового гравця можна зареєструвати на сторінці `/app/register.html`.

### Змінні середовища

Застосунок сам не читає файл `.env`: [.env.example](./.env.example) лише перелічує змінні, їх треба задати в оточенні.

| Змінна | За замовчуванням | Призначення |
|---|---|---|
| `API_HOST` | `127.0.0.1` | Адреса, на якій слухає `python main.py` |
| `DATABASE_URL` | `sqlite:///club.db` | Адреса бази; файл SQLite лежить у корені репозиторію |
| `DATA_DIR` | корінь репозиторію | Каталог для `club.db` |
| `PASSWORD_SALT` | небезпечне dev-значення | Сіль для хешування паролів. Для розгортання задайте власну |
| `MASTER_TOKEN`, `PLAYER_TOKEN`, `OWNER_TOKEN` | `master-token`, `player-token`, `owner-token` | Демо-токени |
| `API_CORS_ORIGINS` | `https://ukma-fin-ssdm-2026.github.io` | Дозволені origin для Swagger UI на GitHub Pages, через кому |

### Запуск у Docker

```
docker build -t vibecoders .
docker run --rm -p 8000:8000 -e PASSWORD_SALT=change-me vibecoders
```

Інтерфейс: `http://localhost:8000/app/`. Контейнер слухає порт із змінної `PORT` (за замовчуванням 8000).

### Тести та перевірки якості

```
python -m pytest
```

Те саме, що виконує CI (з покриттям, порогом 95% та перевірками стилю й безпеки):

```
python -m black --check src/api
python -m flake8
python -m bandit -x src/api/tests -r src/api
python scripts/check_traceability.py
python -m pytest src/api/tests --cov=src/api --cov-report=term-missing --cov-fail-under=95
```

У `requirements.txt` закріплено `pytest<9`: pytest 9.2 несумісний з `pytest-benchmark`, і тест продуктивності PERF-001 падає.

## Розгортання

API і веб-інтерфейс розгортаються на Render з [Dockerfile](./Dockerfile) за конфігурацією [render.yaml](./render.yaml) (безкоштовний тариф).

- **Адреса розгорнутого API:** https://vibecoders.onrender.com (та сама адреса вказана в `servers` у [main.py](./src/api/main.py) і в `openapi-generated.yaml`). Веб-інтерфейс: `/app/`, Swagger UI: `/api-docs`.
- **Swagger UI на GitHub Pages** ([відкрити](https://ukma-fin-ssdm-2026.github.io/vibecoders/)) виконує запити до цього сервера: адреса береться з `servers`, а API дозволяє origin Pages через CORS.
- Безкоштовний сервіс Render засинає після 15 хвилин без запитів, перший запит після сну триває близько хвилини.
- Файл бази лежить на тимчасовому диску, тому після перезапуску чи нового деплою дані повертаються до демо-стану.
- Демо-токени й демо-паролі публічні, розгортання призначене лише для показу. Ризик прийнято і описано в [static-analysis.md](./docs/code-quality/static-analysis.md), розділ 4.

## Артефакти вимог

- [Опис проєкту, міні-ТЗ (Project-Description.md)](./Project-Description.md)
- [Користувацькі історії (user-stories.md)](./docs/requirements/user-stories.md)
- [Функціональні та нефункціональні вимоги (requirements.md)](./docs/requirements/requirements.md)
- [Матриця простежуваності (rtm.md)](./docs/requirements/rtm.md)

## Дизайн і архітектура

- [High level design](./docs/architecture/high-level-design.md)
- [Матриця простежуваності дизайну (traceability-matrix.md)](./docs/architecture/traceability-matrix.md)
- [Модель даних (data-model.md)](./docs/architecture/data-model.md)
- [Модель загроз STRIDE (threat-model.md)](./docs/architecture/threat-model.md)
- [UML-діаграми](./docs/architecture/uml/): [компонентів](./docs/architecture/uml/component-diagram.puml), [розгортання](./docs/architecture/uml/deployment-diagram.puml), [послідовності](./docs/architecture/uml/sequence-diagram.puml), [моделі даних](./docs/architecture/uml/data-model.puml) ([PNG](./docs/architecture/uml/data-model.png))
- Архітектурні рішення: [ADR-001](./docs/architecture/decisions/ADR-001.md), [ADR-002](./docs/architecture/decisions/ADR-002.md), [ADR-003](./docs/architecture/decisions/ADR-003.md), [ADR-004](./docs/architecture/decisions/ADR-004.md)
- Уся тека: [docs/architecture/](./docs/architecture/)

## Документація за лабораторними

| Лаб | Тема | Файли | Відео Loom |
|---|---|---|---|
| 1 | Репозиторій, статут, CI | [TeamCharter.md](./TeamCharter.md), [README.md](./README.md), [Project-Description.md](./Project-Description.md), [ci.yml](./.github/workflows/ci.yml), [deploy-api-docs.yml](./.github/workflows/deploy-api-docs.yml), [.pre-commit-config.yaml](./.pre-commit-config.yaml) | [Labs/Lab01](./Labs/Lab01/) |
| 2 | Вимоги | [user-stories.md](./docs/requirements/user-stories.md), [requirements.md](./docs/requirements/requirements.md), [rtm.md](./docs/requirements/rtm.md) | [Labs/Lab02](./Labs/Lab02/) |
| 3 | Архітектура | [high-level-design.md](./docs/architecture/high-level-design.md), [traceability-matrix.md](./docs/architecture/traceability-matrix.md), [data-model.md](./docs/architecture/data-model.md), [threat-model.md](./docs/architecture/threat-model.md), [uml/](./docs/architecture/uml/), [decisions/](./docs/architecture/decisions/) | [Labs/Lab03](./Labs/Lab03/) |
| 4 | API | [api-design.md](./docs/api/api-design.md), [openapi-generated.yaml](./docs/api/openapi-generated.yaml), [quality-attributes.md](./docs/api/quality-attributes.md), [index.html](./docs/api/index.html), [mocks/users.json](./docs/api/mocks/users.json) | [Labs/Lab04](./Labs/Lab04/) |
| 5 | Якість коду | [review-report.md](./docs/code-quality/review-report.md), [static-analysis.md](./docs/code-quality/static-analysis.md), [progress.md](./docs/code-quality/progress.md) | [Labs/Lab05](./Labs/Lab05/) |
| 6 | Тестування й налагодження | [testing-strategy.md](./docs/testing/testing-strategy.md), [debugging-log.md](./docs/testing/debugging-log.md), [Веб-інтерфейс](#веб-інтерфейс) | [Labs/Lab06](./Labs/Lab06/) |
| 7 | План тестування й взаємні огляди | [test-plan.md](./docs/validation/test-plan.md), [review-log.md](./docs/validation/review-log.md) | [Labs/Lab07](./Labs/Lab07/) |
| Рефакторинг | Аналіз SonarCloud | [sonarcloud-report.md](./docs/refactoring/sonarcloud-report.md) | — |

Усі відео лежать у теці [Labs/](./Labs/) за шаблоном `Labs/LabNN/video_<Прізвище>.txt`.

## Веб-інтерфейс

Інтерфейс доступний за адресою `/app/`; локально після запуску сервера — [http://127.0.0.1:3000/app/](http://127.0.0.1:3000/app/). Це статичні сторінки HTML і JavaScript без фронтенд-фреймворків; клієнт надсилає запити до JSON API під `/api/v1`.

| Файл | Призначення | Ролі, для яких сторінка доступна |
|---|---|---|
| `index.html` | Головна сторінка, навігація, вітання та кількість нових сповіщень після входу | Гість, гравець, майстер, власник клубу |
| `login.html` | Вхід у систему | Гість; після входу показується повідомлення про активну сесію |
| `register.html` | Реєстрація акаунта гравця | Гість; після входу показується повідомлення про активну сесію |
| `games.html` | Перегляд ігор, фільтр за кімнатою, перехід до деталей; створення гри для відповідних ролей | Усі ролі; «Створити гру» — майстер і власник клубу |
| `game.html` | Деталі гри, запис і вихід; список гравців і керування грою | Усі можуть переглянути сторінку; запис доступний після входу, керування — майстру гри та власнику клубу |
| `create-game.html` | Форма створення гри | Майстер і власник клубу; гість бачить пропозицію увійти, гравець — повідомлення про відсутність прав |
| `calendar.html` | Перегляд бронювань і блокувань кімнат на вибрану дату | Гравець, майстер, власник клубу через навігацію |
| `notifications.html` | Перегляд сповіщень поточного користувача | Гравець, майстер, власник клубу; гість бачить пропозицію увійти |
| `profile.html` | Перегляд і редагування профілю, контактів та URL аватара | Гравець, майстер, власник клубу; гість бачить пропозицію увійти |
| `admin.html` | Перегляд кімнат, блокування кімнати на період та керування блокуваннями | Власник клубу; гість бачить пропозицію увійти, інші ролі — повідомлення про обмеження доступу |

### Як перевірити за ролями

На сторінці входу доступні демо-акаунти:

| Роль | Електронна пошта | Пароль |
|---|---|---|
| Майстер | `master@club.test` | `master-pass-1` |
| Гравець | `player@club.test` | `player-pass-1` |
| Власник клубу | `owner@club.test` | `owner-pass-1` |

1. **Гравець:** увійдіть як `player@club.test`, перегляньте ігри, відкрийте деталі гри, запишіться або скасуйте запис; перевірте календар, сповіщення та редагування профілю.
2. **Майстер:** увійдіть як `master@club.test`, створіть гру, перегляньте список гравців власної гри та за потреби видаліть гравця або гру.
3. **Власник клубу:** увійдіть як `owner@club.test`, перегляньте адміністрування, заблокуйте кімнату на період і перевірте календар та сповіщення. Сторінка адміністрування наразі не надає інтерфейсу блокування акаунтів: розділ користувачів прихований.

### Знімки екрана

![Сторінка входу](./docs/img/login.png)

*Сторінка входу.*

![Список ігор](./docs/img/games.png)

*Сторінка зі списком ігор.*

![Деталі гри](./docs/img/game.png)

*Сторінка деталей гри.*

![Календар кімнат](./docs/img/calendar.png)

*Календар кімнат.*

![Адміністрування](./docs/img/admin.png)

*Сторінка адміністрування.*

## Використання ШІ

Структуру цього README, таблиці й тексти розділів «Запуск» і «Розгортання» підготовлено за допомогою Claude. Перевірено: усі відносні посилання вказують на наявні файли; команди запуску, тестів і перевірок якості виконано на поточному коді (Python 3.9 як у CI і 3.12), сервер стартував за тією самою командою, що й Dockerfile; ролі скопійовано з розділу 2 статуту; адресу розгортання взято з `servers` у `main.py`. Роботу розгорнутого сервера на Render і збірку Docker-образу локально не перевіряли.

Розділ «Веб-інтерфейс» згенеровано за допомогою Claude і вручну звірено зі сторінками `src/api/web/`. Файли знімків екрана мають бути додані окремо.
