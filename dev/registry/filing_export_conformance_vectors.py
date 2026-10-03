"""Load pinned public vector evidence and build value-independent writer inputs."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Protocol, cast

from pydantic import BaseModel, Field, ValidationError

from cadrumo.application.calculations.observations_repository import CalculationObservationRepositoryProtocol
from cadrumo.application.filing.draft_construction import build_draft
from cadrumo.application.filing.draft_review import approve_draft
from cadrumo.application.filing.draft_review_ports import DraftReviewPorts
from cadrumo.application.filing.producer_snapshot import (
    FilingElectionFacts,
    FilingProducerSnapshot,
    GeneralFilingProfileFacts,
    PresenterIdentity,
    TaxpayerIdentityFacts,
    build_filing_producer_snapshot,
)
from cadrumo.application.filing.runtime import (
    ModeloOperatorProfile,
    schema_provider_from_authority,
)
from cadrumo.core.hashing import sha256_hex
from cadrumo.core.modelo import Modelo
from cadrumo.core.models import STRICT_FROZEN_CONFIG
from cadrumo.core.payment_election import PaymentElection
from cadrumo.core.period import Period
from cadrumo.core.prior_domiciliation_election import PriorDomiciliationElection
from cadrumo.core.refund_election import RefundElection
from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.core.toml import TomlDecodeError, parse_toml
from cadrumo.domain.calculations.registry.authority import (
    bundled_indexed_authority,
)
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.domain.filing.protocols import ModeloInputs
from cadrumo.domain.filing.schema import ModeloDraft
from cadrumo.domain.invoices.models import InvoiceCatalogue
from cadrumo.domain.invoices.protocols import InvoiceCatalogueRepositoryProtocol
from cadrumo.domain.transactions.models import TransactionCatalogue
from cadrumo.domain.transactions.protocols import TransactionCatalogueRepositoryProtocol

from .compiler.authority import compile_validated_authority
from .compiler.export_fragment_grammar import EXPORT_FRAGMENT_PROVENANCE_FILENAME
from .filing_export_proof_contracts import (
    FilingExportConformanceRenderInputs,
    FilingExportConformanceVectorEvidence,
    FilingExportGeneratedOutput,
    FilingExportOfficialProbe,
    FilingExportProofCoordinate,
    FilingExportPublicProvenance,
)
from .pipeline.export_fragment_provenance import (
    ExportFragmentProvenanceManifest,
    load_export_fragment_provenance_manifest,
)


@dataclass(frozen=True, slots=True)
class FilingExportConformanceVector:
    """One explicitly public mechanism vector; never taxpayer truth."""

    evidence: FilingExportConformanceVectorEvidence
    builder: FilingExportConformanceVectorBuilder


class FilingExportConformanceVectorBuilder(Protocol):
    """Materialise transient canonical-writer inputs from public vector source."""

    def build(
        self,
        evidence: FilingExportConformanceVectorEvidence,
    ) -> FilingExportConformanceRenderInputs:
        """Return source-derived inputs without storing taxpayer values in the vector."""


_PINNED_CONFORMANCE_VECTOR_DIR = Path(__file__).parent / "conformance_vectors"


# The public conformance vector for the one revision whose generated provenance
# currently reaches candidate status. The evidence is PINNED as committed data
# rather than re-derived beside the enrollment: re-deriving it here would make
# the enrollment's equality check tautological, whereas a pinned file makes a
# regenerated export tree fail closed as `canonical_builder_conflict` until the
# pin is refreshed under review.
_MODELO_200_2025_PINNED_EVIDENCE = _PINNED_CONFORMANCE_VECTOR_DIR / "modelo_200_2025_y_siguientes.toml"


class PinnedConformanceProbe(BaseModel):
    """One pinned official positioned-literal probe declaration."""

    model_config = STRICT_FROZEN_CONFIG

    record_id: str = Field(min_length=1, max_length=128)
    field_id: str = Field(min_length=1, max_length=128)
    emitted_offset: int = Field(ge=0)
    length: int = Field(ge=1)


class PinnedConformanceCoordinate(BaseModel):
    """The pinned law-selected coordinate one vector declares."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str = Field(min_length=1, max_length=32)
    revision: str = Field(min_length=1, max_length=128)
    layout_ids: tuple[str, ...] = Field(min_length=1)


