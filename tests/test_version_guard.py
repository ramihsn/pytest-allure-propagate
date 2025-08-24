from __future__ import annotations

import importlib
import sys
from typing import Any, Set

SUPPORTED_VERSIONS: Set[str] = {"2.13.3", "2.13.4"}


def _reload_plugin(monkeypatch: Any) -> Any:
    if "allure_pytest_ext.plugin" in sys.modules:
        del sys.modules["allure_pytest_ext.plugin"]
    import allure_pytest_ext.plugin as plugin  # type: ignore

    importlib.reload(plugin)
    return plugin


def test_version_guard_supported_set(monkeypatch: Any) -> None:
    monkeypatch.setenv("ALLURE_EXT_ALLOW_VERSION_MISMATCH", "")
    plugin = _reload_plugin(monkeypatch)
    assert getattr(plugin, "ALLURE_SUPPORTED_VERSIONS", set()) == SUPPORTED_VERSIONS


def test_version_guard_supported_set_even_if_env_set(monkeypatch: Any) -> None:
    monkeypatch.setenv("ALLURE_EXT_ALLOW_VERSION_MISMATCH", "1")
    import allure as allure_mod  # type: ignore

    monkeypatch.setattr(allure_mod, "__version__", "0.0.0", raising=False)
    plugin = _reload_plugin(monkeypatch)
    assert getattr(plugin, "ALLURE_SUPPORTED_VERSIONS", set()) == SUPPORTED_VERSIONS
