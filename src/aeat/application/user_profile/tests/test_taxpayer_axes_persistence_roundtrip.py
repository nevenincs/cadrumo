"""Encrypted-SQL persistence-boundary roundtrip for the taxpayer-axis facts.

The structured three-axis taxpayer model (entity type, IRPF
income-category set, IRPF estimation regime, and the SII / REDEME
special-enrolment flags) is collected by the wizard, projected onto
:class:`UserProfileFact` rows, and persisted in the encrypted
user-profile aggregate. The companion wizard test exercises the
canonical-token JSON cycle; this file closes the remaining boundary
by pushing those facts through the *real* encrypted-SQL store.

Real adapters only: a real active-profile SQLite runtime and a real
:class:`SecureObjectRepository`.

The fixture sets every taxpayer-axis fact to a NON-DEFAULT value so a
save-drops-fact / load-re-defaults-fact regression surfaces as
inequality. The forward-compatibility test additionally proves a
v1-shaped record — one carrying no taxpayer-axis facts at all — still
loads cleanly under the v2 schema and projects the new axes to their
"undeclared" form, locking the additive-only schema contract.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from ....core.resources import resources
from ....domain.deadlines import (
    EntityType,
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IVARegime,
)
from ....domain.user_profile import ProfileSchemaDefinition, UserProfileFact, UserProfileRecord
from ....tests.secure_sql import isolated_profile_storage_root
from ...workflow._models import WorkflowState
from .._orchestration import (
    profile_create_storage_span,
    read_active_profile,
    register_active_profile,
)
from .._projections import projection_for_taxpayer

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(autouse=True)
def _storage_root(tmp_path: Path) -> Iterator[None]:
    """Real file-backed storage root for the production create-span mint path.

    Each test registers its profile inside
    :func:`profile_create_storage_span`, which mints the per-bucket
    wrapped DEK under the resolved file-backend master key before
    :func:`register_active_profile` writes the manifest — the genuine
    ``BUCKET_DEK_V1`` create path, not a legacy no-DEK shortcut.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


@pytest.fixture(scope="module")
def schema() -> ProfileSchemaDefinition:
    return resources().user_profile_schema.singleton


def _required_facts(schema: ProfileSchemaDefinition) -> list[UserProfileFact]:
    """Every required non-repeatable schema field with a placeholder value.

    The required-field set must be satisfied for ``register_active_profile``
    to accept the registration; values are placeholders because this test
    asserts on the taxpayer-axis facts, not the required identity facts.
    """

    facts: list[UserProfileFact] = []
    for section in schema.sections:
        if section.repeatable:
            continue
        for field in section.fields:
            if field.required:
                facts.append(UserProfileFact(path=f"{section.key}.{field.key}", value="placeholder"))
    return facts


# The taxpayer-axis facts, every value deliberately non-default:
# - entity_type: an explicit branch (default is undeclared/None)
# - legal_entity_form: an explicit recognised form
# - irpf_income_categories: a multi-member set in non-sorted input order
#   so the canonical-string projection is exercised on a real set
# - irpf.estimation_regime: a non-default regime
# - iva.regime: REAGP (the non-default member, not GENERAL)
# - iva.sii_enrolled / iva.redeme_enrolled: both True (default False)
_TAXPAYER_AXIS_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
    UserProfileFact(path="taxpayer_type.legal_entity_form", value="cooperativa"),
    UserProfileFact(
        path="taxpayer_type.irpf_income_categories",
        value="trabajo,capital_inmobiliario,pension",
    ),
    UserProfileFact(path="irpf.estimation_regime", value="directa_simplificada"),
    UserProfileFact(path="iva.sii_enrolled", value=True),
    UserProfileFact(path="iva.redeme_enrolled", value=True),
)


def _fact_value(record: UserProfileRecord, path: str) -> object:
    """Return the single fact value at ``path`` on ``record``."""

    matches = [fact.value for fact in record.facts if fact.path == path]
    assert len(matches) == 1, f"expected exactly one fact at {path!r}, found {len(matches)}"
    return matches[0]


def test_taxpayer_axis_facts_survive_encrypted_sql_roundtrip(
    schema: ProfileSchemaDefinition,
) -> None:
    """Every taxpayer-axis fact survives the real encrypted-SQL cycle.

    Registers a profile carrying the full taxpayer-axis fact set at
    non-default values through ``register_active_profile`` (which
    delegates the cross-store create to ``ProfileRepository``), reloads
    the :class:`UserProfileRecord` from the encrypted store via
    ``read_active_profile``, and asserts every fact survived. The
    reloaded record is then projected through the canonical
    ``taxpayer_profile_from_mapping`` path to confirm the typed
    three-axis model reconstructs correctly on the far side.
    """

    facts = tuple(_required_facts(schema)) + _TAXPAYER_AXIS_FACTS
    # iva.regime is required; override the placeholder with the real
    # REAGP token so the regime axis is exercised non-default.
    facts = tuple(UserProfileFact(path="iva.regime", value="REAGP") if f.path == "iva.regime" else f for f in facts)

    with profile_create_storage_span("taxpayer-axes-roundtrip") as routing_profile_id:
        state = register_active_profile(
            WorkflowState(),
            profile_id="taxpayer-axes-roundtrip",
            display_name="Taxpayer axes operator",
            facts=facts,
            schema=schema,
            routing_profile_id=routing_profile_id,
        )

        record = read_active_profile(state, schema=schema)
    assert record is not None
    assert record.profile_id == "taxpayer-axes-roundtrip"

    # Every taxpayer-axis fact survives the encrypted boundary with its
    # exact persisted value — boolean facts included.
    assert _fact_value(record, "taxpayer_type.entity_type") == "legal_entity"
    assert _fact_value(record, "taxpayer_type.legal_entity_form") == "cooperativa"
    assert _fact_value(record, "taxpayer_type.irpf_income_categories") == "trabajo,capital_inmobiliario,pension"
    assert _fact_value(record, "irpf.estimation_regime") == "directa_simplificada"
    assert _fact_value(record, "iva.regime") == "REAGP"
    assert _fact_value(record, "iva.sii_enrolled") is True
    assert _fact_value(record, "iva.redeme_enrolled") is True

    # The reloaded record reconstructs the typed three-axis taxpayer
    # model through the canonical taxpayer_profile_from_mapping path.
    profile = projection_for_taxpayer(record)
    assert profile.entity_type is EntityType.LEGAL_ENTITY
    assert profile.irpf_income_categories == frozenset(
        {
            IrpfIncomeCategory.TRABAJO,
            IrpfIncomeCategory.CAPITAL_INMOBILIARIO,
            IrpfIncomeCategory.PENSION,
        },
    )
    assert profile.irpf_estimation_regime is IrpfEstimationRegime.DIRECTA_SIMPLIFICADA
    assert profile.iva_regime is IVARegime.REAGP
    assert profile.iva.sii_enrolled is True
    assert profile.iva.redeme_enrolled is True


