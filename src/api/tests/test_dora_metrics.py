import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dora_metrics.py"
spec = importlib.util.spec_from_file_location("dora_metrics", SCRIPT)
dora = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dora)

UTC = timezone.utc


def at(day, hour, minute=0):
    return datetime(2026, 11, day, hour, minute, tzinfo=UTC)


RUNS = [
    {
        "id": 1,
        "head_sha": "aaaaaaa1111",
        "created_at": "2026-11-10T10:00:00Z",
        "updated_at": "2026-11-10T10:10:00Z",
        "conclusion": "success",
        "run_attempt": 1,
    },
    {
        "id": 2,
        "head_sha": "bbbbbbb2222",
        "created_at": "2026-11-10T12:00:00Z",
        "updated_at": "2026-11-10T12:10:00Z",
        "conclusion": "failure",
        "run_attempt": 1,
    },
    {
        "id": 3,
        "head_sha": "ccccccc3333",
        "created_at": "2026-11-10T13:00:00Z",
        "updated_at": "2026-11-10T13:40:00Z",
        "conclusion": "success",
        "run_attempt": 2,
    },
]
JOBS = {
    1: [
        {"started_at": "2026-11-10T10:02:00Z", "completed_at": "2026-11-10T10:05:00Z"},
        {"started_at": "2026-11-10T10:03:00Z", "completed_at": "2026-11-10T10:06:00Z"},
    ],
    2: [{"started_at": "2026-11-10T12:01:00Z", "completed_at": "2026-11-10T12:05:00Z"}],
    3: [{"started_at": "2026-11-10T13:30:00Z", "completed_at": "2026-11-10T13:35:00Z"}],
}
PULLS = {"aaaaaaa1111": [{"number": 7}], "bbbbbbb2222": [], "ccccccc3333": [{"number": 8}]}
PULL_COMMITS = {
    7: [
        {"commit": {"author": {"date": "2026-11-10T09:30:00Z"}}},
        {"commit": {"author": {"date": "2026-11-10T09:00:00Z"}}},
    ],
    8: [{"commit": {"author": {"date": "2026-11-10T13:00:00Z"}}}],
}
COMMITS = {"bbbbbbb2222": {"commit": {"author": {"date": "2026-11-10T11:50:00Z"}}}}


def make_fake_gh(calls, runs=RUNS):
    def fake(args):
        calls.append(args)
        endpoint = next(a for a in args if a.startswith("repos/"))
        if endpoint.endswith("/ci.yml/runs"):
            return "\n".join(json.dumps(run) for run in runs)
        if "/actions/runs/" in endpoint:
            run_id = int(endpoint.split("/actions/runs/")[1].split("/")[0])
            return json.dumps({"jobs": JOBS[run_id]})
        if "/commits/" in endpoint and endpoint.endswith("/pulls"):
            sha = endpoint.split("/commits/")[1].split("/")[0]
            return json.dumps(PULLS[sha])
        if "/pulls/" in endpoint and endpoint.endswith("/commits"):
            number = int(endpoint.split("/pulls/")[1].split("/")[0])
            return json.dumps(PULL_COMMITS[number])
        if "/commits/" in endpoint:
            return json.dumps(COMMITS[endpoint.rsplit("/", 1)[1]])
        raise AssertionError(endpoint)

    return fake


@pytest.mark.technical
def test_parse_iso_datetime_handles_z_and_invalid_values():
    assert dora.parse_iso_datetime("2026-11-10T10:00:00Z") == at(10, 10)
    assert dora.parse_iso_datetime("2026-11-10T12:00:00+02:00") == at(10, 10)
    assert dora.parse_iso_datetime("not a date") is None
    assert dora.parse_iso_datetime(None) is None


@pytest.mark.technical
def test_job_timings_split_queue_and_execution():
    timings = dora.calculate_job_timings("2026-11-10T10:00:00Z", JOBS[1])
    assert timings["queue_minutes"] == 2.0
    assert timings["execution_minutes"] == 4.0


@pytest.mark.technical
def test_job_timings_without_jobs_are_empty():
    timings = dora.calculate_job_timings("2026-11-10T10:00:00Z", [])
    assert timings["queue_seconds"] is None
    assert timings["execution_seconds"] is None


@pytest.mark.technical
def test_classify_run_status():
    assert dora.classify_run_status("success") == "green"
    assert dora.classify_run_status("failure") == "red"
    assert dora.classify_run_status("timed_out") == "red"
    assert dora.classify_run_status("cancelled") == "cancelled"
    assert dora.classify_run_status("skipped") == "skipped"
    assert dora.classify_run_status(None) == "unknown"


