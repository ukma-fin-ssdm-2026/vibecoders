#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
cp "$ROOT"/src/api/*.py "$WORK"/
cp -r "$ROOT"/src/api/routes "$WORK"/routes
cp -r "$ROOT"/src/api/tests "$WORK"/tests
rm -f "$WORK"/tests/test_api.py
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
    routes
    tests
CFG
cd "$WORK"
python -m mutmut run || true
python -m mutmut results
echo "Робоча папка: $WORK"
