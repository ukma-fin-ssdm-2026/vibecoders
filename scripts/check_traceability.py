import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RTM_PATH = ROOT / "docs" / "requirements" / "rtm.md"
TESTS_DIR = ROOT / "src" / "api" / "tests"

REQUIREMENT_ID = re.compile(r"^(US|FR|SEC|PERF|REL|USAB|MAINT)-\d{3}$")

DEFERRED = {
    "REL-003": "доступність залежить від інфраструктури",
    "USAB-001": "потрібні UI і тестова група",
    "MAINT-001": "кімнати зафіксовані в store.py",
}


def read_requirements(rtm_path):
    ids = []
    for line in Path(rtm_path).read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        first_cell = line.split("|")[1].strip()
        if REQUIREMENT_ID.match(first_cell):
            ids.append(first_cell)
    return ids


def mark_name(node):
    if isinstance(node, ast.Call):
        node = node.func
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "mark"
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "pytest"
    ):
        return node.attr
    return None


def read_tests(tests_dir):
    tests = {}
    for path in sorted(Path(tests_dir).glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
                continue
            requirements = []
            technical = False
            for decorator in node.decorator_list:
                name = mark_name(decorator)
                if name == "requirement" and isinstance(decorator, ast.Call):
                    requirements.extend(arg.value for arg in decorator.args if isinstance(arg, ast.Constant))
                elif name == "technical":
                    technical = True
            tests[f"{path.name}::{node.name}"] = (requirements, technical)
    return tests


def check(rtm_path, tests_dir):
    known = read_requirements(rtm_path)
    tests = read_tests(tests_dir)
    errors = []
    coverage = {req: [] for req in known}
    for test_id, (requirements, technical) in tests.items():
        if not requirements and not technical:
            errors.append(f"тест без вимоги: {test_id}")
        if requirements and technical:
            errors.append(f"тест позначено і requirement, і technical: {test_id}")
        for req in requirements:
            if req in coverage:
                coverage[req].append(test_id)
            else:
                errors.append(f"тест {test_id} посилається на вимогу, якої немає в rtm.md: {req}")
    for req, covered_by in coverage.items():
        if not covered_by and req not in DEFERRED:
            errors.append(f"вимога без жодного тесту: {req}")
        if covered_by and req in DEFERRED:
            errors.append(f"вимога {req} відкладена, але має тести: приберіть її з DEFERRED")
    return errors, coverage, tests


def main():
    errors, coverage, tests = check(RTM_PATH, TESTS_DIR)
    for req, covered_by in coverage.items():
        status = f"відкладено ({DEFERRED[req]})" if req in DEFERRED and not covered_by else f"тестів: {len(covered_by)}"
        print(f"{req}: {status}")
    technical_count = sum(1 for _, technical in tests.values() if technical)
    print(f"Усього тестів: {len(tests)}, технічних: {technical_count}")
    if errors:
        print("\nПроблеми простежуваності:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("Простежуваність у порядку")
    return 0


if __name__ == "__main__":
    sys.exit(main())
