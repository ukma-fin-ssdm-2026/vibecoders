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


def calculate_mean(values: List[float]) -> Optional[float]:
    """Обчислює середнє арифметичне списку чисел."""
    if not values:
        return None
    return sum(values) / len(values)


def calculate_median(values: List[float]) -> Optional[float]:
    """Обчислює медіану списку чисел."""
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return float(s[mid])
    return (s[mid - 1] + s[mid]) / 2.0


def calculate_deployment_frequency(
    green_runs: List[Dict[str, Any]],
    since_dt: datetime,
    until_dt: datetime,
    tz: tzinfo,
) -> Dict[str, Any]:
    """Обчислює частоту розгортань: зелені запуски на тиждень і на активний день."""
    total_green = len(green_runs)
    period_seconds = max(86400.0, (until_dt - since_dt).total_seconds())
    weeks = period_seconds / (7.0 * 86400.0)

    active_days = set()
    for r in green_runs:
        comp_dt = r.get("completed_at_dt")
        if comp_dt:
            active_days.add(comp_dt.astimezone(tz).date())

    active_days_count = len(active_days)
    per_week = total_green / max(weeks, 1.0 / 7.0)
    per_active_day = (total_green / active_days_count) if active_days_count > 0 else 0.0

    return {
        "total_green": total_green,
        "weeks": round(weeks, 1),
        "per_week": round(per_week, 1),
        "active_days_count": active_days_count,
        "per_active_day": round(per_active_day, 1),
    }


def calculate_lead_time_metrics(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Обчислює статистику часу виконання змін та частку черги і виконання."""
    lead_times = [r["lead_time_minutes"] for r in runs if r.get("lead_time_minutes") is not None]
    mean_lead = calculate_mean(lead_times)
    median_lead = calculate_median(lead_times)

    valid_qe = [r for r in runs if r.get("queue_seconds") is not None and r.get("execution_seconds") is not None]
    total_q = sum(r["queue_seconds"] for r in valid_qe)
    total_e = sum(r["execution_seconds"] for r in valid_qe)
    sum_qe = total_q + total_e

    q_share = (total_q / sum_qe * 100.0) if sum_qe > 0 else 0.0
    e_share = (total_e / sum_qe * 100.0) if sum_qe > 0 else 0.0

    return {
        "mean_minutes": round(mean_lead, 1) if mean_lead is not None else None,
        "median_minutes": round(median_lead, 1) if median_lead is not None else None,
        "queue_share_pct": round(q_share, 1),
        "execution_share_pct": round(e_share, 1),
    }


def calculate_change_failure_rate(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Обчислює частоту збоїв: червоні / усі завершені × 100%."""
    total_completed = len(runs)
    red_count = sum(1 for r in runs if r.get("classified_status") == "red")
    green_count = sum(1 for r in runs if r.get("classified_status") == "green")
    cancelled_count = sum(1 for r in runs if r.get("classified_status") == "cancelled")
    skipped_count = sum(1 for r in runs if r.get("classified_status") == "skipped")

    rate = (red_count / total_completed * 100.0) if total_completed > 0 else 0.0
    return {
        "total_completed": total_completed,
        "green_count": green_count,
        "red_count": red_count,
        "cancelled_count": cancelled_count,
        "skipped_count": skipped_count,
        "failure_rate_pct": round(rate, 1),
    }


def calculate_time_to_restore(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Обчислює час відновлення: від червоного запуску до наступного зеленого."""
    sorted_runs = sorted(
        runs,
        key=lambda r: r.get("completed_at_dt") or r.get("created_at_dt") or datetime.min.replace(tzinfo=timezone.utc),
    )

    restore_times_min: List[float] = []
    red_count = sum(1 for r in sorted_runs if r.get("classified_status") == "red")

    for i, r in enumerate(sorted_runs):
        if r.get("classified_status") == "red":
            red_comp = r.get("completed_at_dt") or r.get("created_at_dt")
            for next_r in sorted_runs[i + 1 :]:
                if next_r.get("classified_status") == "green":
                    green_comp = next_r.get("completed_at_dt") or next_r.get("created_at_dt")
                    if red_comp and green_comp:
                        diff_sec = max(0.0, (green_comp - red_comp).total_seconds())
                        restore_times_min.append(diff_sec / 60.0)
                    break

    if red_count == 0:
        return {
            "has_red": False,
            "mean_minutes": None,
            "median_minutes": None,
            "status_label": "н/д (червоних запусків немає)",
        }

    if not restore_times_min:
        return {
            "has_red": True,
            "mean_minutes": None,
            "median_minutes": None,
            "status_label": "н/д (після збою немає зеленого запуску)",
        }

    mean_rest = calculate_mean(restore_times_min)
    med_rest = calculate_median(restore_times_min)
    return {
        "has_red": True,
        "mean_minutes": round(mean_rest, 1) if mean_rest is not None else None,
        "median_minutes": round(med_rest, 1) if med_rest is not None else None,
        "status_label": f"середнє: {round(mean_rest, 1)} хв, медіана: {round(med_rest, 1)} хв",
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
