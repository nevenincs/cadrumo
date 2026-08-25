"""Profile facts reach the exported declaration under AEAT's dictionary field ids.

The bindings under test are read from the real bundled Modelo 100 revision rather
than hand-built, so a registry edit that changes a selector, a format, or a
precondition is felt here rather than silently agreed with.

The taxpayer facts ARE hand-built, and that is the point: these cases are about
which declared slots get written and with what, not about any particular
person's return. A fact set assembled here can be pointed at exactly the case
under test -- a spouse present but a filing that is individual, a name whose
second part is blank -- which a captured profile cannot.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest

from ....core import BindingSourceKind, Modelo
from ....core.resources import resources
from cadrumo.domain.calculations.registry.schema import DataBindingDefinition
from ....domain.user_profile.loader import load_user_profile_schema
from .._profile_export_binding import compose_legal_full_name, resolve_profile_export_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "d24bdc40-1623-4255-a9c3-a4b5c34dd9bb"  # was 'bucket-under-test'


@dataclass(frozen=True)
class _Fact:
    path: str
    value: object


@dataclass(frozen=True)
class _Record:
    facts: tuple[_Fact, ...]


def _export_bindings() -> tuple[DataBindingDefinition, ...]:
    """The real Modelo 100 2024 profile bindings that carry an export address."""
    snapshot = resources().modelos.authority.snapshot(
        Modelo.M100.value,
        filing_year=2024,
        period="0A",
    )
    return tuple(
        binding
        for binding in snapshot.revision.bindings
        if binding.source == BindingSourceKind.PROFILE
        and getattr(binding.selector, "dictionary_field", None) is not None
    )


def _resolve(*facts: _Fact) -> dict[str, object]:
    return dict(
        resolve_profile_export_values(
            _export_bindings(),
            bucket_id=_BUCKET,
            profile_record=_Record(facts=facts),
            schema=load_user_profile_schema(),
        ),
    )


_DECLARANTE = (
    _Fact("identity.surnames", "GARCIA LOPEZ"),
    _Fact("identity.name", "MARIA"),
    _Fact("identity.tax_id", "12345678Z"),
)
_SPOUSE = (
    _Fact("renta_spouse.surnames", "PEREZ RUIZ"),
    _Fact("renta_spouse.name", "JUAN"),
    _Fact("renta_spouse.tax_id", "87654321X"),
)


def test_a_declared_identity_slot_is_populated_from_the_profile() -> None:
    """The registry's own declarations drive the join, so nothing is named twice.

    Each of these lands because a binding declares it, not because the composer
    knows the field id. ``ZCCAD`` is included deliberately: its selector uses the
    ``profile_model``/``field`` form rather than a fact path, so it also proves
    the resolver covers both selector shapes.
    """
    values = _resolve(
        *_DECLARANTE,
        _Fact("renta_taxpayer.sex", "M"),
        _Fact("tax_residence.ccaa", "10"),
        _Fact("renta_filing.declaration_type", "1"),
    )

    assert values["DP_APENOM_D"] == "GARCIA LOPEZ MARIA"
    assert values["DPNIF_D"] == "12345678Z"
    assert values["SEXO_D"] == "M"
    assert values["ZCCAD"] == "10"
    assert values["TIPOTRIBUTACION"] == "1"


def test_an_individual_filing_writes_no_spouse_row() -> None:
    """A spouse on the profile does not put a spouse on an individual return.

    The conjunta-only slots are declared with a precondition, and honouring it
    is the difference between filing what the taxpayer declared and disclosing
    a second person's name, NIF and sex on a return they never consented to.
    The profile here HOLDS the spouse facts, so this fails if the precondition
    is dropped rather than merely if the facts are absent.
    """
    values = _resolve(
        *_DECLARANTE,
        *_SPOUSE,
        _Fact("renta_spouse.sex", "H"),
        _Fact("renta_filing.declaration_type", "1"),
    )

    assert [field for field in values if field.endswith("_C")] == []


def test_a_conjunta_filing_writes_the_spouse_rows() -> None:
    """Positive control for the precondition: satisfied, the slots are written.

    Without this, a resolver that dropped every conditional binding outright
    would satisfy the individual-filing case above while silently never filing
    a spouse at all.
    """
    values = _resolve(
        *_DECLARANTE,
        *_SPOUSE,
        _Fact("renta_spouse.sex", "H"),
        _Fact("renta_filing.declaration_type", "2"),
    )

    assert values["DP_APENOM_C"] == "PEREZ RUIZ JUAN"
    assert values["DPNIF_C"] == "87654321X"
    assert values["SEXO_C"] == "H"


def test_an_unanswered_precondition_does_not_disclose() -> None:
    """Absent is not satisfied: silence must not open a conditional slot.

    A profile that never recorded a declaration type has not said the filing is
    conjunta. Treating a missing gate fact as permissive would put the spouse's
    identity on the declaration on the strength of an unanswered question.
    """
    values = _resolve(*_DECLARANTE, *_SPOUSE)

    assert [field for field in values if field.endswith("_C")] == []


def test_the_precondition_fact_is_never_used_as_the_value() -> None:
    """A gate fact says WHETHER a slot applies, never WHAT it holds.

    ``profile_binding_selectors`` returns a binding's whole dependency set,
    including its ``required_when_profile_key``, and the shared resolver returns
    the first non-blank selector it finds. So a conjunta filing whose spouse
    birth date was never recorded resolved ``DPFNAC_C`` to the DECLARATION TYPE
    -- filing ``2`` as a date of birth, a wrong value on a filed artefact that
    is indistinguishable from a real one.

    The spouse rows that DO have facts are asserted alongside, so this cannot be
    satisfied by a resolver that simply stopped emitting conditional slots.
    """
    values = _resolve(
        *_DECLARANTE,
        *_SPOUSE,
        _Fact("renta_filing.declaration_type", "2"),
    )

    assert "DPFNAC_C" not in values
    assert values["DPNIF_C"] == "87654321X"


def test_a_multi_part_name_is_composed_rather_than_truncated() -> None:
    """``surnames_name`` declares PARTS, not fallbacks.

    The shared resolver returns the first non-blank selector, which for a
    two-key binding would file the surnames alone as the taxpayer's full legal
    name. The declared format is what says the keys compose.
    """
    values = _resolve(*_DECLARANTE, _Fact("renta_filing.declaration_type", "1"))

    assert values["DP_APENOM_D"] == "GARCIA LOPEZ MARIA"
    assert values["DP_APENOM_D"] != "GARCIA LOPEZ"


def test_a_blank_name_part_contributes_no_separator() -> None:
    """A legal entity's blank individual-name slot must not pad the value."""
    assert compose_legal_full_name(surnames="EMPRESA EJEMPLO SL", name="") == "EMPRESA EJEMPLO SL"
    assert compose_legal_full_name(surnames="GARCIA LOPEZ", name="MARIA") == "GARCIA LOPEZ MARIA"


