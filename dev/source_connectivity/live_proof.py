"""Canonical ephemeral composition for live connected-census proof gates."""

from __future__ import annotations

import secrets
import tempfile
import tomllib
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import (
    CalculationRevisionCatalogueRepository,
)
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.storage import KEY_SIZE, SecureObjectRepository
from cadrumo.adapters.persistence.storage.master_key import BucketSession, activate_session
from cadrumo.application.aggregation import CalculationSourceContext
from cadrumo.application.invoices import InvoiceCatalogueSourceResolver
from cadrumo.application.modelo._calculation_actions import (
    _calculate_modelo_revision_with_trusted_mesh_sources,
    _require_calculation_route_resolver,
    _source_bound_casilla_inputs,
    _source_provenance_refs,
)
from cadrumo.application.modelo._registry_resources import authority_via_resources
from cadrumo.application.operator_surface import build_supported_modelo_calculation_workflow_catalogue
from cadrumo.application.registry import (
    LiveSourceConnectivityProofAuthority,
    LiveSourceConnectivityProofExpectation,
    RepositoryRootEvidenceDigestVerifier,
    build_calculation_route_source_ownership_catalogue,
)
from cadrumo.core import (
    BindingSourceKind,
    CalculationSourceLineageRole,
    Period,
    validated_casilla_id,
)
from cadrumo.core._calculation_route import ModeloCalculationRouteId
from cadrumo.core.resources import bundled_path
from cadrumo.core.source_connectivity import SourceConnectivityConnectionIdentity
from cadrumo.core.time import now
from cadrumo.domain.invoices import Invoice, InvoiceCatalogue
from cadrumo.domain.modelos import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from cadrumo.entrypoints.cli._common import _current_operator_surface_reconciliation


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
    destination_identities: tuple[tuple[str, str, str], ...]
    modelo: str
    revision_id: str
    filing_year: int
    period: str
    expected_casilla_id: str
    expected_casilla_value: Decimal
    invoice: Invoice


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
    work_unit_id = derive_work_unit_id(
        bucket_id=fixture.invoice.bucket_id,
        modelo=fixture.modelo,
        filing_year=fixture.filing_year,
        period=period,
        revision_id=fixture.revision_id,
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=fixture.invoice.bucket_id,
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
    InvoiceCatalogueRepository(objects=objects).save(InvoiceCatalogue.from_invoices((fixture.invoice,)))
    invoice_repository = InvoiceCatalogueRepository(objects=objects)
    snapshot = authority_via_resources().snapshot(
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
    revision = _calculate_modelo_revision_with_trusted_mesh_sources(
        work_unit_id,
        casilla_inputs={},
        backend_binding_values=resolution.binding_values,
        row_binding_values=resolution.row_binding_values,
        backend_casilla_inputs=_source_bound_casilla_inputs(
            snapshot.revision,
            source_resolution=resolution,
            backend_binding_values=resolution.binding_values,
        ),
        source_transaction_ids=tuple(resolution.source_transaction_ids),
        source_provenance=_source_provenance_refs(resolution),
        detail_rows=resolution.detail_rows,
        work_unit_repository=work_units,
        calculation_repository=repository,
        bucket_event_repository=BucketEventHistoryRepository(objects=objects),
        clock=datetime(2026, 8, 23, 11, 0, tzinfo=UTC),
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


@contextmanager
def _live_authority_for_fixtures(
    repository_root: Path,
    fixtures: tuple[ConnectedProofFixture, ...],
) -> Iterator[LiveSourceConnectivityProofAuthority]:
    """Execute typed fixtures through the canonical ephemeral production route."""
    key = secrets.token_bytes(KEY_SIZE)
    session = BucketSession.open(
        bucket_id=fixtures[0].invoice.bucket_id,
        kek=key,
        dek=key,
        idle_minutes=5,
        opened_at=now(),
        unsecured_backend=False,
    )
    with tempfile.TemporaryDirectory(prefix="cadrumo-source-connectivity-") as temporary:
        engine = create_engine(f"sqlite:///{(Path(temporary) / 'proof.db').as_posix()}")
        with ExitStack() as cleanup:
            cleanup.callback(engine.dispose)
            cleanup.callback(session.close)
            cleanup.enter_context(activate_session(session))
            objects = SecureObjectRepository(engine=engine)
            revisions = CalculationRevisionCatalogueRepository(objects=objects)
            expectations = tuple(_execute_fixture(objects, revisions, fixture) for fixture in fixtures)
            yield LiveSourceConnectivityProofAuthority(
                source_ownership=build_calculation_route_source_ownership_catalogue(),
                workflows=build_supported_modelo_calculation_workflow_catalogue(
                    _current_operator_surface_reconciliation(),
                ),
                calculation_revisions=revisions,
                evidence_verifier=RepositoryRootEvidenceDigestVerifier(repository_root=repository_root),
                independent_expectations=expectations,
            )


@contextmanager
def canonical_live_connected_proof_authority(
    repository_root: Path,
) -> Iterator[LiveSourceConnectivityProofAuthority | None]:
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
