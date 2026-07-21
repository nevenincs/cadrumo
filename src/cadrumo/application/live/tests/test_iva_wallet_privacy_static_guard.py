"""Static privacy guard for the live IVA wallet source surfaces."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_VALID_LOOKING_SPANISH_TAX_ID = re.compile(r"\b(?:[XYZ][0-9]{7}|[0-9]{8}|[ABCDEFGHJKLMNPQRSUVW][0-9]{7})[A-Z0-9]\b")
_LIVE_IVA_WALLET_SURFACES = (
    "src/cadrumo/application/live/__init__.py",
    "src/cadrumo/application/live/*iva_wallet*.py",
    "src/cadrumo/application/live/*iva_remote_state*.py",
    "src/cadrumo/adapters/outbound/aeat/sede/*iva_compensation_wallet*.py",
)


def test_live_iva_wallet_surfaces_do_not_commit_valid_looking_taxpayer_identifiers() -> None:
    """Live wallet source must not carry taxpayer-shaped literals."""

    offenders: list[str] = []
    for pattern in _LIVE_IVA_WALLET_SURFACES:
        for path in sorted(_PROJECT_ROOT.glob(pattern)):
            if not path.is_file():
                continue
            relative = path.relative_to(_PROJECT_ROOT).as_posix()
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if match := _VALID_LOOKING_SPANISH_TAX_ID.search(line):
                    offenders.append(f"{relative}:{line_number}: {match.group(0)}")

    assert offenders == []