def test_a_value_keeps_the_type_the_renderer_decides_from() -> None:
    """Values are carried, not rendered, so the renderer keeps its one authority.

    ``_format_xml_dictionary_value`` decides a row's rendering from the Python
    type it receives. Pre-rendering a date to text here would both destroy that
    signal and put a second formatting authority beside it.
    """
    values = _resolve(
        *_DECLARANTE,
        _Fact("renta_taxpayer.birth_date", date(1980, 5, 17)),
        _Fact("renta_filing.declaration_type", "1"),
    )

    assert values["DPFNAC_D"] == date(1980, 5, 17)


def test_the_repeating_family_slots_are_a_known_structural_gap() -> None:
    """The per-child and per-ascendant rows resolve to nothing, on purpose.

    These name array paths (``RentaFamilyProfile.descendants.*`` /
    ``.ascendants.*``) that nothing in production writes -- the real writer is
    the ``renta_family.descendiente`` OBJECT, which carries neither
    ``death_date`` nor ``display_name`` -- and the dictionary writer reuses a
    child element by tag, so several would overwrite one another rather than
    producing several rows.

    Pinned here rather than reported at runtime: an advisory firing on every
    single export, for a gap no operator can act on, is what teaches operators
    to ignore advisories that do matter. This test is the record, and it fails
    if a writer appears for these paths -- which is the point at which the
    decision should be revisited.
    """
    repeating = {
        str(getattr(binding.selector, "dictionary_field", ""))
        for binding in _export_bindings()
        if getattr(binding.selector, "repeating", False)
    }
    values = _resolve(
        *_DECLARANTE,
        _Fact("renta_family.descendiente.0.birth_date", "2020-01-01"),
        _Fact("renta_filing.declaration_type", "1"),
    )

    assert repeating, "the revision no longer declares repeating export bindings; revisit this pin"
    assert repeating.isdisjoint(values)
