"""Canonical ephemeral composition for live connected-census proof gates."""

from __future__ import annotations

import secrets
import tempfile
import tomllib
from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import (
    CalculationRevisionCatalogueRepository,
)
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.storage.crypto.aead import KEY_SIZE
from cadrumo.adapters.persistence.storage.master_key.active_session import activate_session
from cadrumo.adapters.persistence.storage.master_key.bucket_session import BucketSession
from cadrumo.adapters.persistence.storage.sql import SecureObjectRepository
from cadrumo.application.aggregation import CalculationSourceContext
from cadrumo.application.invoices.catalogue_creation import build_catalogue_invoice, create_catalogue_invoice
from cadrumo.application.invoices.source_resolver import InvoiceCatalogueSourceResolver
from cadrumo.application.modelo._calculation_helpers import build_typed_observations
from cadrumo.application.modelo.calculation_actions import (
    _require_calculation_route_resolver,
    _source_bound_casilla_inputs,
    _source_provenance_refs,
)
from cadrumo.application.modelo.calculation_resolution import build_calculation_replay_payloads
from cadrumo.application.modelo.revision_persistence import persist_calculation_revision
from cadrumo.application.operator_surface.calculation_workflows import (
    build_supported_modelo_calculation_workflow_catalogue,
)
from cadrumo.core.aggregation import BindingSourceKind, CalculationSourceLineageRole, IntracomOperationType
from cadrumo.core.calculation_route import ModeloCalculationRouteId
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.source_connectivity import SourceConnectivityConnectionIdentity
from cadrumo.core.time.clock import now
from cadrumo.domain.calculations.registry.authority import bundled_authority
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from cadrumo.domain.invoices.enums import PaymentStatus
from cadrumo.domain.iva.classification import InvoiceKind
from cadrumo.domain.iva.schema import IvaCategory
from cadrumo.domain.modelos.calculation_revision import CalculationRevision
from cadrumo.domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from cadrumo.entrypoints.cli import current_operator_surface_reconciliation

from .source_connectivity_authority import (
    LiveSourceConnectivityProofAuthority,
    LiveSourceConnectivityProofExpectation,
    RepositoryRootEvidenceDigestVerifier,
    build_calculation_route_source_ownership_catalogue,
)


class ConnectedProofCompositionError(ValueError):
    """A connected claim has no independent executable proof fixture."""


@dataclass(frozen=True, slots=True)
class ConnectedProofFixture:
    """Independently authored synthetic input for one connected census claim."""

    candidate_id: str
    source_kind: BindingSourceKind
    resolver_id: str
    source_ref: str
    entrypoint_id: str
    command_id: str
    route_id: ModeloCalculationRouteId
    canonical_cli_path: tuple[str, ...]
    destination_identities: tuple[tuple[str, str, str, str, str, str], ...]
    modelo: str
    revision_id: str
    filing_year: int
    period: str
    expected_casilla_id: str
    expected_casilla_value: Decimal
    invoice_bucket_id: str
    invoice_kind: InvoiceKind
    invoice_number: str
    invoice_issued_at: date
    invoice_counterparty_name: str
    invoice_counterparty_tax_id: str
    invoice_counterparty_country: str
    invoice_taxable_base: Decimal
    invoice_iva_rate: Decimal
    invoice_currency: str
    invoice_payment_status: PaymentStatus
    invoice_iva_category: IvaCategory
    invoice_operation_type: IntracomOperationType


# Deliberately independent of census.toml. A vertical slice adds its fixture here
# before promoting the corresponding census row to ``connected``.
CONNECTED_PROOF_FIXTURES: tuple[ConnectedProofFixture, ...] = ()


def connected_candidate_ids(census_path: Path | None = None) -> tuple[str, ...]:
    """Read only the disposition/candidate axes needed to decide composition."""
    path = census_path or bundled_path("source_connectivity", "census.toml")
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    entries = raw.get("entries", ())
    if not isinstance(entries, list):
        raise ConnectedProofCompositionError("source-connectivity census entries must be an array")
    connected: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("disposition") != "connected":
            continue
        candidate_id = entry.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise ConnectedProofCompositionError("connected census row has no candidate_id")
        connected.append(candidate_id)
    return tuple(sorted(connected))


def _selected_fixtures(candidate_ids: tuple[str, ...]) -> tuple[ConnectedProofFixture, ...]:
    fixtures = {fixture.candidate_id: fixture for fixture in CONNECTED_PROOF_FIXTURES}
    if len(fixtures) != len(CONNECTED_PROOF_FIXTURES):
        raise ConnectedProofCompositionError("connected proof fixture candidate ids must be unique")
    missing = tuple(candidate_id for candidate_id in candidate_ids if candidate_id not in fixtures)
    if missing:
        raise ConnectedProofCompositionError(
            "connected census rows lack independent proof fixtures: " + ", ".join(missing),
        )
    return tuple(fixtures[candidate_id] for candidate_id in candidate_ids)


