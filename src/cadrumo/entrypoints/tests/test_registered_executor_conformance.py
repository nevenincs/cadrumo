"""Real-supervisor conformance matrix for every production executor."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Final, cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from ...adapters.persistence.operations.financial_operand_custody import (
    OperationFinancialOperandCustodyFilesystemRepository,
)
from ...adapters.persistence.operations.journal import OperationJournalRepository
from ...adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ...adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ...application.auth.operation_definitions import build_auth_operation_definitions
from ...application.export.google_operation import build_google_sheets_export_operation_definition
from ...application.modelo.calculation_actions import calculate_modelo_revision
from ...application.modelo.external_import_actions import import_external_filing_evidence
from ...application.modelo.operation_definitions import resolve_active_workflow_profile
from ...application.modelo.tests.justificante_metadata import persist_justificante_metadata
from ...application.modelo.verification_actions import verify_modelo_revision
from ...application.modelo.work_lifecycle import create_work_unit
from ...application.operations.composition import (
    OperationComposedServices,
    OperationSubmission,
    compose_operation_services,
)
from ...application.operations.frontend_contracts import (
    OperationCancellationRefusalV1,
    OperationCancellationRequestV1,
    OperationCancellationSuccessV1,
    OperationNoPendingInteractionV1,
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationPublicPhaseEventV1,
    OperationResponseApplyRequestV1,
    OperationResponseControlRequestV1,
    OperationResponseMutationSuccessV1,
    OperationReviewAvailableInteractionV1,
    OperationReviewProjectionReferenceV1,
    OperationReviewProjectionRefusalCode,
    OperationReviewProjectionRefusalV1,
    OperationReviewProjectionRequestV1,
)
from ...application.operations.models import OperationRequest
from ...application.operations.registry import (
    OperationDefinition,
    OperationRegistry,
)
from ...application.user_profile.bundle_export_contracts import ProfileBundleExportPurpose
from ...application.user_profile.censal_observation import (
    CensalObservation,
    CensalObservationAddress,
    CensalObservationIdentity,
)
from ...application.user_profile.censal_operation import (
    CensalFieldIntent,
    CensalOperationAcquisition,
    CensalProfileBaseline,
    CensalReviewedFieldIntent,
    build_censal_operation_definition,
)
from ...application.user_profile.censo_sync import CENSAL_ADOPTABLE_PATHS
from ...application.user_profile.custody_ports import profile_custody_secure_object_repository
from ...application.user_profile.login_session import login_profile
from ...application.user_profile.profile_record_repository import ProfileRecordRepository
from ...application.user_profile.registration import register_profile_with_credentials
from ...core.auth_provider import AuthProviderKind
from ...core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from ...core.period import Period
from ...core.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from ...core.time.clock import now
from ...domain.modelos.calculation_revision_amendment import CalculationRevisionAmendmentKind
from ...domain.modelos.filing_record import ExternalEvidenceKind
from ...domain.modelos.verification_report import VerificationCompletenessStatus
from ...domain.modelos.work_unit import WorkUnit
from ...domain.user_profile.values import UserProfileFact
from ...tests.aeat_literal_fixtures import aeat_url
from ...tests.cross_period_seeding import (
    SEEDED_SOURCE_TAX_ID,
    resolved_revision,
    seed_clean_cross_period_sources,
)
from ...tests.profile_capsule import seed_modelo_ready_profile_record
from ...tests.secure_sql import isolated_profile_storage_root
from ..censal_review import _run as run_censal_review_through_services
from ..operation_composition import build_production_operation_registry

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PASSPHRASE = "s45-registered-executor-passphrase"  # noqa: S105 - isolated integration fixture
_ROTATED_PASSPHRASE = "s45-registered-executor-rotated-passphrase"  # noqa: S105
_ACTOR = "operator:s45"


@dataclass(frozen=True, slots=True)
class _RegisteredExecutorConformanceCase:
    definition_id: str
    expected_terminal: OperationTerminalCondition
    expected_effect: OperationEffect
    expected_phase_codes: tuple[str, ...] | None = None
    expected_refusal_ref: str | None = None


_PROFILE_CLOCK = datetime(2026, 8, 24, 18, tzinfo=UTC)
_MODELO = "130"
_MODELO_FILING_YEAR = 2025
_MODELO_PERIOD = "1T"


def _seed_modelo_ready_profile(profile_id: UUID) -> None:
    """Give this case's profile the taxpayer facts modelo work requires.

    The runtime registers with `identity.tax_id` alone, which is enough for the
    auth and profile operations but NOT for modelo work: the readiness gate
    refuses every modelo executor until the baseline paths are present. That
    refusal is correct -- a work unit cannot be calculated against a taxpayer
    whose regime is unknown -- so the fixture is what has to change.

    Delegates to the canonical seeder rather than restating the fact tuple.
    That tuple was already copied verbatim into four test modules and this was
    nearly a fifth; the readiness gate decides what modelo work may run, so
    every copy is another place for the answer to drift.

    Seeded HERE rather than at registration because the profile is shared by
    every case in this runtime, and `user-profile.censo-review` builds its
    baseline from the record -- adding facts globally would change what that
    operation is asked to adopt.
    """
    # Seeded under the identity the cross-period seeder files its sources with:
    # the clean-state gate compares that evidence's authenticated identity
    # against the ACTIVE profile's tax id, so a profile carrying a different one
    # is refused with `mismatched_external_evidence_record` -- which names the
    # source modelo, not the identity, and reads as a seeding failure instead.
    seed_modelo_ready_profile_record(str(profile_id), clock=_PROFILE_CLOCK, tax_id=SEEDED_SOURCE_TAX_ID)


def _seeded_modelo_work_unit(profile_id: UUID) -> WorkUnit:
    """Create one real work unit in the active bucket through the production door.

    The modelo lifecycle operations address a work unit by id, so a payload
    for any of them needs one to exist. It is created through
    ``create_work_unit`` rather than written into the catalogue directly:
    a hand-written unit could carry a revision the law-determined resolver
    would never select, and every one of these executors resolves its
    revision from the unit.
    """
    _seed_modelo_ready_profile(profile_id)
    revision = resolved_revision(modelo=_MODELO, filing_year=_MODELO_FILING_YEAR, period=_MODELO_PERIOD)
    return create_work_unit(
        bucket_id=str(profile_id),
        modelo=_MODELO,
        filing_year=_MODELO_FILING_YEAR,
        period=Period.from_year_and_code(_MODELO_FILING_YEAR, _MODELO_PERIOD),
        revision_id=revision.id,
        actor=_ACTOR,
    )


def _registered_definition_ids() -> tuple[str, ...]:
    """Every definition the production registry actually composes.

    The matrix is parametrised from this rather than from a hand-listed
    tuple. A hardcoded item list encodes the registry as it stood on the
    day it was written and then detects nothing: this test's own name
    claims it covers EVERY production registered executor, and while the
    list was hand-maintained it silently covered none of the modelo
    family. Deriving the subjects means a newly composed operation joins
    the matrix by existing, and reports a missing scenario rather than
    reconciling quietly.
    """
    return tuple(sorted(definition.definition_id for definition in build_production_operation_registry().definitions))


_EXPECTATIONS: Mapping[str, _RegisteredExecutorConformanceCase] = {
    case.definition_id: case
    for case in (
        _RegisteredExecutorConformanceCase(
            "auth.profile.login", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "auth.profile.passphrase-rotate", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "auth.provider.configure", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "auth.session.acquire",
            OperationTerminalCondition.REFUSED,
            OperationEffect.UNKNOWN,
            expected_refusal_ref="REFUSED_AUTH_LOGIN_LIVE_TESTS_DISABLED",
        ),
        _RegisteredExecutorConformanceCase(
            "auth.session.logout", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        _RegisteredExecutorConformanceCase(
            "auth.session.reset", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        _RegisteredExecutorConformanceCase(
            "user-profile.field-mutation", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "user-profile.repeatable-row-mutation", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "user-profile.bundle-export", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "user-profile.logout", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "live.filed-history.pull",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            expected_refusal_ref="REFUSED_ACCESS_GATE_LIVE_READ_NOT_ENABLED",
        ),
        _RegisteredExecutorConformanceCase(
            "export.google-sheets",
            OperationTerminalCondition.FAILED,
            OperationEffect.UNKNOWN,
            (
                "export.google-sheets.preflight",
                "export.google-sheets.plan",
                "export.google-sheets.apply",
            ),
        ),
        _RegisteredExecutorConformanceCase(
            "user-profile.censo-review", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.work.rename", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.work.discard", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.work.verify", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.work.file", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.edit.apply", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.export", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.work.amend", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
    )
}
"""The settlement each registered executor is expected to reach.

