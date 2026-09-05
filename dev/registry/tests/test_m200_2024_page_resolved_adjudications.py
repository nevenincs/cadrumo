"""Contract tests for the page-resolved M200/2024 adjudication cohort.

The cohort's claim is narrow and mechanical: a record-qualified casilla names
its own page, the design is segmented by page, so the number resolves to one
cell. These prove the compiler actually enforces that rather than believing what
its receipt says.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..analysis import m200_2024_page_resolved_adjudications as subject

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_compiles_the_cohort_and_resolves_every_member_on_its_own_page() -> None:
    authority = subject.compile_m200_2024_page_resolved_authority()

    assert len(authority.adjudications) == 40
    assert all(":" in row.casilla_id for row in authority.adjudications), (
        "every member must be record-qualified; a bare number has no page to resolve on"
    )
    assert all(row.official_label.endswith(f"[{row.casilla_id.split(':')[-1]}]") for row in authority.adjudications)


def test_refuses_a_recorded_digest_that_the_design_does_not_produce(tmp_path) -> None:
    """The receipt is checked against the design, not trusted.

    This is what makes the file a receipt rather than the authority: a digest
    edited by hand -- or left behind when the design is re-pinned -- fails
    instead of being believed.
    """
    body = subject.ADJUDICATION_PATH.read_text(encoding="utf-8")
    target = tmp_path / "receipt.toml"
    original = subject.compile_m200_2024_page_resolved_authority().adjudications[0]
    target.write_text(body.replace(original.official_label_sha256, "0" * 64, 1), encoding="utf-8")

    with pytest.raises(RegistryValidationError, match="official label drifted"):
        subject.compile_m200_2024_page_resolved_authority(target)


def test_refuses_a_member_whose_declared_section_its_design_cell_contradicts(tmp_path) -> None:
    """Corroboration is the part a page cannot supply on its own.

    Resolving to one cell says WHICH cell the design puts the number in. It does
    not say the declaration agrees, and casilla 00067 is the standing proof that
    it sometimes does not. A member is admitted only when its declared section
    appears in the resolved cell's own path.
    """
    body = subject.ADJUDICATION_PATH.read_text(encoding="utf-8")
    target = tmp_path / "foreign.toml"
    # 00067 is the known contradiction: declared under an AIE/UTE section 6 the
    # 2024 design does not put it in.
    target.write_text(
        body.replace(
            '[[adjudications]]\ncasilla_id = "',
            '[[adjudications]]\ncasilla_id = "00067"\nofficial_label_sha256 = '
            '"a08fa03f71e2ab7a9c2c200df630ea298dc1347a18d0640fe6e9b998f4101469"\n\n'
            '[[adjudications]]\ncasilla_id = "',
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(RegistryValidationError, match="no record page|contradicts"):
        subject.compile_m200_2024_page_resolved_authority(target)