def _execute_fixture(
    objects: SecureObjectRepository,
    repository: CalculationRevisionCatalogueRepository,
    fixture: ConnectedProofFixture,
) -> LiveSourceConnectivityProofExpectation:
    period = Period.from_year_and_code(fixture.filing_year, fixture.period)
    timestamp = datetime(2026, 8, 23, 10, 0, tzinfo=UTC)
    invoice = build_catalogue_invoice(
        bucket_id=fixture.invoice_bucket_id,
        kind=fixture.invoice_kind,
        invoice_number=fixture.invoice_number,
        issued_at=fixture.invoice_issued_at,
        counterparty_name=fixture.invoice_counterparty_name,
        counterparty_tax_id=fixture.invoice_counterparty_tax_id,
        counterparty_country=fixture.invoice_counterparty_country,
        taxable_base=fixture.invoice_taxable_base,
        iva_rate=fixture.invoice_iva_rate,
        currency=fixture.invoice_currency,
        payment_status=fixture.invoice_payment_status,
        iva_category=fixture.invoice_iva_category,
        operation_type=fixture.invoice_operation_type,
    )
    work_unit_id = derive_work_unit_id(
        bucket_id=fixture.invoice_bucket_id,
        modelo=fixture.modelo,
        filing_year=fixture.filing_year,
        period=period,
        revision_id=fixture.revision_id,
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=fixture.invoice_bucket_id,
        modelo=fixture.modelo,
        filing_year=fixture.filing_year,
        period=period,
        revision_id=fixture.revision_id,
        name=f"proof-{fixture.candidate_id}",
        created_at=timestamp,
        updated_at=timestamp,
    )
    work_units = WorkUnitCatalogueRepository(objects=objects)
    work_units.save(WorkUnitCatalogue.from_work_units((work_unit,)))
    invoice_repository = InvoiceCatalogueRepository(objects=objects)
    create_catalogue_invoice(
        invoice=invoice,
        repository=invoice_repository,
        event_repository=BucketEventHistoryRepository(objects=objects),
        occurred_at=timestamp,
        actor="source-connectivity-proof",
    )
    snapshot = bundled_authority().snapshot(
        fixture.modelo,
        filing_year=fixture.filing_year,
        period=fixture.period,
    )
    resolver = InvoiceCatalogueSourceResolver(invoice_repository=invoice_repository)
    _require_calculation_route_resolver("mesh", resolver)
    resolution = resolver.resolve(
        CalculationSourceContext(
            bucket_id=work_unit.bucket_id,
            work_unit_id=work_unit.work_unit_id,
            modelo=work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period,
            revision=snapshot.revision,
        ),
    )
    source_inputs = _source_bound_casilla_inputs(
        snapshot.revision,
        source_resolution=resolution,
        backend_binding_values=resolution.binding_values,
    )
    engine_result = calculate_registry_snapshot(
        snapshot,
        inputs=source_inputs,
        date_context={"filing_period": period.end_date},
        binding_values=resolution.binding_values,
    )
    replay = build_calculation_replay_payloads(
        resolved_inputs=source_inputs,
        resolved_bindings=resolution.binding_values,
        resolved_enum_bindings={},
        resolved_date_bindings={},
        resolved_relations={},
        resolved_row_bindings=resolution.row_binding_values,
    )
    work_unit_catalogue, work_unit_catalogue_revision_id = work_units.load_revisioned()
    revision = persist_calculation_revision(
        work_unit_id=work_unit_id,
        work_unit=work_unit,
        work_units=work_unit_catalogue,
        work_units_revision_id=work_unit_catalogue_revision_id,
        input_values_by_casilla_id=replay.input_values_by_casilla_id,
        binding_overrides=replay.binding_overrides,
        row_binding_values=replay.row_binding_values,
        row_source_identities={},
        row_casilla_values={},
        row_casilla_provenance={},
        relation_overrides=replay.relation_overrides,
        casilla_values=dict(engine_result.values),
        source_transaction_ids=tuple(resolution.source_transaction_ids),
        borrador_snapshot_id=None,
        bindings_sourced_from_borrador=(),
        observations=build_typed_observations(engine_result=engine_result, snapshot=snapshot),
        unresolved_outcomes=engine_result.unresolved_outcomes,
        source_provenance=_source_provenance_refs(resolution),
        source_issues=(),
        detail_rows=resolution.detail_rows,
        formula_count=len(engine_result.entries),
        actor="source-connectivity-proof",
        now=datetime(2026, 8, 23, 11, 0, tzinfo=UTC),
        work_unit_repository=work_units,
        calculation_repository=repository,
        bucket_event_repository=BucketEventHistoryRepository(objects=objects),
    )
    revision_id = revision.calculation_revision_id
    actual_value = revision.casilla_values.get(validated_casilla_id(fixture.expected_casilla_id))
    if actual_value != fixture.expected_casilla_value:
        raise ConnectedProofCompositionError(
            f"production fixture destination mismatch for {fixture.candidate_id}: {actual_value!r}",
        )
    catalogue = repository.load()
    revision = catalogue.revisions.get(revision_id)
    if revision is None:
        raise ConnectedProofCompositionError(
            f"production fixture did not persist calculation revision: {fixture.candidate_id}",
        )
    _require_unique_primary(revision, fixture)
    connection = SourceConnectivityConnectionIdentity(
        candidate_id=fixture.candidate_id,
        source_kind=fixture.source_kind,
        source_ref=fixture.source_ref,
        resolver_id=fixture.resolver_id,
        calculation_revision_id=revision_id,
    )
    return LiveSourceConnectivityProofExpectation(
        connection=connection,
        entrypoint_id=fixture.entrypoint_id,
        command_id=fixture.command_id,
        route_id=fixture.route_id,
        canonical_cli_path=fixture.canonical_cli_path,
        destination_identities=fixture.destination_identities,
    )