@pytest.mark.technical
def test_earliest_commit_date_uses_minimum_and_fallback():
    assert dora.find_earliest_commit_date(PULL_COMMITS[7]) == at(10, 9)
    assert dora.find_earliest_commit_date([], fallback_dt=at(10, 8)) == at(10, 8)
    assert dora.find_earliest_commit_date([]) is None


@pytest.mark.technical
def test_mean_and_median_for_odd_even_and_empty_lists():
    assert dora.calculate_median([3.0, 1.0, 2.0]) == 2.0
    assert dora.calculate_median([4.0, 1.0, 2.0, 3.0]) == 2.5
    assert dora.calculate_mean([1.0, 2.0, 6.0]) == 3.0
    assert dora.calculate_mean([1.0, 2.0, 3.0, 4.0]) == 2.5
    assert dora.calculate_median([]) is None
    assert dora.calculate_mean([]) is None


@pytest.mark.technical
def test_deployment_frequency_per_week_and_active_day():
    green = [{"completed_at_dt": at(day, 10)} for day in (3, 3, 5, 5)]
    result = dora.calculate_deployment_frequency(green, at(1, 0), at(15, 0), UTC)
    assert result["weeks"] == 2.0
    assert result["per_week"] == 2.0
    assert result["active_days_count"] == 2
    assert result["per_active_day"] == 2.0


@pytest.mark.technical
def test_change_failure_rate_ignores_cancelled_and_skipped():
    statuses = ["green", "green", "green", "red", "cancelled", "skipped"]
    result = dora.calculate_change_failure_rate([{"classified_status": s} for s in statuses])
    assert result["total_completed"] == 4
    assert result["failure_rate_pct"] == 25.0
    assert result["cancelled_count"] == 1
    assert result["skipped_count"] == 1


@pytest.mark.technical
def test_time_to_restore_is_not_available_without_red_runs():
    runs = [{"classified_status": "green", "completed_at_dt": at(10, 10)}]
    result = dora.calculate_time_to_restore(runs)
    assert result["has_red"] is False
    assert result["median_minutes"] is None
    assert "н/д" in result["status_label"]


@pytest.mark.technical
def test_time_to_restore_measures_red_to_next_green():
    runs = [
        {"classified_status": "green", "completed_at_dt": at(10, 10)},
        {"classified_status": "red", "completed_at_dt": at(10, 12)},
        {"classified_status": "red", "completed_at_dt": at(10, 13)},
        {"classified_status": "green", "completed_at_dt": at(10, 14)},
    ]
    result = dora.calculate_time_to_restore(runs)
    assert result["mean_minutes"] == 90.0
    assert result["median_minutes"] == 90.0


@pytest.mark.technical
def test_lead_time_metrics_split_ci_time_and_lead_time():
    runs = [
        {"lead_time_minutes": 100.0, "lead_time_seconds": 6000.0, "queue_seconds": 600.0, "execution_seconds": 1800.0}
    ]
    result = dora.calculate_lead_time_metrics(runs)
    assert result["median_minutes"] == 100.0
    assert result["queue_share_pct"] == 25.0
    assert result["execution_share_pct"] == 75.0
    assert result["queue_of_lead_pct"] == 10.0
    assert result["execution_of_lead_pct"] == 30.0
    assert result["other_of_lead_pct"] == 60.0


@pytest.mark.technical
def test_dora_2025_categories_at_thresholds():
    assert dora.classify_lead_time_dora2025(59.9).startswith("<1 год")
    assert dora.classify_lead_time_dora2025(60.0).startswith("<1 доби")
    assert dora.classify_lead_time_dora2025(1440.0).startswith("доба–тиждень")
    assert dora.classify_lead_time_dora2025(10080.0).startswith("тиждень–місяць")
    assert dora.classify_lead_time_dora2025(43200.0) == ">1 місяця"
    assert dora.classify_lead_time_dora2025(None) == "н/д"
    assert dora.classify_failure_rate_dora2025(0.0).startswith("0–2%")
    assert dora.classify_failure_rate_dora2025(2.0).startswith("0–2%")
    assert dora.classify_failure_rate_dora2025(2.1).startswith("2–4%")
    assert dora.classify_failure_rate_dora2025(4.0).startswith("2–4%")
    assert dora.classify_failure_rate_dora2025(4.1).startswith("4–8%")
    assert dora.classify_failure_rate_dora2025(8.0).startswith("4–8%")
    assert dora.classify_failure_rate_dora2025(8.1).startswith("8–16%")
    assert dora.classify_failure_rate_dora2025(16.0).startswith("8–16%")
    assert dora.classify_failure_rate_dora2025(16.1).startswith("16–32%")
    assert dora.classify_failure_rate_dora2025(32.0).startswith("16–32%")
    assert dora.classify_failure_rate_dora2025(32.1).startswith("32–64%")
    assert dora.classify_failure_rate_dora2025(64.0).startswith("32–64%")
    assert dora.classify_failure_rate_dora2025(64.1) == ">64%"
    assert dora.classify_restore_time_dora2025(59.0).startswith("<1 год")
    assert dora.classify_restore_time_dora2025(60.0).startswith("<1 доби")
    assert dora.classify_restore_time_dora2025(1440.0).startswith("доба–тиждень")
    assert dora.classify_restore_time_dora2025(10080.0).startswith("тиждень–місяць")
    assert dora.classify_restore_time_dora2025(43200.0) == ">1 місяця"
    assert dora.classify_restore_time_dora2025(25 * 60.0).startswith("доба–тиждень")


