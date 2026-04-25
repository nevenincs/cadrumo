"""Closed-catalogue tests for :class:`LegalCitationSource` (#339).

The issue mandates that ``LegalCitation.source`` be constrained to a
recognised enum value with no freeform strings. The existing
:class:`LegalCitationSource` :class:`enum.StrEnum` already satisfies
this contract — these tests serve as living documentation of the
constraint and a regression guard against any future widening of the
field type to ``str``.

The handover prompt's proposed catalogue (BOE / RD / Orden / Directiva
UE / LIRPF / LIVA / LIS / RIRPF / RIVA / RIS / LGT) conflates source-
kind (BOE, RD, Orden, Directiva UE) with individual norms (LIRPF, LIVA,
LIS, …). The shipped enum uses the source-kind axis: an LIRPF citation
is ``(source=LEY, article="99")``; a RIRPF citation is
``(source=REGLAMENTO, article="110")``. ``DIRECTIVA_UE`` is not a
member because zero landed rulesets cite an EU directive directly —
adding it now would be premature.
"""

from __future__ import annotations

from datetime import date
from typing import cast

import pytest
from pydantic import ValidationError

from . import LegalCitation, LegalCitationSource

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]


def _build(source: LegalCitationSource | str) -> LegalCitation:
    """Build a :class:`LegalCitation` with the supplied ``source`` value.

    The ``source`` parameter accepts a deliberately-loose
    ``LegalCitationSource | str`` so the negative-path tests can pass
    freeform strings without violating the call-site signature. The
    runtime constructor is strict and refuses any non-enum input —
    that's the contract under test.
    """
    return LegalCitation(
        source=cast(LegalCitationSource, source),
        article="1",
        url=None,
        quoted_text_es=(
            "Fixture-only quotation for the source-enum closure tests; not authored as a binding ruleset reference."
        ),
        retrieval_date=date(2026, 4, 25),
        is_curated_summary=True,
    )


def test_every_enum_member_accepted_as_source() -> None:
    """Every :class:`LegalCitationSource` member constructs cleanly.

    Locks the closed catalogue: any future addition / removal forces
    this test to fail and the change to be documented.
    """
    expected_members = {
        LegalCitationSource.LEY,
        LegalCitationSource.REAL_DECRETO,
        LegalCitationSource.ORDEN_MINISTERIAL,
        LegalCitationSource.REGLAMENTO,
        LegalCitationSource.MANUAL_PRACTICO,
        LegalCitationSource.BOE,
    }
    actual_members = set(LegalCitationSource)
    assert actual_members == expected_members
    for member in expected_members:
        citation = _build(member)
        assert citation.source is member


def test_freeform_string_source_rejected() -> None:
    """A non-member string value for ``source`` raises ``ValidationError``."""
    with pytest.raises(ValidationError):
        _build("convenio")


def test_string_canonical_value_rejected_in_strict_mode() -> None:
    """A canonical enum-value string is still rejected in strict mode.

    :class:`LegalCitation` is declared ``strict=True``, so even a
    string that exactly matches an enum member's canonical value
    (``"ley"`` vs :data:`LegalCitationSource.LEY`) is refused. This
    is the tightest constraint available — only true enum instances
    pass — and is the behaviour locked by the modelo-inventory ADR.
    """
    with pytest.raises(ValidationError):
        _build("ley")


def test_unrecognised_directiva_ue_string_rejected() -> None:
    """A non-member canonical-shape string still raises.

    Documents the deliberate omission of ``DIRECTIVA_UE``: zero
    landed rulesets cite an EU directive directly, so adding the
    member would be premature. If a future ruleset (e.g. Modelo 369
    OSS / IOSS) needs the citation, it lands as a single enum
    addition with no further architectural commitment.
    """
    with pytest.raises(ValidationError):
        _build("directiva_ue")
