"""Формує звіт про нестабільні тести з JUnit XML."""

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
TestId = Tuple[str, str]
TestResults = Dict[TestId, List[Optional[str]]]


def resolve_reports_dir(path: str) -> Optional[Path]:
    """Повертає каталог звітів лише тоді, коли він лежить у корені репозиторію."""
    try:
        root = ROOT.resolve()
        requested = Path(path)
        candidate = requested if requested.is_absolute() else root / requested
        directory = candidate.resolve()
        if not directory.is_relative_to(root) or not directory.is_dir():
            return None
        return directory
    except (OSError, RuntimeError, ValueError):
        return None


def find_junit_files(directory: Path) -> List[Path]:
    """Знаходить лише безпосередні файли run*.xml без переходу за межі каталогу."""
    files = []
    for candidate in directory.glob("run*.xml"):
        try:
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError):
            print(f"Попередження: не вдалося перевірити {candidate.name}", file=sys.stderr)
            continue
        if resolved.parent != directory or not resolved.is_file():
            print(f"Попередження: пропущено недопустимий файл {candidate.name}", file=sys.stderr)
            continue
        files.append(resolved)
    return sorted(files, key=_run_file_sort_key)


def _run_file_sort_key(path: Path) -> Tuple[int, object]:
    """Сортує runN.xml за номером повтору, інші run*.xml — за назвою."""
    suffix = path.stem[3:]
    if suffix.isdigit():
        return 0, int(suffix)
    return 1, path.name


def parse_junit_file(path: Path) -> Dict[TestId, str]:
    """Читає результат кожного testcase з одного JUnit XML."""
    root = ET.parse(path).getroot()
    results = {}
    for testcase in root.iter("testcase"):
        test_id = (testcase.attrib.get("classname", ""), testcase.attrib.get("name", "<без назви>"))
        if testcase.find("failure") is not None or testcase.find("error") is not None:
            result = "failed"
        elif testcase.find("skipped") is not None:
            result = "skipped"
        else:
            result = "passed"
        results[test_id] = result
    return results


def collect_test_results(files: List[Path]) -> TestResults:
    """Об'єднує результати повторів, позначаючи відсутні тести окремо."""
    results = {}
    for repeat_index, path in enumerate(files):
        run_results = parse_junit_file(path)
        for test_id in run_results:
            if test_id not in results:
                results[test_id] = [None] * repeat_index
        for test_id, outcomes in results.items():
            outcomes.append(run_results.get(test_id))
    return results


def _display_test(test_id: TestId) -> str:
    classname, name = test_id
    return f"{classname}::{name}" if classname else name


def _markdown_cell(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("`", "\\`").replace("\n", " ")


def render_report(results: TestResults, repeats: int) -> str:
    """Формує зведення, нестабільні тести та стабільні збої."""
    flaky = [(test_id, outcomes) for test_id, outcomes in sorted(results.items()) if len(set(outcomes)) > 1]
    stable_failures = [
        test_id
        for test_id, outcomes in sorted(results.items())
        if len(outcomes) == repeats and all(outcome == "failed" for outcome in outcomes)
    ]
    lines = [
        "# Звіт про нестабільні тести",
        "",
        f"- Повторів: {repeats}",
        f"- Унікальних тестів: {len(results)}",
        "",
        "## Нестабільні тести",
        "",
    ]
    if flaky:
        lines.extend(
            [
                "| Тест | Результати по повторах |",
                "|---|---|",
            ]
        )
        for test_id, outcomes in flaky:
            rendered = ", ".join(
                f"{index}: {outcome if outcome is not None else 'не запускався'}"
                for index, outcome in enumerate(outcomes, 1)
            )
            lines.append(f"| `{_markdown_cell(_display_test(test_id))}` | {rendered} |")
    else:
        lines.append("Нестабільних тестів не виявлено")

    lines.extend(["", "## Стабільні збої", ""])
    if stable_failures:
        lines.extend(
            f"- `{_markdown_cell(_display_test(test_id))}` — failed у всіх повторах" for test_id in stable_failures
        )
    else:
        lines.append("Стабільних збоїв не виявлено.")
    return "\n".join(lines) + "\n"


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Розбирає аргументи командного рядка."""
    parser = argparse.ArgumentParser(description="Звіт про нестабільні тести з JUnit XML.")
    parser.add_argument("reports_dir", nargs="?", default="reports", help="Каталог із файлами run*.xml.")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    """Запускає формування звіту; нестабільні тести не роблять код виходу ненульовим."""
    args = parse_args(argv)
    directory = resolve_reports_dir(args.reports_dir)
    if directory is None:
        print("Помилка: каталог звітів недопустимий або поза коренем репозиторію.", file=sys.stderr)
        return 1

    files = find_junit_files(directory)
    if not files:
        print("Помилка: JUnit XML-файлів run*.xml не знайдено.", file=sys.stderr)
        return 1
    try:
        results = collect_test_results(files)
    except (ET.ParseError, OSError, ValueError) as exc:
        print(f"Помилка читання JUnit XML: {exc}", file=sys.stderr)
        return 1

    print(render_report(results, len(files)), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
