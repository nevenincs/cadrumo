"""Admit unchanged preparation from current source and independently projected controls."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from .installation_plan import Preparation, project


def public_permissions(path: Path) -> bool:
    """Published Windows outputs must retain destination-inherited permissions."""
    if os.name != "nt":
        return True
    import win32security

    descriptor = win32security.GetNamedSecurityInfo(
        str(path), win32security.SE_FILE_OBJECT, win32security.DACL_SECURITY_INFORMATION
    )
    control, _ = descriptor.GetSecurityDescriptorControl()
    dacl = descriptor.GetSecurityDescriptorDacl()
    return (
        not control & win32security.SE_DACL_PROTECTED
        and dacl is not None
        and all(dacl.GetAce(index)[0][1] & win32security.INHERITED_ACE for index in range(dacl.GetAceCount()))
    )


def _permissions(root: Path, metadata: Path, plan: Preparation) -> None:
    from .installation import member

    for name, mode in plan.modes.items():
        path = member(root, name)
        if path.stat().st_mode & 0o7777 != mode or not public_permissions(path):
            raise ValueError(f"Installation member permissions changed: {name}")
    for directory in (root, metadata, *(item for item in root.rglob("*") if item.is_dir())):
        member(directory.parent, directory.name)
        if not public_permissions(directory):
            raise ValueError("Installation directory permissions changed")
    if os.name != "nt" and root.stat().st_mode & 0o7777 != 0o700:
        raise ValueError("Installation root permissions changed")


def existing(
    payload: Path,
    identity_file: Path,
    root: Path,
    metadata: Path,
    desktop: str | None,
    control_root: Path,
    *,
    allow_change: bool,
) -> bool:
    """Return currency only after actual source, stage and control admission.

    A receipt selects a candidate generation; it cannot establish expected bytes.
    Older preparations without a binding take the safe fresh migration path once.
    """
    from .installation import member, validate_payload, verify_inventory

    receipt_file = member(metadata, "installation.json")
    if not receipt_file.is_file():
        raise ValueError("Existing native installation stage has no owning receipt; select a fresh build directory")
    receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
    validate_payload(payload, identity_file, desktop)
    plan = project(payload, identity_file, desktop, control_root)
    recorded = receipt.get("preparation")
    # Bind the existing package manifest independently of a potentially edited
    # file inventory. A forged inventory cannot disguise a different package.
    anchors = [name for name in receipt["files"] if name.endswith("/data/package-manifest.json")]
    if len(anchors) != 1:
        raise ValueError("Installation receipt must identify exactly one package manifest")
    staged_manifest = member(root, anchors[0])
    if (
        isinstance(recorded, dict)
        and recorded.get("payload_manifest") != hashlib.sha256(staged_manifest.read_bytes()).hexdigest()
    ):
        raise ValueError("Installation package manifest changed from its preparation")
    current = bool(recorded == plan.identity)
    if current:
        source_manifest = json.loads(member(payload, "data/package-manifest.json").read_text(encoding="utf-8"))
        if (
            receipt.get("application_id") != source_manifest["build"]["application_id"]
            or receipt.get("staging_generation") != 1
        ):
            raise ValueError("Installation receipt identity or staging generation changed")
        expected_manifest = member(root, f"{plan.destination}/data/package-manifest.json")
        if expected_manifest.read_bytes() != member(payload, "data/package-manifest.json").read_bytes():
            raise ValueError("Installation package manifest differs from current source")
        if receipt["files"] != plan.files:
            raise ValueError("Installation inventory differs from current payload and controls")
        allowed = {"installation.json", "wix", *plan.metadata}
        if any(member(metadata, child.name).name not in allowed for child in metadata.iterdir()):
            raise ValueError("Installation metadata membership changed")
        for name, contents in plan.metadata.items():
            output = member(metadata, name)
            if output.read_bytes() != contents or not public_permissions(output):
                raise ValueError("Installation metadata changed")
        if not public_permissions(receipt_file):
            raise ValueError("Installation receipt permissions changed")
        _permissions(root, metadata, plan)
    elif not allow_change and (recorded is not None or receipt["files"] != plan.files):
        raise ValueError("Native installation stage differs from the requested payload; select a fresh build directory")
    # Full membership and bytes are checked against the independently projected
    # current map when currency matches, and the admitted prior owner otherwise.
    # Keep this last: no-copy return/publication retains the final stage boundary.
    verify_inventory(root, receipt_file)
    return current
