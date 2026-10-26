"""Installed M303 package and published authority identity guards."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, cast

from cadrumo.core.hashing import sha256_hex
from cadrumo.domain.calculations.registry.authority_store import (
    AUTHORITY_DESCRIPTOR_FILENAME,
    AuthorityDescriptor,
    AuthorityStoreError,
)
from dev.product_environment import clean_product_env

from .m303_evidence_contracts import IvaInstalledM303Error

if TYPE_CHECKING:
    pass


def _installed_identity(python: Path) -> tuple[str, str, str, str]:
    """Return (package version, __init__ path, __init__ sha256, bundled authority generation)."""
    probe = (
        "import json, importlib.metadata as m, importlib.resources as r, cadrumo;"
        "d=r.files('cadrumo').joinpath('_data','registry','authority','authority.current.json');"
        "print(json.dumps({'v': m.version('cadrumo'), 'init': cadrumo.__file__,"
        " 'gen': json.loads(d.read_bytes())['logical_generation']}))"
    )
    environment = clean_product_env()
    completed = subprocess.run(  # noqa: S603 - explicit acceptance interpreter
        [str(python), "-c", probe], check=True, capture_output=True, text=True, cwd=python.parent, env=environment
    )
    payload = cast(dict[str, str], json.loads(completed.stdout))
    init_path = Path(payload["init"]).resolve(strict=True)
    if "site-packages" not in init_path.parts:
        raise IvaInstalledM303Error("installed interpreter did not import cadrumo from site-packages")
    return payload["v"], str(init_path), sha256_hex(init_path.read_bytes()), payload["gen"]


def _authority(authority_root: Path) -> tuple[str, str]:
    descriptor_path = authority_root / AUTHORITY_DESCRIPTOR_FILENAME
    try:
        descriptor = AuthorityDescriptor.read(descriptor_path)
    except AuthorityStoreError as exc:
        raise IvaInstalledM303Error(f"authority descriptor is unavailable: {exc}") from exc
    return descriptor.logical_generation, sha256_hex(descriptor_path.read_bytes())
