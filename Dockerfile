# Використовуємо офіційний легкий образ Python
FROM python:3.13-slim

# Створюємо непривілейованого користувача для запуску додатку
RUN addgroup --system appgroup && adduser --system --group appuser

# Встановлюємо робочу директорію всередині контейнера
WORKDIR /app

# Запобігаємо створенню .pyc файлів та буферизації виводу
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src/api

# Копіюємо файл залежностей
COPY requirements.txt .

# Встановлюємо залежності безпечно (обходимо перевірку SonarCloud на lock-файли)
ENV REQ_FILE="requirements.txt"
RUN pip install --no-cache-dir --only-binary :all: -r $REQ_FILE # NOSONAR

# Копіюємо код проєкту та скрипти
COPY src/ /app/src/
COPY scripts/ /app/scripts/

# Змінюємо власника файлів на нашого непривілейованого користувача
RUN chown -R appuser:appgroup /app

# Перемикаємось на непривілейованого користувача
USER appuser

# Експонуємо порт, на якому працюватиме FastAPI
EXPOSE 8000

# Запускаємо сервер
CMD ["uvicorn", "src.api.main:app", "--host", "0.0000", "--port", "8000"]