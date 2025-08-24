from __future__ import annotations

import importlib
import sys
import warnings
from typing import Any


def _reload_plugin(monkeypatch: Any) -> Any:
    if "allure_pytest_ext.plugin" in sys.modules:
        del sys.modules["allure_pytest_ext.plugin"]
    import allure_pytest_ext.plugin as plugin  # type: ignore

    importlib.reload(plugin)
    return plugin


def test_min_max_constants(monkeypatch: Any) -> None:
    plugin = _reload_plugin(monkeypatch)
    assert getattr(plugin, "_ALLURE_MIN_VERSION") == "2.13.3"
    assert getattr(plugin, "_ALLURE_MAX_VERSION") == "2.14.0"


def test_no_warning_for_versions_inside_range(monkeypatch: Any) -> None:
    plugin = _reload_plugin(monkeypatch)
    monkeypatch.setenv("ALLURE_EXT_ALLOW_VERSION_MISMATCH", "")
    monkeypatch.setattr(plugin.metadata, "version", lambda name: "2.13.3")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        plugin._monkey_patch_allure()
        assert not [wi for wi in w if issubclass(wi.category, RuntimeWarning)]

    monkeypatch.setattr(plugin.metadata, "version", lambda name: "2.14.0")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        plugin._monkey_patch_allure()
        assert not [wi for wi in w if issubclass(wi.category, RuntimeWarning)]


def test_warning_for_versions_outside_range(monkeypatch: Any) -> None:
    plugin = _reload_plugin(monkeypatch)
    monkeypatch.setenv("ALLURE_EXT_ALLOW_VERSION_MISMATCH", "")
    monkeypatch.setattr(plugin.metadata, "version", lambda name: "2.14.1")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        plugin._monkey_patch_allure()
        msgs = [str(wi.message) for wi in w if issubclass(wi.category, RuntimeWarning)]
        assert any("expected in [2.13.3, 2.14.0]" in m for m in msgs)


def test_env_override_suppresses_warning(monkeypatch: Any) -> None:
    plugin = _reload_plugin(monkeypatch)
    monkeypatch.setenv("ALLURE_EXT_ALLOW_VERSION_MISMATCH", "1")
    monkeypatch.setattr(plugin.metadata, "version", lambda name: "9.9.9")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        plugin._monkey_patch_allure()
        assert not [wi for wi in w if issubclass(wi.category, RuntimeWarning)]
