"""Real-behaviour tests for the censal-consulta profile autofill.

Exercises the projection onto declared schema paths, the reconciliation that
adopts only blank paths and reports every disagreement, and the commit
through the single cotejo apply authority — against a real encrypted profile
record via the sanctioned write path, never a mock.

The censal reads here are constructed as real ``CensalDatosResult`` models
rather than parsed from captured HTML: the parser is the adapter's contract
and is tested there, while what these tests defend is the projection and the
adopt-versus-report decision.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from ....adapters.outbound.aeat.sede import CensalDatosResult, CensalDomicilio, CensalIdentity
from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....core.external_constants import PROVENANCE_SOURCE_MANUAL_CLI
from ....core.resources import resources
from ....domain.buckets import BucketEventType
from ....domain.user_profile import ProfileSchemaDefinition, UserProfileFact
from ....tests.aeat_literal_fixtures import aeat_url, configured_path
from ....tests.secure_sql import isolated_profile_storage_root
from ...workflow import WorkflowState
from .. import (
    CENSAL_ADOPTABLE_PATHS,
    CENSO_SOURCE_TAG,
    apply_censal_read,
    censal_facts_from_read,
    open_censo_divergences,
    reconcile_censal_read,
)
from .._orchestration import profile_create_storage_span, register_active_profile, set_active_fields

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "5d5d5d5d-5d5d-4d5d-8d5d-5d5d5d5d5d5d"
#: Source URL stamped on the fixture read. Nothing here asserts it — it only
#: populates a required field — so the origin is deliberately the UNNUMBERED
#: sede host rather than a numbered one. A numbered host is not invariant:
#: the same path answers on one www{n}, 404s on several others, and bounces a
#: session minted elsewhere on another, so pinning one in a fixture would
#: encode the assumption the host-dispatch work exists to remove.
_SOURCE_URL = aeat_url("sede", configured_path("sede_paths", "censal_datos"))


@pytest.fixture(autouse=True)
def _storage_root(tmp_path: Path):
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


@pytest.fixture(scope="module")
def schema() -> ProfileSchemaDefinition:
    return resources().user_profile_schema.singleton


def _read(
    *,
    nif: str = "Y0000001Z",
    apellidos_y_nombre: str = "SANITIZED SURNAME GIVEN",
    codigo_postal: str | None = "08032",
    referencia_catastral: str | None = "0000000AA0000A0000AA",
) -> CensalDatosResult:
    """Build a censal read with the shape MdcAcceso actually renders."""
    domicilio = CensalDomicilio(
        tipo_via="CALLE",
        nombre_via="MAYOR",
        tipo_numero="NUM",
        numero_casa="1",
        planta="3",
        puerta="B",
        codigo_postal=codigo_postal,
        municipio="BARCELONA",
        provincia="BARCELONA",
        referencia_catastral=referencia_catastral,
    )
    return CensalDatosResult(
        identity=CensalIdentity(nif=nif, apellidos_y_nombre=apellidos_y_nombre),
        domicilio_fiscal=domicilio,
        domicilio_notificacion=domicilio,
        captured_at=datetime(2026, 7, 25, 12, 0, tzinfo=UTC),
        source_url=AnyHttpUrl(_SOURCE_URL),
    )


def _required_facts(schema: ProfileSchemaDefinition) -> tuple[UserProfileFact, ...]:
    facts: list[UserProfileFact] = []
    for section in schema.sections:
        if section.repeatable:
            continue
        for field in section.fields:
            if field.required:
                facts.append(UserProfileFact(path=f"{section.key}.{field.key}", value="placeholder"))
    return tuple(facts)


def _register(schema: ProfileSchemaDefinition, routing_profile_id: str) -> WorkflowState:
    return register_active_profile(
        WorkflowState(),
        profile_id=_PROFILE_ID,
        display_name="Censal sync test profile",
        facts=_required_facts(schema),
        schema=schema,
        routing_profile_id=routing_profile_id,
    )


def _censo_applied_count() -> int:
    catalogue = BucketEventHistoryRepository().load()
    return sum(1 for event in catalogue.events.values() if event.event_type is BucketEventType.CENSO_APPLIED)


def _value_at(state: WorkflowState, schema: ProfileSchemaDefinition, path: str) -> str | None:
    record = state.active_profile_record(schema=schema)
    assert record is not None
    latest: str | None = None
    for fact in record.facts:
        if fact.path == path:
            latest = None if fact.value is None else str(fact.value)
    return latest


class TestProjection:
    """The read is projected onto declared paths, stamped as an AEAT read."""

    def test_every_projected_path_is_declared_by_the_schema(self, schema: ProfileSchemaDefinition) -> None:
        declared = {f"{section.key}.{field.key}" for section in schema.sections for field in section.fields}
        for fact in censal_facts_from_read(_read()):
            assert fact.path in declared, f"{fact.path} is not a declared profile path"

    def test_projection_carries_the_declared_aeat_read_provenance(self, schema: ProfileSchemaDefinition) -> None:
        declared_sources = {
            tuple(field.enum_values or ())
            for section in schema.sections
            if section.key == "provenance"
            for field in section.fields
            if field.key == "source"
        }
        assert declared_sources, "the schema no longer declares a provenance source enum"
        allowed = next(iter(declared_sources))
        for fact in censal_facts_from_read(_read()):
            assert fact.source == CENSO_SOURCE_TAG
            assert fact.source in allowed

    def test_address_parts_are_composed_into_the_single_declared_field(self) -> None:
        values = {fact.path: str(fact.value) for fact in censal_facts_from_read(_read())}
        composed = values["contact.fiscal_address"]
        for part in ("CALLE", "MAYOR", "1", "BARCELONA"):
            assert part in composed

    def test_absent_read_fields_emit_no_fact(self) -> None:
        values = {fact.path: fact.value for fact in censal_facts_from_read(_read(codigo_postal=None))}
        assert "contact.postcode" not in values
        assert "contact.fiscal_address_cadastral_reference" in values

    def test_combined_name_is_never_split_into_given_name_and_surnames(self) -> None:
        """A single-surname holder with two given names must not be mangled.

        AEAT renders one combined *Apellidos y Nombre*. Assuming the Spanish
        two-surname convention would parse "SURNAME GIVEN1 GIVEN2" as two
        surnames plus one given name, reversing the operator's identity. The
        projection therefore emits neither name field, and must not smuggle
        the combined string into some other path either.
        """
        facts = censal_facts_from_read(_read(apellidos_y_nombre="SURNAME GIVEN1 GIVEN2"))
        paths = {fact.path for fact in facts}
        assert "identity.name" not in paths
        assert "identity.surnames" not in paths
        assert not any("GIVEN1 GIVEN2" in str(fact.value) for fact in facts)
        assert "identity.name" not in CENSAL_ADOPTABLE_PATHS


class TestReconciliation:
    """Blank paths adopt; equal paths no-op; differing paths are reported."""

    def test_blank_paths_are_adopted(self) -> None:
        outcome = reconcile_censal_read(None, censal_facts_from_read(_read()))
        assert {fact.path for fact in outcome.adopted} == {fact.path for fact in censal_facts_from_read(_read())}
        assert outcome.divergences == ()

    def test_matching_declared_value_is_neither_adopted_nor_reported(
        self,
        schema: ProfileSchemaDefinition,
    ) -> None:
        with profile_create_storage_span(_PROFILE_ID) as routing:
            state = _register(schema, routing)
            state = set_active_fields(state, (UserProfileFact(path="contact.postcode", value="08032"),))
            outcome = reconcile_censal_read(state.active_profile_record(schema=schema), censal_facts_from_read(_read()))
            assert "contact.postcode" not in {fact.path for fact in outcome.adopted}
            assert "contact.postcode" not in {axis for axis, _ in outcome.divergences}

    def test_conflicting_declared_value_is_reported_not_overwritten(
        self,
        schema: ProfileSchemaDefinition,
    ) -> None:
        with profile_create_storage_span(_PROFILE_ID) as routing:
            state = _register(schema, routing)
            state = set_active_fields(state, (UserProfileFact(path="contact.postcode", value="28001"),))
            outcome = reconcile_censal_read(state.active_profile_record(schema=schema), censal_facts_from_read(_read()))
            assert ("contact.postcode", "08032") in outcome.divergences
            assert "contact.postcode" not in {fact.path for fact in outcome.adopted}

    def test_a_previously_pulled_value_refreshes_instead_of_diverging(
        self,
        schema: ProfileSchemaDefinition,
    ) -> None:
        """A changed authority value must not diverge against the authority.

        When the recorded value carries the censal-read token, a previous
        pull wrote it and there is no operator answer to protect. Reporting
        a divergence would strand the profile on the stale value forever and
        assert a conflict between two values that are both AEAT's.
        """
        with profile_create_storage_span(_PROFILE_ID) as routing:
            state = _register(schema, routing)
            state = set_active_fields(
                state,
                (UserProfileFact(path="contact.postcode", value="08032", source=CENSO_SOURCE_TAG),),
            )
            outcome = reconcile_censal_read(
                state.active_profile_record(schema=schema),
                censal_facts_from_read(_read(codigo_postal="08033")),
            )
            assert "contact.postcode" not in {axis for axis, _ in outcome.divergences}
            refreshed = {fact.path: str(fact.value) for fact in outcome.adopted}
            assert refreshed["contact.postcode"] == "08033"

    @pytest.mark.parametrize(
        ("source", "expect_divergence"),
        [
            pytest.param(CENSO_SOURCE_TAG, False, id="previously-pulled-refreshes"),
            pytest.param(PROVENANCE_SOURCE_MANUAL_CLI, True, id="operator-declared-diverges"),
        ],
    )
    def test_provenance_decides_the_conflict_not_the_value(
        self,
        schema: ProfileSchemaDefinition,
        source: str,
        expect_divergence: bool,
    ) -> None:
        """The same value conflict resolves oppositely by who wrote it.

        Anti-tautology: both cases present an identical recorded-versus-read
        disagreement (08032 on record, 08033 from AEAT) and differ ONLY in the
        recorded fact's provenance. A reconciliation that ignored provenance
        would give both the same answer and could not satisfy both cases.
        """
        with profile_create_storage_span(_PROFILE_ID) as routing:
            state = _register(schema, routing)
            state = set_active_fields(
                state,
                (UserProfileFact(path="contact.postcode", value="08032", source=source),),
            )
            outcome = reconcile_censal_read(
                state.active_profile_record(schema=schema),
                censal_facts_from_read(_read(codigo_postal="08033")),
            )
            diverged = "contact.postcode" in {axis for axis, _ in outcome.divergences}
            assert diverged is expect_divergence, f"source={source} diverged={diverged}"


class TestApply:
    """The commit routes through the one cotejo authority."""

    def test_apply_adopts_blank_paths_and_emits_exactly_one_event(self, schema: ProfileSchemaDefinition) -> None:
        with profile_create_storage_span(_PROFILE_ID) as routing:
            state = _register(schema, routing)
            before = _censo_applied_count()
            state = apply_censal_read(state, _read())
            assert _value_at(state, schema, "contact.postcode") == "08032"
            assert _censo_applied_count() == before + 1

    def test_apply_never_overwrites_an_operator_declared_answer(self, schema: ProfileSchemaDefinition) -> None:
        with profile_create_storage_span(_PROFILE_ID) as routing:
            state = _register(schema, routing)
            state = set_active_fields(state, (UserProfileFact(path="contact.postcode", value="28001"),))
            state = apply_censal_read(state, _read())
            assert _value_at(state, schema, "contact.postcode") == "28001"
            axes = {
                divergence.axis for divergence in open_censo_divergences(state.active_profile_record(schema=schema))
            }
            assert "contact.postcode" in axes
