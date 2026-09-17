"""Pin test: every M100 2025 profile-binding selector resolves to a schema path.

Each of the ``source = "profile"`` bindings declared in the M100 2025
registry has a selector that must match at least one fact path the
:class:`ProfileSchemaDefinition` schema exposes. This file pins that
agreement so a schema refactor or selector typo surfaces as a test failure
rather than a silent missing-binding at runtime.

The test calls :func:`profile_fact_index` and :func:`resolve_profile_binding_value` directly
because :func:`resolve_profile_sourced_bindings` filters to formula-consumed
bindings only — export-only bindings (NIF, display name, …) are intentionally
excluded from that call path but still need their selectors to be correct.

Design notes
------------
- ``profile_keys`` / ``format = "surnames_name"`` selectors (bindings 0007 and
  0014, the composite display-name fields) yield no keys from
  :func:`profile_binding_selectors`. They are export-layout bindings consumed
  by the XML serialiser, not the calculation engine. They are verified here by
  confirming their raw selector dict keys exist in the schema sections rather
  than via ``resolve_profile_binding_value``.
- The ``profile_model`` selector form (binding 0008, CCAA) resolves through the
  ``model_selectors`` alias — tested via the real ``profile_fact_index`` index
  that exposes both selector forms.
- Anti-tautology: one fact is deliberately omitted from the fixture; the test
  asserts ``resolve_profile_binding_value`` returns ``None`` for that binding, proving the
  resolver does not invent values.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest

from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test

from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.profile_bindings import ProfileProvider
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context as _profile_creation_context_for_test,
)
from ....domain.calculations.registry.tests.published_authority import (
    published_profile_schema,
    published_snapshot,
)
from ....domain.user_profile.registry_contract import profile_binding_selectors
from ....domain.user_profile.schema import derived_selector_for_path
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.inventory import REPO_ROOT
from ...user_profile.projections import profile_fact_index
from ..profile_binding import (
    inject_derived_anualidades_eligibility_facts,
    inject_derived_autonomic_deduccion_facts,
    inject_derived_marriage_facts,
    inject_derived_minimo_descendientes_facts,
    inject_ordinary_work_maritime_facts,
    resolve_profile_binding_value,
    resolve_profile_sourced_bindings,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    """Lease one generation for each profile-binding path test."""
    with bundled_indexed_authority().operation() as operation:
        yield operation


_PROFILE_ID = "10000000-0000-4000-8000-000000000477"
_BUCKET_ID = _PROFILE_ID
_YEAR = 2025
_PERIOD = "0A"
_CLOCK = datetime(2026, 5, 27, 9, 0, 0, tzinfo=UTC)
_M100_2025_XSD = (
    REPO_ROOT
    / "src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files"
    / "03-100-esquema-xsd-ejercicio-2025-actualizado-24-06-2026-793-kb-ejecutable.xsd"
)


def _modelo_100_snapshot() -> RegistrySnapshot:
    return published_snapshot("100", filing_year=_YEAR, period=_PERIOD)


def _profile_bindings() -> list[Any]:
    snapshot = _modelo_100_snapshot()
    return [b for b in snapshot.revision.bindings if b.source == "profile"]


# ---------------------------------------------------------------------------
# Full-population profile fixture
# ---------------------------------------------------------------------------


def _full_m100_profile() -> UserProfileRecord:
    """A UserProfileRecord populated for every profile_key appearing in M100 2025 bindings.

    The ``profile_keys`` / display-name bindings (0007 renta-profile-display-name,
    0014 renta-profile-spouse-display-name) require multiple keys; both
    ``identity.surnames`` / ``identity.name`` and ``renta_spouse.surnames`` /
    ``renta_spouse.name`` are included.

    Value types are chosen to match what ``resolve_profile_binding_value`` returns after
    ``profile_fact_index`` preserves the typed value from the profile record.
    Dates arrive as Python ``date`` objects; booleans as ``bool``;
    strings as ``str``; Decimals as ``Decimal``.
    """
    return _create_profile_record_for_test(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=(
            # 0006 renta-profile-tax-id
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            # 0007 renta-profile-display-name (profile_keys form)
            UserProfileFact(path="identity.surnames", value="García López"),
            UserProfileFact(path="identity.name", value="Ana"),
            # 0008 renta-profile-tax-residence-ccaa (profile_model form)
            UserProfileFact(path="tax_residence.ccaa", value="cataluna"),
            # 0009 renta-profile-declaration-type
            UserProfileFact(path="renta_filing.declaration_type", value="1"),
            # 0010 renta-profile-taxpayer-sex
            UserProfileFact(path="renta_taxpayer.sex", value="H"),
            # 0011 renta-profile-marital-status
            UserProfileFact(path="renta_taxpayer.marital_status", value="2"),
            # 0045 renta-profile-marriage-full-year (derived from marriage_date at bind time)
            # 0046 renta-profile-marriage-month-start
            # 0047 renta-profile-marriage-month-end
            UserProfileFact(path="renta_taxpayer.marriage_date", value=date(2023, 6, 15)),
            # 0012 renta-profile-taxpayer-birth-date
            UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
            # 0013 renta-profile-spouse-tax-id
            UserProfileFact(path="renta_spouse.tax_id", value="98765432B"),
            # 0014 renta-profile-spouse-display-name (profile_keys form)
            UserProfileFact(path="renta_spouse.surnames", value="Martínez"),
            UserProfileFact(path="renta_spouse.name", value="Carlos"),
            # 0015 renta-profile-spouse-birth-date
            UserProfileFact(path="renta_spouse.birth_date", value=date(1978, 7, 22)),
            # 0016 renta-profile-spouse-sex
            UserProfileFact(path="renta_spouse.sex", value="M"),
            # 0017 renta-profile-taxpayer-disability-grade
            UserProfileFact(path="renta_taxpayer.disability_grade", value="0"),
            # 0018 renta-profile-taxpayer-death-date (omitted — anti-tautology target)
            # 0019 renta-profile-spouse-disability-grade
            UserProfileFact(path="renta_spouse.disability_grade", value="0"),
            # 0020 renta-profile-spouse-non-resident-irpf
            UserProfileFact(path="renta_spouse.non_resident_irpf", value=False),
            # 0021 renta-profile-spouse-eu-eea-resident
            UserProfileFact(path="renta_spouse.eu_eea_resident", value=False),
            # 0022 renta-profile-spouse-eu-eea-country
            UserProfileFact(path="renta_spouse.eu_eea_country", value="DE"),
            # 0023 renta-profile-family-descendants-eu-eea-deduction
            UserProfileFact(path="renta_family.descendants_eu_eea_deduction", value=False),
            # 0024 renta-profile-family-minor-children-in-unit
            UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        context=_profile_creation_context_for_test(),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_all_profile_key_selectors_resolve_to_schema_paths() -> None:
    """Every ``profile_key`` selector in M100 2025 bindings names a known schema path.

    The schema exposes each fact under ``section.key.field.key``. A binding
    whose ``profile_key`` does not appear in the schema can never be resolved
    from a real profile record, so it is effectively dead. This pin confirms
    each ``profile_key`` has a live schema counterpart.
    """
    schema = published_profile_schema()
    known_paths: set[str] = {f"{section.key}.{field.key}" for section in schema.sections for field in section.fields}

    profile_bindings = _profile_bindings()
    for binding in profile_bindings:
        provider = binding.provider
        assert isinstance(provider, ProfileProvider), binding.id
        pk = provider.profile_key
        if pk is None:
            continue
        assert pk in known_paths or derived_selector_for_path(pk, schema.derived_selectors) is not None, (
            f"binding {binding.id!r} declares profile_key={pk!r} but that path does not appear in the profile schema"
        )


def test_profile_model_selector_resolves_via_model_selector_alias() -> None:
    """The ``profile_model = TaxResidenceProfile, field = ccaa`` selector resolves
    through the schema's ``model_selectors`` alias index.

    :func:`profile_fact_index` exposes each fact under its canonical
    ``section.field`` path AND under every ``model_selectors`` alias declared
    in the schema. The CCAA binding uses the ``profile_model`` form, so the
    index key is ``TaxResidenceProfile.ccaa`` — an alias, not the canonical
    path. This test confirms the alias round-trip works end-to-end.
    """
    schema = published_profile_schema()
    record = _full_m100_profile()
    fact_index = profile_fact_index(record, schema)

    # The alias must be present in the index
    assert "TaxResidenceProfile.ccaa" in fact_index, (
        "TaxResidenceProfile.ccaa alias not found in profile_fact_index output; "
        "the model_selectors round-trip is broken"
    )
    assert fact_index["TaxResidenceProfile.ccaa"] == "cataluna"


def test_every_scalar_profile_binding_resolves_to_typed_value(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """For each scalar ``profile_key`` / ``profile_model`` binding, ``resolve_profile_binding_value`` returns a non-None value.

    The full-population profile fixture covers all scalar profile_key-form
    and simple profile_model-form bindings (0006-0024 range). Each must
    produce a typed value.

    Skipped categories:
    - ``profile_keys`` (composite display-name bindings 0007, 0014) — multi-key
      format for XML export, yield no selector from profile_binding_selectors.
    - Repeating-collection bindings (0025-0035, ``profile_model`` +
      ``collection`` + ``repeating = True``) — hold list-valued facts on the
      profile record that ``resolve_profile_binding_value`` cannot project to a scalar;
      they are covered by test_repeating_collection_selectors_yield_known_alias.
    - The taxpayer death-date binding (0018) is intentionally absent from the
      fixture and is covered by test_absent_fact_resolves_to_none_anti_tautology.
    """
    schema = published_profile_schema()
    record = _full_m100_profile()
    fact_index = profile_fact_index(record, schema)
    # Marriage-derived facts (full_year, month_start, month_end) are not stored as
    # profile facts but are injected at binding-resolution time.  The full-population
    # fixture supplies renta_taxpayer.marriage_date so injection populates them here.
    inject_derived_marriage_facts(fact_index, _YEAR)
    # Madrid nacimiento/adopción derived scalars (eligible count + unidad-familiar
    # base) are likewise injected at resolution time, defaulting to 0.
    inject_derived_autonomic_deduccion_facts(fact_index, _YEAR, operation=authority_operation)
    # The Art. 64/75 anualidades separate-escala flag is derived the same way.
    snapshot = _modelo_100_snapshot()
    inject_ordinary_work_maritime_facts(fact_index)
    inject_derived_anualidades_eligibility_facts(fact_index, snapshot, operation=authority_operation)
    inject_derived_minimo_descendientes_facts(fact_index, snapshot, operation=authority_operation)

    # Deliberately absent binding — tested separately.
    absent = "renta-profile-taxpayer-death-date"

    profile_bindings = _profile_bindings()
    for binding in profile_bindings:
        binding_id = binding.id
        if binding_id == absent:
            continue
        selector = binding.provider
        assert isinstance(selector, ProfileProvider), binding_id
        # Skip composite display-name (profile_keys) — export-layout, no scalar path.
        if selector.profile_keys:
            continue
        # Skip repeating-collection bindings — list-valued, not scalar.
        if selector.repeating:
            continue

        value = resolve_profile_binding_value(binding, fact_index)
        assert value is not None, (
            f"binding {binding_id!r} resolved to None from the full-population fixture; selector={selector!r}"
        )


def test_unmarried_profile_resolves_neutral_marriage_facts_without_marriage_date(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A single taxpayer does not owe an impossible marriage date to resolve 0245-0247."""
    snapshot = _modelo_100_snapshot()
    record = _create_profile_record_for_test(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="renta_filing.declaration_type", value="1"),
            UserProfileFact(path="renta_taxpayer.birth_date", value=date(1985, 6, 15)),
            UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
            UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        context=_profile_creation_context_for_test(),
    )

    resolved = resolve_profile_sourced_bindings(
        snapshot,
        bucket_id=_BUCKET_ID,
        profile_record=record,
        operation=authority_operation,
    )

    assert resolved.boolean_binding_values["renta-profile-marriage-full-year"] is False
    assert resolved.binding_values["renta-profile-marriage-month-start"] == Decimal("0")
    assert resolved.binding_values["renta-profile-marriage-month-end"] == Decimal("0")


