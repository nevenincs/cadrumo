"""The cotejo preserves the certificate's obligation prose instead of dropping it.

The Certificado de Situación Censal certifies two obligation-bearing fields —
``situacion_tributaria`` and ``obligaciones_periodicas`` — whose printed
vocabulary is unpinned until a real G313 specimen exists. The cotejo therefore
adopts NEITHER as a typed profile fact (mapping their prose onto the Ley
49/2002 régimen axis, or onto any other, would be invented tax semantics), and
preserves both verbatim as unadopted-evidence divergence rows so AEAT's
certified statement reaches the operator rather than being discarded.

These tests drive the real encrypted profile write path through
``apply_cotejo``, never a mock: the property that matters is that the evidence
survives persistence and re-emerges on the standing warning.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....core.external_constants import PROVENANCE_SOURCE_CENSO_ARTEFACT
from ....core.json_contract import NoticeSeverity
from ....core.resources import resources
from ....domain.censo import (
    ActividadLocalCertificada,
    CertificadoSituacionCensal,
    censo_facts_from_certificado,
)
from ....domain.user_profile import ProfileSchemaDefinition, UserProfileFact
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import complete_conditional_facts, schema_valid_placeholder
from ...workflow import WorkflowState
from .. import (
    CENSO_CERTIFICATE_AXIS_PREFIX,
    CENSO_UNADOPTED_EVIDENCE_FIELDS,
    apply_cotejo,
    censo_divergence_notice,
    censo_unadopted_evidence,
    open_censo_divergences,
)
from .._orchestration import profile_create_storage_span, register_active_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "6e6e6e6e-6e6e-4e6e-8e6e-6e6e6e6e6e6e"

#: A certified line that CONTAINS the punctuation a joined-string projection
#: would have to use as its separator. If the projection ever collapses the
#: certified lines into one value, this line is the one that gets silently
#: re-split into two obligations that AEAT never certified.
_SEPARATOR_BEARING_LINE = "Obligación 303; con periodicidad trimestral"


def _certificado() -> CertificadoSituacionCensal:
    return CertificadoSituacionCensal(
        domicilio_fiscal="CALLE MAYOR 1, 08032 BARCELONA",
        condicion_residencia="Residente",
        situacion_tributaria=("Alta en el censo de empresarios",),
        actividades=(ActividadLocalCertificada(descripcion="Servicios", epigrafe_iae="763"),),
        obligaciones_periodicas=(_SEPARATOR_BEARING_LINE, "130 trimestral"),
    )


@pytest.fixture(autouse=True)
def _storage_root(tmp_path: Path):
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


@pytest.fixture(scope="module")
def schema() -> ProfileSchemaDefinition:
    return resources().user_profile_schema.singleton


def _required_facts(schema: ProfileSchemaDefinition) -> tuple[UserProfileFact, ...]:
    """Fill every schema-required non-repeatable field through the shared filler.

    The shared ``schema_valid_placeholder`` is used rather than a local table
    so this fixture inherits the guard that sweeps it against every declared
    field, instead of privately restating the admissibility rule.
    """
    facts: list[UserProfileFact] = []
    for section in schema.sections:
        if section.repeatable:
            continue
        facts.extend(
            UserProfileFact(path=f"{section.key}.{field.key}", value=schema_valid_placeholder(field))
            for field in section.fields
            if field.required
        )
    return complete_conditional_facts(schema, facts)


def _register(schema: ProfileSchemaDefinition, routing_profile_id: str) -> WorkflowState:
    return register_active_profile(
        WorkflowState(),
        profile_id=_PROFILE_ID,
        display_name="Cotejo evidence test profile",
        facts=_required_facts(schema),
        schema=schema,
        routing_profile_id=routing_profile_id,
    )


class TestNoRegimenAdoption:
    """The régimen axis is not adopted from certificate prose."""

    def test_the_certificate_projects_no_regimen_fact(self) -> None:
        """No certified field becomes a Ley 49/2002 régimen profile fact.

        The régimen axis drives deadline derivation, so an adoption grounded
        only in a guessed phrase mapping would put an invented tax semantic on
        the filing calendar. Asserted over the projection's whole output, not
        a named path, so adding a régimen projection anywhere reds this.
        """
        adopted = censo_facts_from_certificado(_certificado())
        assert adopted, "the projection must still adopt the axes it CAN ground"
        assert not [fact for fact in adopted if "special_regime" in fact.path]
        assert not [fact for fact in adopted if fact.path.startswith("taxpayer_type.")]

    def test_unadopted_evidence_never_names_a_profile_regimen_path(self) -> None:
        """Evidence rows address the certificate namespace, not profile state."""
        rows = censo_unadopted_evidence(_certificado())
        assert rows
        for row in rows:
            assert row.axis.startswith(f"{CENSO_CERTIFICATE_AXIS_PREFIX}.")
            assert "special_regime" not in row.axis


class TestEvidenceIsPreservedVerbatim:
    """Every certified obligation line survives as its own row, unparsed."""

    def test_each_certified_line_becomes_one_row_carrying_it_byte_for_byte(self) -> None:
        certificado = _certificado()
        rows = censo_unadopted_evidence(certificado)
        expected = [
            *certificado.situacion_tributaria,
            *certificado.obligaciones_periodicas,
        ]
        assert [row.artefact_value for row in rows] == expected
        assert _SEPARATOR_BEARING_LINE in {row.artefact_value for row in rows}
        assert all(row.source == PROVENANCE_SOURCE_CENSO_ARTEFACT for row in rows)

    def test_every_declared_evidence_field_is_actually_projected(self) -> None:
        """The declared field set drives the projection, so neither can rot.

        A field added to ``CENSO_UNADOPTED_EVIDENCE_FIELDS`` but never read
        would leave that certified statement silently discarded again — the
        exact defect this projection exists to close.
        """
        rows = censo_unadopted_evidence(_certificado())
        addressed = {row.axis.rsplit(".", 1)[0] for row in rows}
        assert addressed == {f"{CENSO_CERTIFICATE_AXIS_PREFIX}.{field}" for field in CENSO_UNADOPTED_EVIDENCE_FIELDS}

    def test_a_certificate_with_no_obligation_prose_yields_no_rows(self) -> None:
        """A clean certificate carries no standing warning."""
        bare = CertificadoSituacionCensal(
            domicilio_fiscal="CALLE MAYOR 1",
            condicion_residencia="Residente",
        )
        assert censo_unadopted_evidence(bare) == ()


class TestEvidenceSurvivesTheWritePath:
    """The rows persist through the real cotejo commit and re-emerge."""

    def test_apply_persists_the_evidence_and_raises_the_standing_warning(
        self,
        schema: ProfileSchemaDefinition,
    ) -> None:
        with profile_create_storage_span(_PROFILE_ID) as routing:
            state = _register(schema, routing)
            certificado = _certificado()
            state = apply_cotejo(
                state,
                adopted=censo_facts_from_certificado(certificado),
                divergences=censo_unadopted_evidence(certificado),
            )
            record = state.active_profile_record(schema=schema)
            reloaded = open_censo_divergences(record)
            assert [row.artefact_value for row in reloaded] == [
                *certificado.situacion_tributaria,
                *certificado.obligaciones_periodicas,
            ]
            notice = censo_divergence_notice(record)
            assert notice is not None
            assert notice.severity is NoticeSeverity.WARNING
            assert notice.context is not None
            assert notice.context["count"] == str(len(reloaded))

    def test_a_re_cotejo_with_fewer_obligations_clears_the_stale_row(
        self,
        schema: ProfileSchemaDefinition,
    ) -> None:
        """A dropped obligation must not keep warning after AEAT drops it.

        The namespace-replace is the property under test: a shrinking
        certificate leaves no orphan evidence standing.
        """
        with profile_create_storage_span(_PROFILE_ID) as routing:
            state = _register(schema, routing)
            first = _certificado()
            state = apply_cotejo(
                state,
                adopted=(),
                divergences=censo_unadopted_evidence(first),
            )
            shrunk = first.model_copy(update={"obligaciones_periodicas": ()})
            state = apply_cotejo(
                state,
                adopted=(),
                divergences=censo_unadopted_evidence(shrunk),
            )
            record = state.active_profile_record(schema=schema)
            assert [row.artefact_value for row in open_censo_divergences(record)] == list(
                shrunk.situacion_tributaria,
            )

    def test_evidence_rows_coexist_with_an_operator_deferred_profile_axis(
        self,
        schema: ProfileSchemaDefinition,
    ) -> None:
        """Certificate-side and profile-side axes share one divergence namespace."""
        from .. import CensoDivergence

        with profile_create_storage_span(_PROFILE_ID) as routing:
            state = _register(schema, routing)
            certificado = _certificado()
            operator_deferred = CensoDivergence(
                axis="contact.fiscal_address",
                artefact_value=certificado.domicilio_fiscal,
            )
            state = apply_cotejo(
                state,
                adopted=(UserProfileFact(path="contact.postcode", value="08032"),),
                divergences=(operator_deferred, *censo_unadopted_evidence(certificado)),
            )
            axes = {row.axis for row in open_censo_divergences(state.active_profile_record(schema=schema))}
            assert "contact.fiscal_address" in axes
            assert any(axis.startswith(f"{CENSO_CERTIFICATE_AXIS_PREFIX}.") for axis in axes)