Keyed by definition id, never ordered or counted. Coverage is asserted
against the live registry below, so an operation that gains a definition
without gaining a scenario fails by name instead of by tally."""


@dataclass(slots=True)
class _CloseWitness:
    """Observe cleanup owned by the actual CENSO executor."""

    closed: bool = False

    async def close(self) -> None:
        self.closed = True


@dataclass(slots=True)
class _ExecutionDriver:
    """Single registered execution driver over the canonical composed supervisor."""

    services: OperationComposedServices

    async def prepare(self, *, definition_id: str, subject_ref: str, payload: BaseModel, secret: bytes | None = None):
        submitted = await self.services.submission.submit(
            OperationRequest(definition_id=definition_id, subject_ref=subject_ref, payload=payload), actor_ref=_ACTOR
        )
        requirement = submitted.receipt.secret_requirement
        if requirement is not None:
            assert secret is not None
            buffer = bytearray(secret)
            await self.services.submission.submit_secret(requirement, buffer)
            assert buffer == bytearray(len(secret))
        else:
            assert secret is None
        return submitted

    async def run(self, *, definition_id: str, subject_ref: str, payload: BaseModel, secret: bytes | None = None):
        submitted = await self.prepare(
            definition_id=definition_id,
            subject_ref=subject_ref,
            payload=payload,
            secret=secret,
        )
        before_start = await self.observe(submitted.receipt.operation_id)
        cancellation = await self.services.cancellation.request(
            OperationCancellationRequestV1(
                operation_id=submitted.receipt.operation_id, expected_revision=before_start.projection.revision
            )
        )
        assert isinstance(cancellation, OperationCancellationRefusalV1)
        await self.services.submission.start(submitted.receipt.operation_id)
        return submitted, await self.observe(submitted.receipt.operation_id)

    async def observe(self, operation_id: str) -> OperationObservationSuccessV1:
        observed = await self.services.observation.observe(
            OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=256)
        )
        assert isinstance(observed, OperationObservationSuccessV1)
        return observed

    async def respond_apply(self, submitted: OperationSubmission, observed: OperationObservationSuccessV1) -> str:
        pending = observed.projection.pending_interaction
        assert isinstance(pending, OperationReviewAvailableInteractionV1)
        response = await self.services.response(
            OperationResponseControlRequestV1(
                operation_id=pending.operation_id,
                interaction_id=pending.interaction_id,
                revision=pending.revision,
                actor_ref=_ACTOR,
            ),
            submitted.response_capability,
        )
        accepted = await response.apply(
            OperationResponseApplyRequestV1(
                operation_id=pending.operation_id,
                interaction_id=pending.interaction_id,
                revision=pending.revision,
                actor_ref=_ACTOR,
                responded_at=now(),
            )
        )
        assert isinstance(accepted, OperationResponseMutationSuccessV1)
        return pending.operation_id

    async def apply_review(
        self, submitted: OperationSubmission, observed: OperationObservationSuccessV1
    ) -> OperationObservationSuccessV1:
        operation_id = await self.respond_apply(submitted, observed)
        return await self.await_terminal(operation_id)

    async def await_terminal(self, operation_id: str) -> OperationObservationSuccessV1:
        """Observe a public terminal projection after real executor work completes."""
        for _ in range(100):
            observed = await self.observe(operation_id)
            if observed.projection.lifecycle is OperationLifecycle.TERMINAL:
                return observed
            await asyncio.sleep(0)
        raise AssertionError("review continuation did not settle")

    async def review_not_pending(self, *, operation_id: str, revision: int, registry: OperationRegistry) -> None:
        """Prove the public REVIEW control truthfully refuses an operation without a pending review."""
        review_contract = registry.lookup_public_contract("user-profile.censo-review")
        assert review_contract.review_projection_schema is not None
        result = await self.services.review.resolve(
            OperationReviewProjectionRequestV1(
                reference=OperationReviewProjectionReferenceV1(
                    operation_id=operation_id,
                    interaction_id="0" * 64,
                    revision=revision,
                    review_projection_schema=review_contract.review_projection_schema,
                    definition_contract_digest=review_contract.definition_contract_digest,
                    expires_at=None,
                )
            )
        )
        assert isinstance(result, OperationReviewProjectionRefusalV1)
        assert result.code is OperationReviewProjectionRefusalCode.REVIEW_NOT_PENDING


def _observation() -> CensalObservation:
    return CensalObservation(
        identity=CensalObservationIdentity(nif="12345678Z"),
        domicilio_fiscal=CensalObservationAddress(
            tipo_via="CALLE",
            nombre_via="Mayor",
            numero_casa="7",
            codigo_postal="28013",
            referencia_catastral="1234567VK4713C0001AB",
        ),
        domicilio_notificacion=CensalObservationAddress(),
        captured_at=datetime(2026, 8, 24, 18, tzinfo=UTC),
        source_url=aeat_url("sede", "/censo/consulta"),
    )


_FIRST_QUARTER_PRIOR_PERIOD_BINDINGS: Final[dict[str, Decimal]] = {
    "irpf.previous_year_economic_activity_net_income": Decimal("0"),
    "modelo-130-resultados-negativos-anteriores": Decimal("0"),
    "modelo-130-pagos-fraccionados-anteriores": Decimal("0"),
}
"""The three prior-period bindings M130 requires, zeroed because this is a 1T unit.

