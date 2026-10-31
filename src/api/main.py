import os
import runpy
from db import init_db
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles

from errors import register_error_handlers
from routes.auth import router as auth_router
from routes.games import router as games_router
from routes.rooms import router as rooms_router
from spec import install_openapi, save_openapi_spec

host = os.getenv("API_HOST", "127.0.0.1")
WEB_DIR = Path(__file__).resolve().parent / "web"


def operation_id(route: APIRoute) -> str:
    return route.name


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ініціалізуємо базу даних
    init_db()

    # Викликаємо сід-скрипт для заповнення демо-даними
    seed_script = Path(__file__).resolve().parents[2] / "scripts" / "seed.py"
    if seed_script.exists():
        try:
            runpy.run_path(str(seed_script))
        except Exception as e:
            print(f"Помилка під час сідування БД: {e}")

    save_openapi_spec(app)
    yield


app = FastAPI(
    title="NRI Organizer API",
    description=(
        "REST API організатора настільних рольових ігор: ігри, гравці та кімнати клубу. "
        "Усі відповіді — заглушки в пам'яті процесу. Для захищених операцій натисніть Authorize "
        "і введіть демо-токен: master-token, player-token або owner-token."
    ),
    version="1.0.0",
    docs_url="/api-docs",
    redoc_url="/redoc",
    # Змінено сервери для коректної роботи Swagger на Render
    servers=[
        {"url": "https://vibecoders.onrender.com", "description": "Продакшн сервер"},
        {"url": "http://localhost:3000", "description": "Локальний сервер"},
    ],
    openapi_tags=[
        {"name": "Auth", "description": "Вхід у систему"},
        {"name": "Games", "description": "Ігрові сесії та запис гравців"},
        {"name": "Rooms", "description": "Кімнати клубу"},
    ],
    generate_unique_id_function=operation_id,
    lifespan=lifespan,
)

register_error_handlers(app)
install_openapi(app)

app.include_router(auth_router)
app.include_router(games_router)
app.include_router(rooms_router)

app.mount("/app", StaticFiles(directory=str(WEB_DIR), html=True), name="web")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=os.getenv("API_HOST", "127.0.0.1"), port=3000)
