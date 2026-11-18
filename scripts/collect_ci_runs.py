#!/usr/bin/env python3

import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "ci-cd" / "evidence"
OUTPUT = ROOT / "docs" / "ci-cd" / "metrics-raw.md"
KYIV = ZoneInfo("Europe/Kyiv")
RUN_FIELDS = "databaseId,headSha,workflowName,conclusion,attempt,createdAt,updatedAt"


def command(args):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("Command failed: {}\n{}".format(" ".join(args), result.stderr.strip()))
    return result.stdout


def parse_time(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def display_time(value):
    moment = parse_time(value)
    return moment.astimezone(KYIV).strftime("%d.%m %H:%M") if moment else "—"


def minutes(start, end):
    start_time = parse_time(start)
    end_time = parse_time(end)
    if not start_time or not end_time:
        return "н/д"
    return "{:.1f}".format((end_time - start_time).total_seconds() / 60)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def get_runs():
    raw = command(
        [
            "gh",
            "run",
            "list",
            "--branch",
            "main",
            "--limit",
            "50",
            "--json",
            RUN_FIELDS,
        ]
    )
    runs = json.loads(raw)
    write_json(EVIDENCE / "runs.json", runs)
    return runs


def get_commit_runs(sha):
    result = command(
        [
            "gh",
            "run",
            "list",
            "--branch",
            "main",
            "--commit",
            sha,
            "--limit",
            "50",
            "--json",
            RUN_FIELDS,
        ]
    )
    runs = json.loads(result)
    write_json(EVIDENCE / "runs" / "by-commit" / "{}.json".format(sha), runs)
    return runs


def get_run_jobs(run):
    attempt = run.get("attempt") or 1
    path = EVIDENCE / "jobs" / "{}-attempt-{}.json".format(run["databaseId"], attempt)
    if path.exists():
        return load_json(path).get("jobs", [])
    result = command(
        [
            "gh",
            "run",
            "view",
            str(run["databaseId"]),
            "--attempt",
            str(attempt),
            "--json",
            "jobs",
        ]
    )
    jobs = json.loads(result)
    write_json(path, jobs)
    return jobs.get("jobs", [])


def get_commit_prs(repo, sha):
    path = EVIDENCE / "prs" / "commit-{}.json".format(sha)
    if path.exists():
        return load_json(path)
    result = command(
        [
            "gh",
            "api",
            "repos/{}/commits/{}/pulls".format(repo, sha),
            "-H",
            "Accept: application/vnd.github+json",
        ]
    )
    prs = json.loads(result)
    write_json(path, prs)
    return prs


def get_pr_commits(number):
    path = EVIDENCE / "prs" / "pr-{}.json".format(number)
    if path.exists():
        return load_json(path)
    result = command(["gh", "pr", "view", str(number), "--json", "number,title,url,commits"])
    pr = json.loads(result)
    write_json(path, pr)
    return pr


def get_commit(repo, sha):
    path = EVIDENCE / "commits" / "{}.json".format(sha)
    if path.exists():
        return load_json(path)
    result = command(["gh", "api", "repos/{}/commits/{}".format(repo, sha)])
    commit = json.loads(result)
    write_json(path, commit)
    return commit


def get_failure_log(run):
    result = subprocess.run(
        ["gh", "run", "view", str(run["databaseId"]), "--log-failed"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() or result.stderr.strip()


def failure_reason(log):
    if not log:
        return "лог невдалого кроку порожній або недоступний"
    lines = [line.strip() for line in log.splitlines() if line.strip()]
    for line in reversed(lines):
        lowered = line.lower()
        if any(
            marker in lowered
            for marker in (
                "error",
                "failed",
                "failure",
                "traceback",
                "assertionerror",
                "exception",
            )
        ):
            return line.replace("|", "/")[:240]
    return lines[-1].replace("|", "/")[:240]


def choose_primary_pr(prs, sha):
    if not prs:
        return None
    merged = [pr for pr in prs if pr.get("merged_at")]
    candidates = merged or prs
    candidates.sort(
        key=lambda pr: (
            pr.get("merge_commit_sha") != sha,
            pr.get("base", {}).get("ref") != "main",
            pr.get("merged_at") or "",
        )
    )
    return candidates[0]


def first_change_time(repo, sha, prs):
    primary = choose_primary_pr(prs, sha)
    if primary:
        pr = get_pr_commits(primary["number"])
        commits = pr.get("commits", [])
        if commits:
            return commits[0].get("authoredDate"), "#{}".format(primary["number"])
    commit = get_commit(repo, sha)
    authored = commit.get("commit", {}).get("author", {}).get("date")
    return authored, None


def summarize_failure_runs(runs, logs):
    result = []
    for run in runs:
        if run.get("conclusion") != "success":
            result.append(
                "- Run {} (`{}`): {}".format(
                    run["databaseId"],
                    run.get("workflowName", "workflow невідомий"),
                    failure_reason(logs.get(run["databaseId"], "")),
                )
            )
    return result


def main():
    try:
        repo = command(["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"]).strip()
        listed_runs = get_runs()
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=21)
        selected_shas = {
            run["headSha"]
            for run in listed_runs
            if parse_time(run.get("createdAt")) and parse_time(run["createdAt"]) >= cutoff
        }
        runs_by_key = {(run["databaseId"], run.get("attempt", 1)): run for run in listed_runs}
        for sha in sorted(selected_shas):
            for run in get_commit_runs(sha):
                runs_by_key[(run["databaseId"], run.get("attempt", 1))] = run
        runs = list(runs_by_key.values())
        all_jobs = {}
        prs_by_sha = {}
        logs = {}
        for run in runs:
            all_jobs[run["databaseId"]] = get_run_jobs(run)
            sha = run["headSha"]
            if sha not in prs_by_sha:
                prs_by_sha[sha] = get_commit_prs(repo, sha)
            if run.get("conclusion") not in (None, "success"):
                logs[run["databaseId"]] = get_failure_log(run)

        recent_runs = [
            run for run in runs if parse_time(run.get("createdAt")) and parse_time(run["createdAt"]) >= cutoff
        ]
        recent_shas = {run["headSha"] for run in recent_runs}
        grouped = defaultdict(list)
        for run in runs:
            created_at = parse_time(run.get("createdAt"))
            if (
                run["headSha"] in recent_shas
                and run.get("conclusion") is not None
                and created_at
                and created_at >= cutoff
            ):
                grouped[run["headSha"]].append(run)

        rows = []
        red_runs = []
        for sha, commit_runs in grouped.items():
            prs = prs_by_sha[sha]
            primary_pr = choose_primary_pr(prs, sha)
            pr_numbers = sorted({pr["number"] for pr in prs})
            pr_display = ", ".join("#{}".format(number) for number in pr_numbers) or "—"
            first_change, pr_label = first_change_time(repo, sha, prs)
            completed = []
            started = []
            created = []
            for run in commit_runs:
                created_time = parse_time(run.get("createdAt"))
                if created_time:
                    created.append(created_time)
                for job in all_jobs.get(run["databaseId"], []):
                    start_time = parse_time(job.get("startedAt"))
                    end_time = parse_time(job.get("completedAt"))
                    if start_time:
                        started.append(start_time)
                    if end_time:
                        completed.append(end_time)
            first_start = min(started) if started else None
            last_complete = max(completed) if completed else None
            first_created = min(created) if created else None
            queue = (
                "{:.1f}".format((first_start - first_created).total_seconds() / 60)
                if first_start and first_created
                else "н/д"
            )
            execution = (
                "{:.1f}".format((last_complete - first_start).total_seconds() / 60)
                if last_complete and first_start
                else "н/д"
            )
            status = "✅" if all(run.get("conclusion") == "success" for run in commit_runs) else "❌"
            workflow_names = sorted({run.get("workflowName", "невідомий") for run in commit_runs})
            notes = ["workflow: {}".format(", ".join(workflow_names))]
            if status == "✅" and first_change and last_complete:
                notes.append(
                    "час змін: {} хв від {}".format(
                        minutes(first_change, last_complete),
                        pr_label or "коміту напряму в main",
                    )
                )
            for run in commit_runs:
                if run.get("attempt", 1) > 1 and run.get("conclusion") == "success":
                    notes.append(
                        "run {} attempt {}: ймовірно нестабільний тест".format(run["databaseId"], run["attempt"])
                    )
                if run.get("conclusion") != "success":
                    red_runs.append(run)
                    notes.append(
                        "run {}: {}".format(
                            run["databaseId"],
                            failure_reason(logs.get(run["databaseId"], "")),
                        )
                    )
            rows.append(
                {
                    "sha": sha,
                    "pr": pr_display,
                    "first_change": display_time(first_change) if pr_label else "—",
                    "completed": display_time(last_complete.isoformat()) if last_complete else "н/д",
                    "queue": queue,
                    "execution": execution,
                    "status": status,
                    "notes": "; ".join(notes),
                    "sort_time": (
                        last_complete or max(created) if created else datetime.min.replace(tzinfo=timezone.utc)
                    ),
                    "prs": prs,
                    "primary_pr": primary_pr,
                }
            )

        rows.sort(key=lambda row: row["sort_time"], reverse=True)
        workflow_names = sorted({run.get("workflowName", "невідомий") for run in recent_runs})
        starts = [parse_time(run["createdAt"]) for run in recent_runs if run.get("createdAt")]
        period_start = min(starts).astimezone(KYIV).strftime("%d.%m.%Y") if starts else "немає запусків"
        period_end = max(starts).astimezone(KYIV).strftime("%d.%m.%Y") if starts else "немає запусків"

        lines = [
            "# Сирі метрики CI/CD (гілка main)",
            "",
            "Період: {} – {} (Europe/Kyiv); охоплено останні 21 день до запуску скрипту.".format(
                period_start, period_end
            ),
            "Джерело: `gh run list --branch main --limit 50 --json {}`.".format(RUN_FIELDS),
            (
                "За цей період знайдено {} запусків на `main` у {} комітах. ".format(len(recent_runs), len(rows))
                + "Базова вибірка містить {} запусків; список пов'язаний із кожним її комітом, "
                "щоб не пропустити інші workflow того самого коміту.".format(len(listed_runs))
            ),
            "",
            "| № | Коміт | PR | Перший коміт PR | Запуск завершено | Черга, хв | Виконання, хв | Статус | Примітка |",
            "|---:|---|---|---|---|---:|---:|:---:|---|",
        ]
        for index, row in enumerate(rows, 1):
            lines.append(
                "| {} | `{}` | {} | {} | {} | {} | {} | {} | {} |".format(
                    index,
                    row["sha"][:7],
                    row["pr"],
                    row["first_change"],
                    row["completed"],
                    row["queue"],
                    row["execution"],
                    row["status"],
                    row["notes"].replace("|", "/"),
                )
            )

        lines.extend(
            [
                "",
                "## Методика і вибірка",
                "",
                "- Враховані workflow: {}.".format(", ".join(workflow_names) or "немає"),
                "- Один рядок на коміт: ✅ якщо всі враховані workflow успішні, інакше ❌.",
                (
                    "- Черга: найраніший `createdAt` коміту до старту першого job. Виконання: "
                    "від старту першого job до завершення останнього серед workflow."
                ),
                (
                    "- Час змін у примітці: від `authoredDate` першого коміту PR до завершення "
                    "останнього зеленого job; для прямого коміту — від його authored date."
                ),
                (
                    "- Лише завершені запуски, створені в останні 21 день; незавершені "
                    "запуски окремо не класифікуються."
                ),
                "- Час у таблиці — `Europe/Kyiv`, формат `ДД.ММ ГГ:ХХ`; тривалості в хвилинах округлено до 0,1.",
            ]
        )
        if len(recent_runs) < 10:
            lines.extend(
                [
                    "",
                    (
                        "**Недостатня вибірка:** за 21 день знайдено менше 10 запусків "
                        "на `main` ({}); вибірку не доповнено старішими даними."
                    ).format(len(recent_runs)),
                ]
            )
        failure_lines = summarize_failure_runs(recent_runs, logs)
        lines.extend(["", "## Червоні запуски", ""])
        lines.extend(failure_lines or ["За вибраний період червоних запусків на `main` не знайдено."])
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(
            "Збережено {} запусків; {} за 21 день; {} комітів у таблиці: {}".format(
                len(runs), len(recent_runs), len(rows), OUTPUT.relative_to(ROOT)
            )
        )
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        print("collect_ci_runs: {}".format(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
