# SonarQube Cloud Analysis Report

**Команда:** vibecoders

---

## 1. Метрики «до» 

- **Дата аналізу:** 01.11.2026, остання версія гілки `main`
- **Обсяг:** ≈ 9,7 тис. рядків коду
- **Quality Gate:** Passed
- **Всього зауважень на панелі:** 26

| Показник | Значення «до» | Деталі |
| :--- | :---: | :--- |
| **Security Rating** | **C** | 9 Security issues (≈11% High, ≈89% Medium) |
| **Reliability Rating** | **C** | 17 Reliability issues (≈6% High, ≈94% Medium) |
| **Maintainability Rating** | **A** | 15 Maintainability issues (Code Smells) |
| **Code Smells** | **15** | відповідає Maintainability issues |
| **Technical Debt** | **1 д 1 год** | - |
| **Duplicated Lines (%)** | **0,0%** | - |

> Одне зауваження може впливати на кілька якостей (Security, Reliability, Maintainability), тому 9 + 17 + 15 більше за 26.

Скриншоти «до»: 
<img width="1129" height="260" alt="image" src="https://github.com/user-attachments/assets/4488b8c1-2b50-4119-850e-acaa2ac3ce4c" />
<img width="1126" height="723" alt="image" src="https://github.com/user-attachments/assets/122a40c1-1fc4-43f2-8d13-52787ff02fe9" />
<img width="1126" height="721" alt="image" src="https://github.com/user-attachments/assets/410b0004-51ad-4708-b5ca-8d537f130a88" />
<img width="1134" height="727" alt="image" src="https://github.com/user-attachments/assets/bf545c3c-f52b-4571-845b-933ca382c6c0" />

---

## 2. Обрані метрики для покращення (3 показники)

1. **Reliability Rating (C, 17 issues)**
   * Рейтинг C вказує на проблеми, що впливають на стабільність виконання. 14 з 17 зауважень: глобальні `isNaN()` і `parseInt()` замість `Number.isNaN()` і `Number.parseInt()` у клієнтському JS; ще `lang` у `index.html`, порожній заголовок у `game.html` і `[` у `run_mutation.sh`.
2. **Code Smells (15 issues, Maintainability A)**
   * Рейтинг уже A, але 15 зауважень є технічним боргом. Мета: зменшити кількість Code Smells (15 зауважень, ≈ 30 хв боргу, усі в `src/api/web/*`).
3. **Technical Debt (1 д 1 год)**
   * Мета: зменшити сумарний час усунення зауважень. Нотатка: Maintainability Rating уже A, тому його рівень піднімати нема куди; покращення вимірюємо в хвилинах боргу.

---

## 3. Security Rating 

* **Security Rating «до»:** **C** (9 issues: 1 High, 8 Medium). Усі 9 знахідок лежать у CI-конфігурації, у Python-коді `src/api` Security-зауважень немає.

| # | Правило | Файл, рядок | Severity | Що робимо |
| :-: | :--- | :--- | :---: | :--- |
| 1 | `Use full commit SHA hash for this dependency` (supply chain, former hotspot) | `deploy-api-docs.yml` L34 (`peaceiris/actions-gh-pages@v4`) | High | Закріпити action за повним 40-символьним SHA коміту |
| 2 | `Omitting "--only-binary :all:" can lead to the execution of setup scripts` | `ci.yml` L24, L25, L26; `deploy-api-docs.yml` L27 | Medium (×4) | Додати `--only-binary :all:` до `pip install`; перевірити, що всі пакети мають wheel |
| 3 | `Using dependencies without locking resolved versions is security-sensitive` | `ci.yml` L24, L25, L26; `deploy-api-docs.yml` L27 | Medium (×4) | Зафіксувати версії: `pip==...`, `black/flake8/bandit/pytest` з `==`, залежності з `requirements.txt` перевести на точні версії (за можливості з `--require-hashes`) |

Рядки `ci.yml`: L24 `pip install --upgrade pip`, L25 `pip install -r src/api/requirements.txt`, L26 `pip install black flake8 bandit pytest pytest-cov`. `deploy-api-docs.yml` L27: `pip install -r requirements.txt`.

