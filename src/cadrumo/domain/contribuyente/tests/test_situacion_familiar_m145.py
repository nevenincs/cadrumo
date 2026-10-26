"""Tests for the M145 situacion-familiar trinary axis.

Per the M145 form (BOE-A-2011-208, RIRPF art. 88), box 1 carries a
3-value family-situation axis distinct from the Art. 82 LIRPF conjunta
trinary :class:`SituacionFamiliar`. The eligibility test for the RIRPF
art. 81.1 supplementary withholding reduction is a pure function of the
chosen option.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.situacion_familiar_catalogue import situacion_familiar_choices
from cadrumo.domain.calculations.registry.situacion_familiar_m145_catalogue import (
    resolve_situacion_familiar_m145_catalogue,
)
from cadrumo.domain.calculations.registry.tests.published_authority import PublishedGovernedFactSource

from ..renta_codes import SituacionFamiliarM145

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_AUTHORITY = PublishedGovernedFactSource()
_M145_CATALOGUE = resolve_situacion_familiar_m145_catalogue(authority=_AUTHORITY)


def test_three_form_numbered_values() -> None:
    """The enum mirrors the three numbered boxes on the M145 form."""
    assert {member.value for member in _M145_CATALOGUE.choices} == {
        "familia_1",
        "familia_2",
        "familia_3",
    }


def test_disjoint_from_situacion_familiar_art82() -> None:
    """The M145 trinary MUST NOT share members with the Art. 82 conjunta enum.

    Sharing names would invite operator/registry confusion between the
    Art. 81 withholding axis (M145) and the Art. 82 conjunta axis
    (declaracion). The grounding rule in the docstring depends on these
    enums being structurally distinct.
    """

    m145_values = {member.value for member in _M145_CATALOGUE.choices}
    art82_values = {member.value for member in situacion_familiar_choices(authority=_AUTHORITY)}
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
