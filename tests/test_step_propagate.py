from __future__ import annotations

from tests.utils_allure import run_pytest_and_collect


def _get_only_test(results):
    tests = results["results"]["tests"]
    assert len(tests) == 1
    return tests[0]


def test_propagate_true_marks_failed_but_does_not_raise() -> None:
    code = (
        "import allure\n"
        "def test_case():\n"
        "    with allure.step('S1', propagate=True):\n"
        "        try:\n"
        "            raise ValueError('boom')\n"
        "        except ValueError:\n"
        "            pass\n"
    )
    out = run_pytest_and_collect(code)
    assert out["exit_code"] == 0
    test = _get_only_test(out)
    assert test["status"] == "passed"
    assert test["steps"][0]["name"] == "S1"
    assert test["steps"][0]["status"] in {"failed", "broken"}


def test_propagate_true_with_raise_on_parent_reraises_after_context() -> None:
    code = (
        "import allure, pytest\n"
        "def test_case():\n"
        "    with pytest.raises(ValueError):\n"
        "        with allure.step('S1', propagate=True, raise_on_parent=True):\n"
        "            try:\n"
        "                raise ValueError('boom')\n"
        "            except ValueError:\n"
        "                pass\n"
    )
    out = run_pytest_and_collect(code)
    assert out["exit_code"] == 0
    test = _get_only_test(out)
    # Test itself passed under pytest.raises
    assert test["status"] == "passed"
    assert test["steps"][0]["status"] in {"failed", "broken"}


def test_nested_propagate_parent_does_not_fail_without_raise_on_parent() -> None:
    code = (
        "import allure\n"
        "def test_case():\n"
        "    with allure.step('P'):\n"
        "        with allure.step('C', propagate=True):\n"
        "            try:\n"
        "                raise RuntimeError('x')\n"
        "            except RuntimeError:\n"
        "                pass\n"
    )
    out = run_pytest_and_collect(code)
    assert out["exit_code"] == 0
    test = _get_only_test(out)
    parent = test["steps"][0]
    assert parent["status"] == "passed"
    assert parent["steps"][0]["name"] == "C" and parent["steps"][0]["status"] in {"failed", "broken"}


def test_propagate_on_success_is_noop() -> None:
    code = "import allure\n" "def test_case():\n" "    with allure.step('S1', propagate=True):\n" "        pass\n"
    out = run_pytest_and_collect(code)
    assert out["exit_code"] == 0
    test = _get_only_test(out)
    assert test["steps"][0]["status"] == "passed"
