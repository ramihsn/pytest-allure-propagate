allure-pytest-ext
==================

Extensions for `allure-pytest` focused on test ergonomics and clear reporting.

This plugin adds two capabilities on top of Allure's standard API:

- `with allure.step(title, propagate=True, ...)`: make steps fail even if exceptions inside are caught by user code; optionally re-raise on the parent after the step finishes.
- `with allure.aggregate_step(title)`: run all child steps and aggregate failures into a single error raised at the end.

Links
-----

- Live Allure demo report (GitHub Pages): [pytest-allure-propagate report](https://ramihsn.github.io/pytest-allure-propagate/)
- The demo report is generated automatically on tag creation (release workflow), and can also be built manually via the "Allure Pages" workflow.
- Official Allure docs: `https://allurereport.org`
- Allure pytest page on PyPI: `https://pypi.org/project/allure-pytest/`

Installation
------------

Official (uv)

```bash
uv add allure-pytest-ext
```

Alternative (pip)

```bash
pip install allure-pytest-ext
```

Compatibility
-------------

- Python: 3.8 – 3.13
- Allure pytest adapter: designed for `allure-pytest` versions 2.13.3–2.13.4.
  At runtime, the plugin emits a warning if the installed `allure-pytest` version is outside this range.

Quick start
-----------

1) Write tests using the plugin’s features where they add value in your flow.

```python
import pytest
import allure


def test_propagate_caught_error() -> None:
    # Your code catches the error locally, but you still want the step to fail
    # and the error to surface at the test level.
    with allure.step('parnet-step')
        try:
            with allure.step("child-step", propagate=True):
                raise ValueError("missing required field: id")
        except Exception:
            ...
            # Not only the child-step will apper red,
            # also the parnet-step will apper yellow, but It won't raise an expecptiom


def test_aggregate_sibling_failures() -> None:
    # Run independent checks and see all failures together rather than failing fast.
    with allure.aggregate_step("check downstream services"):
        with allure.step("service A health"):
            raise RuntimeError("timeout")
        with allure.step("service B schema"):
            ... # this step will run
        # now the step `check downstream services` will rise the expection
```

2) Run tests and generate Allure results folder.

```bash
uv run pytest --alluredir=.allure-results --ignore=tests/test_mock.py
# or
pytest --alluredir=.allure-results --ignore=tests/test_mock.py
```

3) Serve the report locally.

```bash
allure serve .allure-results
```

4) Optional: log step start/end in test logs

Enable source logger messages for step START/END via any of the following:

```bash
pytest --alluredir=.allure-results --ignore=tests/test_mock.py --allure-log-steps
```

```ini
# pytest.ini
allure_log_steps = true
```

```bash
ALLURE_EXT_LOG_STEPS=1 pytest --alluredir=.allure-results --ignore=tests/test_mock.py
```

API additions
-------------

- `allure.step(title: str, propagate: bool = False, raise_on_parent: bool = False)`
  - `propagate=True`: if any exception occurs inside the step and is caught by test code, the step is still marked failed.
  - `raise_on_parent=True`: when used together with `propagate=True`, re-raise the first observed exception after the step exits (affects the parent scope).

- `allure.aggregate_step(title: str)`
  - Executes all nested steps even if some fail. At the end, raises an aggregated error comprising all child failures.
  - The aggregated error type is `allure_pytest_ext.plugin.AggregateError`.

Configuration
-------------

- Source logger step events (START/END) can be enabled via any of:
  - CLI: `--allure-log-steps`
  - pytest.ini: `allure_log_steps = true`
  - Env: `ALLURE_EXT_LOG_STEPS=1` (or `ALLURE_LOG_STEPS=1`)

- Debug tracing (prints when exceptions are seen inside steps):
  - Env: `ALLURE_EXT_DEBUG_TRACE=1`

Development
-----------

```bash
# Setup dev environment
uv sync --all-extras --dev

# Lint, type-check, test
uv run black --check src tests
uv run flake8 src tests
uv run mypy --strict src tests
uv run pytest -q --ignore=tests/test_mock.py
```

License
-------

MIT
