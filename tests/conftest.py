"""Shared fixtures for the little_monkey tests.

The API client does not depend on Home Assistant. Its modules are loaded here
by file path, without running the integration `__init__.py`, so that these
tests run with only the packages of requirements_test.txt installed.
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
def api() -> types.ModuleType:
    """Return the api module of the integration."""
    _load("const")
    _load("utils")
    return _load("api")
