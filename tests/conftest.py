"""Shared fixtures for the little_monkey tests.

The API client does not depend on Home Assistant. Its modules are loaded here
by file path, without running the integration `__init__.py`, so that these
tests run with only the packages of requirements_test.txt installed.

The tests of the `ha` folder run the integration inside a Home Assistant
core. They are collected only when pytest-homeassistant-custom-component is
installed (requirements_test_ha.txt).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types

import pytest

COMPONENT_DIR = (
    Path(__file__).parent.parent / "custom_components" / "little_monkey"
)
PACKAGE = "little_monkey_under_test"

HOME_ASSISTANT_TESTS = (
    importlib.util.find_spec("pytest_homeassistant_custom_component") is not None
)
if not HOME_ASSISTANT_TESTS:
    collect_ignore = ["ha"]
elif sys.platform == "win32":
    # On Windows the asyncio event loop needs a socket pair, which the Home
    # Assistant test plugin forbids. No test uses the network.
    import pytest_socket

    pytest_socket.disable_socket = lambda *args, **kwargs: None
    pytest_socket.socket_allow_hosts = lambda *args, **kwargs: None


def _load(name: str) -> types.ModuleType:
    """Load a module of the integration as a submodule of a bare package."""
    full_name = f"{PACKAGE}.{name}"
    if full_name in sys.modules:
        return sys.modules[full_name]
    if PACKAGE not in sys.modules:
        package = types.ModuleType(PACKAGE)
        package.__path__ = [str(COMPONENT_DIR)]
        sys.modules[PACKAGE] = package
    spec = importlib.util.spec_from_file_location(
        full_name, COMPONENT_DIR / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def utils() -> types.ModuleType:
    """Return the utils module of the integration."""
    return _load("utils")


@pytest.fixture(scope="session")
def api() -> types.ModuleType:
    """Return the api module of the integration."""
    _load("const")
    _load("utils")
    return _load("api")
