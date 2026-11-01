FROM python:3.13-slim

RUN addgroup --system appgroup && adduser --system --group appuser
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src/api

# Правильний шлях до requirements
COPY src/api/requirements.txt .
RUN echo "pip install --no-cache-dir --only-binary :all: -r requirements.txt" | sh

COPY src/ /app/src/
COPY scripts/ /app/scripts/

RUN chown -R appuser:appgroup /app
USER appuser
EXPOSE 8000

# Використання $PORT та 0.0.0.0
CMD ["sh", "-c", "uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]