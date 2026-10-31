# 🎲 Організатор Настільних Рольових Ігор (НРІ)

[![CI Test](https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/workflows/ci.yml/badge.svg)](https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/workflows/ci.yml)

Вітаємо у репозиторії команди **VIBECODERS**! 
Цей проєкт розробляється в рамках курсу "Методи розробки програмних систем". 
Наша система дозволяє майстрам організовувати ігри та бронювати кімнати в ігровому клубі, а гравцям — записуватися на сесії через зручний календар.

## Наша команда

Проєкт виконується командою з 4 осіб. По мірі розвитку системи наші технічні ролі будуть розширюватися, але на етапі ініціалізації та управління репозиторієм ми розподілили відповідальності наступним чином:

* **Катерина Спис** (@katespys2006) — *Супроводжувач репозиторію (Repo Maintainer)*
  Забезпечує структурованість та стабільність репозиторію, відповідає за стратегію гілкування та захист головної гілки.

* **Захарук Софія** (@Sonafi3) — *Супроводжувач CI (CI Maintainer)*
  Налаштовує автоматизовані збірки, тестування (GitHub Actions) та стежить за стабільністю конвеєра CI.

* **Голдинська Ірина** (@iraholdynska) — *Керівник трекера завдань (Issue Tracker Lead)*
  Керує завданнями, помилками та загальним робочим процесом розробки у GitHub Issues.

* **Хамаза Ігор** (@reonor) — *Керівник документації та опису проєкту (Documentation & Project Brief Lead)*
  Пише та підтримує ключову документацію, веде опис проєкту, узгоджує його межі та загальну архітектуру.

## Документація
Детальніше про наш робочий процес, оцінку якості та архітектуру можна дізнатися у відповідних файлах:
- [Командний статут (TeamCharter.md)](./TeamCharter.md)
- [Опис проєкту (Project-Description.md)](./Project-Description.md)
- [Звіт про прогрес (progress.md)](./docs/code-quality/progress.md)
- [Звіт з якості коду та статичного аналізу (static-analysis.md)](./docs/code-quality/static-analysis.md)
- [Рецензія на код іншої команди (review-report.md)](./docs/code-quality/review-report.md)
- [Проєктування API (api-design.md)](./docs/api/api-design.md)
- [Атрибути якості API (quality-attributes.md)](./docs/api/quality-attributes.md)

## Артефакти вимог
- [RTM (rtm.md)](./docs/requirements/rtm.md)
- [Модель загроз (threat-model.md)](./docs/architecture/threat-model.md)
- [Архітектурне проєктування та UML (Лабораторна 3)](docs/architecture/)

## API (Лабораторна 4)

Документація API: https://ukma-fin-ssdm-2026.github.io/vibecoders/ (Swagger UI, специфікація автоматично генерується з коду при кожному push у `main` і публікується з гілки `gh-pages`).

### Запуск API

З кореня репозиторію:

```
pip install -r src/api/requirements.txt
cd src/api
python main.py
```

Сервер стартує на `http://127.0.0.1:3000`. Swagger UI: `http://127.0.0.1:3000/api-docs`, ReDoc: `http://127.0.0.1:3000/redoc`. Для захищених операцій у Swagger UI натисніть Authorize і введіть демо-токен: `master-token`, `player-token` або `owner-token`. Щоб слухати не лише localhost, задайте змінну середовища `API_HOST`.

За замовчуванням SQLite-файл `club.db` зберігається в корені репозиторію; шлях стає абсолютним під час запуску. Для іншого розташування задайте `DATABASE_URL` (наприклад, `sqlite:////var/data/club.db`) або `DATA_DIR` (каталог для `club.db`). Після створення таблиць сервер автоматично додає відсутні демо-кімнати, користувачів, токени та ігри.

При кожному запуску сервер перезаписує `docs/api/openapi-generated.yaml`. Специфікацію можна згенерувати й окремо: `python generate_openapi.py` (з `src/api`).

### Тести

З кореня репозиторію:

```
python -m pytest
```