@pytest.mark.technical
def test_parse_json_stream_accepts_objects_and_arrays():
    text = '[{"a": 1}]\n[{"a": 2}, {"a": 3}]\n{"a": 4}'
    assert [item["a"] for item in dora.parse_json_stream(text)] == [1, 2, 3, 4]
    assert dora.parse_json_stream("  ") == []


@pytest.mark.technical
def test_format_tz_label():
    assert dora.format_tz_label(2.0) == "UTC+2"
    assert dora.format_tz_label(-5.0) == "UTC-5"
    assert dora.format_tz_label(5.5) == "UTC+5.5"


@pytest.mark.technical
def test_detect_repo_prefers_explicit_value_and_fails_without_gh(monkeypatch):
    assert dora.detect_repo(" owner/repo ") == "owner/repo"

    def broken(args):
        raise RuntimeError("gh недоступний")

    monkeypatch.setattr(dora, "run_gh_cmd", broken)
    with pytest.raises(RuntimeError, match="--repo"):
        dora.detect_repo(None)


@pytest.mark.technical
def test_main_builds_report_and_anonymized_json(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(dora, "run_gh_cmd", make_fake_gh(calls))
    out = tmp_path / "docs" / "dora-auto.md"
    export = tmp_path / "evidence" / "runs.json"
    code = dora.main(
        [
            "--since",
            "2026-11-01",
            "--until",
            "2026-11-14",
            "--repo",
            "owner/repo",
            "--out",
            str(out),
            "--export-json",
            str(export),
        ]
    )
    assert code == 0
    assert any("created=2026-11-01..2026-11-14" in call for call in calls)

    report = out.read_text(encoding="utf-8")
    assert "| 1 | aaaaaaa | #7 | 10.11 11:00 | 10.11 12:06 | 2.0 | 4.0 | 66.0 | ✅ |" in report
    assert "| 2 | bbbbbbb | — | 10.11 13:50 | 10.11 14:05 | 1.0 | 4.0 | 15.0 | ❌ | без PR (прямий пуш) |" in report
    assert "повторний запуск (спроба 2)" in report
    assert "1 / 3 × 100% = 33.3%" in report
    assert "середнє 50.5 хв, медіана 50.5 хв" in report
    assert "середнє: 90.0 хв, медіана: 90.0 хв" in report
    assert "черга 78.0%, виконання 22.0%" in report

    payload = json.loads(export.read_text(encoding="utf-8"))
    assert [run["run_id"] for run in payload["runs"]] == [1, 2, 3]
    assert payload["runs"][0]["lead_time_minutes"] == 66.0
    assert "author" not in export.read_text(encoding="utf-8")


@pytest.mark.technical
def test_main_returns_error_codes(tmp_path, monkeypatch):
    out = str(tmp_path / "out.md")
    monkeypatch.setattr(dora, "run_gh_cmd", make_fake_gh([], runs=[]))
    assert dora.main(["--since", "2026-11-01", "--repo", "o/r", "--out", out]) == 1
    assert dora.main(["--since", "2026-11-10", "--until", "2026-11-01", "--repo", "o/r", "--out", out]) == 2
    assert dora.main(["--since", "not-a-date", "--repo", "o/r", "--out", out]) == 2

    def missing_gh(args):
        raise FileNotFoundError("gh")

    monkeypatch.setattr(dora, "run_gh_cmd", missing_gh)
    assert dora.main(["--since", "2026-11-01", "--repo", "o/r", "--out", out]) == 1
