"""Real-behaviour tests for the cotejo censal apply write path.

Exercises adopt / defer commit, the ``censo.divergencia.{n}.*`` persistence
with the open-divergence warning notice, the single ``CENSO_APPLIED`` event
contract, and the namespace-replace clearing on re-cotejo — all against a
real encrypted profile record through the sanctioned write path, never a
mock. The cotejo family is unreachable live until a G313 specimen pins the
parser, so the certificate-derived facts are constructed directly here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....core.external_constants import PROVENANCE_SOURCE_CENSO_ARTEFACT, PROVENANCE_SOURCE_MANUAL_CLI
from ....core.resources import resources
from ....domain.buckets import BucketEventType
from ....domain.user_profile import ProfileSchemaDefinition, UserProfileFact
from ....tests.secure_sql import isolated_profile_storage_root
from ...workflow import WorkflowState, workflow_state_repository
from .. import (
    CensoDivergence,
    apply_cotejo,
    censo_divergence_notice,
    open_censo_divergences,
)
from .._orchestration import profile_create_storage_span, register_active_profile, set_active_fields

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "3c3c3c3c-3c3c-4c3c-8c3c-3c3c3c3c3c3c"
_ACTIVITY_PATH = "activities.description"


@pytest.fixture(autouse=True)
def _storage_root(tmp_path: Path):
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


@pytest.fixture(scope="module")
def schema() -> ProfileSchemaDefinition:
    return resources().user_profile_schema.singleton


def _required_facts(schema: ProfileSchemaDefinition) -> tuple[UserProfileFact, ...]:
    facts: list[UserProfileFact] = []
    for section in schema.sections:
        if section.repeatable:
            continue
        for field in section.fields:
            if field.required:
                facts.append(UserProfileFact(path=f"{section.key}.{field.key}", value=(field.enum_values[0] if field.enum_values else "placeholder")))
    return tuple(facts)


def _register(schema: ProfileSchemaDefinition, routing_profile_id: str) -> WorkflowState:
    return register_active_profile(
        WorkflowState(),
        profile_id=_PROFILE_ID,
        display_name="Cotejo test profile",
        facts=_required_facts(schema),
        schema=schema,
        routing_profile_id=routing_profile_id,
    )


def _censo_applied_count() -> int:
    catalogue = BucketEventHistoryRepository().load()
    return sum(1 for event in catalogue.events.values() if event.event_type is BucketEventType.CENSO_APPLIED)


def _fact_source(state: WorkflowState, schema: ProfileSchemaDefinition, path: str, value: str) -> str | None:
    record = state.active_profile_record(schema=schema)
    assert record is not None
    for fact in record.facts:
        if fact.path == path and fact.value == value:
            return fact.source
    return None


def test_adopt_commit_persists_provenance_stamped_fact_and_one_event(schema: ProfileSchemaDefinition) -> None:
    with profile_create_storage_span(_PROFILE_ID) as routing_profile_id:
        state = _register(schema, routing_profile_id)
        adopted = (
            UserProfileFact(
                path=_ACTIVITY_PATH,
                value="Consultoria informatica",
                source=PROVENANCE_SOURCE_CENSO_ARTEFACT,
            ),
        )
        state = apply_cotejo(state, adopted=adopted, divergences=())
        assert (
            _fact_source(state, schema, _ACTIVITY_PATH, "Consultoria informatica") == PROVENANCE_SOURCE_CENSO_ARTEFACT
        )
        assert _censo_applied_count() == 1


def test_defer_commit_persists_divergence_rows_and_read_surfaces_warning(schema: ProfileSchemaDefinition) -> None:
    with profile_create_storage_span(_PROFILE_ID) as routing_profile_id:
        state = _register(schema, routing_profile_id)
        divergences = (
            CensoDivergence(axis=_ACTIVITY_PATH, artefact_value="Consultoria informatica"),
            CensoDivergence(axis="contact.fiscal_address", artefact_value="Calle Mayor 1"),
        )
        state = apply_cotejo(state, adopted=(), divergences=divergences)

        record = state.active_profile_record(schema=schema)
        open_rows = open_censo_divergences(record)
        assert {row.axis for row in open_rows} == {_ACTIVITY_PATH, "contact.fiscal_address"}
        assert all(row.source == PROVENANCE_SOURCE_CENSO_ARTEFACT for row in open_rows)

        notice = censo_divergence_notice(record)
        assert notice is not None
        assert notice.code == "profile.censo.divergences_open"
        assert notice.severity.value == "warning"
        assert notice.context is not None
        assert notice.context["count"] == "2"
        assert _censo_applied_count() == 1


def test_clean_profile_read_surfaces_no_divergence_notice(schema: ProfileSchemaDefinition) -> None:
    with profile_create_storage_span(_PROFILE_ID) as routing_profile_id:
        state = _register(schema, routing_profile_id)
        record = state.active_profile_record(schema=schema)
        assert open_censo_divergences(record) == ()
        assert censo_divergence_notice(record) is None


def test_recotejo_clears_stale_divergence_rows_the_fresh_set_omits(schema: ProfileSchemaDefinition) -> None:
    with profile_create_storage_span(_PROFILE_ID) as routing_profile_id:
        state = _register(schema, routing_profile_id)
        state = apply_cotejo(
            state,
            adopted=(),
            divergences=(
                CensoDivergence(axis=_ACTIVITY_PATH, artefact_value="Consultoria informatica"),
                CensoDivergence(axis="contact.fiscal_address", artefact_value="Calle Mayor 1"),
            ),
        )
        assert len(open_censo_divergences(state.active_profile_record(schema=schema))) == 2

        # Re-cotejo declares a single, different divergence: the stale rows
        # the fresh set does not re-declare must be cleared, never left standing.
        state = apply_cotejo(
            state,
            adopted=(),
            divergences=(CensoDivergence(axis="contact.fiscal_address", artefact_value="Calle Nueva 7"),),
        )
        open_rows = open_censo_divergences(state.active_profile_record(schema=schema))
        assert [(row.axis, row.artefact_value) for row in open_rows] == [("contact.fiscal_address", "Calle Nueva 7")]


def test_adopt_all_shape_emits_one_event_the_file_door_routing(schema: ProfileSchemaDefinition) -> None:
    """The ``censo file --apply`` door is the adopt-all shape of this authority.

    Every mapped censo fact adopted, none deferred — the exact call the door
    makes (``apply_cotejo(state, adopted=facts, divergences=())``). One
    ``CENSO_APPLIED`` marks the artefact-apply, and each adopted fact carries
    the non-official provenance token.
    """
    from ....domain.censo import ActividadLocalCertificada, CertificadoSituacionCensal, censo_facts_from_certificado

    certificado = CertificadoSituacionCensal(
        domicilio_fiscal="Calle Mayor 1, 28013 Madrid",
        condicion_residencia="Residente",
        actividades=(ActividadLocalCertificada(descripcion="Consultoria informatica", epigrafe_iae="899"),),
    )
    facts = censo_facts_from_certificado(certificado)
    assert facts  # the adopt-all set the door persists
    with profile_create_storage_span(_PROFILE_ID) as routing_profile_id:
        state = _register(schema, routing_profile_id)
        state = apply_cotejo(state, adopted=facts, divergences=())
        record = state.active_profile_record(schema=schema)
        assert record is not None
        adopted_sources = {fact.source for fact in record.facts if fact.source == PROVENANCE_SOURCE_CENSO_ARTEFACT}
        assert adopted_sources == {PROVENANCE_SOURCE_CENSO_ARTEFACT}
        assert _censo_applied_count() == 1


def test_apply_emits_exactly_one_event_regardless_of_fact_count(schema: ProfileSchemaDefinition) -> None:
    """The apply-commit marker is one CENSO_APPLIED, never one per fact."""
    with profile_create_storage_span(_PROFILE_ID) as routing_profile_id:
        state = _register(schema, routing_profile_id)
        apply_cotejo(
            state,
            adopted=(
                UserProfileFact(
                    path=_ACTIVITY_PATH,
                    value="Consultoria informatica",
                    source=PROVENANCE_SOURCE_CENSO_ARTEFACT,
                ),
            ),
            divergences=(
                CensoDivergence(axis="contact.fiscal_address", artefact_value="Calle Mayor 1"),
                CensoDivergence(axis="contact.fiscal_address_is_habitual_vivienda", artefact_value="true"),
            ),
        )
        # Three fact writes (one adopted + two divergence rows across six
        # subpath writes), but exactly one apply-commit event.
        assert _censo_applied_count() == 1


def test_adopt_all_clears_pre_existing_open_divergences(schema: ProfileSchemaDefinition) -> None:
    """A file-door adopt-all replaces the divergence namespace deliberately.

    Declaring zero deferred means a full reconciliation: any divergence a
    prior cotejo left open cannot coherently remain standing after an
    adopt-all apply, so the namespace-replace clears it — intentional
    semantics, pinned here directly rather than inferred from the re-cotejo
    case. Each apply-commit still marks exactly one event.
    """
    from ....domain.censo import ActividadLocalCertificada, CertificadoSituacionCensal, censo_facts_from_certificado

    with profile_create_storage_span(_PROFILE_ID) as routing_profile_id:
        state = _register(schema, routing_profile_id)
        state = apply_cotejo(
            state,
            adopted=(),
            divergences=(CensoDivergence(axis=_ACTIVITY_PATH, artefact_value="Consultoria informatica"),),
        )
        assert len(open_censo_divergences(state.active_profile_record(schema=schema))) == 1

        certificado = CertificadoSituacionCensal(
            domicilio_fiscal="Calle Mayor 1, 28013 Madrid",
            condicion_residencia="Residente",
            actividades=(ActividadLocalCertificada(descripcion="Consultoria informatica", epigrafe_iae="899"),),
        )
        state = apply_cotejo(state, adopted=censo_facts_from_certificado(certificado), divergences=())

        record = state.active_profile_record(schema=schema)
        assert open_censo_divergences(record) == ()
        assert censo_divergence_notice(record) is None
        assert _censo_applied_count() == 2


def test_divergence_rows_survive_encrypted_reload_with_strict_equality(schema: ProfileSchemaDefinition) -> None:
    """Roundtrip: two divergence rows survive a FRESH encrypted-store reload.

    The other defer tests read the in-memory ``WorkflowState`` projection;
    this one reloads the record afresh through the workflow repository, so
    the assertion exercises the genuine save -> encrypt -> decrypt -> load
    boundary. Every subfield of both rows is populated NON-DEFAULT: distinct
    ``axis`` and ``artefact_value`` per row, and ``source`` set to
    ``PROVENANCE_SOURCE_MANUAL_CLI`` (the non-default vs the
    ``CensoDivergence.source`` artefact-token default). A save-drops-subfield
    regression on ``source`` would re-default the reloaded row to the
    artefact token and break the strict tuple equality below.
    """
    with profile_create_storage_span(_PROFILE_ID) as routing_profile_id:
        state = _register(schema, routing_profile_id)
        divergences = (
            CensoDivergence(
                axis=_ACTIVITY_PATH,
                artefact_value="Consultoria informatica",
                source=PROVENANCE_SOURCE_MANUAL_CLI,
            ),
            CensoDivergence(
                axis="contact.fiscal_address",
                artefact_value="Calle Mayor 1",
                source=PROVENANCE_SOURCE_MANUAL_CLI,
            ),
        )
        apply_cotejo(state, adopted=(), divergences=divergences)

        # Fresh reload from the encrypted repository -- not the in-memory state.
        reloaded = workflow_state_repository().load().active_profile_record()
        assert open_censo_divergences(reloaded) == divergences


def test_divergence_read_is_driven_by_persisted_subfields(schema: ProfileSchemaDefinition) -> None:
    """Anti-tautology: clearing one persisted subfield strictly changes the read.

    Proves the reconstructed divergence set reflects on-disk facts, never a
    constant. After persisting two rows, one row's ``artefact_value`` subpath
    is cleared through the canonical ``value=None`` fact-removal seam (the
    lowest legitimate write, never a mock); a fresh reload then omits that
    incomplete index, so the reconstructed set strictly differs. If the read
    were tautological (hardcoded), the clear would not move it.
    """
    with profile_create_storage_span(_PROFILE_ID) as routing_profile_id:
        state = _register(schema, routing_profile_id)
        divergences = (
            CensoDivergence(
                axis=_ACTIVITY_PATH,
                artefact_value="Consultoria informatica",
                source=PROVENANCE_SOURCE_MANUAL_CLI,
            ),
            CensoDivergence(
                axis="contact.fiscal_address",
                artefact_value="Calle Mayor 1",
                source=PROVENANCE_SOURCE_MANUAL_CLI,
            ),
        )
        state = apply_cotejo(state, adopted=(), divergences=divergences)
        before = open_censo_divergences(workflow_state_repository().load().active_profile_record())
        assert before == divergences

        # Remove index 0's artefact_value subfield via the canonical clearing
        # fact; index 0 becomes incomplete and drops from the reconstruction.
        set_active_fields(state, (UserProfileFact(path="censo.divergencia.0.artefact_value", value=None),))

        after = open_censo_divergences(workflow_state_repository().load().active_profile_record())
        assert after != before
        assert [row.axis for row in after] == ["contact.fiscal_address"]
