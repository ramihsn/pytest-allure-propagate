from __future__ import annotations

from tests.utils_allure import run_pytest_and_collect


def _get_only_test(results):
    tests = results["results"]["tests"]
    assert len(tests) == 1
    return tests[0]


def test_aggregate_runs_all_children_then_fails_if_any_failed() -> None:
    code = (
        "import allure, pytest\n"
        "def test_case():\n"
        "    with pytest.raises(Exception):\n"
        "        with allure.aggregate_step('A'):\n"
        "            with allure.step('C1'):\n"
        "                pass\n"
        "            with allure.step('C2'):\n"
        "                raise AssertionError('e2')\n"
        "            with allure.step('C3'):\n"
        "                pass\n"
    )
    out = run_pytest_and_collect(code)
    assert out["exit_code"] == 0
    test = _get_only_test(out)
    A = test["steps"][0]
    assert A["name"] == "A" and A["status"] in {"failed", "broken"}
    assert [s["status"] for s in A["steps"]] == ["passed", "failed", "passed"]


def test_aggregate_all_passes() -> None:
    code = (
        "import allure\n"
        "def test_case():\n"
        "    with allure.aggregate_step('A'):\n"
        "        with allure.step('C1'):\n"
        "            pass\n"
        "        with allure.step('C2'):\n"
        "            pass\n"
    )
    out = run_pytest_and_collect(code)
    assert out["exit_code"] == 0
    test = _get_only_test(out)
    A = test["steps"][0]
    assert A["status"] == "passed"
    assert [s["status"] for s in A["steps"]] == ["passed", "passed"]


def test_aggregate_collects_multiple_failures_message_contains_both() -> None:
    code = (
        "import allure, pytest\n"
        "def test_case():\n"
        "    with pytest.raises(Exception) as excinfo:\n"
        "        with allure.aggregate_step('A'):\n"
        "            with allure.step('C1'):\n"
        "                raise AssertionError('e1')\n"
        "            with allure.step('C2'):\n"
        "                raise RuntimeError('e2')\n"
        "    assert 'e1' in str(excinfo.value) and 'e2' in str(excinfo.value)\n"
    )
    out = run_pytest_and_collect(code)
    assert out["exit_code"] == 0
    test = _get_only_test(out)
    A = test["steps"][0]
    assert A["status"] in {"failed", "broken"}
    assert [s["status"] for s in A["steps"]] == ["failed", "failed"]


def test_nested_aggregate_inside_aggregate() -> None:
    code = (
        "import allure, pytest\n"
        "def test_case():\n"
        "    with pytest.raises(Exception):\n"
        "        with allure.aggregate_step('A'):\n"
        "            with allure.aggregate_step('B'):\n"
        "                with allure.step('C1'):\n"
        "                    raise AssertionError('x')\n"
        "            with allure.step('C2'):\n"
        "                pass\n"
    )
    out = run_pytest_and_collect(code)
    assert out["exit_code"] == 0
    test = _get_only_test(out)
    A = test["steps"][0]
    assert A["name"] == "A"
    # A failed due to inner B failure; B failed; C2 passed
    assert A["status"] in {"failed", "broken"}
    assert A["steps"][0]["name"] == "B" and A["steps"][0]["status"] == "failed"
    assert A["steps"][1]["name"] == "C2" and A["steps"][1]["status"] == "passed"


def test_aggregate_with_child_propagate_true_does_not_abort_siblings() -> None:
    code = (
        "import allure, pytest\n"
        "def test_case():\n"
        "    with pytest.raises(Exception):\n"
        "        with allure.aggregate_step('A'):\n"
        "            with allure.step('C1', propagate=True):\n"
        "                try:\n"
        "                    raise AssertionError('boom')\n"
        "                except AssertionError:\n"
        "                    pass\n"
        "            with allure.step('C2'):\n"
        "                pass\n"
    )
    out = run_pytest_and_collect(code)
    assert out["exit_code"] == 0
    test = _get_only_test(out)
    A = test["steps"][0]
    assert A["status"] in {"failed", "broken"}
    assert [s["status"] for s in A["steps"]] == ["failed", "passed"]


def test_mixing_raise_on_parent_inside_aggregate_defers_and_raises_once() -> None:
    code = (
        "import allure, pytest\n"
        "def test_case():\n"
        "    with pytest.raises(Exception):\n"
        "        with allure.aggregate_step('A'):\n"
        "            with allure.step('C1', propagate=True, raise_on_parent=True):\n"
        "                try:\n"
        "                    raise AssertionError('e1')\n"
        "                except AssertionError:\n"
        "                    pass\n"
        "            with allure.step('C2', propagate=True, raise_on_parent=True):\n"
        "                try:\n"
        "                    raise RuntimeError('e2')\n"
        "                except RuntimeError:\n"
        "                    pass\n"
    )
    out = run_pytest_and_collect(code)
    assert out["exit_code"] == 0
    test = _get_only_test(out)
    A = test["steps"][0]
    assert A["status"] in {"failed", "broken"}
    assert [s["status"] for s in A["steps"]] == ["failed", "failed"]
