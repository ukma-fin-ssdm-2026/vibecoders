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
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Any, Dict, List, Optional


def parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    """Безпечно розбирає рядок ISO-8601 у datetime з часовим поясом UTC."""
    if not value or not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def calculate_job_timings(run_created_at_str: str, jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Обчислює чергу і виконання на основі завдань запуску.

    - Черга: мінімум started_at завдань мінус created_at запуску.
    - Виконання: максимум completed_at завдань мінус мінімум started_at завдань.
    """
    run_created = parse_iso_datetime(run_created_at_str)
    started_times: List[datetime] = []
    completed_times: List[datetime] = []

    for job in jobs:
        st = parse_iso_datetime(job.get("started_at"))
        ct = parse_iso_datetime(job.get("completed_at"))
        if st:
            started_times.append(st)
        if ct:
            completed_times.append(ct)

    min_started = min(started_times) if started_times else None
    max_completed = max(completed_times) if completed_times else None

    queue_sec: Optional[float] = None
    exec_sec: Optional[float] = None

    if min_started and run_created:
        queue_sec = max(0.0, (min_started - run_created).total_seconds())

    if min_started and max_completed:
        exec_sec = max(0.0, (max_completed - min_started).total_seconds())

    return {
        "min_started_at": min_started.isoformat() if min_started else None,
        "max_completed_at": max_completed.isoformat() if max_completed else None,
        "queue_seconds": queue_sec,
        "execution_seconds": exec_sec,
        "queue_minutes": round(queue_sec / 60.0, 1) if queue_sec is not None else None,
        "execution_minutes": round(exec_sec / 60.0, 1) if exec_sec is not None else None,
    }


def classify_run_status(conclusion: Optional[str]) -> str:
    """Класифікує результат запуску: green (успіх), red (збій), cancelled або skipped."""
    c = (conclusion or "").lower().strip()
    if c == "success":
        return "green"
    if c in ("failure", "timed_out"):
        return "red"
    if c == "cancelled":
        return "cancelled"
    if c == "skipped":
        return "skipped"
    return c or "unknown"


def extract_commit_author_date(commit_obj: Dict[str, Any]) -> Optional[datetime]:
    """Витягує дату автора (commit.author.date) із об'єкта коміту GitHub API."""
    commit_data = commit_obj.get("commit")
    if isinstance(commit_data, dict):
        author = commit_data.get("author")
        if isinstance(author, dict):
            dt = parse_iso_datetime(author.get("date"))
            if dt:
                return dt
        committer = commit_data.get("committer")
        if isinstance(committer, dict):
            dt = parse_iso_datetime(committer.get("date"))
            if dt:
                return dt
    return None


def find_earliest_commit_date(
    commits: List[Dict[str, Any]], fallback_dt: Optional[datetime] = None
) -> Optional[datetime]:
    """Знаходить найранішу дату commit.author.date серед списку комітів PR."""
    dates: List[datetime] = []
    for c in commits:
        dt = extract_commit_author_date(c)
        if dt:
            dates.append(dt)
    if dates:
        return min(dates)
    return fallback_dt


def calculate_lead_time_seconds(
    first_commit_dt: Optional[datetime], completion_dt: Optional[datetime]
) -> Optional[float]:
    """Обчислює час виконання змін у секундах: завершення останнього завдання мінус перший коміт."""
    if not first_commit_dt or not completion_dt:
        return None
    delta = (completion_dt - first_commit_dt).total_seconds()
    return max(0.0, delta)


def fetch_pull_requests_for_commit(repo: str, sha: str) -> List[Dict[str, Any]]:
    """Отримує список PR, пов'язаних із комітом."""
    endpoint = f"repos/{repo}/commits/{sha}/pulls"
    try:
        raw = run_gh_cmd(["api", "-X", "GET", endpoint])
        if not raw.strip():
            return []
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def fetch_pull_request_commits(repo: str, pull_number: int) -> List[Dict[str, Any]]:
    """Отримує всі коміти PR із пагінацією."""
    endpoint = f"repos/{repo}/pulls/{pull_number}/commits"
    try:
        raw = run_gh_cmd(["api", "--paginate", "-X", "GET", endpoint])
        return parse_json_stream(raw)
    except Exception:
        return []


def fetch_commit_details(repo: str, sha: str) -> Optional[Dict[str, Any]]:
    """Отримує дані про окремий коміт."""
    endpoint = f"repos/{repo}/commits/{sha}"
    try:
        raw = run_gh_cmd(["api", "-X", "GET", endpoint])
        if raw.strip():
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return None


def resolve_commit_pr_info(repo: str, sha: str, completion_dt: Optional[datetime]) -> Dict[str, Any]:
    """Визначає інформацію про PR, перший коміт і час виконання змін."""
    prs = fetch_pull_requests_for_commit(repo, sha)
    pr_label = "—"
    first_commit_dt: Optional[datetime] = None

    if prs:
        pr = prs[0]
        pr_number = pr.get("number")
        if pr_number:
            pr_label = f"#{pr_number}"
            pr_commits = fetch_pull_request_commits(repo, pr_number)
            first_commit_dt = find_earliest_commit_date(pr_commits)

    if not first_commit_dt:
        commit_obj = fetch_commit_details(repo, sha)
        if commit_obj:
            first_commit_dt = extract_commit_author_date(commit_obj)

    lead_sec = calculate_lead_time_seconds(first_commit_dt, completion_dt)
    lead_min = round(lead_sec / 60.0, 1) if lead_sec is not None else None

    return {
        "pr_label": pr_label,
        "first_commit_dt": first_commit_dt,
        "lead_time_seconds": lead_sec,
        "lead_time_minutes": lead_min,
    }


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
