"""Tests for the M145 situacion-familiar trinary axis.

Per the M145 form (BOE-A-2011-208, RIRPF art. 88), box 1 carries a
3-value family-situation axis distinct from the Art. 82 LIRPF conjunta
trinary :class:`SituacionFamiliar`. The eligibility test for the RIRPF
art. 81.1 supplementary withholding reduction is a pure function of the
chosen option.
"""

from __future__ import annotations

import pytest

from ..renta_codes import SituacionFamiliarM145

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_three_form_numbered_values() -> None:
    """The enum mirrors the three numbered boxes on the M145 form."""
    assert {member.value for member in SituacionFamiliarM145} == {
        "familia_1",
        "familia_2",
        "familia_3",
    }


def test_familia_1_eligible_for_supplementary_reduction() -> None:
    """RIRPF art. 81.1.1° viudo/separado with descendientes -> eligible."""
    assert SituacionFamiliarM145.FAMILIA_1.is_eligible_for_supplementary_reduction()


def test_familia_2_eligible_for_supplementary_reduction() -> None:
    """RIRPF art. 81.1.2° casado with low-income spouse -> eligible."""
    assert SituacionFamiliarM145.FAMILIA_2.is_eligible_for_supplementary_reduction()


def test_familia_3_not_eligible_for_supplementary_reduction() -> None:
    """Default option -> no supplementary withholding reduction."""
    assert not SituacionFamiliarM145.FAMILIA_3.is_eligible_for_supplementary_reduction()


def test_disjoint_from_situacion_familiar_art82() -> None:
    """The M145 trinary MUST NOT share members with the Art. 82 conjunta enum.

    Sharing names would invite operator/registry confusion between the
    Art. 81 withholding axis (M145) and the Art. 82 conjunta axis
    (declaracion). The grounding rule in the docstring depends on these
    enums being structurally distinct.
    """
    from ..renta_codes import SituacionFamiliar

    m145_values = {member.value for member in SituacionFamiliarM145}
    art82_values = {member.value for member in SituacionFamiliar}
    assert not (m145_values & art82_values)


def test_reachable_at_its_owning_module() -> None:
    """The enum is public on the module that declares it.

    This asserted a re-export through the package namespace until that
    namespace was made inert. What it protects -- that the enum is reachable
    from outside the package -- is unchanged; the address is now the module
    that owns it rather than the package root.
    """
    from .. import renta_codes

    assert renta_codes.SituacionFamiliarM145 is SituacionFamiliarM145