ZERO IS THE GROUNDED ANSWER HERE, not a placeholder. The seeded unit is the
FIRST quarter of its filing year, so there is no prior quarter to carry a
negative result or a previous payment from, and no prior-year activity income
recorded against this freshly created profile. The registry refuses a
calculation with any of these unsupplied -- it named
`irpf.previous_year_economic_activity_net_income` explicitly -- so they must be
answered, and for a first quarter the true answer is nought.

Supplying a non-zero figure would be the fabrication: it would assert prior
filings this profile does not have.
"""


def _seeded_modelo_calculation_revision(profile_id: UUID) -> str:
    """Calculate one real revision for the seeded unit, and return its id.

    `casilla_inputs={}` is deliberate and is NOT a stub. The M130 revision
    `2019-y-siguientes` declares eight bindings and twenty casillas and marks
    NONE of them required, so an empty input set yields a genuine revision --
    a return with nothing declared yet -- rather than a fabricated one.

    That matters because this matrix asserts the executor SETTLES, cleans up
    and refuses truthfully; it asserts no tax figure. Inventing income and
    expense values to make the revision look substantial would put numbers
    nobody grounded behind an AEAT-shaped conformance test name, and would
    also require restating the M130 casilla constants that are already
    redeclared in thirty-four modules.

    The repositories resolve from the active session, as they do for the work
    unit itself, so nothing here opens a second write path.
    """
    unit = _seeded_modelo_work_unit(profile_id)
    revision = calculate_modelo_revision(
        unit.work_unit_id,
        actor=_ACTOR,
        casilla_inputs={},
        binding_values=_FIRST_QUARTER_PRIOR_PERIOD_BINDINGS,
    )
    return str(revision.calculation_revision_id)


def _seeded_modelo_verification_report(profile_id: UUID) -> tuple[str, str]:
    """Calculate a revision and verify it, returning both ids.

    Reaches the verification authority through the SAME door the verify
    executor uses, rather than re-deriving a report here: a fixture that built
    its own report would be asserting that filing accepts something the
    verification path never produced.

    `file` approves a revision AND the verification that justified it, so both
    ids have to come from one act of verification -- pairing a revision with a
    report from some other run is exactly the stale-approval case the filing
    authority exists to refuse.
    """
    unit = _seeded_modelo_work_unit(profile_id)
    # Verification refuses a revision whose cross-period sources are unproven
    # (`cross_period_dependency_unclean`, blocking), and filing in turn refuses
    # anything not VERIFICADO_COMPLETO -- so the file path needs those sources
    # materialised before it calculates. Seeded through the canonical helper,
    # which files each source through the real external-import door and records
    # an `aeat_sede_justificante` observation: the clean-state gate accepts
    # nothing weaker, and stamping a passing observation without the filing
    # behind it would prove the gate green on evidence no operator has.
    seed_clean_cross_period_sources(
        unit,
        work_unit_repository=WorkUnitCatalogueRepository(),
        calculation_repository=CalculationRevisionCatalogueRepository(),
        filing_repository=ModeloRecordCatalogueRepository(),
        bucket_event_repository=BucketEventHistoryRepository(),
    )
    revision = calculate_modelo_revision(
        unit.work_unit_id,
        actor=_ACTOR,
        casilla_inputs={},
        binding_values=_FIRST_QUARTER_PRIOR_PERIOD_BINDINGS,
    )
    revision_id = str(revision.calculation_revision_id)
    report = verify_modelo_revision(
        revision_id,
        actor=_ACTOR,
        workflow_profile=resolve_active_workflow_profile(),
    )
    # Verifying SUCCESSFULLY and GRANTING completeness are different outcomes: a
    # run that reports blocking findings settles fine while leaving the revision
    # in BORRADOR, and filing then refuses a state this fixture believed it had
    # established. Naming the completeness status and the findings here turns
    # that into a legible failure instead of an opaque refusal one layer down.
    if report.completeness_status is not VerificationCompletenessStatus.COMPLETE:
        # The facts, not just the kind: a blocking cross-period finding names the
        # source modelo and the blockers that made it unclean, and those are the
        # difference between "the fixture seeded nothing" and "the fixture seeded
        # something the gate does not accept".
        findings = (
            "; ".join(
                sorted(
                    f"{finding.kind.value}/{finding.severity.value} {dict(finding.message_facts)}"
                    for finding in report.findings
                )
            )
            or "no findings reported"
        )
        raise AssertionError(
            f"verification did not grant completeness on the seeded revision "
            f"(status={report.completeness_status.value}); filing cannot be exercised until it does: {findings}"
        )
    return revision_id, str(report.verification_report_id)


def _seeded_modelo_filing_record(profile_id: UUID) -> tuple[str, str]:
    """File one real revision and return its filing-record and casilla ids.

    Amendment corrects something already FILED, so its fixture cannot stop at a
    verified revision: it needs the filing record that amendment is addressed
    to. Reached through the same filing authority the `file` operation uses, so
    the record amendment corrects is one the product actually produces.

    The casilla is taken from the revision's own declared inputs rather than
    named, for the reason the edit fixture gives: the M130 casilla mapping is
    revision-scoped, and a literal here would be silently wrong the moment the
    governing revision changes.
    """
    unit = _seeded_modelo_work_unit(profile_id)
    revision = resolved_revision(modelo=_MODELO, filing_year=_MODELO_FILING_YEAR, period=_MODELO_PERIOD)
    casilla_id = sorted(casilla.id for casilla in revision.casillas)[0]
    evidence_reference_id = f"CSV{_MODELO}{_MODELO_FILING_YEAR}{_MODELO_PERIOD}".upper()
    # The unit is created at the live clock, so the evidence cannot be stamped
    # with the profile's fixed seeding clock: the catalogue refuses a work unit
    # whose updated_at precedes its created_at, and rightly so.
    evidence_clock = now()

    # Amendment refuses a baseline with no external evidence
    # (`AmendmentEvidenceMissingError`), and that refusal is correct: an
    # amendment corrects a return the authority already holds, so the baseline
    # has to be one AEAT evidenced rather than one this process filed locally.
    # The record therefore comes through the external-import door, exactly as
    # the cross-period seeder produces its own sources.
    persist_justificante_metadata(
        evidence_reference_id,
        modelo=_MODELO,
        filing_year=_MODELO_FILING_YEAR,
        period=_MODELO_PERIOD,
        captured_at=evidence_clock,
        tax_id=SEEDED_SOURCE_TAX_ID,
    )
    record = import_external_filing_evidence(
        work_unit_id=unit.work_unit_id,
        casilla_values={casilla_id: Decimal("100")},
        evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
        evidence_reference_id=evidence_reference_id,
        actor=_ACTOR,
        work_unit_repository=WorkUnitCatalogueRepository(),
        calculation_repository=CalculationRevisionCatalogueRepository(),
        filing_repository=ModeloRecordCatalogueRepository(),
        bucket_event_repository=BucketEventHistoryRepository(),
        expected_tax_id=SEEDED_SOURCE_TAX_ID,
        clock=evidence_clock,
    )
    return str(record.filing_record_id), str(casilla_id)


def _seeded_modelo_edit_submission(profile_id: UUID) -> tuple[str, object]:
    """Admit an edit over a seeded revision and return its wire submission.

    The casilla is RESOLVED FROM THE ADMISSION rather than named. The permitted
    surface reports which scalars this revision actually accepts, so taking the
    first writable one keeps this fixture free of a hardcoded casilla id --
    which matters because that mapping is revision-scoped, and thirty-four
    modules already freeze it as a literal.

    The wire submission is built by
    `ModeloEditApplySubmissionV1.from_submission`, the domain-to-wire
    translation the contract owns, rather than by assembling the payload here.
    A second translator would be free to disagree with the one the executor
    reverses.
    """
    from ...adapters.persistence.profile.modelos_calculation import (
        CalculationRevisionCatalogueRepository,
    )
    from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
    from ...application.modelo.edit_contract import ModeloEditCompatibilityTupleV1, ModeloEditMutationFamily
    from ...application.modelo.edit_models import (
        ModeloEditAdmissionRequestV1,
        ModeloEditAdmittedV1,
        ModeloEditScalarAddressV1,
        ModeloEditScalarIntentKind,
        ModeloEditSubmissionV1,
        ModeloScalarEditIntentV1,
    )
    from ...application.modelo.edit_services import (
        admit_modelo_edit,
        modelo_edit_request_schema_identity,
        modelo_edit_result_schema_identity,
    )
    from ...application.modelo.operation_definitions import ModeloEditApplySubmissionV1
    from ...application.modelo.work_addressing import ModeloExactWorkUnitTarget
    from ...application.modelo.workspace_models import ModeloWorkspaceExactWorkUnitTargetV1
    from ...application.operations.registry import OperationSchemaIdentityV1

    unit = _seeded_modelo_work_unit(profile_id)
    calculate_modelo_revision(
        unit.work_unit_id,
        actor=_ACTOR,
        casilla_inputs={},
        binding_values=_FIRST_QUARTER_PRIOR_PERIOD_BINDINGS,
    )
    objects = secure_object_repository_for_active_bucket()
    identity = OperationSchemaIdentityV1(
        schema_id="modelo.edit.contract", schema_version=1, schema_fingerprint="a" * 64
    )
    admitted = admit_modelo_edit(
        ModeloEditAdmissionRequestV1(
            target=ModeloWorkspaceExactWorkUnitTargetV1(
                target=ModeloExactWorkUnitTarget(work_unit_id=unit.work_unit_id, bucket_id=unit.bucket_id)
            ),
            mutation_family=ModeloEditMutationFamily.CALCULATE,
        ),
        bucket_id=unit.bucket_id,
        work_catalogue=WorkUnitCatalogueRepository(objects=objects).load(),
        calculation_catalogue=CalculationRevisionCatalogueRepository(objects=objects).load(),
        compatibility=ModeloEditCompatibilityTupleV1(
            contract_set_digest="a" * 64,
            operation_definition_id="modelo.calculate",
            definition_contract_digest="a" * 64,
            request_schema=modelo_edit_request_schema_identity(),
            result_schema=modelo_edit_result_schema_identity(),
            review_projection_contract_version=None,
            review_schema=None,
            workspace_refresh_target_schema=identity,
            financial_operand_schema=identity,
        ),
    )
    if not isinstance(admitted, ModeloEditAdmittedV1):
        raise AssertionError(f"edit admission refused for the conformance fixture: {admitted}")
    writable = [
        entry for entry in admitted.baseline.permitted_surface if getattr(entry, "kind", None) == "writable_scalar"
    ]
    if not writable:
        raise AssertionError("the admitted revision permits no writable scalar; this fixture would be vacuous")
    submission = ModeloEditSubmissionV1(
        baseline=admitted.baseline,
        mutation_family=ModeloEditMutationFamily.CALCULATE,
        scalar_intents=(
            ModeloScalarEditIntentV1(
                address=ModeloEditScalarAddressV1(casilla_id=str(writable[0].casilla_id)),
                kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
                value="100.00",
            ),
        ),
    )
    return unit.work_unit_id, ModeloEditApplySubmissionV1.from_submission(submission)


def _payload(
    definition: OperationDefinition, *, profile_id: UUID, tmp_path: Path
) -> tuple[str, BaseModel, bytes | None]:
    """Use only the exact request type exported by the registered definition."""
    values: dict[str, object]
    secret: bytes | None = None
    subject_ref = f"profile:{profile_id}"
    match definition.definition_id:
        case "auth.profile.login":
            values = {"profile_id": profile_id}
            secret = _PASSPHRASE.encode()
        case "auth.profile.passphrase-rotate":
            values = {"profile_id": profile_id}
            secret = (
                '{"current_passphrase":"'
                + _PASSPHRASE
                + '","new_passphrase":"'
                + _ROTATED_PASSPHRASE
                + '","new_passphrase_confirmation":"'
                + _ROTATED_PASSPHRASE
                + '"}'
            ).encode()
        case "auth.provider.configure":
            values = {"provider": AuthProviderKind.CERTIFICATE}
        case "auth.session.acquire":
            values = {}
        case "auth.session.logout" | "auth.session.reset":
            values = {"all_providers": True}
        case "user-profile.field-mutation":
            values = {"profile_id": profile_id, "path": PROFILE_OUTPUT_LANGUAGE_PATH, "value": "es"}
        case "user-profile.repeatable-row-mutation":
            values = {
                "profile_id": profile_id,
                "section_key": "activities",
                "values": ({"field_key": "description", "value": "Consultoria"},),
            }
        case "user-profile.bundle-export":
            values = {
                "profile_id": profile_id,
                "destination": tmp_path / "profile.bundle",
                "purpose": ProfileBundleExportPurpose.PORTABLE_TRANSFER,
            }
            secret = _PASSPHRASE.encode()
        case "user-profile.logout":
            values = {"profile_id": profile_id}
        case "live.filed-history.pull":
            subject_ref = str(profile_id)
            values = {"output_root": tmp_path / "filed-history", "dry_run": True}
        case "export.google-sheets":
            values = {"profile_id": profile_id, "modelo": "130", "filing_year": 2025, "period": "1T", "dry_run": False}
        case "user-profile.censo-review":
            subject_ref = str(profile_id)
            record = ProfileRecordRepository.for_current_session(profile_id).load(profile_id)
            values = {
                "baseline": CensalProfileBaseline.from_record(record),
                "field_intents": tuple(
                    CensalReviewedFieldIntent(path=path, intent=CensalFieldIntent.ADOPT)
                    for path in CENSAL_ADOPTABLE_PATHS
                ),
            }
        case "modelo.work.rename":
            unit = _seeded_modelo_work_unit(profile_id)
            subject_ref = unit.work_unit_id
            values = {
                "work_unit_id": unit.work_unit_id,
                "new_name": "Conformance renamed unit",
                "actor": _ACTOR,
            }
        case "modelo.export":
            # A DRAFT revision is not exportable. `_require_exportable_revision_state`
            # admits only SEALED states (VERIFICADO_COMPLETO, PRESENTADO,
            # PRESENTADO_SUPERSEDIDO), because a fichero is a filing-grade
            # artefact and a return still being edited has no business becoming
            # one. So this seeds through verification rather than calculation.
            revision_id, _report_id = _seeded_modelo_verification_report(profile_id)
            subject_ref = revision_id
            values = {
                "calculation_revision_id": revision_id,
                "output_path": str(tmp_path / "modelo-130-2025-1T.txt"),
                "actor": _ACTOR,
            }
        case "modelo.edit.apply":
            work_unit_id, wire_submission = _seeded_modelo_edit_submission(profile_id)
            subject_ref = work_unit_id
            values = {"submission": wire_submission}
        case "modelo.work.file":
            revision_id, report_id = _seeded_modelo_verification_report(profile_id)
            subject_ref = revision_id
            values = {
                "approval": {
                    "calculation_revision_id": revision_id,
                    "verification_report_id": report_id,
                },
                "actor": _ACTOR,
            }
        case "modelo.work.amend":
            filing_record_id, casilla_id = _seeded_modelo_filing_record(profile_id)
            # The subject is the FILED RECORD, not the work unit: two amendments
            # of one filed return describe competing corrections to the same
            # declaration and must serialise against each other.
            subject_ref = filing_record_id
            values = {
                "baseline": {"from_filing_record_id": filing_record_id},
                # The request model is strict: the enum instance and a tuple,
                # not their loose equivalents. A `.value` string and a list both
                # round-trip through JSON but are refused at the boundary, which
                # is the point of declaring the schema strict.
                "amendment_kind": CalculationRevisionAmendmentKind.COMPLEMENTARIA,
                "overrides": ({"casilla_id": casilla_id, "value": "150.00"},),
                "reason": "corrected the declared base for the conformance matrix",
                "actor": _ACTOR,
            }
        case "modelo.work.verify":
            revision_id = _seeded_modelo_calculation_revision(profile_id)
            subject_ref = revision_id
            values = {"calculation_revision_id": revision_id, "actor": _ACTOR}
        case "modelo.work.discard":
            # The baseline is the operator's EXACT APPROVAL, so it carries the
            # unit's state as observed rather than as re-read: name and
            # updated_at come off the seeded unit itself. A baseline resolved
            # inside the executor would match by construction and the
            # compare-and-swap this operation declares would never refuse.
            unit = _seeded_modelo_work_unit(profile_id)
            subject_ref = unit.work_unit_id
            values = {
                "baseline": {
                    "work_unit_id": unit.work_unit_id,
                    "name": unit.name,
                    "observed_updated_at": unit.updated_at,
                },
                "reason": "discarded by the registered-executor conformance matrix",
                "actor": _ACTOR,
            }
        case _:  # pragma: no cover - the coverage census names any definition missing a scenario.
            raise AssertionError(f"no conformance scenario for {definition.definition_id}")
    return subject_ref, definition.request_type.model_validate(values, strict=True), secret


@contextmanager
def _runtime(
    tmp_path: Path,
    *,
    cleanup: _CloseWitness,
    before_irreversible_section: Callable[[], Awaitable[None]] | None = None,
    execution_timeout: timedelta = timedelta(hours=1),
) -> Generator[tuple[_ExecutionDriver, OperationRegistry, UUID]]:
    """Fresh production profile, inventory, journal, lease, and operand custody per case."""

    async def acquire_censo() -> CensalOperationAcquisition:
        return CensalOperationAcquisition(observation=_observation(), resource=cleanup)

    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        enrolled = register_profile_with_credentials(
            label="S45 registered executor subject",
            passphrase=_PASSPHRASE,
            facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
        )
        profile_id = UUID(enrolled.profile_id)
        initial_login = login_profile(name=enrolled.profile_id, passphrase_callback=lambda: _PASSPHRASE)
        registry = build_production_operation_registry(
            auth_definitions=build_auth_operation_definitions(profile_login=lambda **_kwargs: initial_login),
            censal_definition=build_censal_operation_definition(
                acquire=acquire_censo,
                before_irreversible_section=before_irreversible_section,
            ),
            google_export_definition=build_google_sheets_export_operation_definition(),
        )
        journal = OperationJournalRepository(storage_root=root / "operations")
        with profile_custody_secure_object_repository(profile_id=profile_id, dek=b"", root=root) as objects:
            services = compose_operation_services(
                registry=registry,
                journal=journal,
                reader=journal,
                event_stream=journal,
                leases=OperationLeaseFilesystemRepository(storage_root=root / "operations"),
                operands=operation_secure_reference_repository(objects=cast(SecureObjectRepository, objects)),
                owner_id="1" * 64,
                lease_token_factory=lambda: "2" * 64,
                clock=now,
                lease_duration=timedelta(minutes=10),
                execution_timeout=execution_timeout,
                cleanup_timeout=timedelta(minutes=2),
                financial_operand_custody=OperationFinancialOperandCustodyFilesystemRepository(
                    root=root / "operations" / "financial_operand_custody",
                ),
            )
            try:
                yield _ExecutionDriver(services=services), registry, profile_id
            finally:
                asyncio.run(services.shutdown())


@pytest.mark.parametrize("apply", [True, False], ids=["apply", "reject"])
def test_censal_frontend_driver_reviews_one_acquisition_and_rolls_back_rejection(
    tmp_path: Path,
    apply: bool,
) -> None:
    """The public frontend driver answers the encrypted exact proposal once."""
    cleanup = _CloseWitness()
    with _runtime(tmp_path / f"frontend-{apply}", cleanup=cleanup) as (driver, _registry, profile_id):
        repository = ProfileRecordRepository.for_current_session(profile_id)
        before = repository.load(profile_id)
        decisions: list[tuple[str | None, ...]] = []

        def decide(projection) -> bool:
            decisions.append(tuple(field.observed_value for field in projection.fields))
            return apply

        result = asyncio.run(
            run_censal_review_through_services(
                actor_ref="operator:frontend-test",
                decide=decide,
                services=driver.services,
            )
        )

        assert result.applied is apply
        assert len(decisions) == 1
        assert len(decisions[0]) == len(CENSAL_ADOPTABLE_PATHS)
        assert decisions[0][0]
        assert decisions[0][1] == "28013"
        assert cleanup.closed is True
        after = repository.load(profile_id)
        if apply:
            assert after.record_revision == before.record_revision + 1
            assert after.content_digest != before.content_digest
        else:
            assert after == before


def test_censal_frontend_driver_never_reports_a_failed_terminal_as_applied(tmp_path: Path) -> None:
    """An accepted response followed by a failed continuation stays a failure."""
    cleanup = _CloseWitness()
    with _runtime(tmp_path / "frontend-failed", cleanup=cleanup) as (driver, _registry, _profile_id):
        delegate = driver.services.observation

        class _FailedTerminalObservation:
            async def observe(self, request):
                observed = await delegate.observe(request)
                if (
                    isinstance(observed, OperationObservationSuccessV1)
                    and observed.projection.lifecycle is OperationLifecycle.TERMINAL
                ):
                    return observed.model_copy(
                        update={
                            "projection": observed.projection.model_copy(
                                update={
                                    "terminal_condition": OperationTerminalCondition.FAILED,
                                    "effect": OperationEffect.UNKNOWN,
                                    "result_ref": None,
                                    "diagnostic_ref": "diagnostic:censo-stale",
                                }
                            )
                        }
                    )
                return observed

        failed_services = replace(driver.services, observation=_FailedTerminalObservation())
        with pytest.raises(RuntimeError, match="did not succeed"):
            asyncio.run(
                run_censal_review_through_services(
                    actor_ref="operator:frontend-failed-test",
                    decide=lambda _projection: True,
                    services=failed_services,
                )
            )


def test_every_registered_definition_has_a_conformance_scenario() -> None:
    """The matrix's subjects are the registry's, in both directions.

    This is the census the hardcoded item list used to stand in for. It
    asserts membership, never a count: a tally would have to be edited
    every time an operation is composed, which trains everyone to update
    the constant and then detects nothing.
    """
    registered = set(_registered_definition_ids())
    declared = set(_EXPECTATIONS)

    assert not registered - declared, (
        "registered operations run through the supervisor with no conformance scenario, so this "
        f"matrix does not cover what its name claims: {sorted(registered - declared)}"
    )
    assert not declared - registered, (
        f"conformance scenarios name operations the production registry does not compose: {sorted(declared - registered)}"
    )


@pytest.mark.parametrize("definition_id", _registered_definition_ids())
@pytest.mark.timeout(90)
def test_every_production_registered_executor_runs_through_the_shared_supervisor_matrix(
    tmp_path: Path, definition_id: str
) -> None:
    """Actual execution, effects, settlement, review, cleanup, and truthful control refusal."""
    case = _EXPECTATIONS.get(definition_id)
    if case is None:
        pytest.fail(
            f"{definition_id} is composed into the production registry but declares no conformance "
            "scenario, so nothing proves its executor settles, cleans up, or refuses truthfully"
        )
    cleanup = _CloseWitness()
    with _runtime(tmp_path / case.definition_id, cleanup=cleanup) as (driver, registry, profile_id):
        definitions = {definition.definition_id: definition for definition in registry.definitions}
        definition = definitions[case.definition_id]
        subject_ref, payload, secret = _payload(
            definition, profile_id=profile_id, tmp_path=tmp_path / case.definition_id
        )
        submitted, observed = asyncio.run(
            driver.run(definition_id=definition.definition_id, subject_ref=subject_ref, payload=payload, secret=secret)
        )
        phase_codes = tuple(
            event.phase_code for event in observed.event_page.events if isinstance(event, OperationPublicPhaseEventV1)
        )
        if case.expected_phase_codes is None:
            assert set(phase_codes) & set(definition.phase_codes)
        else:
            assert phase_codes == case.expected_phase_codes
        if case.definition_id == "user-profile.censo-review":
            assert observed.projection.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION
            assert isinstance(observed.projection.pending_interaction, OperationReviewAvailableInteractionV1)
            assert observed.projection.execution_deadline_at is not None
            assert cleanup.closed is True
            observed = asyncio.run(driver.apply_review(submitted, observed))
        assert observed.projection.lifecycle is OperationLifecycle.TERMINAL
        assert observed.projection.terminal_condition is case.expected_terminal, case.definition_id
        assert observed.projection.effect is case.expected_effect, case.definition_id
        assert observed.projection.refusal_ref == case.expected_refusal_ref, case.definition_id
        if case.expected_terminal is OperationTerminalCondition.FAILED:
            assert observed.projection.diagnostic_ref is not None
        assert isinstance(observed.projection.pending_interaction, OperationNoPendingInteractionV1)
        asyncio.run(
            driver.review_not_pending(
                operation_id=submitted.receipt.operation_id,
                revision=observed.projection.revision,
                registry=registry,
            )
        )


def test_censo_cooperative_cancellation_settles_after_its_irreversible_section(tmp_path: Path) -> None:
    """Drive manual cancellation through the public control service to its exact terminal receipt."""
    reached_boundary = asyncio.Event()
    release_boundary = asyncio.Event()

    async def before_irreversible_section() -> None:
        reached_boundary.set()
        await release_boundary.wait()

    cleanup = _CloseWitness()
    with _runtime(
        tmp_path / "censo-cancellation",
        cleanup=cleanup,
        before_irreversible_section=before_irreversible_section,
    ) as (driver, registry, profile_id):
        definition = registry.lookup("user-profile.censo-review")
        subject_ref, payload, secret = _payload(definition, profile_id=profile_id, tmp_path=tmp_path)

        async def run() -> None:
            submitted = await driver.prepare(
                definition_id=definition.definition_id,
                subject_ref=subject_ref,
                payload=payload,
                secret=secret,
            )
            await driver.services.submission.start(submitted.receipt.operation_id)
            waiting = await driver.observe(submitted.receipt.operation_id)
            operation_id = await driver.respond_apply(submitted, waiting)
            await reached_boundary.wait()
            running = await driver.observe(operation_id)
            requested = await driver.services.cancellation.request(
                OperationCancellationRequestV1(operation_id=operation_id, expected_revision=running.projection.revision)
            )
            assert isinstance(requested, OperationCancellationSuccessV1)
            assert requested.cancellation_acknowledged is False
            release_boundary.set()
            terminal = await driver.await_terminal(operation_id)
            assert terminal.projection.terminal_condition is OperationTerminalCondition.CANCELLED
            assert terminal.projection.effect is OperationEffect.NONE
            assert terminal.projection.cancellation_acknowledged is True
            assert terminal.projection.cleanup_deadline_at is not None
            assert cleanup.closed is True

        asyncio.run(run())


def test_censo_execution_deadline_settles_its_actual_cooperative_safe_stop(tmp_path: Path) -> None:
    """Let the supervisor-owned deadline drive the production CENSO continuation to timed out."""
    cleanup = _CloseWitness()
    with _runtime(
        tmp_path / "censo-deadline",
        cleanup=cleanup,
        execution_timeout=timedelta(milliseconds=50),
    ) as (driver, registry, profile_id):
        definition = registry.lookup("user-profile.censo-review")
        subject_ref, payload, secret = _payload(definition, profile_id=profile_id, tmp_path=tmp_path)

        async def run() -> None:
            submitted, waiting = await driver.run(
                definition_id=definition.definition_id,
                subject_ref=subject_ref,
                payload=payload,
                secret=secret,
            )
            assert waiting.projection.execution_deadline_at is not None
            await asyncio.sleep(max((waiting.projection.execution_deadline_at - now()).total_seconds(), 0) + 0.01)
            operation_id = await driver.respond_apply(submitted, waiting)
            terminal = await driver.await_terminal(operation_id)
            assert terminal.projection.terminal_condition is OperationTerminalCondition.TIMED_OUT
            assert terminal.projection.effect is OperationEffect.NONE
            assert terminal.projection.cancellation_requested is True
            assert terminal.projection.cancellation_acknowledged is True
            assert terminal.projection.cleanup_deadline_at is not None
            assert cleanup.closed is True

        asyncio.run(run())


def test_the_filing_authority_succeeds_on_the_same_fixture_its_operation_fails_on(tmp_path: Path) -> None:
    """Localise a `modelo.work.file` failure to the platform or to the domain.

    The registered `modelo.work.file` operation settles FAILED on this exact
    fixture, and the supervisor stores the executor's exception as a digest
    rather than a message -- so the projection cannot say whether filing itself
    refused or the wrapper around it broke.

    This is the control that answers it. Same runtime, same seeded and verified
    revision, same actor and workflow profile; the only thing removed is the
    operations platform. If this passes while the operation fails, the domain
    path is sound and the defect is in the executor or the supervisor -- and
    nobody has to repeat the investigation to find that out.
    """
    from ...application.modelo.filing_actions import file_modelo_revision

    with _runtime(tmp_path / "authority-control", cleanup=_CloseWitness()) as (_driver, _registry, profile_id):
        revision_id, _report_id = _seeded_modelo_verification_report(profile_id)

        record = file_modelo_revision(
            revision_id,
            actor=_ACTOR,
            workflow_profile=resolve_active_workflow_profile(),
            notes=None,
        )

        assert record is not None, "the filing authority produced no record for a verified-complete revision"

