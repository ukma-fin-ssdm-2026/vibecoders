import pytest
import yaml
from fastapi import FastAPI

import spec
from main import app


@pytest.mark.technical
def test_build_openapi_removes_default_validation_schemas():
    schema = spec.build_openapi(FastAPI(title="Demo", version="0.1"))
    for path_item in schema["paths"].values():
        for operation in path_item.values():
            assert "422" not in operation["responses"]
    components = schema.get("components", {}).get("schemas", {})
    assert "HTTPValidationError" not in components
    assert "ValidationError" not in components


@pytest.mark.technical
def test_build_openapi_is_cached_on_app():
    demo = FastAPI(title="Demo", version="0.1")
    assert spec.build_openapi(demo) is spec.build_openapi(demo)


@pytest.mark.technical
def test_main_app_spec_documents_all_routers():
    paths = spec.build_openapi(app)["paths"]
    assert "/api/v1/games" in paths
    assert "/api/v1/rooms/{room_id}/bookings" in paths
    assert "/api/v1/auth/login" in paths


@pytest.mark.technical
def test_operation_ids_equal_function_names():
    operation = spec.build_openapi(app)["paths"]["/api/v1/auth/login"]["post"]
    assert operation["operationId"] == "login"


@pytest.mark.technical
def test_save_openapi_spec_writes_yaml_to_stubbed_path(tmp_path, monkeypatch, capsys):
    target = tmp_path / "nested" / "openapi.yaml"
    monkeypatch.setattr(spec, "SPEC_PATH", target)
    result = spec.save_openapi_spec(app)
    assert result == target
    loaded = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert loaded["info"]["title"] == "NRI Organizer API"
    assert loaded["servers"][0]["url"] == "https://vibecoders.onrender.com"  # Оновлено для розгортання
    assert "OpenAPI" in capsys.readouterr().out


@pytest.mark.technical
def test_openapi_endpoint_serves_installed_schema(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["version"] == "1.0.0"


@pytest.mark.technical
def test_every_operation_has_summary_description_and_documented_4xx():
    for path, path_item in app.openapi()["paths"].items():
        for method, operation in path_item.items():
            where = f"{method.upper()} {path}"
            assert operation.get("summary"), f"{where}: немає summary"
            assert operation.get("description"), f"{where}: немає description"
            assert any(code.startswith("4") for code in operation["responses"]), f"{where}: немає описаних 4xx"