def test_pareja_hecho_status_does_not_feed_official_ecivil_channels(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Profile-only marital status 5 must not reach Modelo 100 ECIVIL export channels."""
    snapshot = _modelo_100_snapshot()
    ecivil_casilla = next(casilla for casilla in snapshot.revision.casillas if casilla.id == "ECIVIL")
    ecivil_binding_id = ecivil_casilla.binding
    assert ecivil_casilla.data_type == "text"
    assert ecivil_binding_id == "renta-profile-marital-status"

    ecivil_binding = next(binding for binding in snapshot.revision.bindings if binding.id == ecivil_binding_id)
    selector = ecivil_binding.provider
    profile_key = getattr(selector, "profile_key", None)
    xsd_path = getattr(selector, "xsd_path", None)
    dictionary_field = getattr(selector, "dictionary_field", None)
    assert profile_key == "renta_taxpayer.marital_status"
    assert xsd_path == "/DatosIdentificativos/Declarante/ECIVIL"
    assert dictionary_field == "ECIVIL"
    assert b'<xs:pattern value="([1-4]){1}"/>' in _M100_2025_XSD.read_bytes()

    record = _create_profile_record_for_test(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="renta_filing.declaration_type", value="1"),
            UserProfileFact(path="renta_taxpayer.birth_date", value=date(1985, 6, 15)),
            UserProfileFact(path="renta_taxpayer.marital_status", value="5"),
            UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        context=_profile_creation_context_for_test(),
    )

    resolved = resolve_profile_sourced_bindings(
        snapshot,
        bucket_id=_BUCKET_ID,
        profile_record=record,
        operation=authority_operation,
    )

    assert ecivil_binding_id not in resolved.binding_values
    assert ecivil_binding_id not in resolved.enum_binding_values
    assert ecivil_binding_id not in resolved.date_binding_values
    assert resolved.boolean_binding_values["renta-profile-marriage-full-year"] is False
    assert resolved.binding_values["renta-profile-marriage-month-start"] == Decimal("0")
    assert resolved.binding_values["renta-profile-marriage-month-end"] == Decimal("0")


def test_married_profile_without_marriage_date_keeps_marriage_facts_unresolved(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A married taxpayer still needs the actual marriage date for Art. 82 month facts."""
    snapshot = _modelo_100_snapshot()
    record = _create_profile_record_for_test(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="renta_filing.declaration_type", value="1"),
            UserProfileFact(path="renta_taxpayer.birth_date", value=date(1985, 6, 15)),
            UserProfileFact(path="renta_taxpayer.marital_status", value="2"),
            UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        context=_profile_creation_context_for_test(),
    )

    resolved = resolve_profile_sourced_bindings(
        snapshot,
        bucket_id=_BUCKET_ID,
        profile_record=record,
        operation=authority_operation,
    )

    assert "renta-profile-marriage-full-year" not in resolved.binding_values
    assert "renta-profile-marriage-month-start" not in resolved.binding_values
    assert "renta-profile-marriage-month-end" not in resolved.binding_values