### 3.1. Зв'язок знахідок із `static-analysis.md` (Лаб 5) і `threat-model.md` (Лаб 3)

**Зв'язок із `threat-model.md` (STRIDE).** Усі 9 знахідок стосуються ланцюга постачання в CI/CD (GitHub Actions, PyPI). У моделі загроз такого компонента немає: вона описує лише межі TB1 (Інтернет ↔ FastAPI), TB2 (FastAPI ↔ SQLite) і TB3 (FastAPI ↔ SMTP). Тож Sonar виявив прогалину моделі, а не ризик, який там уже враховано.

| Знахідка Sonar | Категорія STRIDE | Яка загроза | Зв'язок із `threat-model.md` | Контрзахід |
| :--- | :--- | :--- | :--- | :--- |
| `peaceiris/actions-gh-pages@v4` без SHA (`deploy-api-docs.yml` L34), High | **Tampering** (зламаний action або підмінений тег виконає шкідливий код); **Elevation of Privilege** (workflow має `contents: write` і передає action `GITHUB_TOKEN`) | Зловмисник отримує право запису в репозиторій і публікацію на GitHub Pages | Не покрито. Найближчі рядки таблиці: Tampering і Elevation of Privilege, але лише для TB1 | Закріпити action за повним SHA |
| Немає `--only-binary :all:` (`ci.yml` L24–26, `deploy-api-docs.yml` L27), Medium ×4 | **Tampering** | Під час `pip install` може виконатися `setup.py` шкідливого пакета на CI-раннері | Не покрито | `--only-binary :all:` |
| Незафіксовані версії залежностей (ті самі рядки), Medium ×4 | **Tampering** | Нова (або підмінена) версія пакета потрапляє в збірку без перевірки | Не покрито | Точні версії, за можливості `--require-hashes` |

Висновок для моделі загроз: додати межу **TB4 (GitHub Actions ↔ зовнішні action та PyPI)** і рядок Tampering/Elevation of Privilege із цим контрзаходом. Це можна записати як окремий рядок у `threat-model.md` разом із PR рефакторингу.

**Зв'язок зі `static-analysis.md`.**
- Bandit (розділ 2.3) повідомляє 0 зауважень, і це не суперечить Sonar: Bandit сканує лише Python у `src/api` (2020 рядків, 17 файлів), а 9 Security-знахідок Sonar лежать у `.github/workflows/*.yml`, які Bandit не перевіряє. Два інструменти доповнюють один одного.
- Знахідку Sonar про передбачувану сіль у `store.py`, зафіксовану в попередньому аналізі, закрито ще в Лаб 5: `PASSWORD_SALT` тепер береться зі змінної середовища (розділ 4 і розділ 6 `static-analysis.md`, хук `detect-secrets`). У поточних 26 issues її немає.
- Ризики, які `static-analysis.md` (розділ 4) прийняв свідомо, Sonar зараз не показує: демо-токени (`master-token` та ін.) і демо-паролі в `seed.py` і `web/login.html`, а також значення солі за замовчуванням `default-insecure-salt-for-dev` у `store.py`. Вони не впливають на Security Rating, але лишаються відкритими для реального розгортання.
- `static-analysis.md` розділ 2.3 згадує, що Docker-образ запускається з `--host 0.0.0.0`; Dockerfile Bandit не сканує, тож це теж варто мати на увазі як окрему поверхню.

**Security Rating до/після рефакторингу.**

| Показник | До | Після |
| :--- | :---: | :---: |
| Security Rating | C | _заповнити_ |
| Security issues | 9 (1 High, 8 Medium) | _заповнити_ |

---

## 4. Reliability: ключові знахідки (17 issues)

