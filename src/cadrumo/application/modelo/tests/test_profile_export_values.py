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

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ....core import BindingSourceKind, Modelo
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.schema import DataBindingDefinition
from ....domain.user_profile.loader import load_user_profile_schema
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from .._profile_export_binding import compose_legal_full_name, resolve_profile_export_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "d24bdc40-1623-4255-a9c3-a4b5c34dd9bb"  # was 'bucket-under-test'


_T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _fact(path: str, value: object) -> UserProfileFact:
    """Build a REAL profile fact.

    These were hand-rolled dataclasses standing in for the domain models.
    ``profile_fact_index`` guards on ``isinstance(record, UserProfileRecord)``
    and returns an EMPTY index for anything else, so the stub record silently
    resolved nothing and every assertion here died on a KeyError naming a
    dictionary field that was never the problem.
    """
    return UserProfileFact(path=path, value=value)


def _record(facts: tuple[UserProfileFact, ...]) -> UserProfileRecord:
    """Build a real record so the production fact index actually reads it."""
    return UserProfileRecord(
        profile_id=_BUCKET,
        setup_state=ProfileSetupState.COMPLETE,
        facts=facts,
        created_at=_T0,
        updated_at=_T0,
    )


def _export_bindings() -> tuple[DataBindingDefinition, ...]:
    """The real Modelo 100 2024 profile bindings that carry an export address."""
    snapshot = bundled_authority().snapshot(
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


def _resolve(*facts: UserProfileFact) -> dict[str, object]:
    return dict(
        resolve_profile_export_values(
            _export_bindings(),
            bucket_id=_BUCKET,
            profile_record=_record(facts),
            schema=load_user_profile_schema(),
        ),
    )


_DECLARANTE = (
    _fact("identity.surnames", "GARCIA LOPEZ"),
    _fact("identity.name", "MARIA"),
    _fact("identity.tax_id", "12345678Z"),
)
_SPOUSE = (
    _fact("renta_spouse.surnames", "PEREZ RUIZ"),
    _fact("renta_spouse.name", "JUAN"),
    _fact("renta_spouse.tax_id", "87654321X"),
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
        _fact("renta_taxpayer.sex", "M"),
        # A REAL ccaa value. The schema declares this enum over community NAMES
        # (`madrid`, `andalucia`, ...), never numeric codes, so the "10" this
        # replaced was not a value the field can hold.
        _fact("tax_residence.ccaa", "madrid"),
        _fact("renta_filing.declaration_type", "1"),
    )

    assert values["DP_APENOM_D"] == "GARCIA LOPEZ MARIA"
    assert values["DPNIF_D"] == "12345678Z"
    assert values["SEXO_D"] == "M"
    assert values["ZCCAD"] == "madrid"
    # Decimal, not "1", and deliberately so. `UserProfileFact` runs
    # `_coerce_profile_fact_value`, which restores the Decimal and date types
    # JSON drops on persistence -- a stored "1" is indistinguishable from a
    # round-tripped Decimal(1), and the model resolves that ambiguity towards
    # Decimal. Values with an insignificant leading zero (postcodes) are
    # carved out and stay str. The resolver then preserves the concrete type,
    # because the renderer branches on it.
    assert values["TIPOTRIBUTACION"] == Decimal("1")


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
        _fact("renta_spouse.sex", "H"),
        _fact("renta_filing.declaration_type", "1"),
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
        _fact("renta_spouse.sex", "H"),
        _fact("renta_filing.declaration_type", "2"),
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
        _fact("renta_filing.declaration_type", "2"),
    )

    assert "DPFNAC_C" not in values
    assert values["DPNIF_C"] == "87654321X"


def test_a_multi_part_name_is_composed_rather_than_truncated() -> None:
    """``surnames_name`` declares PARTS, not fallbacks.

    The shared resolver returns the first non-blank selector, which for a
    two-key binding would file the surnames alone as the taxpayer's full legal
    name. The declared format is what says the keys compose.
    """
    values = _resolve(*_DECLARANTE, _fact("renta_filing.declaration_type", "1"))

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
        _fact("renta_taxpayer.birth_date", date(1980, 5, 17)),
        _fact("renta_filing.declaration_type", "1"),
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
        _fact("renta_family.descendiente.0.birth_date", "2020-01-01"),
        _fact("renta_filing.declaration_type", "1"),
    )

    assert repeating, "the revision no longer declares repeating export bindings; revisit this pin"
    assert repeating.isdisjoint(values)
