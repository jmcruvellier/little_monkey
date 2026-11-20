"""Checks that the version is the same wherever it is written."""
from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).parent.parent
COMPONENT_DIR = ROOT / "custom_components" / "little_monkey"


def test_version_is_consistent():
    """const.py, manifest.json and CHANGELOG.md give the same version."""
    manifest = json.loads((COMPONENT_DIR / "manifest.json").read_text("utf-8"))
    version = manifest["version"]

    const = (COMPONENT_DIR / "const.py").read_text("utf-8")
    assert re.search(r'^VERSION = "(.+)"$', const, re.MULTILINE).group(1) == version

    # The documentation link points to the tag of the release
    assert f"/blob/v{version}/" in manifest["documentation"]

    # The first version of the changelog, after the changes not released yet
    changelog = (ROOT / "CHANGELOG.md").read_text("utf-8")
    titles = re.findall(r"^## (.+)$", changelog, re.MULTILINE)
    assert [title for title in titles if title != "Non publié"][0] == version
