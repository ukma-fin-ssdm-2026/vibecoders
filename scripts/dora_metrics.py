"""Скрипт збору та розрахунку метрик DORA на основі запусків GitHub Actions.

Бонусне завдання до Лабораторної роботи №10.
Скрипт збирає дані про запуски робочого процесу CI Pipeline (ci.yml)
через GitHub CLI (`gh api`), розраховує час у черзі, тривалість виконання,
час першого коміту в PR і чотири ключові метрики DORA (2025).
"""

import argparse
import json
import subprocess
import sys
from datetime import timedelta, timezone, tzinfo
from typing import Any, Dict, List, Optional


def run_gh_cmd(args: List[str]) -> str:
    """Виконує команду GitHub CLI (gh) і повертає stdout у вигляді рядка."""
    cmd = ["gh"] + args
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        err_msg = result.stderr.strip() or f"Команда {' '.join(cmd)} завершилася з кодом {result.returncode}"
        raise RuntimeError(f"Помилка виклику gh: {err_msg}")
    return result.stdout


def detect_repo(explicit_repo: Optional[str] = None) -> str:
    """Визначає репозиторій у форматі owner/repo."""
    if explicit_repo:
        return explicit_repo.strip()
    try:
        out = run_gh_cmd(["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]).strip()
        if out:
            return out
    except Exception:
        pass
    return "ukma-fin-ssdm-2026/vibecoders"


def parse_json_stream(text: str) -> List[Dict[str, Any]]:
    """Розбирає потік JSON-об'єктів (JSON lines або послідовні об'єкти від --jq)."""
    text = text.strip()
    if not text:
        return []
    items: List[Dict[str, Any]] = []
    decoder = json.JSONDecoder()
    idx = 0
    while idx < len(text):
        while idx < len(text) and text[idx].isspace():
            idx += 1
        if idx >= len(text):
            break
        obj, end = decoder.raw_decode(text, idx)
        if isinstance(obj, list):
            items.extend(obj)
        elif isinstance(obj, dict):
            items.append(obj)
        idx = end
    return items


def fetch_workflow_runs(repo: str, since: str) -> List[Dict[str, Any]]:
    """Отримує завершені запуски CI Pipeline для гілки main від вказаної дати."""
    endpoint = f"repos/{repo}/actions/workflows/ci.yml/runs"
    args = [
        "api",
        "--paginate",
        "-X",
        "GET",
        endpoint,
        "-f",
        "branch=main",
        "-f",
        "event=push",
        "-f",
        "status=completed",
        "-f",
        f"created=>={since}",
        "--jq",
        ".workflow_runs[]",
    ]
    raw = run_gh_cmd(args)
    return parse_json_stream(raw)


def fetch_run_jobs(repo: str, run_id: int) -> List[Dict[str, Any]]:
    """Отримує завдання (jobs) конкретного запуску workflow."""
    endpoint = f"repos/{repo}/actions/runs/{run_id}/jobs?per_page=100"
    args = ["api", "-X", "GET", endpoint]
    raw = run_gh_cmd(args)
    if not raw.strip():
        return []
    data = json.loads(raw)
    jobs = data.get("jobs", [])
    if isinstance(jobs, list):
        return jobs
    return []


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Розбір аргументів командного рядка."""
    parser = argparse.ArgumentParser(
        description="Розрахунок метрик DORA на основі історії запусків GitHub Actions (CI Pipeline)."
    )
    parser.add_argument(
        "--since",
        required=True,
        help="Початкова дата аналізу у форматі YYYY-MM-DD (включно).",
    )
    parser.add_argument(
        "--until",
        default=None,
        help="Кінцева дата аналізу у форматі YYYY-MM-DD (опціонально).",
    )
    parser.add_argument(
        "--out",
        default="docs/ci-cd/dora-auto.md",
        help="Шлях для збереження Markdown-звіту (за замовчуванням docs/ci-cd/dora-auto.md).",
    )
    parser.add_argument(
        "--export-json",
        default=None,
        help="Шлях для експорту зібраних знеособлених даних у форматі JSON.",
    )
    parser.add_argument(
        "--utc-offset-hours",
        type=float,
        default=2.0,
        help="Зміщення часового поясу в годинах від UTC (за замовчуванням 2.0 для Києва UTC+2).",
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="Репозиторій у форматі owner/repo (якщо не вказано, визначається автоматично).",
    )
    return parser.parse_args(args)


def get_tz(offset_hours: float) -> tzinfo:
    """Повертає часовий пояс із заданим зміщенням у годинах від UTC."""
    return timezone(timedelta(hours=offset_hours))


def format_tz_label(offset_hours: float) -> str:
    """Форматує підпис часового поясу для звітів."""
    sign = "+" if offset_hours >= 0 else "-"
    val = abs(offset_hours)
    if val.is_integer():
        return f"UTC{sign}{int(val)}"
    return f"UTC{sign}{val:.1f}"


def main(argv: Optional[List[str]] = None) -> int:
    """Точка входу CLI."""
    args = parse_args(argv)
    tz_label = format_tz_label(args.utc_offset_hours)
    print(f"DORA metrics: since={args.since}, until={args.until}, tz={tz_label}, out={args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
