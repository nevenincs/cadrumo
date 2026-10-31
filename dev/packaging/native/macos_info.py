"""The application's identity keys for ``Info.plist``, authored once for every consumer."""

from __future__ import annotations

import plistlib
from collections.abc import Mapping
from typing import Any

DESKTOP_INFO_PLIST_NAME = "desktop-info.plist"
"""File name, in the generated directory, of the identity-only property list the desktop embeds."""


def identity_keys(value: Mapping[str, str]) -> dict[str, Any]:
    """Return the keys that identify the application, whatever file carries them."""
    return {
        "CFBundleIdentifier": value["application_id"],
        "CFBundleName": value["name"],
        "CFBundleDisplayName": value["name"],
        "CFBundleShortVersionString": value["version"],
        "CFBundleVersion": value["version"],
        "LSMinimumSystemVersion": value["compatibility_floor"].removeprefix("macos-"),
        "LSApplicationCategoryType": "public.app-category.finance",
        "NSHighResolutionCapable": True,
    }


def render_identity_plist(value: Mapping[str, str]) -> bytes:
    """Serialize the identity keys alone: no executable, icon or package type."""
    return plistlib.dumps(identity_keys(value), sort_keys=True)