def test_v1_shaped_record_without_taxpayer_axes_loads_under_v2_schema(
    schema: ProfileSchemaDefinition,
) -> None:
    """A record carrying no taxpayer-axis facts loads cleanly under v2.

    The taxpayer-axis schema change is additive: every taxpayer-axis field is
    ``required = false``. A v1-shaped record — one persisted before the
    taxpayer axes existed, and therefore carrying none of those facts —
    must still load through the encrypted boundary without error and
    must project the new axes to their "undeclared" form (no invented
    entity type or regime, empty income-category set, enrolment flags
    false). This locks the additive-only contract reviewed as M2.
    """

    # A record with the required facts only and no taxpayer-axis facts
    # is structurally identical to a record persisted under the v1
    # schema: the additive fields are simply absent. iva.regime is a
    # required enum field, so it carries the v1-era GENERAL token
    # rather than a non-enum placeholder.
    v1_shaped_facts = tuple(
        UserProfileFact(path="iva.regime", value="GENERAL") if f.path == "iva.regime" else f
        for f in _required_facts(schema)
    )

    with profile_create_storage_span("v1-shaped-record") as routing_profile_id:
        state = register_active_profile(
            WorkflowState(),
            profile_id="v1-shaped-record",
            display_name="Pre-existing operator",
            facts=v1_shaped_facts,
            schema=schema,
            routing_profile_id=routing_profile_id,
        )

        record = read_active_profile(state, schema=schema)
    assert record is not None
    assert record.profile_id == "v1-shaped-record"
    # No taxpayer-axis facts crossed the boundary.
    taxpayer_axis_paths = {
        "taxpayer_type.entity_type",
        "taxpayer_type.legal_entity_form",
        "taxpayer_type.irpf_income_categories",
        "irpf.estimation_regime",
        "iva.sii_enrolled",
        "iva.redeme_enrolled",
    }
    persisted_paths = {fact.path for fact in record.facts}
    assert not (taxpayer_axis_paths & persisted_paths)

    # The undeclared taxpayer model must not invent any axis value.
    profile = projection_for_taxpayer(record)
    assert profile.entity_type is None
    assert profile.legal_entity_form is None
    assert profile.irpf_income_categories == frozenset()
    assert profile.irpf_estimation_regime is None
    assert profile.iva.sii_enrolled is False
    assert profile.iva.redeme_enrolled is False
    # The optional censo alta date is also undeclared for a v1 record.
    assert profile.activity_start_date is None


def test_activity_start_date_fact_survives_encrypted_sql_roundtrip(
    schema: ProfileSchemaDefinition,
) -> None:
    """The optional censo alta date survives the real encrypted-SQL cycle.

    Round-4 testimonial finding D1 added an optional
    ``censo.activity_start_date`` profile fact. A profile carrying it
    at a NON-DEFAULT value (a real 2026 date, not the ``None`` default)
    must round-trip through the encrypted store and reconstruct the
    typed ``date`` on :class:`TaxpayerProfile.activity_start_date`, so
    the deadline engine's pre-registration-obligation gate receives the
    persisted alta date.
    """

    alta = date(2026, 3, 1)
    facts = (
        *(
            UserProfileFact(path="iva.regime", value="GENERAL") if f.path == "iva.regime" else f
            for f in _required_facts(schema)
        ),
        UserProfileFact(path="censo.activity_start_date", value=alta.isoformat()),
    )

    with profile_create_storage_span("activity-start-date-roundtrip") as routing_profile_id:
        state = register_active_profile(
            WorkflowState(),
            profile_id="activity-start-date-roundtrip",
            display_name="2026 registrant",
            facts=facts,
            schema=schema,
            routing_profile_id=routing_profile_id,
        )

        record = read_active_profile(state, schema=schema)
    assert record is not None
    assert record.profile_id == "activity-start-date-roundtrip"
    # The fact survives the encrypted boundary with its exact value;
    # the schema declares the field ``type = "date"``, so the persisted
    # fact reloads as a typed ``date``, not a string.
    assert _fact_value(record, "censo.activity_start_date") == alta

    # The reloaded record reconstructs the typed date on the taxpayer
    # model, so the deadline-engine gate can suppress pre-alta windows.
    profile = projection_for_taxpayer(record)
    assert profile.activity_start_date == alta