class PinnedConformanceVectorDocument(BaseModel):
    """One pinned public conformance-vector declaration, validated closed.

    Only the generation MANIFEST digest is pinned. The manifest already
    enumerates every generated output with its own digest, so this single value
    carries the same fail-closed property as re-pinning all of them, and it stays
    committed data so the enrollment's equality check is not tautological.
    """

    model_config = STRICT_FROZEN_CONFIG

    authority_id: str = Field(min_length=1, max_length=128)
    mechanism_source_ref: str = Field(min_length=1, max_length=256)
    generation_manifest_sha256: str = Field(min_length=64, max_length=64)
    filing_year: int
    period_code: str = Field(min_length=1, max_length=16)
    coordinate: PinnedConformanceCoordinate
    probes: tuple[PinnedConformanceProbe, ...] = Field(min_length=1)
    inputs: Mapping[str, Mapping[str, str]] = Field(default_factory=dict)


def load_pinned_conformance_document(path: Path) -> PinnedConformanceVectorDocument:
    """Parse and strictly validate one pinned conformance-vector document.

    Every parse, schema, and IO failure is converted to
    :class:`RegistryValidationError` so the enrollment classifies it as a typed
    residue with a named owner. A corrupt or half-refreshed pin must never
    escape as an unrecorded refusal.

    Returns:
        The validated :class:`PinnedConformanceVectorDocument`.

    Raises:
        RegistryValidationError: If the document is absent, unparseable, or
            does not satisfy the closed pinned-vector contract.
    """
    try:
        raw = parse_toml(path.read_text(encoding="utf-8"))
    except (OSError, TomlDecodeError, UnicodeDecodeError) as error:
        raise RegistryValidationError(f"pinned conformance vector {path.name} is unreadable: {error}") from error
    # rtoml yields lists; the pinned contract is strict and frozen, so the two
    # declared array fields are hydrated to tuples before validation rather than
    # relaxing the model. The canonical freezer is private to another package,
    # so the two known fields are converted here instead of importing across it.
    if isinstance(raw.get("probes"), list):
        raw["probes"] = tuple(raw["probes"])
    coordinate = raw.get("coordinate")
    if isinstance(coordinate, dict) and isinstance(coordinate.get("layout_ids"), list):
        coordinate["layout_ids"] = tuple(coordinate["layout_ids"])
    try:
        return PinnedConformanceVectorDocument.model_validate(raw)
    except ValidationError as error:
        raise RegistryValidationError(
            f"pinned conformance vector {path.name} does not satisfy the pinned-vector contract: {error}",
        ) from error


def build_pinned_conformance_evidence(
    document: PinnedConformanceVectorDocument,
    *,
    manifest_raw: bytes,
    manifest: ExportFragmentProvenanceManifest,
) -> FilingExportConformanceVectorEvidence:
    """Derive one vector's evidence from the live manifest under its pinned digest.

    The bulk provenance is read from the manifest the generator itself wrote,
    while the pinned digest is what admits it. A regenerated tree changes the
    manifest digest and is refused here rather than silently absorbed.

    Returns:
        The :class:`FilingExportConformanceVectorEvidence` for ``document``.

    Raises:
        RegistryValidationError: If the live manifest digest is not the pinned one.
    """
    live_digest = sha256_hex(manifest_raw)
    if live_digest != document.generation_manifest_sha256:
        raise RegistryValidationError(
            "generated provenance manifest digest does not match the pinned conformance vector; "
            "refresh the pin under review after regenerating the export tree",
        )
    return FilingExportConformanceVectorEvidence(
        authority_id=document.authority_id,
        coordinate=FilingExportProofCoordinate(
            modelo=document.coordinate.modelo,
            revision=document.coordinate.revision,
            snapshot_ref=RegistrySnapshotRef(
                modelo=document.coordinate.modelo,
                revision_id=document.coordinate.revision,
                modelo_year=document.filing_year,
                period=document.period_code,
            ),
            layout_ids=document.coordinate.layout_ids,
        ),
        filing_year=document.filing_year,
        period=Period.from_year_and_code(document.filing_year, document.period_code),
        mechanism_source_ref=document.mechanism_source_ref,
        mechanism_source_sha256=live_digest,
        provenance=FilingExportPublicProvenance(
            official_source_ref=manifest.source_ref,
            official_source_sha256=manifest.source_sha256,
            design_epoch=manifest.design_epoch,
            generation_manifest_sha256=live_digest,
            semantic_map_sha256=manifest.semantic_map_sha256,
            render_profile_sha256=manifest.render_profile_sha256,
            loader_semantic_sha256=manifest.loader_semantic_sha256,
            generated_outputs=tuple(
                FilingExportGeneratedOutput(relative_path=item.relative_path, sha256=item.sha256)
                for item in manifest.output_files
            ),
            probes=tuple(
                FilingExportOfficialProbe(
                    record_id=probe.record_id,
                    field_id=probe.field_id,
                    emitted_offset=probe.emitted_offset,
                    length=probe.length,
                )
                for probe in document.probes
            ),
        ),
    )


