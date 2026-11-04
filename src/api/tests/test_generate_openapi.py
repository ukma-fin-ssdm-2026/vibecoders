import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.technical
@pytest.mark.parametrize(
    ("run_name", "should_save"),
    [("__main__", True), ("generate_openapi", False)],
)
def test_generate_openapi_saves_app_only_when_run_as_script(monkeypatch, run_name, should_save):
    app = object()
    saved_apps = []
    monkeypatch.setitem(sys.modules, "main", SimpleNamespace(app=app))
    monkeypatch.setitem(
        sys.modules,
        "spec",
        SimpleNamespace(save_openapi_spec=saved_apps.append),
    )

    script = Path(__file__).resolve().parents[1] / "generate_openapi.py"
    runpy.run_path(str(script), run_name=run_name)

    assert saved_apps == ([app] if should_save else [])
