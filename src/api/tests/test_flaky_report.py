import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "flaky_report.py"
spec = importlib.util.spec_from_file_location("flaky_report", SCRIPT)
flaky_report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(flaky_report)


@pytest.fixture
def reports_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(flaky_report, "ROOT", tmp_path)
    directory = tmp_path / "reports"
    directory.mkdir()
    return directory


def write_junit(directory, filename, *testcases):
    content = "<testsuite>" + "".join(testcases) + "</testsuite>"
    (directory / filename).write_text(content, encoding="utf-8")


def xml_testcase(name, result=None):
    child = f"<{result}/>" if result else ""
    return f'<testcase classname="suite.TestExample" name="{name}">{child}</testcase>'


@pytest.mark.technical
def test_identical_repeats_report_no_flaky_tests(reports_dir, capsys):
    write_junit(reports_dir, "run1.xml", xml_testcase("test_ok"))
    write_junit(reports_dir, "run2.xml", xml_testcase("test_ok"))

    assert flaky_report.main([str(reports_dir)]) == 0

    output = capsys.readouterr().out
    assert "- Повторів: 2" in output
    assert "- Унікальних тестів: 1" in output
    assert "Нестабільних тестів не виявлено" in output


@pytest.mark.technical
def test_different_results_are_reported_as_flaky(reports_dir, capsys):
    write_junit(reports_dir, "run1.xml", xml_testcase("test_flaky"))
    write_junit(reports_dir, "run2.xml", xml_testcase("test_flaky", "failure"))

    assert flaky_report.main([str(reports_dir)]) == 0

    output = capsys.readouterr().out
    assert "| `suite.TestExample::test_flaky` | 1: passed, 2: failed |" in output


@pytest.mark.technical
def test_skipped_test_result_is_reported(reports_dir, capsys):
    write_junit(reports_dir, "run1.xml", xml_testcase("test_skipped", "skipped"))
    write_junit(reports_dir, "run2.xml", xml_testcase("test_skipped"))

    assert flaky_report.main([str(reports_dir)]) == 0

    assert "1: skipped, 2: passed" in capsys.readouterr().out


@pytest.mark.technical
def test_failure_in_every_repeat_is_reported_as_stable(reports_dir, capsys):
    write_junit(reports_dir, "run1.xml", xml_testcase("test_always_fails", "failure"))
    write_junit(reports_dir, "run2.xml", xml_testcase("test_always_fails", "failure"))

    assert flaky_report.main([str(reports_dir)]) == 0

    output = capsys.readouterr().out
    assert "Нестабільних тестів не виявлено" in output
    assert "`suite.TestExample::test_always_fails` — failed у всіх повторах" in output


@pytest.mark.technical
def test_missing_junit_files_return_one(reports_dir, capsys):
    assert flaky_report.main([str(reports_dir)]) == 1
    assert "JUnit XML-файлів run*.xml не знайдено" in capsys.readouterr().err


@pytest.mark.technical
def test_directory_outside_root_is_rejected_without_reading(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    write_junit(outside, "run1.xml", xml_testcase("test_untrusted"))
    monkeypatch.setattr(flaky_report, "ROOT", root)
    monkeypatch.setattr(flaky_report.ET, "parse", lambda *_: pytest.fail("XML поза коренем не має читатися"))

    assert flaky_report.main([str(outside)]) == 1
