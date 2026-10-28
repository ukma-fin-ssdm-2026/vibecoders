import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "check_traceability.py"
spec = importlib.util.spec_from_file_location("check_traceability", SCRIPT)
check_traceability = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_traceability)

RTM = "| Історія | Тип |\n|---|---|\n| US-001 | FR |\n| US-004 | FR |\n| SEC-003 | NFR |\n"


@pytest.fixture
def workspace(tmp_path):
    rtm = tmp_path / "rtm.md"
    rtm.write_text(RTM, encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    return rtm, tests


def write_test(tests, name, body):
    (tests / name).write_text("import pytest\n\n\n" + body, encoding="utf-8")


@pytest.mark.technical
def test_read_requirements_takes_ids_from_first_column(workspace):
    rtm, _ = workspace

    assert check_traceability.read_requirements(rtm) == ["US-001", "US-004", "SEC-003"]


@pytest.mark.technical
def test_check_passes_when_every_requirement_has_a_test_and_deferred_is_skipped(workspace):
    rtm, tests = workspace
    write_test(tests, "test_a.py", '@pytest.mark.requirement("US-001")\ndef test_a():\n    pass\n')
    write_test(tests, "test_b.py", '@pytest.mark.requirement("SEC-003")\ndef test_b():\n    pass\n')

    errors, _, _ = check_traceability.check(rtm, tests)

    assert errors == []


@pytest.mark.technical
def test_check_reports_requirement_without_tests(workspace):
    rtm, tests = workspace
    write_test(tests, "test_a.py", '@pytest.mark.requirement("US-001")\ndef test_a():\n    pass\n')

    errors, _, _ = check_traceability.check(rtm, tests)

    assert errors == ["вимога без жодного тесту: SEC-003"]


@pytest.mark.technical
def test_check_reports_test_without_requirement(workspace):
    rtm, tests = workspace
    write_test(tests, "test_a.py", '@pytest.mark.requirement("US-001", "SEC-003")\ndef test_a():\n    pass\n')
    write_test(tests, "test_b.py", "def test_b():\n    pass\n")

    errors, _, _ = check_traceability.check(rtm, tests)

    assert errors == ["тест без вимоги: test_b.py::test_b"]


@pytest.mark.technical
def test_check_reports_unknown_requirement_id(workspace):
    rtm, tests = workspace
    write_test(tests, "test_a.py", '@pytest.mark.requirement("US-001", "SEC-003", "US-099")\ndef test_a():\n    pass\n')

    errors, _, _ = check_traceability.check(rtm, tests)

    assert errors == ["тест test_a.py::test_a посилається на вимогу, якої немає в rtm.md: US-099"]


@pytest.mark.technical
def test_technical_mark_counts_as_declared_but_covers_nothing(workspace):
    rtm, tests = workspace
    write_test(tests, "test_a.py", '@pytest.mark.requirement("US-001", "SEC-003")\ndef test_a():\n    pass\n')
    write_test(tests, "test_b.py", "@pytest.mark.technical\ndef test_b():\n    pass\n")

    errors, _, found = check_traceability.check(rtm, tests)

    assert errors == []
    assert found["test_b.py::test_b"] == ([], True)


@pytest.mark.technical
def test_main_returns_nonzero_exit_code_on_gap(workspace, capsys, monkeypatch):
    rtm, tests = workspace
    write_test(tests, "test_a.py", '@pytest.mark.requirement("US-001")\ndef test_a():\n    pass\n')
    monkeypatch.setattr(check_traceability, "RTM_PATH", rtm)
    monkeypatch.setattr(check_traceability, "TESTS_DIR", tests)

    code = check_traceability.main()

    assert code == 1
    assert "вимога без жодного тесту: SEC-003" in capsys.readouterr().out
