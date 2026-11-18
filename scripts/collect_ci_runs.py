#!/usr/bin/env python3

import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "ci-cd" / "evidence"
OUTPUT = ROOT / "docs" / "ci-cd" / "metrics-raw.md"
KYIV = ZoneInfo("Europe/Kyiv")
RUN_FIELDS = "databaseId,headSha,workflowName,conclusion,attempt,createdAt,updatedAt"
PR_RUN_FIELDS = "databaseId,headSha,headBranch,workflowName,event,conclusion,attempt,createdAt,updatedAt,displayTitle"


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


def fetch_runs(args, fields, path):
    runs = json.loads(command(args + ["--json", fields]))
    write_json(path, runs)
    return runs


def get_runs(snapshot_dir):
    return fetch_runs(
        ["gh", "run", "list", "--branch", "main", "--limit", "1000"],
        RUN_FIELDS,
        snapshot_dir / "runs-main.json",
    )


def get_pr_runs(snapshot_dir):
    return fetch_runs(
        ["gh", "run", "list", "--event", "pull_request", "--limit", "1000"],
        PR_RUN_FIELDS,
        snapshot_dir / "runs-pull-requests.json",
    )


def get_run_jobs(run, snapshot_dir):
    attempt = run.get("attempt") or 1
    jobs = json.loads(
        command(
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
    )
    write_json(snapshot_dir / "jobs" / "{}-attempt-{}.json".format(run["databaseId"], attempt), jobs)
    return jobs.get("jobs", [])


def get_commit_prs(repo, sha, snapshot_dir):
    prs = json.loads(
        command(
            [
                "gh",
                "api",
                "repos/{}/commits/{}/pulls".format(repo, sha),
                "-H",
                "Accept: application/vnd.github+json",
            ]
        )
    )
    write_json(snapshot_dir / "prs" / "commit-{}.json".format(sha), prs)
    return prs


def get_pr_commits(number, snapshot_dir):
    pr = json.loads(command(["gh", "pr", "view", str(number), "--json", "number,title,url,commits"]))
    write_json(snapshot_dir / "prs" / "pr-{}.json".format(number), pr)
    return pr


def get_commit(repo, sha, snapshot_dir):
    commit = json.loads(command(["gh", "api", "repos/{}/commits/{}".format(repo, sha)]))
    write_json(snapshot_dir / "commits" / "{}.json".format(sha), commit)
    return commit


def get_failure_log(run):
    result = subprocess.run(
        ["gh", "run", "view", str(run["databaseId"]), "--log-failed"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return {"exit_code": result.returncode, "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}


def failure_reason(log_result):
    if not log_result or log_result["exit_code"] != 0:
        return "не вдалося отримати лог (`gh run view --log-failed`)"
    log = log_result["stdout"] or log_result["stderr"]
    if not log:
        return "лог невдалого кроку порожній"
    lines = [re.sub(r"\x1b\[[0-9;]*m", "", line).split("Z ", 1)[-1].strip() for line in log.splitlines()]
    for line in lines:
        if "would reformat " in line.lower():
            return "Black: {}".format(line.strip())[:240]
    failed_tests = [line.strip() for line in lines if line.lstrip().startswith("FAILED ")]
    if failed_tests:
        return "Pytest: {}".format(failed_tests[0])[:240]
    for line in reversed(lines):
        lowered = line.lower()
        if (
            any(marker in lowered for marker in ("assertionerror", "traceback", "error:", "exception:"))
            and "deprecationwarning" not in lowered
            and "requirement already satisfied" not in lowered
        ):
            return line.replace("|", "/")[:240]
    for index, line in enumerate(lines):
        if "##[error]process completed with exit code" in line.lower():
            for preceding in reversed(lines[:index]):
                if "##[group]run " in preceding.lower():
                    command_line = preceding.split("##[group]Run ", 1)[-1].strip()
                    return "CI command `{}` failed; no specific diagnostic was emitted.".format(command_line)[:240]
            return "CI step failed with exit code 1; no specific diagnostic was emitted."
    return "failed job log contains no specific diagnostic"


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


def first_change_time(repo, sha, prs, snapshot_dir):
    primary = choose_primary_pr(prs, sha)
    if primary:
        pr = get_pr_commits(primary["number"], snapshot_dir)
        commits = pr.get("commits", [])
        if commits:
            return commits[0].get("authoredDate"), "#{}".format(primary["number"])
    commit = get_commit(repo, sha, snapshot_dir)
    authored = commit.get("commit", {}).get("author", {}).get("date")
    return authored, None


def get_repo_name():
    return command(["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"]).strip()


def job_interval(jobs):
    starts = [parse_time(job.get("startedAt")) for job in jobs]
    starts = [value for value in starts if value and value.year > 1]
    completions = [parse_time(job.get("completedAt")) for job in jobs]
    completions = [value for value in completions if value and value.year > 1]
    return (min(starts) if starts else None, max(completions) if completions else None)


def run_snapshot(run, all_jobs):
    first_start, last_complete = job_interval(all_jobs.get(run["databaseId"], []))
    if not first_start or not last_complete:
        return None
    return {"run": run, "first_start": first_start, "last_complete": last_complete}


def save_run_log(snapshot_dir, directory, run):
    result = get_failure_log(run)
    write_json(
        snapshot_dir / directory / "{}.json".format(run["databaseId"]),
        {"run": run, "log": result},
    )
    return result


def main():
    try:
        now = datetime.now(timezone.utc)
        snapshot_dir = EVIDENCE / "snapshots" / now.strftime("%Y%m%dT%H%M%S%fZ")
        cutoff = now - timedelta(days=21)
        repo = get_repo_name()
        listed_runs = get_runs(snapshot_dir)
        listed_pr_runs = get_pr_runs(snapshot_dir)
        recent_main_runs = [
            run for run in listed_runs if parse_time(run.get("createdAt")) and parse_time(run["createdAt"]) >= cutoff
        ]
        completed_main_runs = [run for run in recent_main_runs if run.get("conclusion")]
        pending_shas = {run["headSha"] for run in recent_main_runs if not run.get("conclusion")}
        runs = completed_main_runs

        all_jobs = {}
        prs_by_sha = {}
        main_failure_logs = {}
        for run in runs:
            all_jobs[run["databaseId"]] = get_run_jobs(run, snapshot_dir)
            sha = run["headSha"]
            if sha not in prs_by_sha:
                prs_by_sha[sha] = get_commit_prs(repo, sha, snapshot_dir)
            if run.get("conclusion") != "success":
                main_failure_logs[run["databaseId"]] = save_run_log(snapshot_dir, "main-failures", run)

        grouped = defaultdict(list)
        for run in runs:
            grouped[run["headSha"]].append(run)

        rows = []
        red_runs = []
        for sha, commit_runs in grouped.items():
            if sha in pending_shas:
                continue
            prs = prs_by_sha[sha]
            pr_numbers = sorted({pr["number"] for pr in prs})
            pr_display = ", ".join("#{}".format(number) for number in pr_numbers) or "—"
            first_change, pr_label = first_change_time(repo, sha, prs, snapshot_dir)
            critical_candidates = []
            for workflow_name in sorted({run.get("workflowName", "невідомий") for run in commit_runs}):
                workflow_runs = [run for run in commit_runs if run.get("workflowName", "невідомий") == workflow_name]
                measurements = [
                    measurement for measurement in (run_snapshot(run, all_jobs) for run in workflow_runs) if measurement
                ]
                if measurements:
                    critical_candidates.append(max(measurements, key=lambda value: value["last_complete"]))

            critical = (
                max(critical_candidates, key=lambda value: value["last_complete"]) if critical_candidates else None
            )
            critical_run = critical["run"] if critical else None
            first_start = critical["first_start"] if critical else None
            last_complete = critical["last_complete"] if critical else None
            created_at = parse_time(critical_run.get("createdAt")) if critical_run else None
            queue_minutes = (first_start - created_at).total_seconds() / 60 if first_start and created_at else None
            execution_minutes = (
                (last_complete - first_start).total_seconds() / 60 if last_complete and first_start else None
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
                            failure_reason(main_failure_logs.get(run["databaseId"])),
                        )
                    )
            rows.append(
                {
                    "sha": sha,
                    "pr": pr_display,
                    "first_change": display_time(first_change) if pr_label else "—",
                    "completed": display_time(last_complete.isoformat()) if last_complete else "н/д",
                    "queue": "{:.1f}".format(queue_minutes) if queue_minutes is not None else "н/д",
                    "execution": "{:.1f}".format(execution_minutes) if execution_minutes is not None else "н/д",
                    "queue_minutes": queue_minutes,
                    "execution_minutes": execution_minutes,
                    "status": status,
                    "notes": "; ".join(notes).replace("|", "/"),
                    "sort_time": last_complete or datetime.min.replace(tzinfo=timezone.utc),
                }
            )

        rows.sort(key=lambda row: row["sort_time"], reverse=True)
        recent_pr_runs = [
            run for run in listed_pr_runs if parse_time(run.get("createdAt")) and parse_time(run["createdAt"]) >= cutoff
        ]
        pr_failure_runs = [run for run in recent_pr_runs if run.get("conclusion") == "failure"]
        pr_failure_notes = []
        for run in pr_failure_runs:
            log = save_run_log(snapshot_dir, "pull-request-failures", run)
            pr_failure_notes.append(
                "- Run {} (`{}`, `{}`): {}".format(
                    run["databaseId"],
                    run.get("headBranch", "branch невідома"),
                    run.get("workflowName", "workflow невідомий"),
                    failure_reason(log),
                )
            )

        workflow_names = sorted({run.get("workflowName", "невідомий") for run in completed_main_runs})
        period_start = cutoff.astimezone(KYIV).strftime("%d.%m.%Y %H:%M")
        period_end = now.astimezone(KYIV).strftime("%d.%m.%Y %H:%M")
        measured_rows = [
            row for row in rows if row["queue_minutes"] is not None and row["execution_minutes"] is not None
        ]
        queue_values = [row["queue_minutes"] for row in measured_rows]
        execution_values = [row["execution_minutes"] for row in measured_rows]
        total_queue = sum(queue_values)
        total_execution = sum(execution_values)
        total_duration = total_queue + total_execution
        queue_share = 100 * total_queue / total_duration if total_duration else 0
        execution_share = 100 * total_execution / total_duration if total_duration else 0
        red_main_count = sum(1 for run in completed_main_runs if run.get("conclusion") != "success")
        successful_main_count = sum(1 for run in completed_main_runs if run.get("conclusion") == "success")
        attempts = sorted({run.get("attempt", 1) for run in completed_main_runs})

        lines = [
            "# Сирі метрики CI/CD (гілка main)",
            "",
            "Період: {} – {} (Europe/Kyiv); ковзне вікно 21 день до збору.".format(period_start, period_end),
            "Джерело main: `gh run list --branch main --limit 1000 --json {}`.".format(RUN_FIELDS),
            "Сирі дані цього звіту: `{}`.".format(snapshot_dir.relative_to(ROOT).as_posix()),
            (
                "За період знайдено {} запусків на `main` (завершених: {}, незавершених: {}); "
                "рядків-комітів у таблиці: {}; комітів із незавершеними запусками пропущено: {}.".format(
                    len(recent_main_runs),
                    len(completed_main_runs),
                    len(recent_main_runs) - len(completed_main_runs),
                    len(rows),
                    len(pending_shas),
                )
            ),
            "Час у таблиці — `Europe/Kyiv`, формат `ДД.ММ ГГ:ХХ`; тривалості в хвилинах округлено до 0,1.",
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
                    row["notes"],
                )
            )

        lines.extend(
            [
                "",
                "## Методика і вибірка",
                "",
                "- Враховані workflow: {}.".format(", ".join(workflow_names) or "немає"),
                "- Один рядок на коміт: коміт зелений, лише якщо всі завершені враховані workflow успішні.",
                (
                    "- Критичний workflow коміту — той, що завершився останнім. Черга: від `createdAt` саме "
                    "цього workflow до старту його першого job; виконання: від старту першого job до "
                    "завершення останнього job цього самого workflow."
                ),
                (
                    "- Час виконання змін у примітці: від `authoredDate` першого коміту PR до завершення "
                    "останнього зеленого запуску; для прямого коміту в `main` — від authored date самого коміту."
                ),
                (
                    "- У таблиці лише завершені запуски у вікні 21 день; незавершені не класифікуються. "
                    "`main`: {} success, {} failure; attempts завершених запусків: {}."
                ).format(
                    successful_main_count,
                    red_main_count,
                    ", ".join(str(attempt) for attempt in attempts) or "немає",
                ),
                (
                    "- PR-запуски отримані через `gh run list --event pull_request --limit 1000`; "
                    "у тому самому періоді {} запусків, з них {} невдалих. Невдачі PR не рахуються "
                    "як невдалі зміни на `main` у DORA."
                ).format(len(recent_pr_runs), len(pr_failure_runs)),
                "",
                "## Розподіл у часі виконання змін",
                "",
                (
                    "Розраховано за {} комітами з обома вимірюваннями; суми охоплюють лише "
                    "критичний workflow кожного коміту."
                ).format(len(measured_rows)),
                "",
                "| Вимір | Сума, хв | Частка суми черги + виконання | Середнє, хв/коміт | Медіана, хв/коміт |",
                "|---|---:|---:|---:|---:|",
                "| Черга | {:.1f} | {:.1f}% | {:.1f} | {:.1f} |".format(
                    total_queue,
                    queue_share,
                    sum(queue_values) / len(queue_values) if queue_values else 0,
                    median(queue_values) if queue_values else 0,
                ),
                "| Виконання | {:.1f} | {:.1f}% | {:.1f} | {:.1f} |".format(
                    total_execution,
                    execution_share,
                    sum(execution_values) / len(execution_values) if execution_values else 0,
                    median(execution_values) if execution_values else 0,
                ),
                "",
                "## Червоні запуски на main",
                "",
            ]
        )
        if red_runs:
            lines.extend(
                "- Run {} (`{}`): {}".format(
                    run["databaseId"],
                    run.get("workflowName", "workflow невідомий"),
                    failure_reason(main_failure_logs.get(run["databaseId"])),
                )
                for run in red_runs
            )
        else:
            lines.append("Завершених червоних запусків на `main` у вибраному періоді немає.")
        lines.extend(
            [
                "",
                "## Невдалі запуски pull request",
                "",
                (
                    "Причини взято з `gh run view <id> --log-failed`. Ці запуски наведені "
                    "окремо й не входять у DORA main-метрики."
                ),
                "",
            ]
        )
        lines.extend(pr_failure_notes or ["Невдалих PR-запусків у вибраному періоді не знайдено."])
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(
            "Збережено {} main runs, {} PR runs та {} PR failure logs у {}.".format(
                len(recent_main_runs), len(recent_pr_runs), len(pr_failure_runs), snapshot_dir
            )
        )
        print("Оновлено {}".format(OUTPUT.relative_to(ROOT)))
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        print("collect_ci_runs: {}".format(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
