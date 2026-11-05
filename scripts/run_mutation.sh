#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
cp "$ROOT"/src/api/*.py "$WORK"/
cp -r "$ROOT"/src/api/routes "$WORK"/routes
cp -r "$ROOT"/src/api/web "$WORK"/web
cp -r "$ROOT"/src/api/tests "$WORK"/tests
cp "$ROOT"/pytest.ini "$WORK"/pytest.ini
rm -f "$WORK"/tests/test_api.py "$WORK"/tests/test_traceability_script.py \
  "$WORK"/tests/test_generate_openapi.py "$WORK"/tests/test_web_app_js.py
python - "$WORK/tests/test_store.py" "$WORK/tests/test_quality_goals.py" "${MUTATION_WITHOUT_TEST:-}" <<'PY'
import re
import sys

tests_to_remove = [
    (sys.argv[2], "test_committed_openapi_yaml_matches_spec_generated_from_code"),
]
if sys.argv[3]:
    tests_to_remove.append((sys.argv[1], sys.argv[3]))

for path, name in tests_to_remove:
    pattern = re.compile(
        r"(?:@pytest\.mark\.\w+(?:\([^)]*\))?\n)*def " + re.escape(name) + r"\(.*?(?=\n\n\n|\Z)",
        re.S,
    )
    with open(path, encoding="utf-8") as file:
        text = file.read()
    text, count = pattern.subn("", text)
    if count != 1:
        sys.exit("тест не знайдено: " + name)
    with open(path, "w", encoding="utf-8") as file:
        file.write(text)
PY
cat > "$WORK"/setup.cfg <<'CFG'
[mutmut]
source_paths=store.py
pytest_add_cli_args_test_selection=tests/
also_copy=
    schemas.py
    errors.py
    security.py
    spec.py
    db.py
    models.py
    seed.py
    notifications.py
    main.py
    utils.py
    pytest.ini
    routes
    web
    tests
CFG
cd "$WORK"
python -m mutmut run
python -m mutmut results --all=true
echo "Робоча папка: $WORK"