def load_pinned_conformance_inputs(document: PinnedConformanceVectorDocument) -> ModeloInputs:
    """Return one pinned vector's declared non-sensitive mechanism inputs.

    Returns:
        The flat binding / relation input map the canonical draft builder reads.

    Raises:
        RegistryValidationError: If one id is declared on both typed channels;
            an ambiguous declaration is refused rather than silently resolved.
    """
    decimal_inputs = document.inputs.get("decimal", {})
    enum_inputs = document.inputs.get("enum", {})
    collisions = sorted(set(decimal_inputs) & set(enum_inputs))
    if collisions:
        raise RegistryValidationError(
            f"pinned conformance inputs declare {collisions} on both the decimal and enum channels",
        )
    inputs: dict[str, object] = {key: Decimal(value) for key, value in decimal_inputs.items()}
    inputs.update(enum_inputs)
    return cast("ModeloInputs", inputs)


class _ConformanceTransactionRepository:
    """Keep the public mechanism vector's transaction state explicitly empty."""

    @staticmethod
    def load() -> TransactionCatalogue:
        return TransactionCatalogue()


class _ConformanceInvoiceRepository:
    """Keep the public mechanism vector's invoice state explicitly empty."""

    @staticmethod
    def load() -> InvoiceCatalogue:
        return InvoiceCatalogue()


class _ConformanceObservationRepository:
    """Unused observation capability because the vector supplies its digest."""

    @staticmethod
    def iter_records() -> Iterator[object]:
        return iter(())


class _ConformanceProfileRepository:
    """Unused profile capability because the vector supplies its digest."""

    @staticmethod
    def load_path_values(*, bucket_id: str) -> Mapping[str, str] | None:
        del bucket_id
        return None


class _ConformanceDraftRepository:
    """Unused draft capability for a proof that never persists its synthetic draft."""

    @staticmethod
    def iter_drafts() -> Iterator[ModeloDraft]:
        return iter(())

    @staticmethod
    def envelope_path_for(identifier: str) -> Path:
        return Path("drafts") / f"{identifier}.json"


def _conformance_draft_review_ports() -> DraftReviewPorts:
    """Compose non-persisted review capabilities for the public mechanism vector."""
    return DraftReviewPorts(
        transaction_repository=cast(
            TransactionCatalogueRepositoryProtocol,
            _ConformanceTransactionRepository(),
        ),
        invoice_repository=cast(
            InvoiceCatalogueRepositoryProtocol,
            _ConformanceInvoiceRepository(),
        ),
        observation_repository=cast(
            CalculationObservationRepositoryProtocol,
            _ConformanceObservationRepository(),
        ),
        profile_repository=_ConformanceProfileRepository(),
        draft_repository=_ConformanceDraftRepository(),
    )


@dataclass(frozen=True, slots=True)
class ModeloSociedadesConformanceVectorBuilder:
    """Materialise value-independent Modelo 200 conformance inputs.

    The draft is built from NO inputs against the law-selected snapshot, and the
    producer snapshot carries only synthetic non-sensitive identity. Neither
    carries taxpayer truth, a source-owned calculation, a filing payload, or an
    accepted payload hash: this vector proves writer and layout MECHANICS, and
    real value arrival is the secure-replay channel's separate burden.
    """

    registry_root: Path
    source_root: Path
    pinned_path: Path

    def build(
        self,
        evidence: FilingExportConformanceVectorEvidence,
    ) -> FilingExportConformanceRenderInputs:
        """Return canonical writer inputs for the pinned Modelo 200 coordinate.

        Returns:
            The :class:`FilingExportConformanceRenderInputs` for ``evidence``.
        """
        modelo_id = str(evidence.coordinate.modelo)
        schema_provider = schema_provider_from_authority(
            compile_validated_authority(self.registry_root, self.source_root),
            filing_year=evidence.filing_year,
            period=evidence.period,
            modelos=(modelo_id,),
        )
        draft = build_draft(
            modelo=modelo_id,
            period=evidence.period,
            profile=ModeloOperatorProfile(tax_id=_CONFORMANCE_SUBJECT_TAX_ID, display_name=_CONFORMANCE_SUBJECT_NAME),
            inputs=load_pinned_conformance_inputs(load_pinned_conformance_document(self.pinned_path)),
            schema_provider=schema_provider,
        )
        # The render contract requires an APPROVED draft, so the vector runs the
        # canonical review path rather than stamping the status by hand. Every
        # catalogue and fingerprint is supplied explicitly so no bucket-scoped
        # secure repository is opened for a public mechanism proof.
        with bundled_indexed_authority().operation() as operation:
            approved = approve_draft(
                draft,
                bucket_id=_CONFORMANCE_BUCKET_ID,
                approved_by=_CONFORMANCE_APPROVER,
                schema_provider=schema_provider,
                ports=_conformance_draft_review_ports(),
                operation=operation,
                prior_filing_observations_fingerprint=_EMPTY_STATE_FINGERPRINT,
                profile_activity_fingerprint=_EMPTY_STATE_FINGERPRINT,
                category_profiles={},
            )
        return FilingExportConformanceRenderInputs(
            coordinate=evidence.coordinate,
            filing_year=evidence.filing_year,
            period=evidence.period,
            draft=approved,
            producer_snapshot=_conformance_producer_snapshot(Modelo(modelo_id)),
        )


