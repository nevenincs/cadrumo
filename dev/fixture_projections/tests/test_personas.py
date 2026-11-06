"""The persona check reads every persona through the catalogue reader and the profile patch judge.

Each case copies one catalogue persona and the identity catalogue into
``tmp_path`` and plants one defect, so the check is shown to find an unknown
role, a year outside the envelope, an unknown wizard question and an unknown
schema field, and to pass the unmodified copy.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from dev._paths import REPO_ROOT

from ..personas import IDENTITIES_FILE, persona_findings
from ..registry import PERSONA_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_PERSONA = "asalariada-familia"


@pytest.fixture(scope="module")
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


def _catalogue(tmp_path: Path) -> Path:
    catalogue = tmp_path / "personas"
    catalogue.mkdir()
    shutil.copy2(REPO_ROOT / PERSONA_ROOT / IDENTITIES_FILE, catalogue / IDENTITIES_FILE)
    shutil.copytree(REPO_ROOT / PERSONA_ROOT / _PERSONA, catalogue / _PERSONA)
    return catalogue


def _plant(catalogue: Path, old: str, new: str) -> None:
    path = catalogue / _PERSONA / "persona.toml"
    text = path.read_text(encoding="utf-8")
    assert old in text, old
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def test_an_unmodified_persona_passes(tmp_path: Path, operation: PinnedAuthorityOperation) -> None:
    assert persona_findings(_catalogue(tmp_path), operation) == ()


@pytest.mark.parametrize(
    ("old", "new", "named"),
    [
        ('taxpayer = "asalariada.titular"', 'taxpayer = "asalariada.nadie"', "asalariada.nadie"),
        ('fiscal_year = "horizon-1"', 'fiscal_year = "horizon+3"', "outside the supported envelope"),
        ('fiscal_year = "horizon-1"', 'fiscal_year = "last-year"', "not a year token"),
        ("[profile]\n", '[profile]\n"no-such-question" = "x"\n', "the wizard refuses its answers"),
        ("[fields]\n", '[fields]\n"identity.no_such_field" = "x"\n', "identity.no_such_field"),
    ],
)
def test_a_planted_defect_is_found(
    tmp_path: Path, operation: PinnedAuthorityOperation, old: str, new: str, named: str
) -> None:
    catalogue = _catalogue(tmp_path)
    _plant(catalogue, old, new)

    findings = persona_findings(catalogue, operation)

    assert findings, "the planted defect was not found"
    assert any(named in finding for finding in findings), findings


def test_an_absent_catalogue_or_identity_file_is_a_finding(tmp_path: Path, operation: PinnedAuthorityOperation) -> None:
    assert persona_findings(tmp_path / "absent", operation) == (f"no persona catalogue at {tmp_path / 'absent'}",)
    catalogue = _catalogue(tmp_path)
    (catalogue / IDENTITIES_FILE).unlink()
    assert persona_findings(catalogue, operation)[0].startswith(IDENTITIES_FILE)
