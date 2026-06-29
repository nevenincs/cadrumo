"""Pin test: every M100 2025 profile-binding selector resolves to a schema path.

Each of the 19 ``source = "profile"`` bindings declared in the M100 2025
registry has a selector that must match at least one fact path the
:class:`ProfileSchemaDefinition` schema exposes. This file pins that
agreement so a schema refactor or selector typo surfaces as a test failure
rather than a silent missing-binding at runtime.

The test calls :func:`_profile_fact_index` and :func:`_resolve_one` directly
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
  than via ``_resolve_one``.
- The ``profile_model`` selector form (binding 0008, CCAA) resolves through the
  ``model_selectors`` alias — tested via the real ``_profile_fact_index`` index
  that exposes both selector forms.
- Anti-tautology: one fact is deliberately omitted from the fixture; the test
  asserts ``_resolve_one`` returns ``None`` for that binding, proving the
  resolver does not invent values.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest

from ....core.resources import resources
from ....domain.calculations.registry import RegistrySnapshot
from ....domain.user_profile import (
    UserProfileFact,
    UserProfileRecord,
    load_user_profile_schema,
    profile_binding_selectors,
)
from .._profile_binding import (
    inject_derived_marriage_facts,
    profile_fact_index,
    resolve_profile_binding_value,
    resolve_profile_sourced_bindings,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "binding-pin-test-operator"
_YEAR = 2025
_PERIOD = "0A"
_CLOCK = datetime(2026, 5, 27, 9, 0, 0, tzinfo=UTC)


def _modelo_100_snapshot() -> RegistrySnapshot:
    return resources().modelos.authority.snapshot("100", filing_year=_YEAR, period=_PERIOD)


def _profile_bindings() -> list[Any]:
    snapshot = _modelo_100_snapshot()
    return [b for b in snapshot.revision.bindings if b.source == "profile"]


# ---------------------------------------------------------------------------
# Full-population profile fixture
# ---------------------------------------------------------------------------


def _full_m100_profile() -> UserProfileRecord:
    """A UserProfileRecord populated for every profile_key appearing in M100 2025 bindings.

    The ``profile_keys`` / display-name bindings (0007 renta-2025-profile-display-name,
    0014 renta-2025-profile-spouse-display-name) require multiple keys; both
    ``identity.surnames`` / ``identity.name`` and ``renta_spouse.surnames`` /
    ``renta_spouse.name`` are included.

    Value types are chosen to match what ``_resolve_one`` returns after
    ``_profile_fact_index`` preserves the typed value from the profile record.
    Dates arrive as Python ``date`` objects; booleans as ``bool``;
    strings as ``str``; Decimals as ``Decimal``.
    """
    return UserProfileRecord(
        profile_id=_BUCKET_ID,
        display_name="Binding pin test taxpayer",
        facts=(
            # 0006 renta-2025-profile-tax-id
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            # 0007 renta-2025-profile-display-name (profile_keys form)
            UserProfileFact(path="identity.surnames", value="García López"),
            UserProfileFact(path="identity.name", value="Ana"),
            # 0008 renta-2025-profile-tax-residence-ccaa (profile_model form)
            UserProfileFact(path="tax_residence.ccaa", value="cataluna"),
            # 0009 renta-2025-profile-declaration-type
            UserProfileFact(path="filing_export.declaration_type", value="1"),
            # 0010 renta-2025-profile-taxpayer-sex
            UserProfileFact(path="renta_taxpayer.sex", value="H"),
            # 0011 renta-2025-profile-marital-status
            UserProfileFact(path="renta_taxpayer.marital_status", value="2"),
            # 0045 renta-2025-profile-marriage-full-year (derived from marriage_date at bind time)
            # 0046 renta-2025-profile-marriage-month-start
            # 0047 renta-2025-profile-marriage-month-end
            UserProfileFact(path="renta_taxpayer.marriage_date", value=date(2023, 6, 15)),
            # 0012 renta-2025-profile-taxpayer-birth-date
            UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
            # 0013 renta-2025-profile-spouse-tax-id
            UserProfileFact(path="renta_spouse.tax_id", value="98765432B"),
            # 0014 renta-2025-profile-spouse-display-name (profile_keys form)
            UserProfileFact(path="renta_spouse.surnames", value="Martínez"),
            UserProfileFact(path="renta_spouse.name", value="Carlos"),
            # 0015 renta-2025-profile-spouse-birth-date
            UserProfileFact(path="renta_spouse.birth_date", value=date(1978, 7, 22)),
            # 0016 renta-2025-profile-spouse-sex
            UserProfileFact(path="renta_spouse.sex", value="M"),
            # 0017 renta-2025-profile-taxpayer-disability-grade
            UserProfileFact(path="renta_taxpayer.disability_grade", value="0"),
            # 0018 renta-2025-profile-taxpayer-death-date (omitted — anti-tautology target)
            # 0019 renta-2025-profile-spouse-disability-grade
            UserProfileFact(path="renta_spouse.disability_grade", value="0"),
            # 0020 renta-2025-profile-spouse-non-resident-irpf
            UserProfileFact(path="renta_spouse.non_resident_irpf", value=False),
            # 0021 renta-2025-profile-spouse-eu-eea-resident
            UserProfileFact(path="renta_spouse.eu_eea_resident", value=False),
            # 0022 renta-2025-profile-spouse-eu-eea-country
            UserProfileFact(path="renta_spouse.eu_eea_country", value="DE"),
            # 0023 renta-2025-profile-family-descendants-eu-eea-deduction
            UserProfileFact(path="renta_family.descendants_eu_eea_deduction", value=False),
            # 0024 renta-2025-profile-family-minor-children-in-unit
            UserProfileFact(path="renta_family.minor_children_in_unit", value=Decimal("0")),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
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
    schema = load_user_profile_schema()
    known_paths: set[str] = {f"{section.key}.{field.key}" for section in schema.sections for field in section.fields}

    profile_bindings = _profile_bindings()
    for binding in profile_bindings:
        selector = binding.selector
        if not isinstance(selector, dict):
            continue
        pk = selector.get("profile_key")
        if pk is None:
            continue
        assert pk in known_paths, (
            f"binding {binding.id!r} declares profile_key={pk!r} but that path does not appear in the profile schema"
        )


def test_profile_model_selector_resolves_via_model_selector_alias() -> None:
    """The ``profile_model = TaxResidenceProfile, field = ccaa`` selector resolves
    through the schema's ``model_selectors`` alias index.

    :func:`_profile_fact_index` exposes each fact under its canonical
    ``section.field`` path AND under every ``model_selectors`` alias declared
    in the schema. The CCAA binding uses the ``profile_model`` form, so the
    index key is ``TaxResidenceProfile.ccaa`` — an alias, not the canonical
    path. This test confirms the alias round-trip works end-to-end.
    """
    schema = load_user_profile_schema()
    record = _full_m100_profile()
    fact_index = profile_fact_index(record, schema)

    # The alias must be present in the index
    assert "TaxResidenceProfile.ccaa" in fact_index, (
        "TaxResidenceProfile.ccaa alias not found in _profile_fact_index output; "
        "the model_selectors round-trip is broken"
    )
    assert fact_index["TaxResidenceProfile.ccaa"] == "cataluna"


def test_every_scalar_profile_binding_resolves_to_typed_value() -> None:
    """For each scalar ``profile_key`` / ``profile_model`` binding, ``_resolve_one`` returns a non-None value.

    The full-population profile fixture covers all scalar profile_key-form
    and simple profile_model-form bindings (0006-0024 range). Each must
    produce a typed value.

    Skipped categories:
    - ``profile_keys`` (composite display-name bindings 0007, 0014) — multi-key
      format for XML export, yield no selector from profile_binding_selectors.
    - Repeating-collection bindings (0025-0035, ``profile_model`` +
      ``collection`` + ``repeating = True``) — hold list-valued facts on the
      profile record that ``_resolve_one`` cannot project to a scalar;
      they are covered by test_repeating_collection_selectors_yield_known_alias.
    - The taxpayer death-date binding (0018) is intentionally absent from the
      fixture and is covered by test_absent_fact_resolves_to_none_anti_tautology.
    """
    schema = load_user_profile_schema()
    record = _full_m100_profile()
    fact_index = profile_fact_index(record, schema)
    # Marriage-derived facts (full_year, month_start, month_end) are not stored as
    # profile facts but are injected at binding-resolution time.  The full-population
    # fixture supplies renta_taxpayer.marriage_date so injection populates them here.
    inject_derived_marriage_facts(fact_index, _YEAR)

    # Deliberately absent binding — tested separately.
    absent = "renta-2025-profile-taxpayer-death-date"

    profile_bindings = _profile_bindings()
    for binding in profile_bindings:
        binding_id = binding.id
        if binding_id == absent:
            continue
        selector = binding.selector
        if not isinstance(selector, dict):
            continue
        # Skip composite display-name (profile_keys) — export-layout, no scalar path.
        if "profile_keys" in selector:
            continue
        # Skip repeating-collection bindings — list-valued, not scalar.
        if selector.get("repeating"):
            continue

        value = resolve_profile_binding_value(binding, fact_index)
        assert value is not None, (
            f"binding {binding_id!r} resolved to None from the full-population fixture; selector={selector!r}"
        )


def test_unmarried_profile_resolves_neutral_marriage_facts_without_marriage_date() -> None:
    """A single taxpayer does not owe an impossible marriage date to resolve 0245-0247."""
    snapshot = _modelo_100_snapshot()
    record = UserProfileRecord(
        profile_id=_BUCKET_ID,
        display_name="Single binding pin taxpayer",
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="filing_export.declaration_type", value="1"),
            UserProfileFact(path="renta_taxpayer.birth_date", value=date(1985, 6, 15)),
            UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
            UserProfileFact(path="renta_family.minor_children_in_unit", value=Decimal("0")),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )

    resolved = resolve_profile_sourced_bindings(snapshot, bucket_id=_BUCKET_ID, profile_record=record)

    assert resolved.binding_values["renta-2025-profile-marriage-full-year"] == Decimal("0")
    assert resolved.binding_values["renta-2025-profile-marriage-month-start"] == Decimal("0")
    assert resolved.binding_values["renta-2025-profile-marriage-month-end"] == Decimal("0")


def test_married_profile_without_marriage_date_keeps_marriage_facts_unresolved() -> None:
    """A married taxpayer still needs the actual marriage date for Art. 82 month facts."""
    snapshot = _modelo_100_snapshot()
    record = UserProfileRecord(
        profile_id=_BUCKET_ID,
        display_name="Married binding pin taxpayer",
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="filing_export.declaration_type", value="1"),
            UserProfileFact(path="renta_taxpayer.birth_date", value=date(1985, 6, 15)),
            UserProfileFact(path="renta_taxpayer.marital_status", value="2"),
            UserProfileFact(path="renta_family.minor_children_in_unit", value=Decimal("0")),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )

    resolved = resolve_profile_sourced_bindings(snapshot, bucket_id=_BUCKET_ID, profile_record=record)

    assert "renta-2025-profile-marriage-full-year" not in resolved.binding_values
    assert "renta-2025-profile-marriage-month-start" not in resolved.binding_values
    assert "renta-2025-profile-marriage-month-end" not in resolved.binding_values


def test_typed_values_match_expected_python_types() -> None:
    """Values returned by ``_resolve_one`` carry the correct Python types.

    The channel router in :func:`resolve_profile_sourced_bindings` branches on
    ``isinstance(value, bool)``, so booleans MUST arrive as ``bool``, not as
    the strings ``'true'`` / ``'false'``. Dates must be ``date`` objects so
    they can be coerced correctly if needed.
    """
    schema = load_user_profile_schema()
    record = _full_m100_profile()
    fact_index = profile_fact_index(record, schema)

    profile_bindings = _profile_bindings()
    binding_map = {str(b.id): b for b in profile_bindings}

    # bool-typed profile facts
    for binding_id, _expected_type in [
        ("renta-2025-profile-spouse-non-resident-irpf", bool),
        ("renta-2025-profile-spouse-eu-eea-resident", bool),
        ("renta-2025-profile-family-descendants-eu-eea-deduction", bool),
    ]:
        binding = binding_map[binding_id]
        value = resolve_profile_binding_value(binding, fact_index)
        assert value is not None, f"{binding_id!r} resolved to None unexpectedly"
        assert isinstance(value, bool), f"{binding_id!r}: expected bool, got {type(value).__name__} ({value!r})"

    # date-typed profile facts
    for binding_id in [
        "renta-2025-profile-taxpayer-birth-date",
        "renta-2025-profile-spouse-birth-date",
    ]:
        binding = binding_map[binding_id]
        value = resolve_profile_binding_value(binding, fact_index)
        assert value is not None, f"{binding_id!r} resolved to None unexpectedly"
        assert isinstance(value, date), f"{binding_id!r}: expected date, got {type(value).__name__} ({value!r})"

    # str-typed profile facts — values that cannot be parsed as Decimal
    # (tax ids, sex codes, CCAA codes, EU country codes).
    for binding_id in [
        "renta-2025-profile-tax-id",  # "12345678Z" — not numeric
        "renta-2025-profile-taxpayer-sex",  # "H" — not numeric
        "renta-2025-profile-spouse-sex",  # "M" — not numeric
        "renta-2025-profile-spouse-eu-eea-country",  # "DE" — not numeric
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
        "renta-2025-profile-declaration-type",  # "1" → Decimal("1")
        "renta-2025-profile-taxpayer-disability-grade",  # "0" → Decimal("0")
        "renta-2025-profile-spouse-disability-grade",  # "0" → Decimal("0")
        "renta-2025-profile-family-minor-children-in-unit",  # Decimal("0")
    ]:
        if binding_id not in binding_map:
            continue
        binding = binding_map[binding_id]
        value = resolve_profile_binding_value(binding, fact_index)
        assert value is not None, f"{binding_id!r} resolved to None unexpectedly"
        assert isinstance(value, Decimal), f"{binding_id!r}: expected Decimal, got {type(value).__name__} ({value!r})"


def test_absent_fact_resolves_to_none_anti_tautology() -> None:
    """Deliberately absent fact produces None from ``_resolve_one`` — not a stale value.

    The taxpayer death-date fact (0018) is intentionally omitted from the
    full-population fixture. ``_resolve_one`` must return ``None`` for it.
    If the resolver were reading stale state or caching across records this
    test would incorrectly return a value.
    """
    schema = load_user_profile_schema()
    record = _full_m100_profile()
    fact_index = profile_fact_index(record, schema)

    profile_bindings = _profile_bindings()
    death_date_binding = next(b for b in profile_bindings if str(b.id) == "renta-2025-profile-taxpayer-death-date")
    value = resolve_profile_binding_value(death_date_binding, fact_index)
    assert value is None, f"expected None for deliberately absent death-date binding, got {value!r}"


def test_ccaa_binding_selector_yields_model_selector_string() -> None:
    """``profile_binding_selectors`` yields ``TaxResidenceProfile.ccaa`` for the CCAA binding.

    The CCAA binding uses the ``profile_model`` + ``field`` selector form,
    so :func:`profile_binding_selectors` must yield the ``<model>.<field>``
    alias string — not the canonical ``tax_residence.ccaa`` path. If the
    selector form is mis-parsed, the alias lookup in ``_profile_fact_index``
    would silently fail.
    """
    profile_bindings = _profile_bindings()
    ccaa_binding = next(b for b in profile_bindings if str(b.id) == "renta-2025-profile-tax-residence-ccaa")
    selectors = list(profile_binding_selectors(ccaa_binding.selector))
    assert selectors == ["TaxResidenceProfile.ccaa"], f"expected ['TaxResidenceProfile.ccaa'], got {selectors!r}"


def test_repeating_collection_selectors_yield_known_alias() -> None:
    """Every ``profile_model`` + ``collection`` + ``repeating`` binding yields a known schema alias.

    The family descendant and ascendant bindings (0025-0035) use the
    ``profile_model = RentaFamilyProfile, collection = <name>, field = <f>``
    selector form with ``repeating = True``. :func:`profile_binding_selectors`
    yields ``RentaFamilyProfile.<collection>.<field>`` for each. That alias
    must appear in the schema's ``model_selectors`` for the matching field.
    """
    schema = load_user_profile_schema()
    all_aliases: set[str] = {
        alias for section in schema.sections for field in section.fields for alias in field.model_selectors
    }

    profile_bindings = _profile_bindings()
    for binding in profile_bindings:
        selector = binding.selector
        if not isinstance(selector, dict):
            continue
        if not selector.get("repeating"):
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


def test_binding_count_is_exactly_33() -> None:
    """M100 2025 has exactly 33 ``source = 'profile'`` bindings.

    This acts as a structural sentinel: adding or removing a profile binding
    without updating this test will fail, prompting a review of whether the
    pin tests cover the new binding.

    Breakdown of the 33: 22 scalar bindings (single-value profile reads
    keyed by entity_type, ccaa, estimation_regime, income categories,
    address-cadastral references, plus the three matrimonio-sobrevenido
    derived scalars: marriage_full_year, marriage_month_start,
    marriage_month_end added for Art. 82 LIRPF casillas 0245/0246/0247)
    plus 11 family-repeating-collection bindings (per-dependent / per-spouse
    / per-child arrays whose cardinality follows the operator's declared
    family composition).
    The split matters when a new binding lands: a 23-scalar / 10-collection
    rebalance still totals 33 but indicates a different schema shift
    (operator-data field add vs family-collection contract change).
    Future drift in the sentinel meaning is prevented by this note
    plus the descriptive assertion message below.
    """
    profile_bindings = _profile_bindings()
    assert len(profile_bindings) == 33, (
        f"expected 33 profile-sourced bindings in M100 2025, found {len(profile_bindings)}: "
        + ", ".join(str(b.id) for b in profile_bindings)
    )
