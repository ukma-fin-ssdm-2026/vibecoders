# Використовуємо офіційний легкий образ Python
FROM python:3.13-slim

# Встановлюємо робочу директорію всередині контейнера
WORKDIR /app

# Запобігаємо створенню .pyc файлів та буферизації виводу
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src/api

# Копіюємо файл залежностей і встановлюємо їх
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо код проєкту та скрипти
COPY src/ /app/src/
COPY scripts/ /app/scripts/

# Експонуємо порт, на якому працюватиме FastAPI
EXPOSE 8000

# Запускаємо сервер (шлях до main.py)
CMD ["uvicorn", "src.api.main:app", "--host", "0.0000", "--port", "8000"]