def _require_unique_primary(revision: CalculationRevision, fixture: ConnectedProofFixture) -> None:
    """Refuse unless the encrypted result has one exact resolver-owned primary."""
    matching = tuple(
        row
        for row in revision.source_provenance
        if row.lineage_role is CalculationSourceLineageRole.PRIMARY
        and row.resolved_binding_source is fixture.source_kind
        and row.resolver_id == fixture.resolver_id
        and row.source_ref == fixture.source_ref
    )
    if len(matching) != 1:
        raise ConnectedProofCompositionError(
            f"production fixture emitted no unique expected primary provenance: {fixture.candidate_id}",
        )


@contextmanager
def _ephemeral_connected_proof_material(
    fixtures: tuple[ConnectedProofFixture, ...],
) -> Generator[
    tuple[
        CalculationRevisionCatalogueRepository,
        tuple[LiveSourceConnectivityProofExpectation, ...],
        Path,
    ]
]:
    """Execute typed fixtures in one deterministic credential-free lifecycle."""
    with ExitStack() as cleanup:
        temporary = cleanup.enter_context(tempfile.TemporaryDirectory(prefix="cadrumo-source-connectivity-"))
        key = secrets.token_bytes(KEY_SIZE)
        session = BucketSession.open(
            bucket_id=fixtures[0].invoice_bucket_id,
            kek=key,
            dek=key,
            idle_minutes=5,
            opened_at=now(),
            unsecured_backend=False,
        )
        cleanup.callback(session.close)
        database_path = Path(temporary) / "proof.db"
        engine = create_engine(f"sqlite:///{database_path.as_posix()}")
        cleanup.callback(engine.dispose)
        cleanup.enter_context(activate_session(session))
        objects = SecureObjectRepository(engine=engine)
        revisions = CalculationRevisionCatalogueRepository(objects=objects)
        expectations = tuple(_execute_fixture(objects, revisions, fixture) for fixture in fixtures)
        yield revisions, expectations, database_path


@contextmanager
def _live_authority_for_fixtures(
    repository_root: Path,
    fixtures: tuple[ConnectedProofFixture, ...],
) -> Generator[LiveSourceConnectivityProofAuthority]:
    """Compose canonical authorities over independently executed proof material."""
    with _ephemeral_connected_proof_material(fixtures) as (revisions, expectations, _database_path):
        yield LiveSourceConnectivityProofAuthority(
            source_ownership=build_calculation_route_source_ownership_catalogue(),
            workflows=build_supported_modelo_calculation_workflow_catalogue(
                current_operator_surface_reconciliation(),
            ),
            calculation_revisions=revisions,
            evidence_verifier=RepositoryRootEvidenceDigestVerifier(repository_root=repository_root),
            independent_expectations=expectations,
        )


@contextmanager
def canonical_live_connected_proof_authority(
    repository_root: Path,
) -> Generator[LiveSourceConnectivityProofAuthority | None]:
    """Yield the canonical live authority only when connected rows require it."""
    candidate_ids = connected_candidate_ids()
    if not candidate_ids:
        yield None
        return
    fixtures = _selected_fixtures(candidate_ids)
    with _live_authority_for_fixtures(repository_root, fixtures) as authority:
        yield authority


__all__ = [
    "CONNECTED_PROOF_FIXTURES",
    "ConnectedProofCompositionError",
    "ConnectedProofFixture",
    "canonical_live_connected_proof_authority",
    "connected_candidate_ids",
]
