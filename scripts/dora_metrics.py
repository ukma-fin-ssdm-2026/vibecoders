"""Скрипт збору та розрахунку метрик DORA на основі запусків GitHub Actions.

Бонусне завдання до Лабораторної роботи №10.
Скрипт збирає дані про запуски робочого процесу CI Pipeline (ci.yml)
через GitHub CLI (`gh api`), розраховує час у черзі, тривалість виконання,
час першого коміту в PR і чотири ключові метрики DORA (2025).
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Any, Dict, List, Optional, Tuple


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
        warn(f"неочікуваний формат відповіді PR для коміту {sha[:7]}")
    except Exception as exc:
        warn(f"не вдалося отримати PR для коміту {sha[:7]}: {exc}")
    return []


def fetch_pull_request_commits(repo: str, pull_number: int) -> List[Dict[str, Any]]:
    """Отримує всі коміти PR із пагінацією."""
    endpoint = f"repos/{repo}/pulls/{pull_number}/commits"
    try:
        raw = run_gh_cmd(["api", "--paginate", "-X", "GET", endpoint])
        return parse_json_stream(raw)
    except Exception as exc:
        warn(f"не вдалося отримати коміти PR #{pull_number}: {exc}")
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
            warn(f"неочікуваний формат відповіді коміту {sha[:7]}")
    except Exception as exc:
        warn(f"не вдалося отримати коміт {sha[:7]}: {exc}")
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
    """Обчислює статистику часу виконання змін та частку черги і виконання.

    Частки рахуються двома способами: у часі CI (черга + виконання) і в часі виконання змін
    (від першого коміту до завершення запуску).
    """
    lead_times = [r["lead_time_minutes"] for r in runs if r.get("lead_time_minutes") is not None]
    mean_lead = calculate_mean(lead_times)
    median_lead = calculate_median(lead_times)

    valid_qe = [r for r in runs if r.get("queue_seconds") is not None and r.get("execution_seconds") is not None]
    total_q = sum(r["queue_seconds"] for r in valid_qe)
    total_e = sum(r["execution_seconds"] for r in valid_qe)
    sum_qe = total_q + total_e

    q_share = (total_q / sum_qe * 100.0) if sum_qe > 0 else 0.0
    e_share = (total_e / sum_qe * 100.0) if sum_qe > 0 else 0.0

    valid_lead = [r for r in valid_qe if r.get("lead_time_seconds")]
    total_lead = sum(r["lead_time_seconds"] for r in valid_lead)
    lead_q = sum(r["queue_seconds"] for r in valid_lead)
    lead_e = sum(r["execution_seconds"] for r in valid_lead)
    q_of_lead = (lead_q / total_lead * 100.0) if total_lead > 0 else 0.0
    e_of_lead = (lead_e / total_lead * 100.0) if total_lead > 0 else 0.0
    other_of_lead = max(0.0, 100.0 - q_of_lead - e_of_lead) if total_lead > 0 else 0.0

    return {
        "mean_minutes": round(mean_lead, 1) if mean_lead is not None else None,
        "median_minutes": round(median_lead, 1) if median_lead is not None else None,
        "queue_share_pct": round(q_share, 1),
        "execution_share_pct": round(e_share, 1),
        "queue_of_lead_pct": round(q_of_lead, 1),
        "execution_of_lead_pct": round(e_of_lead, 1),
        "other_of_lead_pct": round(other_of_lead, 1),
    }


def calculate_change_failure_rate(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Обчислює частоту збоїв: червоні / (зелені + червоні) × 100%. Cancelled і skipped не рахуються."""
    red_count = sum(1 for r in runs if r.get("classified_status") == "red")
    green_count = sum(1 for r in runs if r.get("classified_status") == "green")
    cancelled_count = sum(1 for r in runs if r.get("classified_status") == "cancelled")
    skipped_count = sum(1 for r in runs if r.get("classified_status") == "skipped")
    total_completed = green_count + red_count

    rate = (red_count / total_completed * 100.0) if total_completed > 0 else 0.0
    return {
        "total_runs": len(runs),
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


def classify_lead_time_dora2025(minutes: Optional[float]) -> str:
    """Визначає категорію DORA 2025 для часу виконання змін.

    Категорії:
      <1 год (9,4%) · <1 доби (24,4%) · доба–тиждень (56,4%) · тиждень–місяць (84,7%).
    """
    if minutes is None:
        return "н/д"
    if minutes < 60.0:
        return "<1 год (9,4% опитаних)"
    if minutes < 24.0 * 60.0:
        return "<1 доби (24,4% опитаних)"
    if minutes < 7.0 * 24.0 * 60.0:
        return "доба–тиждень (56,4% опитаних)"
    if minutes < 30.0 * 24.0 * 60.0:
        return "тиждень–місяць (84,7% опитаних)"
    return ">1 місяця"


def classify_failure_rate_dora2025(rate_pct: float) -> str:
    """Визначає категорію DORA 2025 для частоти збоїв розгортань.

    Категорії:
      0–2% (8,5%) · 2–4% (16,7%) · 4–8% (36,2%) · 8–16% (62,2%) · 16–32% (81,6%) · 32–64% (94,1%).
    """
    if rate_pct <= 2.0:
        return "0–2% (8,5% опитаних)"
    if rate_pct <= 4.0:
        return "2–4% (16,7% опитаних)"
    if rate_pct <= 8.0:
        return "4–8% (36,2% опитаних)"
    if rate_pct <= 16.0:
        return "8–16% (62,2% опитаних)"
    if rate_pct <= 32.0:
        return "16–32% (81,6% опитаних)"
    if rate_pct <= 64.0:
        return "32–64% (94,1% опитаних)"
    return ">64%"


def classify_restore_time_dora2025(minutes: Optional[float]) -> str:
    """Визначає категорію DORA 2025 для часу відновлення після збою.

    Категорії:
      <1 год (21,3%) · <1 доби (56,5%) · доба–тиждень (84,5%) · тиждень–місяць (93,9%).
    """
    if minutes is None:
        return "н/д"
    if minutes < 60.0:
        return "<1 год (21,3% опитаних)"
    if minutes < 24.0 * 60.0:
        return "<1 доби (56,5% опитаних)"
    if minutes < 7.0 * 24.0 * 60.0:
        return "доба–тиждень (84,5% опитаних)"
    if minutes < 30.0 * 24.0 * 60.0:
        return "тиждень–місяць (93,9% опитаних)"
    return ">1 місяця"


def run_gh_cmd(args: List[str]) -> str:
    """Виконує команду GitHub CLI (gh) і повертає stdout у вигляді рядка."""
    validate_gh_args(args)
    cmd = ["gh"] + args
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        check=False,
    )
    if result.returncode != 0:
        err_msg = result.stderr.strip() or f"Команда {' '.join(cmd)} завершилася з кодом {result.returncode}"
        raise RuntimeError(f"Помилка виклику gh: {err_msg}")
    return result.stdout


