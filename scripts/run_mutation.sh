#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
cp "$ROOT"/src/api/*.py "$WORK"/
cp -r "$ROOT"/src/api/routes "$WORK"/routes
cp -r "$ROOT"/src/api/tests "$WORK"/tests
cp "$ROOT"/pytest.ini "$WORK"/pytest.ini
rm -f "$WORK"/tests/test_api.py "$WORK"/tests/test_traceability_script.py
if [ -n "$MUTATION_WITHOUT_TEST" ]; then
  python - "$WORK/tests/test_store.py" "$MUTATION_WITHOUT_TEST" <<'PY'
import re
import sys

path, name = sys.argv[1], sys.argv[2]
text = open(path, encoding="utf-8").read()
pattern = re.compile(r"(?:@pytest\.mark\.\w+(?:\([^)]*\))?\n)*def " + re.escape(name) + r"\(.*?(?=\n\n\n|\Z)", re.S)
text, count = pattern.subn("", text)
if count != 1:
    sys.exit("тест не знайдено: " + name)
open(path, "w", encoding="utf-8").write(text)
PY
fi
cat > "$WORK"/setup.cfg <<'CFG'
[mutmut]
source_paths=store.py
pytest_add_cli_args_test_selection=tests/
also_copy=
    schemas.py
    errors.py
    security.py
    spec.py
    main.py
    utils.py
    pytest.ini
    routes
    tests
CFG
cd "$WORK"
python -m mutmut run || true
python -m mutmut results
echo "Робоча папка: $WORK"
