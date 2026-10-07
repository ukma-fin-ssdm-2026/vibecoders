from pathlib import Path

import yaml
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

SPEC_PATH = Path(__file__).resolve().parents[2] / "docs" / "api" / "openapi-generated.yaml"


def build_openapi(app: FastAPI) -> dict:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
        servers=app.servers,
    )
    for path_item in schema["paths"].values():
        for operation in path_item.values():
            operation["responses"].pop("422", None)
    components = schema.get("components", {}).get("schemas", {})
    components.pop("HTTPValidationError", None)
    components.pop("ValidationError", None)
    app.openapi_schema = schema
    return schema


def install_openapi(app: FastAPI) -> None:
    app.openapi = lambda: build_openapi(app)


def save_openapi_spec(app: FastAPI) -> Path:
    SPEC_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SPEC_PATH, "w", encoding="utf-8") as file:
        yaml.safe_dump(app.openapi(), file, sort_keys=False, allow_unicode=True)
    print(f"OpenAPI-специфікацію згенеровано з коду: {SPEC_PATH}")
    return SPEC_PATH
