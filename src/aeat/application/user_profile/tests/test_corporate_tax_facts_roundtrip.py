"""Encrypted-SQL persistence-boundary roundtrip for the corporate-tax profile facts.

Two OPTIONAL profile facts gate the IS calculation pathways adjudicated
by the corporate-entity calculation contract:

- ``taxpayer_type.incn_prior_12_months`` — Decimal | None, gating the
  Modelo 202 modality split at the 6.000.000 EUR threshold (LIS Art.
  40.3, BOE-A-2014-12328).
- ``taxpayer_type.new_entity_first_two_profit_periods`` — bool | None,
  gating the LIS Art. 29 15 percent reduced-rate override.

Both facts are optional: an undeclared value yields the engine's
existing INCOMPLETE-style fallback, never a guessed modality or rate.
The same boundary now carries the Ley 49/2002 Title II option and
renunciation facts sourced from Modelo 036.
The persistence-boundary contract is the same as for every other
taxpayer-axis fact — survive a real save/load cycle through the
encrypted store with strict pydantic equality.

This file pairs a populated roundtrip (both facts at non-default
values) with an anti-tautology proof (a surgical on-disk mutation
that drops a persisted fact and reloads). Real adapters only — a real
runtime profile and a real :class:`SecureObjectRepository`.

The test exercises :class:`UserProfileLifecycleRepository` directly
because it is the canonical user-profile boundary (the higher-level
``register_active_profile`` orchestration adds bucket-routing concerns
that belong to a separate roundtrip). The persisted facts are pulled
back through the same :class:`projection_for_taxpayer` projection
production consumers use, so the contract under test is the one
downstream callers actually depend on.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage import SensitivityClass
from ....domain.user_profile import (
    UserProfileFact,
    UserProfileRecord,
    UserProfileStatus,
)
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile

# Import side-effect: registers the wizard catalogue with core.wizard_catalogue
# so taxpayer_profile_from_mapping can resolve SETUP_FLOW. Without this import
# the projection raises WizardCatalogueNotRegisteredError on first call.
from .._projections import projection_for_taxpayer
from .._repository import (
    USER_PROFILE_VALUE_NAMESPACE,
    UserProfileLifecycleRepository,
    user_profile_value_object_key,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_BUCKET_ID = "corporate-tax-roundtrip"
_PROFILE_UUID = "8a4e0c5b-1d2f-4e3a-9b7c-6f5e4d3c2b1a"

# Non-default values for both facts:
#  - INCN above the 6.000.000 EUR Art. 40.3 threshold so the persisted
#    Decimal is unambiguously a "force Art. 40.3" value.
#  - new-entity-first-two-profit-periods True so the persisted bool is
#    the positively-declared affirmative (distinct from undeclared
#    None and from the negatively-declared False).
_INCN_VALUE = Decimal("7500000.00")
_NEW_ENTITY_VALUE = True
_LEY49_OPTION_DECLARED = True
_LEY49_OPTION_DATE = date(2024, 2, 3)
_LEY49_RENUNCIATION_DECLARED = False
_LEY49_RENUNCIATION_DATE = date(2026, 5, 11)


def _populated_record() -> UserProfileRecord:
    """A UserProfileRecord populated for the corporate-tax facts roundtrip.

    Every defaultable lifecycle field carries a non-default value so a
    save-drops-field / load-re-defaults-field regression surfaces as
    inequality; the two corporate-tax facts are carried alongside an
    explicit entity-type fact so the persisted set models a realistic
    legal-entity profile.
    """

    created = datetime(2024, 1, 4, 9, 0, 0, tzinfo=UTC)
    updated = datetime(2024, 6, 15, 14, 32, 17, tzinfo=UTC)
    return UserProfileRecord(
        schema_id="aeat.user_profile",
        schema_version=2,
        profile_id=_PROFILE_UUID,
        display_name="IS operator (INCN + new-entity roundtrip)",
        status=UserProfileStatus.ACTIVE,
        facts=(
            # entity_type is the routing axis the corporate-tax facts
            # describe; the wizard only surfaces the new-entity fact
            # when entity_type == legal_entity.
            UserProfileFact(
                path="taxpayer_type.entity_type",
                value="legal_entity",
                source="manual_cli",
            ),
            UserProfileFact(
                path="taxpayer_type.legal_entity_form",
                value="sl",
                source="manual_cli",
            ),
            # The two corporate-tax facts under test, both at non-default
            # positively-declared values.
            UserProfileFact(
                path="taxpayer_type.incn_prior_12_months",
                value=_INCN_VALUE,
                source="manual_cli",
            ),
            UserProfileFact(
                path="taxpayer_type.new_entity_first_two_profit_periods",
                value=_NEW_ENTITY_VALUE,
                source="manual_cli",
            ),
            UserProfileFact(
                path="taxpayer_type.ley_49_2002_special_regime_option_declared",
                value=_LEY49_OPTION_DECLARED,
                source="manual_cli",
            ),
            UserProfileFact(
                path="taxpayer_type.ley_49_2002_special_regime_option_date",
                value=_LEY49_OPTION_DATE.isoformat(),
                source="manual_cli",
            ),
            UserProfileFact(
                path="taxpayer_type.ley_49_2002_special_regime_renunciation_declared",
                value=_LEY49_RENUNCIATION_DECLARED,
                source="manual_cli",
            ),
            UserProfileFact(
                path="taxpayer_type.ley_49_2002_special_regime_renunciation_date",
                value=_LEY49_RENUNCIATION_DATE.isoformat(),
                source="manual_cli",
            ),
        ),
        created_at=created,
        updated_at=updated,
    )


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_BUCKET_ID,
        label="Corporate tax roundtrip",
    ) as profile:
        yield profile


@pytest.fixture
def lifecycle(runtime_profile: TestRuntimeProfile) -> UserProfileLifecycleRepository:
    """A real lifecycle repository over a real runtime profile."""

    return UserProfileLifecycleRepository(
        bucket_id=_BUCKET_ID,
        objects=runtime_profile.repository,
    )


def _fact_value(record: UserProfileRecord, path: str) -> object:
    matches = [fact.value for fact in record.facts if fact.path == path]
    assert len(matches) == 1, f"expected exactly one fact at {path!r}, found {len(matches)}"
    return matches[0]


def test_corporate_tax_facts_survive_encrypted_sql_roundtrip(
    lifecycle: UserProfileLifecycleRepository,
) -> None:
    """Both corporate-tax facts survive a real encrypted-SQL save/load cycle.

    Persists a populated :class:`UserProfileRecord` carrying the INCN
    Decimal and the new-entity bool at non-default values, reloads it
    through the real encrypted boundary, and asserts strict pydantic
    equality on the full record plus per-fact witnesses for the two
    facts under test. The reloaded record is then projected through
    the canonical :func:`projection_for_taxpayer` path consumers
    downstream actually read, confirming the typed
    :class:`TaxpayerProfile` reconstructs the Decimal and the
    three-state optional bool.
    """

    original = _populated_record()
    lifecycle.save(original)
    loaded = lifecycle.load(original.profile_id)

    # Strict pydantic equality across the full lifecycle record. A
    # silent save-drops / load-re-defaults regression on any field
    # (lifecycle metadata, fact tuple ordering, fact value typing,
    # source attribution) would surface here.
    assert loaded == original

    # Per-fact witnesses for the two facts under test — the Decimal
    # survives JSON roundtrip as a Decimal (not a string or float);
    # the bool survives as a bool.
    persisted_incn = _fact_value(loaded, "taxpayer_type.incn_prior_12_months")
    assert isinstance(persisted_incn, Decimal)
    assert persisted_incn == _INCN_VALUE
    persisted_new_entity = _fact_value(loaded, "taxpayer_type.new_entity_first_two_profit_periods")
    assert isinstance(persisted_new_entity, bool)
    assert persisted_new_entity is _NEW_ENTITY_VALUE
    persisted_ley49_option = _fact_value(loaded, "taxpayer_type.ley_49_2002_special_regime_option_declared")
    assert isinstance(persisted_ley49_option, bool)
    assert persisted_ley49_option is _LEY49_OPTION_DECLARED
    persisted_ley49_option_date = _fact_value(loaded, "taxpayer_type.ley_49_2002_special_regime_option_date")
    assert persisted_ley49_option_date == _LEY49_OPTION_DATE
    persisted_ley49_renunciation = _fact_value(
        loaded,
        "taxpayer_type.ley_49_2002_special_regime_renunciation_declared",
    )
    assert isinstance(persisted_ley49_renunciation, bool)
    assert persisted_ley49_renunciation is _LEY49_RENUNCIATION_DECLARED
    persisted_ley49_renunciation_date = _fact_value(
        loaded,
        "taxpayer_type.ley_49_2002_special_regime_renunciation_date",
    )
    assert persisted_ley49_renunciation_date == _LEY49_RENUNCIATION_DATE

    # The deadline-engine projection reconstructs the typed Decimal
    # and the three-state optional bool on TaxpayerProfile, so every
    # production consumer that reads through the canonical projection
    # surface sees the persisted values without re-parsing.
    profile = projection_for_taxpayer(loaded)
    assert profile.incn_prior_12_months == _INCN_VALUE
    assert profile.new_entity_first_two_profit_periods is _NEW_ENTITY_VALUE
    assert profile.ley_49_2002_special_regime_option_declared is _LEY49_OPTION_DECLARED
    assert profile.ley_49_2002_special_regime_option_date == _LEY49_OPTION_DATE
    assert profile.ley_49_2002_special_regime_renunciation_declared is _LEY49_RENUNCIATION_DECLARED
    assert profile.ley_49_2002_special_regime_renunciation_date == _LEY49_RENUNCIATION_DATE


def test_undeclared_corporate_tax_facts_project_to_none(
    lifecycle: UserProfileLifecycleRepository,
) -> None:
    """A record without either fact projects both axes to ``None``.

    The two corporate-tax facts are OPTIONAL — an undeclared value must
    yield the engine's existing INCOMPLETE-style fallback, never a
    guessed modality or rate. This test pins the absent-means-None
    contract through the real encrypted boundary so a save-side default
    that silently materialises ``False`` or ``Decimal('0')`` would
    surface as inequality on the typed projection.
    """

    base = _populated_record()
    facts_without_corporate_tax = tuple(
        fact
        for fact in base.facts
        if fact.path
        not in {
            "taxpayer_type.incn_prior_12_months",
            "taxpayer_type.new_entity_first_two_profit_periods",
            "taxpayer_type.ley_49_2002_special_regime_option_declared",
            "taxpayer_type.ley_49_2002_special_regime_option_date",
            "taxpayer_type.ley_49_2002_special_regime_renunciation_declared",
            "taxpayer_type.ley_49_2002_special_regime_renunciation_date",
        }
    )
    record = base.model_copy(update={"facts": facts_without_corporate_tax})
    lifecycle.save(record)
    loaded = lifecycle.load(record.profile_id)

    persisted_paths = {fact.path for fact in loaded.facts}
    assert "taxpayer_type.incn_prior_12_months" not in persisted_paths
    assert "taxpayer_type.new_entity_first_two_profit_periods" not in persisted_paths
    assert "taxpayer_type.ley_49_2002_special_regime_option_declared" not in persisted_paths
    assert "taxpayer_type.ley_49_2002_special_regime_option_date" not in persisted_paths
    assert "taxpayer_type.ley_49_2002_special_regime_renunciation_declared" not in persisted_paths
    assert "taxpayer_type.ley_49_2002_special_regime_renunciation_date" not in persisted_paths

    profile = projection_for_taxpayer(loaded)
    assert profile.incn_prior_12_months is None
    assert profile.new_entity_first_two_profit_periods is None
    assert profile.ley_49_2002_special_regime_option_declared is None
    assert profile.ley_49_2002_special_regime_option_date is None
    assert profile.ley_49_2002_special_regime_renunciation_declared is None
    assert profile.ley_49_2002_special_regime_renunciation_date is None


def test_dropping_a_persisted_corporate_tax_fact_surfaces_on_reload(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """Anti-tautology proof: stripping the persisted INCN fact must surface.

    The pattern follows ``aeat-roundtrip-discipline``: save a populated
    record through the real encrypted boundary, surgically mutate the
    JSON envelope to remove the INCN fact, reload through the real
    path, and assert the reloaded :class:`TaxpayerProfile` no longer
    carries the persisted Decimal. If the projection still surfaced
    the original Decimal — or surfaced any non-``None`` substitute —
    the persistence boundary would be tautological because the save
    side would be carrying the value through a path the load side does
    not actually depend on.

    The mutation loads the encrypted boundary payload through the
    runtime repository, drops the INCN fact from the persisted
    ``facts`` list, and writes the mutated envelope back. The load side
    then runs the full real decrypt/parse pipeline; the absence of the
    INCN fact must propagate to the typed projection.
    """

    lifecycle = UserProfileLifecycleRepository(
        bucket_id=_BUCKET_ID,
        objects=runtime_profile.repository,
    )

    original = _populated_record()
    lifecycle.save(original)

    # Sanity: the populated record carries the INCN fact before the
    # persisted mutation. A reload that fails this assertion means the
    # save path is the regression, not the load path.
    pre_mutation = lifecycle.load(original.profile_id)
    assert any(fact.path == "taxpayer_type.incn_prior_12_months" for fact in pre_mutation.facts)

    stored = runtime_profile.repository.load(
        USER_PROFILE_VALUE_NAMESPACE,
        user_profile_value_object_key(original.profile_id),
        expected_class=SensitivityClass.IDENTITY,
        max_supported_version=1,
    )
    assert stored is not None
    envelope = json.loads(stored.payload.decode("utf-8"))
    payload = envelope["payload"]
    original_fact_count = len(payload["facts"])
    payload["facts"] = [fact for fact in payload["facts"] if fact.get("path") != "taxpayer_type.incn_prior_12_months"]
    assert len(payload["facts"]) == original_fact_count - 1, (
        "fixture must persist exactly one INCN fact for this anti-tautology proof to be meaningful"
    )
    runtime_profile.repository.save(
        namespace=stored.namespace,
        object_key=user_profile_value_object_key(original.profile_id),
        classification=stored.classification,
        schema_version=stored.schema_version,
        written_at=stored.written_at,
        payload=json.dumps(envelope).encode("utf-8"),
    )

    reloaded = lifecycle.load(original.profile_id)
    persisted_paths = {fact.path for fact in reloaded.facts}
    assert "taxpayer_type.incn_prior_12_months" not in persisted_paths

    # Strict inequality on the typed projection: the
    # undeclared-after-drop state projects to ``None`` and is therefore
    # != the originally-persisted Decimal.
    profile = projection_for_taxpayer(reloaded)
    assert profile.incn_prior_12_months is None
    assert profile.incn_prior_12_months != _INCN_VALUE

    # The full-record equality also breaks — the reloaded record is not
    # equal to the in-memory original because the persisted facts list
    # lost an entry.
    assert reloaded != original