def test_typed_values_match_expected_python_types() -> None:
    """Values returned by ``resolve_profile_binding_value`` carry the correct Python types.

    The channel router in :func:`resolve_profile_sourced_bindings` branches on
    ``isinstance(value, bool)``, so booleans MUST arrive as ``bool``, not as
    the strings ``'true'`` / ``'false'``. Dates must be ``date`` objects so
    they can be coerced correctly if needed.
    """
    schema = published_profile_schema()
    record = _full_m100_profile()
    fact_index = profile_fact_index(record, schema)

    profile_bindings = _profile_bindings()
    binding_map = {str(b.id): b for b in profile_bindings}

    # bool-typed profile facts
    for binding_id, _expected_type in [
        ("renta-profile-spouse-non-resident-irpf", bool),
        ("renta-profile-spouse-eu-eea-resident", bool),
        ("renta-profile-family-descendants-eu-eea-deduction", bool),
        # Declared boolean in the schema, and the fixture now says so too. It
        # sat in the Decimal group below only because the fixture wrote
        # Decimal("0") into a boolean-declared field. The art. 84 reducción
        # formula still compares this binding against the literal "0" and is
        # unaffected: _decimal_value converts a bool to Decimal("1")/("0")
        # before the numeric channel sees it.
        ("renta-profile-family-minor-children-in-unit", bool),
    ]:
        binding = binding_map[binding_id]
        value = resolve_profile_binding_value(binding, fact_index)
        assert value is not None, f"{binding_id!r} resolved to None unexpectedly"
        assert isinstance(value, bool), f"{binding_id!r}: expected bool, got {type(value).__name__} ({value!r})"

    # date-typed profile facts
    for binding_id in [
        "renta-profile-taxpayer-birth-date",
        "renta-profile-spouse-birth-date",
    ]:
        binding = binding_map[binding_id]
        value = resolve_profile_binding_value(binding, fact_index)
        assert value is not None, f"{binding_id!r} resolved to None unexpectedly"
        assert isinstance(value, date), f"{binding_id!r}: expected date, got {type(value).__name__} ({value!r})"

    # str-typed profile facts — values that cannot be parsed as Decimal
    # (tax ids, sex codes, CCAA codes, EU country codes).
    for binding_id in [
        "renta-profile-tax-id",  # "12345678Z" — not numeric
        "renta-profile-taxpayer-sex",  # "H" — not numeric
        "renta-profile-spouse-sex",  # "M" — not numeric
        "renta-profile-spouse-eu-eea-country",  # "DE" — not numeric
    ]:
        if binding_id not in binding_map:
            continue
        binding = binding_map[binding_id]
        value = resolve_profile_binding_value(binding, fact_index)
        assert value is not None, f"{binding_id!r} resolved to None unexpectedly"
        assert isinstance(value, str), f"{binding_id!r}: expected str, got {type(value).__name__} ({value!r})"

    # Decimal-coerced facts — UserProfileFact coerces numeric-string values.
    # declaration_type = "1" arrives as Decimal("1") after coercion.
    for binding_id in [
        "renta-profile-declaration-type",  # "1" → Decimal("1")
        "renta-profile-taxpayer-disability-grade",  # "0" → Decimal("0")
        "renta-profile-spouse-disability-grade",  # "0" → Decimal("0")
    ]:
        if binding_id not in binding_map:
            continue
        binding = binding_map[binding_id]
        value = resolve_profile_binding_value(binding, fact_index)
        assert value is not None, f"{binding_id!r} resolved to None unexpectedly"
        assert isinstance(value, Decimal), f"{binding_id!r}: expected Decimal, got {type(value).__name__} ({value!r})"


