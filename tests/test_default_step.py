from __future__ import annotations

from tests.utils_allure import run_pytest_and_collect


def _get_only_test(results):
    tests = results["results"]["tests"]
    assert len(tests) == 1
    return tests[0]


def test_step_passes_no_exception() -> None:
    code = "import allure\n" "def test_case():\n" "    with allure.step('S1'):\n" "        pass\n"
    out = run_pytest_and_collect(code)
    assert out["exit_code"] == 0
    test = _get_only_test(out)
    assert test["status"] == "passed"
    assert [s["name"] for s in test["steps"]] == ["S1"]
    assert test["steps"][0]["status"] == "passed"


def test_step_fails_on_uncaught_exception() -> None:
    code = "import allure\n" "def test_case():\n" "    with allure.step('S1'):\n" "        raise Exception('boom')\n"
    out = run_pytest_and_collect(code)
    assert out["exit_code"] != 0
    test = _get_only_test(out)
    assert test["status"] in {"failed", "broken"}
    assert test["steps"][0]["name"] == "S1"
    assert test["steps"][0]["status"] in {"failed", "broken"}


def test_step_green_when_exception_caught_inside() -> None:
    code = (
        "import allure\n"
        "def test_case():\n"
        "    with allure.step('S1'):\n"
        "        try:\n"
        "            raise Exception('x')\n"
        "        except Exception:\n"
        "            pass\n"
    )
    out = run_pytest_and_collect(code)
    assert out["exit_code"] == 0
    test = _get_only_test(out)
    assert test["status"] == "passed"
    assert test["steps"][0]["status"] == "passed"


def test_nested_steps_uncaught_bubbles() -> None:
    code = (
        "import allure\n"
        "def test_case():\n"
        "    with allure.step('P'):\n"
        "        with allure.step('C'):\n"
        "            raise Exception('x')\n"
    )
    out = run_pytest_and_collect(code)
    assert out["exit_code"] != 0
    test = _get_only_test(out)
    assert test["status"] in {"failed", "broken"}
    parent = test["steps"][0]
    assert parent["name"] == "P"
    assert parent["status"] in {"failed", "broken"}
    assert parent["steps"][0]["name"] == "C"
    assert parent["steps"][0]["status"] in {"failed", "broken"}


def test_attachments_do_not_affect_status() -> None:
    code = (
        "import allure\n"
        "def test_case():\n"
        "    with allure.step('S1'):\n"
        "        allure.attach('hello', 'note', 'text/plain')\n"
    )
    out = run_pytest_and_collect(code)
    assert out["exit_code"] == 0
    test = _get_only_test(out)
    assert test["steps"][0]["name"] == "S1"
    assert test["steps"][0]["status"] == "passed"
