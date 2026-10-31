import os
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
    servers=[{"url": "http://localhost:3000", "description": "Локальний сервер"}],
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
