"""Persistence-boundary roundtrip for the IRPF special-regime axis.

Task #162: Profile schema axis irpf_special_regime + special_regime_start_date
(Beckham foundation). Grounds LIRPF Art. 93 (Ley Beckham) in the profile
schema so downstream task #163 (M720 NOT_APPLICABLE) and the M151 stub
refusal guard can interrogate the axis without string-matching.

Three contract claims exercised here:

1. An ``impatriado`` special-regime fact + a ``special_regime_start_date``
   fact both survive the real encrypted-SQL roundtrip and project onto the
   typed ``TaxpayerProfile`` fields introduced in task #162.

2. A record carrying no special-regime facts (the common case — the vast
   majority of taxpayers are on the general regime) loads cleanly and
   projects ``irpf_special_regime = None``, ``special_regime_start_date =
   None``.

3. Anti-tautology: mutating the stored fact from ``impatriado`` back to
   ``general`` produces a ``TaxpayerProfile`` whose ``irpf_special_regime``
   field differs from the ``impatriado`` value — proving the projection
   is not hard-coded.

Real adapters only: real encrypted-SQL store, real active-profile runtime,
real schema loader.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from ....core.resources import resources
from ....domain.deadlines import IrpfSpecialRegime
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
    facts: list[UserProfileFact] = []
    for section in schema.sections:
        if section.repeatable:
            continue
        for field in section.fields:
            if field.required:
                facts.append(UserProfileFact(path=f"{section.key}.{field.key}", value="placeholder"))
    return facts


def _fact_value(record: UserProfileRecord, path: str) -> object:
    matches = [fact.value for fact in record.facts if fact.path == path]
    assert len(matches) == 1, f"expected exactly one fact at {path!r}, found {len(matches)}"
    return matches[0]


def test_impatriado_regime_and_start_date_survive_encrypted_sql_roundtrip(
    schema: ProfileSchemaDefinition,
) -> None:
    """irpf.special_regime + irpf.special_regime_start_date survive the
    real encrypted-SQL cycle and project onto the typed TaxpayerProfile fields.

    The election date is a non-default value (2023-01-15) so a
    save-drops-fact / load-re-defaults-fact regression surfaces as a typed
    date mismatch rather than passing silently.
    """

    election_date = date(2023, 1, 15)
    facts = (
        *(
            UserProfileFact(path="iva.regime", value="GENERAL") if f.path == "iva.regime" else f
            for f in _required_facts(schema)
        ),
        UserProfileFact(path="irpf.special_regime", value="impatriado"),
        UserProfileFact(path="irpf.special_regime_start_date", value=election_date.isoformat()),
    )

    with profile_create_storage_span("impatriado-roundtrip") as routing_profile_id:
        state = register_active_profile(
            WorkflowState(),
            profile_id="impatriado-roundtrip",
            display_name="Beckham-regime operator",
            facts=facts,
            schema=schema,
            routing_profile_id=routing_profile_id,
        )

        record = read_active_profile(state, schema=schema)
    assert record is not None
    assert record.profile_id == "impatriado-roundtrip"

    # Both facts cross the encrypted boundary with their exact persisted values.
    assert _fact_value(record, "irpf.special_regime") == "impatriado"
    # irpf.special_regime_start_date is a date type in the schema, so
    # the persisted fact reloads as a typed date, not a bare string.
    assert _fact_value(record, "irpf.special_regime_start_date") == election_date

    # The reloaded record projects to the typed TaxpayerProfile fields.
    profile = projection_for_taxpayer(record)
    assert profile.irpf_special_regime is IrpfSpecialRegime.IMPATRIADO
    assert profile.special_regime_start_date == election_date


def test_record_without_special_regime_projects_to_none(
    schema: ProfileSchemaDefinition,
) -> None:
    """A record carrying no irpf.special_regime fact loads cleanly and
    projects irpf_special_regime = None, special_regime_start_date = None.

    The general regime is the default for the overwhelming majority of
    taxpayers; an absent fact must not be invented as IMPATRIADO.
    """

    facts = tuple(
        UserProfileFact(path="iva.regime", value="GENERAL") if f.path == "iva.regime" else f
        for f in _required_facts(schema)
    )

    with profile_create_storage_span("general-regime-no-special") as routing_profile_id:
        state = register_active_profile(
            WorkflowState(),
            profile_id="general-regime-no-special",
            display_name="General-regime operator",
            facts=facts,
            schema=schema,
            routing_profile_id=routing_profile_id,
        )

        record = read_active_profile(state, schema=schema)
    assert record is not None
    # Neither fact was stored.
    persisted_paths = {fact.path for fact in record.facts}
    assert "irpf.special_regime" not in persisted_paths
    assert "irpf.special_regime_start_date" not in persisted_paths

    # Undeclared axes project to None, not GENERAL or any invented value.
    profile = projection_for_taxpayer(record)
    assert profile.irpf_special_regime is None
    assert profile.special_regime_start_date is None


def test_anti_tautology_mutating_regime_changes_projection(
    schema: ProfileSchemaDefinition,
) -> None:
    """Anti-tautology: projecting ``general`` yields a different
    irpf_special_regime than projecting ``impatriado``.

    If the projection were tautologically true (e.g. always returning None,
    or always returning IMPATRIADO regardless of the stored value) this
    test would fail on the inequality assertion.
    """

    def _build_record(regime_value: str) -> UserProfileRecord:
        extra: list[UserProfileFact] = [UserProfileFact(path="irpf.special_regime", value=regime_value)]
        if regime_value == "impatriado":
            # special_regime_start_date is now required when irpf_special_regime
            # is IMPATRIADO (TaxpayerProfile SCHEMA-001 validator, task #191).
            extra.append(UserProfileFact(path="irpf.special_regime_start_date", value="2023-01-01"))
        facts = (
            *(
                UserProfileFact(path="iva.regime", value="GENERAL") if f.path == "iva.regime" else f
                for f in _required_facts(schema)
            ),
            *extra,
        )
        profile_id = f"anti-tautology-{regime_value}"
        with profile_create_storage_span(profile_id) as routing_profile_id:
            state = register_active_profile(
                WorkflowState(),
                profile_id=profile_id,
                display_name=f"Anti-tautology {regime_value}",
                facts=facts,
                schema=schema,
                routing_profile_id=routing_profile_id,
                # The two records are the same taxpayer re-declared with a
                # mutated regime (both carry the shared placeholder tax id),
                # so the cross-bucket duplicate-tax-id refusal is not the
                # contract under test here — the projection inequality is.
                enforce_unique_tax_id=False,
            )
            record = read_active_profile(state, schema=schema)
            assert record is not None, "active profile must resolve immediately after registration"
            return record

    record_impatriado = _build_record("impatriado")
    record_general = _build_record("general")

    assert record_impatriado is not None
    assert record_general is not None

    profile_impatriado = projection_for_taxpayer(record_impatriado)
    profile_general = projection_for_taxpayer(record_general)

    # The two projections must differ — neither is tautologically the same.
    assert profile_impatriado.irpf_special_regime is IrpfSpecialRegime.IMPATRIADO
    assert profile_general.irpf_special_regime is IrpfSpecialRegime.GENERAL
    assert profile_impatriado.irpf_special_regime != profile_general.irpf_special_regime
