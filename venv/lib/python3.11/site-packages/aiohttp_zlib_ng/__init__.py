__version__ = "0.0.0"

import importlib
import zlib as zlib_original
from typing import TYPE_CHECKING

import aiohttp

if TYPE_CHECKING:
    from zlib_ng import zlib_ng as best_zlib

try:
    from isal import (  # type: ignore
        isal_zlib as best_zlib,
    )
except ImportError:
    from zlib_ng import zlib_ng as best_zlib


TARGETS = (
    "compression_utils",
    "http_writer",
    "http_websocket",
    "http_writer",
    "http_parser",
    "multipart",
    "web_response",
)


def enable_zlib_ng() -> None:
    """Enable zlib-ng."""
    for location in TARGETS:
        try:
            importlib.import_module(f"aiohttp.{location}")
        except ImportError:
            continue
        if module := getattr(aiohttp, location, None):
            module.zlib = best_zlib


def disable_zlib_ng() -> None:
    """Disable zlib-ng and restore the original zlib."""
    for location in TARGETS:
        if module := getattr(aiohttp, location, None):
            module.zlib = zlib_original
