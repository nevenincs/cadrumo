"""Author dormant SMAppService metadata; never register unsigned login start.

Apple's bundled-agent convention uses Contents/Library/LaunchAgents and a
bundle-relative BundleProgram. Registration requires a separate signed native
implementation and runner evidence; merely carrying this plist starts nothing.
"""

from __future__ import annotations

import plistlib
import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from .identity import DistributionIdentity
from .layout import ApplicationImage


@dataclass(frozen=True)
class LaunchAgent:
    """Bundle-relative metadata destination and deterministic XML contents."""

    destination: PurePosixPath
    contents: bytes


def author_agent(identity: DistributionIdentity, manager: ApplicationImage) -> LaunchAgent:
    """Describe the accepted Aqua agent profile without asserting registration."""
    if not identity.target.startswith("macos-"):
        raise ValueError("A macOS target is required for LaunchAgent metadata")
    if not re.fullmatch(r"[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*", identity.manager_id):
        raise ValueError("Manager identity is not a safe launchd label")
    if (
        manager.target != "rust_manager"
        or manager.placement != "."
        or not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", manager.file)
        or manager.desktop
    ):
        raise ValueError("LaunchAgent requires the declared root-level manager image")
    program = f"Contents/MacOS/{manager.package_path}"
    metadata = {
        "Label": identity.manager_id,
        "BundleProgram": program,
        "ProgramArguments": [manager.file, "--sign-in"],
        "LimitLoadToSessionType": "Aqua",
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},
        "AbandonProcessGroup": True,
    }
    return LaunchAgent(
        PurePosixPath("Contents/Library/LaunchAgents") / f"{identity.manager_id}.plist",
        plistlib.dumps(metadata, fmt=plistlib.FMT_XML, sort_keys=True),
    )


def verify_agent(contents: bytes, identity: DistributionIdentity, manager: ApplicationImage) -> None:
    """Verify exact authored bytes, including types, without native acceptance."""
    if contents != author_agent(identity, manager).contents:
        raise ValueError("Bundled LaunchAgent metadata differs from its declared manager profile")