| Група | К-сть | Файли | Що робимо |
| :--- | :-: | :--- | :--- |
| `Prefer Number.isNaN over isNaN` (Medium Reliability + Low Maintainability) | 10 | `admin.html` L272, L277; `app.js` L86, L104; `calendar.html` L79, L97 (×2); `create-game.html` L234, L241, L247 | Замінити на `Number.isNaN` |
| `Prefer Number.parseInt over parseInt` (Medium Reliability + Low Maintainability) | 4 | `app.js` L105, L208; `create-game.html` L189, L190 | Замінити на `Number.parseInt` |
| `lang` у `<html>` (WCAG A) | 1 | `docs/api/index.html` L2 | Додати `lang="en"`; файл статичний, не генерується |
| Порожній заголовок для screen reader | 1 | `game.html` (`<h1 id="game-title">`) | Додати запасний текст у заголовок до завантаження JS |
| `[` замість `[[` (High Reliability) | 1 | `scripts/run_mutation.sh` L10 | Замінити на `[[ ... ]]` |

Примітка про `isNaN` і `parseInt`: глобальний `isNaN("abc")` приводить аргумент до числа, а `Number.isNaN` ні. Тож заміна може змінити поведінку, якщо код передає рядки. Перед масовою заміною перевірити виклики на тип аргумента (це важливо для умови «рефакторинг не змінює поведінку»).

---

## 5. Примітки до метрик «до»

- **Technical Debt 1 д 1 год** (≈ 9 год, 1 день = 8 год) переважно від Security: 8 Medium × 1 год + High 30 хв ≈ 8,5 год. Решта ≈ 30 хв припадає на 15 зауважень Maintainability (≈ 2 хв кожне). 
- **Виключення звіту покриття** (`htmlcov/`, `coverage/`): перевірено на вкладці Code.

## 6. Метрики «після» !!!ЗАПОВНИТИ!!!

| Показник | До | Після |
| :--- | :---: | :---: |
| Reliability Rating | C | |
| Code Smells | 15 | |
| Technical Debt | 1 д 1 год | |
| **Security Rating** | **C** | |

Коментар до Security Rating «після»: _заповнити_.
Скриншоти «після»: _додати_.

## 7. Рефакторинги, нотатка «Використання ШІ», регресійне тестування, бонуси !!!ЗАПОВНИТИ!!!

### Characterization-тест перед рефакторингом (бонус)

Для `src/api/generate_openapi.py` додано тест `src/api/tests/test_generate_openapi.py`, який фіксує поточну поведінку CLI: скрипт викликає `save_openapi_spec(app)` під час запуску як `__main__`, але не викликає його під час імпорту. Тест додано до змін у цьому модулі; виробничий код у цьому PR не змінюється.

## Використання ШІ

**Інструмент:** Claude (Anthropic), чат-асистент. Агент працював із копією репозиторію з архіву й видавав зміни окремими патчами; застосовували, коммітили й ревʼюїли їх учасники команди.

### 1. Документація 
Структуру та формулювання розділів звіту, зокрема таблиці Security (розділ 3) і зв'язок зі `static-analysis.md` та `threat-model.md` (розділ 3.1), згенеровано за допомогою Claude. Цифри й назви правил команда звіряла з панеллю SonarQube Cloud (список issues, Measures); рядки `ci.yml` і `deploy-api-docs.yml` звірено з файлами репозиторію.

### 2. Рефакторинг, виконаний із ШІ-агентом
Закрито 8 зауважень Sonar шістьма окремими комітами `[REFACTOR]`:

| № | Зауваження | Файл | Що згенеровано |
| :-: | :--- | :--- | :--- |
| 1 | `Use full commit SHA hash` (Security, High) | `deploy-api-docs.yml` | `peaceiris/actions-gh-pages@v4` → повний SHA `84c30a85c19949d7eee79c4ff27748b70285e453 # v4` |
| 2 | `Omitting "--only-binary :all:"` (Security, Medium) | `deploy-api-docs.yml` | додано `--only-binary :all:` |
| 3 | те саме правило, 3 місця (Security, Medium) | `ci.yml` | додано `--only-binary :all:`; закріплено `black==25.11.0`, `flake8==7.3.0`, `bandit==1.8.6` |
| 4 | `Use '[['` (Reliability, High) | `scripts/run_mutation.sh` | `[ -n … ]` → `[[ -n … ]]` |
| 5 | немає `lang` у `<html>` (Reliability) | `docs/api/index.html` | додано `lang="en"` |
| 6 | порожній заголовок (Reliability) | `src/api/web/game.html` | у `<h1 id="game-title">` додано «Завантаження…» |