def validate_gh_args(args: List[str]) -> None:
    """Дозволяє лише запити GitHub CLI, потрібні для збору метрик."""
    if not args or not all(isinstance(arg, str) for arg in args):
        raise ValueError("Недозволена команда GitHub CLI")
    if args == ["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]:
        return
    if not args or args[0] != "api":
        raise ValueError("Недозволена команда GitHub CLI")

    index = 1
    paginated = index < len(args) and args[index] == "--paginate"
    if paginated:
        index += 1
    if args[index : index + 2] != ["-X", "GET"]:
        raise ValueError("Недозволені аргументи GitHub CLI")
    index += 2
    if index >= len(args):
        raise ValueError("Не вказано endpoint GitHub API")
    endpoint = args[index]
    tail = args[index + 1 :]

    repository = r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"
    sha = r"[0-9a-fA-F]{7,64}"
    endpoint_pattern = (
        rf"repos/{repository}/(?:actions/workflows/ci\.yml/runs|actions/runs/[1-9]\d*/jobs\?per_page=100"
        rf"|commits/{sha}/pulls|pulls/[1-9]\d*/commits|commits/{sha})"
    )
    if not re.fullmatch(endpoint_pattern, endpoint):
        raise ValueError("Недозволений endpoint GitHub API")

    if endpoint.endswith("/actions/workflows/ci.yml/runs"):
        expected_prefix = ["-f", "branch=main", "-f", "event=push", "-f", "status=completed", "-f"]
        created_pattern = r"created=(?:>=\d{4}-\d{2}-\d{2}|\d{4}-\d{2}-\d{2}\.\.\d{4}-\d{2}-\d{2})"
        if (
            not paginated
            or tail[:7] != expected_prefix
            or len(tail) != 10
            or not re.fullmatch(created_pattern, tail[7])
            or tail[8:] != ["--jq", ".workflow_runs[]"]
        ):
            raise ValueError("Недозволені фільтри GitHub API")
    elif tail or (paginated != endpoint.endswith("/commits")):
        raise ValueError("Недозволені аргументи GitHub API")


def normalize_repo_name(repo: str) -> str:
    """Перевіряє назву репозиторію та повертає її у канонічному форматі owner/repo."""
    match = re.fullmatch(r"\s*([A-Za-z0-9][A-Za-z0-9_.-]*)/([A-Za-z0-9][A-Za-z0-9_.-]*)\s*", repo)
    if not match:
        raise RuntimeError("Некоректна назва репозиторію; вкажіть --repo owner/repo")
    return f"{match.group(1)}/{match.group(2)}"


def detect_repo(explicit_repo: Optional[str] = None) -> str:
    """Визначає репозиторій у форматі owner/repo (--repo або поточна папка через gh)."""
    if explicit_repo:
        return normalize_repo_name(explicit_repo)
    try:
        out = run_gh_cmd(["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]).strip()
    except (RuntimeError, OSError) as exc:
        raise RuntimeError(f"Не вдалося визначити репозиторій; вкажіть --repo owner/repo. {exc}") from exc
    if not out:
        raise RuntimeError("Не вдалося визначити репозиторій: вкажіть --repo owner/repo")
    return normalize_repo_name(out)


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


def fetch_workflow_runs(repo: str, since: datetime, until: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Отримує завершені запуски CI Pipeline для гілки main за період since..until."""
    since_date = since.strftime("%Y-%m-%d")
    until_date = until.strftime("%Y-%m-%d") if until else None
    created = f"{since_date}..{until_date}" if until_date else f">={since_date}"
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
        f"created={created}",
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


REPORT_OUTPUT_PATH = Path("docs/ci-cd/dora-auto.md")
EXPORT_JSON_PATH = Path("docs/ci-cd/evidence/runs-main.json")


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
        choices=[REPORT_OUTPUT_PATH.as_posix()],
        default=REPORT_OUTPUT_PATH.as_posix(),
        help="Фіксований шлях Markdown-звіту: docs/ci-cd/dora-auto.md.",
    )
    parser.add_argument(
        "--export-json",
        choices=[EXPORT_JSON_PATH.as_posix()],
        default=None,
        help="Фіксований шлях JSON-експорту: docs/ci-cd/evidence/runs-main.json.",
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


STATUS_ICONS = {"green": "✅", "red": "❌"}
RAW_TABLE_HEADER = (
    "| № | Коміт | PR | Перший коміт PR | Запуск завершено | Черга, хв | Виконання, хв "
    "| Час виконання змін, хв | Статус | Примітка |"
)


def warn(message: str) -> None:
    """Виводить попередження у stderr, не перериваючи роботу скрипта."""
    print(f"Попередження: {message}", file=sys.stderr)


def configure_output() -> None:
    """Вмикає UTF-8 у stdout/stderr: у PowerShell на Windows за замовчуванням інше кодування."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def parse_date(value: str) -> datetime:
    """Розбирає дату YYYY-MM-DD як початок доби за UTC."""
    parsed = datetime.strptime(value, "%Y-%m-%d")
    if parsed.strftime("%Y-%m-%d") != value:
        raise ValueError("Дата має бути у форматі YYYY-MM-DD")
    return parsed.replace(tzinfo=timezone.utc)


def resolve_period(since: str, until: Optional[str]) -> Tuple[datetime, datetime]:
    """Повертає межі періоду: від початку доби --since до кінця доби --until (або до поточного моменту)."""
    since_dt = parse_date(since)
    if until:
        until_dt = parse_date(until) + timedelta(days=1)
    else:
        until_dt = datetime.now(timezone.utc)
    if until_dt <= since_dt:
        raise ValueError("--until має бути не раніше за --since")
    return since_dt, until_dt


def collect_run_records(repo: str, since: datetime, until: Optional[datetime]) -> List[Dict[str, Any]]:
    """Збирає для кожного запуску статус, чергу, виконання, PR і час виконання змін."""
    runs = fetch_workflow_runs(repo, since, until)
    runs.sort(key=lambda r: r.get("created_at") or "")
    records: List[Dict[str, Any]] = []
    for run in runs:
        sha = run.get("head_sha") or ""
        jobs = fetch_run_jobs(repo, run["id"])
        timings = calculate_job_timings(run.get("created_at"), jobs)
        completed_dt = parse_iso_datetime(timings["max_completed_at"]) or parse_iso_datetime(run.get("updated_at"))
        pr_info = resolve_commit_pr_info(repo, sha, completed_dt)
        records.append(
            {
                "run_id": run["id"],
                "sha": sha,
                "run_attempt": int(run.get("run_attempt") or 1),
                "conclusion": run.get("conclusion"),
                "classified_status": classify_run_status(run.get("conclusion")),
                "created_at_dt": parse_iso_datetime(run.get("created_at")),
                "completed_at_dt": completed_dt,
                "queue_seconds": timings["queue_seconds"],
                "execution_seconds": timings["execution_seconds"],
                "queue_minutes": timings["queue_minutes"],
                "execution_minutes": timings["execution_minutes"],
                "pr_label": pr_info["pr_label"],
                "first_commit_dt": pr_info["first_commit_dt"],
                "lead_time_seconds": pr_info["lead_time_seconds"],
                "lead_time_minutes": pr_info["lead_time_minutes"],
            }
        )
    return records


def build_metrics(records: List[Dict[str, Any]], since_dt: datetime, until_dt: datetime, tz: tzinfo) -> Dict[str, Any]:
    """Обчислює чотири метрики DORA за зібраними запусками."""
    green = [r for r in records if r["classified_status"] == "green"]
    finished = [r for r in records if r["classified_status"] in ("green", "red")]
    return {
        "frequency": calculate_deployment_frequency(green, since_dt, until_dt, tz),
        "lead": calculate_lead_time_metrics(green),
        "failure": calculate_change_failure_rate(records),
        "restore": calculate_time_to_restore(finished),
        "retries": [r for r in records if r["run_attempt"] > 1],
    }


def fmt_minutes(value: Optional[float]) -> str:
    """Форматує хвилини для таблиці."""
    return "н/д" if value is None else f"{value:.1f}"


def fmt_dt(value: Optional[datetime], tz: tzinfo) -> str:
    """Форматує дату й час у вказаному часовому поясі."""
    return value.astimezone(tz).strftime("%d.%m %H:%M") if value else "—"


def render_metrics_section(metrics: Dict[str, Any]) -> List[str]:
    """Формує рядки markdown з метриками DORA, чергою і виконанням."""
    freq = metrics["frequency"]
    lead = metrics["lead"]
    fail = metrics["failure"]
    restore = metrics["restore"]
    return [
        "| Метрика | Формула | Результат | Категорія (DORA 2025) |",
        "|---|---|---|---|",
        "| Частота розгортань | зелені запуски на main / кількість тижнів | "
        f"{freq['total_green']} зелених / {freq['weeks']} тиж. = {freq['per_week']} на тиждень "
        f"({freq['per_active_day']} на активний день, активних днів: {freq['active_days_count']}) | "
        "визначте вручну за таблицею DORA 2025 |",
        "| Час виконання змін | від першого коміту PR до завершення зеленого запуску на main | "
        f"середнє {fmt_minutes(lead['mean_minutes'])} хв, медіана {fmt_minutes(lead['median_minutes'])} хв | "
        f"за медіаною: {classify_lead_time_dora2025(lead['median_minutes'])}; "
        f"за середнім: {classify_lead_time_dora2025(lead['mean_minutes'])} |",
        "| Частота збоїв змін | червоні / (зелені + червоні) на main × 100% | "
        f"{fail['red_count']} / {fail['total_completed']} × 100% = {fail['failure_rate_pct']}% | "
        f"{classify_failure_rate_dora2025(fail['failure_rate_pct'])} |",
        "| Час відновлення | від червоного запуску на main до наступного зеленого | "
        f"{restore['status_label']} | {classify_restore_time_dora2025(restore['median_minutes'])} |",
        "",
        "Черга і виконання (зелені запуски):",
        "",
        f"- У часі CI (черга + виконання): черга {lead['queue_share_pct']}%, виконання {lead['execution_share_pct']}%.",
        f"- У часі виконання змін (від першого коміту): черга {lead['queue_of_lead_pct']}%, "
        f"виконання {lead['execution_of_lead_pct']}%, решта {lead['other_of_lead_pct']}% "
        "припадає на час до запуску CI (розробка, рев'ю, очікування злиття).",
        f"- Запусків: зелених {fail['green_count']}, червоних {fail['red_count']}; "
        f"cancelled {fail['cancelled_count']} і skipped {fail['skipped_count']} у метриках не враховано.",
    ]


def render_raw_table(records: List[Dict[str, Any]], tz: tzinfo) -> List[str]:
    """Формує таблицю сирих даних про запуски."""
    lines = [RAW_TABLE_HEADER, "|" + "---|" * 10]
    for number, record in enumerate(records, 1):
        notes: List[str] = []
        if record["run_attempt"] > 1:
            notes.append(f"повторний запуск (спроба {record['run_attempt']})")
        if record["classified_status"] not in ("green", "red"):
            notes.append(f"результат: {record['conclusion'] or 'невідомо'}")
        if record["pr_label"] == "—":
            notes.append("без PR (прямий пуш)")
        lines.append(
            f"| {number} | {record['sha'][:7]} | {record['pr_label']} | {fmt_dt(record['first_commit_dt'], tz)} "
            f"| {fmt_dt(record['completed_at_dt'], tz)} | {fmt_minutes(record['queue_minutes'])} "
            f"| {fmt_minutes(record['execution_minutes'])} | {fmt_minutes(record['lead_time_minutes'])} "
            f"| {STATUS_ICONS.get(record['classified_status'], '⚪')} | {'; '.join(notes)} |"
        )
    return lines


def render_report(
    repo: str,
    since: str,
    until: Optional[str],
    tz_label: str,
    records: List[Dict[str, Any]],
    metrics: Dict[str, Any],
    tz: tzinfo,
) -> str:
    """Формує повний звіт у форматі Markdown."""
    lines = [
        "# Автоматичний підрахунок метрик DORA",
        "",
        f"- Репозиторій: `{repo}`",
        "- Workflow: CI Pipeline (`ci.yml`), гілка `main`, подія `push`",
        f"- Період: {since} – {until or 'сьогодні'}",
        f"- Час у таблицях: {tz_label}",
        "- Розгортання = зелений запуск CI на main; невдала зміна = червоний запуск на main.",
        f"- Згенеровано: {datetime.now(tz).strftime('%d.%m.%Y %H:%M')} ({tz_label}), скрипт `scripts/dora_metrics.py`",
        "",
        "## Метрики DORA",
        "",
    ]
    lines += render_metrics_section(metrics)
    lines += ["", "## Сирі дані по запусках", ""]
    lines += render_raw_table(records, tz)
    lines += ["", "## Повторні запуски (run_attempt > 1)", ""]
    if metrics["retries"]:
        for record in metrics["retries"]:
            lines.append(f"- {record['sha'][:7]}: спроба {record['run_attempt']}, результат {record['conclusion']}")
    else:
        lines.append("Повторних запусків немає: усі запуски мають run_attempt = 1.")
    return "\n".join(lines) + "\n"


def write_report_file(content: str) -> None:
    """Записує Markdown-звіт у фіксований шлях у поточному каталозі."""
    root = Path.cwd().resolve()
    target = (root / REPORT_OUTPUT_PATH).resolve()
    if not target.is_relative_to(root):
        raise ValueError("Шлях звіту має залишатися в поточному каталозі")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(  # NOSONAR: шлях задано константою; content є текстом звіту, а не шляхом.
        content, encoding="utf-8"
    )


def export_records_json(repo: str, since: str, until: Optional[str], records: List[Dict[str, Any]]) -> None:
    """Експортує знеособлені дані запусків без імен і email авторів."""

    def iso(value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None

    runs = [
        {
            "run_id": record["run_id"],
            "head_sha": record["sha"],
            "run_attempt": record["run_attempt"],
            "conclusion": record["conclusion"],
            "pr": record["pr_label"],
            "created_at": iso(record["created_at_dt"]),
            "completed_at": iso(record["completed_at_dt"]),
            "first_commit_at": iso(record["first_commit_dt"]),
            "queue_minutes": record["queue_minutes"],
            "execution_minutes": record["execution_minutes"],
            "lead_time_minutes": record["lead_time_minutes"],
        }
        for record in records
    ]
    payload = {"repo": repo, "workflow": "ci.yml", "since": since, "until": until, "runs": runs}
    root = Path.cwd().resolve()
    target = (root / EXPORT_JSON_PATH).resolve()
    if not target.is_relative_to(root):
        raise ValueError("Шлях JSON-експорту має залишатися в поточному каталозі")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(  # NOSONAR: шлях задано константою; записується лише JSON-вміст.
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main(argv: Optional[List[str]] = None) -> int:
    """Точка входу CLI."""
    args = parse_args(argv)
    configure_output()
    tz = get_tz(args.utc_offset_hours)
    tz_label = format_tz_label(args.utc_offset_hours)
    try:
        since_dt, until_dt = resolve_period(args.since, args.until)
        api_until_dt = parse_date(args.until) if args.until else None
        since_label = since_dt.strftime("%Y-%m-%d")
        until_label = api_until_dt.strftime("%Y-%m-%d") if api_until_dt else None
    except ValueError as exc:
        print(f"Помилка в аргументах: {exc}", file=sys.stderr)
        return 2
    try:
        repo = detect_repo(args.repo)
        print(f"Збираю запуски CI Pipeline для {repo} з {args.since}...")
        records = collect_run_records(repo, since_dt, api_until_dt)
    except (RuntimeError, OSError, ValueError) as exc:
        print(f"Помилка: {exc}", file=sys.stderr)
        return 1
    if not records:
        print("За цей період завершених запусків не знайдено.", file=sys.stderr)
        return 1

    metrics = build_metrics(records, since_dt, until_dt, tz)
    write_report_file(render_report(repo, since_label, until_label, tz_label, records, metrics, tz))
    if args.export_json:
        export_records_json(repo, since_label, until_label, records)
    print("\n".join(render_metrics_section(metrics)))
    print(f"\nЗвіт збережено: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
