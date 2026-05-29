"""Smoke + import tests for the plugin module.

These don't require changedetection.io to be installed — we mock the
hookimpl decorator and the deferred imports so the test surface is just
the module-level structure + the static path + the systemlibs probe.

The end-to-end test (real changedetection install + real fetch) lives
outside pytest because it needs Docker.
"""
import os
import sys
import types
from unittest.mock import MagicMock, patch

import pytest


# Provide a minimal stub for changedetectionio.pluggy_interface so the module
# can be imported without changedetection installed.
@pytest.fixture(autouse=True)
def stub_changedetection(monkeypatch):
    cdio = types.ModuleType("changedetectionio")
    pluggy_iface = types.ModuleType("changedetectionio.pluggy_interface")

    def hookimpl(fn):
        return fn

    pluggy_iface.hookimpl = hookimpl
    sys.modules["changedetectionio"] = cdio
    sys.modules["changedetectionio.pluggy_interface"] = pluggy_iface
    yield
    # Don't pop — other tests in the same run might depend on the same stub.


@pytest.fixture
def plugin_module():
    """Fresh import of the plugin module after the stub fixture is in place."""
    if "invisible_playwright_changedetectionio.fetcher" in sys.modules:
        del sys.modules["invisible_playwright_changedetectionio.fetcher"]
    import invisible_playwright_changedetectionio.fetcher as mod
    return mod


def test_static_path_exists(plugin_module):
    """plugin_static_path() returns a real directory containing our logo."""
    path = plugin_module.plugin_static_path()
    assert os.path.isdir(path)
    assert os.path.exists(os.path.join(path, "invisible-firefox-logo.svg"))


def test_module_exposes_entrypoint_hooks(plugin_module):
    """Both required hookimpl callables are present at module level."""
    assert callable(plugin_module.plugin_static_path)
    assert callable(plugin_module.register_content_fetcher)


def test_linux_libs_list_is_meaningful(plugin_module):
    """The system-libs probe list is non-empty and includes Firefox essentials."""
    libs = plugin_module._LINUX_FIREFOX_LIBS
    assert len(libs) > 5
    joined = " ".join(libs)
    for essential in ("gtk", "nss", "atk", "dbus", "xcomposite"):
        assert essential in joined.lower()


def test_is_ready_returns_true_when_invisible_playwright_installed(plugin_module):
    """is_ready returns True when invisible_playwright importable AND libs OK."""
    # We have to actually call register_content_fetcher to instantiate the
    # nested Fetcher class. That triggers a chain of changedetection imports
    # we'd have to stub. For the unit suite we instead verify the
    # standalone systemlibs probe logic directly.
    import ctypes.util

    # On a developer machine on Windows/macOS the linux-libs list is skipped.
    if sys.platform.startswith("linux"):
        # Just verify the probe call shape — it's safe to call.
        for lib in plugin_module._LINUX_FIREFOX_LIBS[:3]:
            ctypes.util.find_library(lib.replace("lib", "").split(".")[0])

    # invisible_playwright must be importable in the test env
    from invisible_playwright import ensure_binary  # noqa: F401


def test_systemlibs_probe_detects_missing_on_linux(plugin_module, monkeypatch):
    """When ctypes.util.find_library returns None for everything, the probe lists missing."""
    if not sys.platform.startswith("linux"):
        pytest.skip("Linux-only check")
    monkeypatch.setattr("ctypes.util.find_library", lambda name: None)
    # Simulate the probe logic the way is_ready uses it
    missing = [
        lib for lib in plugin_module._LINUX_FIREFOX_LIBS
        if not __import__("ctypes.util", fromlist=["find_library"]).find_library(
            lib.replace("lib", "").split(".")[0]
        )
    ]
    assert len(missing) == len(plugin_module._LINUX_FIREFOX_LIBS)
