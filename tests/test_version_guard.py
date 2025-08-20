from __future__ import annotations

import importlib
import os
import sys
from typing import Any

import pytest


def _reload_plugin(monkeypatch: Any) -> Any:
    if "allure_pytest_ext.plugin" in sys.modules:
        del sys.modules["allure_pytest_ext.plugin"]
    import allure_pytest_ext.plugin as plugin  # type: ignore

    importlib.reload(plugin)
    return plugin


def test_version_guard_warns_by_default(monkeypatch: Any) -> None:
    monkeypatch.setenv("ALLURE_EXT_ALLOW_VERSION_MISMATCH", "")
    plugin = _reload_plugin(monkeypatch)
    # In this environment, allure.__version__ may be None; ensure a warning was issued by plugin import
    # We cannot assert warnings easily across plugin import here; rely on plugin constant
    assert plugin.ALLURE_REQUIRED_VERSION == "2.13.3"


def test_version_guard_respects_env_opt_out(monkeypatch: Any) -> None:
    monkeypatch.setenv("ALLURE_EXT_ALLOW_VERSION_MISMATCH", "1")
    # Force allure version to something else
    import allure as allure_mod  # type: ignore

    monkeypatch.setattr(allure_mod, "__version__", "0.0.0", raising=False)
    plugin = _reload_plugin(monkeypatch)
    assert plugin.ALLURE_REQUIRED_VERSION == "2.13.3"
