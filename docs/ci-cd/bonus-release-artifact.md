# Бонус: артефакт випуску з кожного зеленого запуску на main

## Що робить workflow

Після успішного CI на `main` workflow збирає Docker-образ застосунку й публікує його в GitHub Container Registry (GHCR). Окремий job `publish-container` залежить від `validate-and-test` і `reliability-tests`, тому образ не публікується, якщо будь-який із цих jobs не завершився успішно. Job запускається лише для push у `main`, не для pull request чи інших гілок.

## Як це працює

1. Два перевірочні jobs виконують основний і reliability-набір тестів.
2. Якщо обидва успішні на push у `main`, `publish-container` запускається на одному Linux runner.
3. Docker Buildx збирає образ із наявного кореневого `Dockerfile`. Він базується на Python slim, встановлює залежності з `src/api/requirements.txt`, копіює API та запускає його через Uvicorn на порту `$PORT` (за замовчуванням 8000).
4. Workflow автентифікується до `ghcr.io` через `GITHUB_TOKEN` і публікує образ з тегом повного SHA коміту. Для прискорення наступних збірок використовуються кешовані Docker-шари.
5. Публікація має лише job-level дозволи `contents: read` і `packages: write`. Тег `latest` не створюється.

## Завантажити образ

Підставити повний SHA зеленого коміту на `main`:

```sh
docker pull ghcr.io/ukma-fin-ssdm-2026/vibecoders:<SHA-коміту>
```

## Посилання та фактичний стан

- Успішний запуск `CI Pipeline` на `main` із зеленим `publish-container` (після PR #239): https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/runs/44510454012 (job: https://github.com/ukma-fin-ssdm-2026/vibecoders/actions/runs/44510454012/job/135513897895).
- Сторінка пакета `vibecoders` у GitHub Packages (приватний пакет, видимий у межах організації): https://github.com/ukma-fin-ssdm-2026/vibecoders/pkgs/container/vibecoders. Образ опубліковано з тегом `f03eb2b97b08163c499dba64d7e3124f52110571` (повний SHA коміту).

## Перевірити після злиття

- Після зеленого запуску на `main` пакет з'явився у вкладці **Packages** репозиторію.
- Перевірити видимість пакета та доступність для учасників команди.
- У тегах пакета є саме повний SHA коміту з `github.sha`; зайвий тег `latest` не створено.
- При невдалому `validate-and-test` або `reliability-tests` job публікації не запускається.