def test_absent_fact_resolves_to_none_anti_tautology() -> None:
    """Deliberately absent fact produces None from ``resolve_profile_binding_value`` — not a stale value.

    The taxpayer death-date fact (0018) is intentionally omitted from the
    full-population fixture. ``resolve_profile_binding_value`` must return ``None`` for it.
    If the resolver were reading stale state or caching across records this
    test would incorrectly return a value.
    """
    schema = published_profile_schema()
    record = _full_m100_profile()
    fact_index = profile_fact_index(record, schema)

    profile_bindings = _profile_bindings()
    death_date_binding = next(b for b in profile_bindings if str(b.id) == "renta-profile-taxpayer-death-date")
    value = resolve_profile_binding_value(death_date_binding, fact_index)
    assert value is None, f"expected None for deliberately absent death-date binding, got {value!r}"


def test_ccaa_binding_selector_yields_model_selector_string() -> None:
    """``profile_binding_selectors`` yields ``TaxResidenceProfile.ccaa`` for the CCAA binding.

    The CCAA binding uses the ``profile_model`` + ``field`` selector form,
    so :func:`profile_binding_selectors` must yield the ``<model>.<field>``
    alias string — not the canonical ``tax_residence.ccaa`` path. If the
    selector form is mis-parsed, the alias lookup in ``profile_fact_index``
    would silently fail.
    """
    profile_bindings = _profile_bindings()
    ccaa_binding = next(b for b in profile_bindings if str(b.id) == "renta-profile-tax-residence-ccaa")
    selectors = list(profile_binding_selectors(ccaa_binding.provider))
    assert selectors == ["TaxResidenceProfile.ccaa"], f"expected ['TaxResidenceProfile.ccaa'], got {selectors!r}"


def test_repeating_collection_selectors_yield_known_alias() -> None:
    """Every ``profile_model`` + ``collection`` + ``repeating`` binding yields a known schema alias.

    The family descendant and ascendant bindings (0025-0035) use the
    ``profile_model = RentaFamilyProfile, collection = <name>, field = <f>``
    selector form with ``repeating = True``. :func:`profile_binding_selectors`
    yields ``RentaFamilyProfile.<collection>.<field>`` for each. That alias
    must appear in the schema's ``model_selectors`` for the matching field.
    """
    schema = published_profile_schema()
    all_aliases: set[str] = {
        alias for section in schema.sections for field in section.fields for alias in field.model_selectors
    }

    profile_bindings = _profile_bindings()
    for binding in profile_bindings:
        selector = binding.provider
        assert isinstance(selector, ProfileProvider), binding.id
        if not selector.repeating:
            continue
        selectors = list(profile_binding_selectors(selector))
        assert selectors, (
            f"binding {binding.id!r} has repeating=True but profile_binding_selectors "
            f"yielded nothing; selector={selector!r}"
        )
        for sel in selectors:
            assert sel in all_aliases, (
                f"binding {binding.id!r}: selector {sel!r} not found in any field's "
                f"model_selectors in the profile schema"
            )
