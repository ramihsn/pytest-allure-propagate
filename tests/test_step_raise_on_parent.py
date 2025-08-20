from __future__ import annotations

from tests.utils_allure import run_pytest_and_collect


def _get_only_test(results):
    tests = results["results"]["tests"]
    assert len(tests) == 1
    return tests[0]


def test_raise_on_parent_deferred_to_parent_exit_first_parent() -> None:
    code = (
        "import allure, pytest\n"
        "def test_case():\n"
        "    with pytest.raises(ValueError):\n"
        "        with allure.step('P', propagate=True, raise_on_parent=True):\n"
        "            with allure.step('C1', propagate=True):\n"
        "                try:\n"
        "                    raise ValueError('boom')\n"
        "                except ValueError:\n"
        "                    pass\n"
        "            with allure.step('C2'):\n"
        "                pass\n"
    )
    out = run_pytest_and_collect(code)
    print(out["stdout"])
    assert out["exit_code"] == 0
    test = _get_only_test(out)
    parent = test["steps"][0]
    assert parent["status"] in {"failed", "broken"}
    assert parent["steps"][0]["status"] in {"failed", "broken"}
    assert parent["steps"][1]["status"] == "passed"


def test_raise_on_parent_multiple_children_aggregated_by_parent_flag_only() -> None:
    code = (
        "import allure, pytest\n"
        "def test_case():\n"
        "    with pytest.raises(AssertionError):\n"
        "        with allure.step('P', propagate=True, raise_on_parent=True):\n"
        "            for i in range(2):\n"
        "                with allure.step(f'C{i+1}', propagate=True):\n"
        "                    try:\n"
        "                        assert False, f'e{i+1}'\n"
        "                    except AssertionError:\n"
        "                        pass\n"
    )
    out = run_pytest_and_collect(code)
    assert out["exit_code"] == 0
    test = _get_only_test(out)
    parent = test["steps"][0]
    assert parent["status"] in {"failed", "broken"}
    assert all(child["status"] in {"failed", "broken"} for child in parent["steps"])


def test_raise_on_parent_no_failures_no_raise() -> None:
    code = (
        "import allure\n"
        "def test_case():\n"
        "    with allure.step('P', propagate=True, raise_on_parent=True):\n"
        "        with allure.step('C1', propagate=True):\n"
        "            pass\n"
    )
    out = run_pytest_and_collect(code)
    assert out["exit_code"] == 0
    test = _get_only_test(out)
    parent = test["steps"][0]
    assert parent["status"] == "passed"
    assert parent["steps"][0]["status"] == "passed"


def test_raise_on_parent_without_parent_behaves_like_self_raise() -> None:
    code = (
        "import allure, pytest\n"
        "def test_case():\n"
        "    with pytest.raises(AssertionError):\n"
        "        with allure.step('C', propagate=True, raise_on_parent=True):\n"
        "            try:\n"
        "                assert False, 'x'\n"
        "            except AssertionError:\n"
        "                pass\n"
    )
    out = run_pytest_and_collect(code)
    assert out["exit_code"] == 0
    test = _get_only_test(out)
    # Test passed under pytest.raises; step should be marked failed
    assert test["steps"][0]["status"] in {"failed", "broken"}