# The project's conventional synthetic counterparty CIF, already used across the
# test corpus. It is checksum-valid by construction rather than shape-only, so
# no claim is made here that it is unallocated; it is never persisted, never
# transmitted, and never filed, and this vector introduces no new exposure.
# The conformance vector genuinely HAS no prior filing observations and no
# taxpayer profile activity, so both fingerprints are the digest of empty state
# rather than a placeholder: an honest digest of nothing, not a fake digest.
_EMPTY_STATE_FINGERPRINT = sha256_hex(b"")


_CONFORMANCE_BUCKET_ID = "filing-export-conformance"


_CONFORMANCE_APPROVER = "filing-export-conformance-vector"


_CONFORMANCE_SUBJECT_TAX_ID = "A58818501"


_CONFORMANCE_SUBJECT_NAME = "Sociedad Conformance Prueba"


def _conformance_producer_snapshot(modelo: Modelo) -> FilingProducerSnapshot:
    """Build the synthetic non-sensitive producer snapshot for one modelo.

    The modelo follows the vector's own coordinate rather than a constant, so
    reusing this builder for another Sociedades revision cannot emit a snapshot
    for a modelo the layout does not belong to.

    Returns:
        The :class:`FilingProducerSnapshot` for ``modelo``.
    """
    return build_filing_producer_snapshot(
        modelo=modelo,
        taxpayer_tax_id=_CONFORMANCE_SUBJECT_TAX_ID,
        taxpayer_identity=TaxpayerIdentityFacts(
            legal_name=_CONFORMANCE_SUBJECT_NAME,
            given_name=None,
            surnames=None,
            full_name=_CONFORMANCE_SUBJECT_NAME,
        ),
        presenter=PresenterIdentity(tax_id="00000000T", full_name="Gestoria Prueba"),
        model_profile=GeneralFilingProfileFacts(),
        elections=FilingElectionFacts(
            result_disposition=ResultDisposition.INGRESO,
            payment=PaymentElection.INGRESO,
            refund=RefundElection.COMPENSAR,
            prior_domiciliation=PriorDomiciliationElection.KEEP,
        ),
        amendment_evidence=None,
        m303_filing_facts=None,
        refund_account=None,
        charge_account=None,
    )


def canonical_filing_export_conformance_vectors(
    *,
    registry_root: Path,
    source_root: Path,
) -> tuple[FilingExportConformanceVector, ...]:
    """Bind every pinned public evidence document to its canonical builder.

    Returns:
        The enrolled :class:`FilingExportConformanceVector` tuple.
    """
    vectors: list[FilingExportConformanceVector] = []
    for pinned_path in sorted(_PINNED_CONFORMANCE_VECTOR_DIR.glob("*.toml")):
        document = load_pinned_conformance_document(pinned_path)
        manifest_raw, manifest = _pinned_vector_manifest(document, registry_root=registry_root)
        vectors.append(
            FilingExportConformanceVector(
                evidence=build_pinned_conformance_evidence(
                    document,
                    manifest_raw=manifest_raw,
                    manifest=manifest,
                ),
                builder=ModeloSociedadesConformanceVectorBuilder(
                    registry_root=registry_root,
                    source_root=source_root,
                    pinned_path=pinned_path,
                ),
            )
        )
    return tuple(vectors)


def _pinned_vector_manifest(
    document: PinnedConformanceVectorDocument,
    *,
    registry_root: Path,
) -> tuple[bytes, ExportFragmentProvenanceManifest]:
    """Load the generated provenance manifest one pinned vector names.

    Returns:
        The manifest bytes and the parsed manifest.

    Raises:
        RegistryValidationError: If the manifest is absent or unparseable.
    """
    manifest_path = (
        registry_root
        / "modelos"
        / document.coordinate.modelo
        / "revisions"
        / document.coordinate.revision
        / "export"
        / EXPORT_FRAGMENT_PROVENANCE_FILENAME
    )
    try:
        manifest_raw = manifest_path.read_bytes()
    except OSError as error:
        raise RegistryValidationError(
            f"pinned conformance vector names a revision with no generated provenance manifest: {error}",
        ) from error
    return manifest_raw, load_export_fragment_provenance_manifest(manifest_raw)
