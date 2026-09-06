"""Static privacy guard for the live IVA wallet source surfaces."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: The repository root. `parents[5]`, counting tests -> live -> application ->
#: cadrumo -> src -> repo. It was `parents[4]`, which lands on `src/`, so every
#: pattern below resolved under `src/src/cadrumo/...` and matched nothing: the
#: guard scanned ZERO files and passed. Proven by injecting a valid-looking NIF
#: into each target -- as written it found none, corrected it found all four.
_PROJECT_ROOT = Path(__file__).resolve().parents[5]

#: Floor for the surfaces this guard must actually read. The path bug above was
#: silent precisely because a glob matching nothing is indistinguishable from a
#: clean sweep, and this is a taxpayer-identifier boundary: the failure mode is
#: a committed NIF nobody sees. Asserting the sweep REACHED something is what
#: turns a future rename or move into a red gate instead of a quiet pass.
_MINIMUM_SCANNED_SURFACES = 4
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
    scanned: list[str] = []
    for pattern in _LIVE_IVA_WALLET_SURFACES:
        for path in sorted(_PROJECT_ROOT.glob(pattern)):
            if not path.is_file():
                continue
            relative = path.relative_to(_PROJECT_ROOT).as_posix()
            scanned.append(relative)
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if match := _VALID_LOOKING_SPANISH_TAX_ID.search(line):
                    offenders.append(f"{relative}:{line_number}: {match.group(0)}")

    assert len(scanned) >= _MINIMUM_SCANNED_SURFACES, (
        f"the privacy guard reached only {len(scanned)} file(s) under {_PROJECT_ROOT}: "
        f"{scanned}. A sweep that matches nothing reports the same green as a clean one, "
        "and this one guards committed taxpayer identifiers."
    )
    assert offenders == []
