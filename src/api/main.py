import os
import yaml
from fastapi import FastAPI
from contextlib import asynccontextmanager
from routes.games import router as games_router

def save_openapi_spec(app: FastAPI):
    openapi_schema = app.openapi()
    os.makedirs("docs/api", exist_ok=True)
    with open("docs/api/openapi-generated.yaml", "w", encoding="utf-8") as f:
        yaml.dump(openapi_schema, f, sort_keys=False, allow_unicode=True)
    print("OpenAPI spec auto-generated to docs/api/openapi-generated.yaml")

@asynccontextmanager
async def lifespan(app: FastAPI):
    save_openapi_spec(app)
    yield

app = FastAPI(
    title="NRI Organizer API", 
    version="1.0.0", 
    docs_url="/api-docs",
    lifespan=lifespan
)

app.include_router(games_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)
