allure-pytest-ext
==================

Extensions for `allure-pytest==2.13.3` adding:

- `with allure.step("...", propagate=True)`: if any exception happens inside the step and is caught by user code,
  the step still fails and the original error re-raises after the step exits (unless running inside an aggregate step).
- `with allure.aggregate_step("...")`: runs all child steps even if some fail; after all children finish, raises a single
  aggregated exception if any child failed.

Requirements
------------

- Python 3.8+
- `allure-pytest==2.13.3`
- Managed with `uv`

Install
-------

```bash
uv add allure-pytest-ext
```

Usage
-----

```python
import allure

# Propagating a caught error
with pytest.raises(ValueError):
    with allure.step("propagate caught", propagate=True):
        try:
            raise ValueError("boom")
        except ValueError:
            pass  # The step fails and the error is re-raised after the step ends

# Aggregating child failures
with pytest.raises(Exception):
    with allure.aggregate_step("aggregate children"):
        with allure.step("child 1"):
            raise ValueError("first")
        with allure.step("child 2"):
            raise RuntimeError("second")
```

Development
-----------

```bash
uv sync --all-extras --dev
uv run pytest -q
uv run black --check src tests
uv run flake8 src tests
uv run mypy --strict src tests
```


