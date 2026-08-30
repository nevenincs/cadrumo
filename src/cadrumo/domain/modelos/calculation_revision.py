"""One calculation attempt under a modelo work unit.

A work unit owns many calculation revisions. Each ``calculate``
invocation produces a fresh, content-addressed
:class:`CalculationRevision`. The work unit carries pointer fields
that disambiguate which revision is the most recent (``current``)
and which one is the filed answer (``filed``). Without those
pointers, multiple drafts under the same work unit have no canonical
selection — every consumer (year-aggregation, amendment delta,
forward-period carry-forward) needs to know which one is THE
revision. Formula provenance for every computed casilla is carried
through :class:`CasillaObservation` entries in the typed observations
envelope.

Lifecycle states:

* ``BORRADOR`` — newly calculated; mutable in the sense that
  re-running ``calculate`` creates a new revision rather than
  editing this one. Multiple borradores can coexist.
* ``VERIFICADO_COMPLETO`` — ``verify`` ran cleanly: all required
  casillas resolved, zero blocking findings, source trace
  persisted. The revision is immutable from this point on; any
  recalculation produces a fresh borrador instead.
* ``PRESENTADO`` — paired with a :class:`ModeloRecord`. The revision
  is the currently-effective filed answer for its (bucket, modelo,
  year, period) tuple. Exactly one presentado revision per tuple at
  any time.
* ``PRESENTADO_SUPERSEDIDO`` — a later verified revision was filed
  against the same tuple. The revision and its filing record remain
  in the audit trail.
* ``DESCARTADO`` — operator abandoned the revision before filing.

Two CalculationRevisions can never share a ``calculation_revision_id``;
the id is the SHA-256 of the inputs + binding overrides + computed
casilla values (plus the parent work_unit_id), so structurally
identical re-runs produce the same id and re-running ``calculate``
with the same data is naturally idempotent.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, TypedDict, override

from pydantic import (
    BaseModel,
    Field,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    TypeAdapter,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_serializer,
    model_validator,
)

from ...core import M210_TIPO_RENTA_CODE_PROJECTION, STRICT_FROZEN_CONFIG, M210GrossIncomeSourceMode
from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.hashing import content_hash_hex
from ...core.identity import CalculationRevisionId, SnapshotId, WorkUnitId
from ...core.time import validate_utc_aware
from ..calculations import DirectRowMaterializationProvenance, RowBindingKey, RowCasillaKey, RowSourceIdentity
from ..calculations.registry.bindings import CasillaObservation
from ..calculations.registry.formula_runtime import RegistryCalculationUnresolvedOutcome
from ..calculations.registry.ids import BindingId, RelationId
from ..identifiers import canonical_decimal_string as _canonical_decimal
from .calculation_revision_amendment import CalculationRevisionAmendmentIdentity, CalculationRevisionAmendmentKind
from .calculation_revision_m303_handoff import (
    M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS,
    FilingInstanceEvidence,
    M303RegimenSimplificadoAnnualSummaryHandoff,
)
from .errors import ModeloError, ModeloValidationError
from .filing_text import ModeloActorLabel, OperatorReason
from .ledger_filing_snapshot import LedgerFilingEvidence, LedgerFilingSnapshot
from .row_models import Modelo210AgrupacionRentaRow, Modelo349OperadorRow, Modelo349RectificacionRow, ModeloDetailRow


class CalculationRevisionState(StrEnum):
    """Closed enumeration of calculation-revision lifecycle states."""

    BORRADOR = "borrador"
    VERIFICADO_COMPLETO = "verificado_completo"
    PRESENTADO = "presentado"
    PRESENTADO_SUPERSEDIDO = "presentado_supersedido"
    DESCARTADO = "descartado"


SEALED_REVISION_STATES: frozenset[CalculationRevisionState] = frozenset(
    {
        CalculationRevisionState.VERIFICADO_COMPLETO,
        CalculationRevisionState.PRESENTADO,
        CalculationRevisionState.PRESENTADO_SUPERSEDIDO,
    },
)
"""States in which a revision is no longer a mutable draft, because something
was verified or filed. :attr:`CalculationRevisionState.BORRADOR` and
:attr:`CalculationRevisionState.DESCARTADO` are excluded.
:attr:`CalculationRevisionState.PRESENTADO_SUPERSEDIDO` IS included -- a
superseded filing still occurred.

This is NOT the same as the narrower "currently authoritative" set, which
additionally excludes :attr:`CalculationRevisionState.PRESENTADO_SUPERSEDIDO`."""


CURRENT_SEALED_REVISION_STATES: frozenset[CalculationRevisionState] = frozenset(
    {
        CalculationRevisionState.VERIFICADO_COMPLETO,
        CalculationRevisionState.PRESENTADO,
    },
)
"""A revision an operator-facing action may select as the CURRENT result --
sealed AND not superseded.

This is :data:`SEALED_REVISION_STATES` minus
:attr:`CalculationRevisionState.PRESENTADO_SUPERSEDIDO`. The two must never be
substituted for one another: this narrower set is for surfaces that hand a
revision to an operator or a third party as the current state of a filing,
while the broader :data:`SEALED_REVISION_STATES` remains correct for surfaces
that need every sealed revision including superseded ones.

The operations replay path (``application.modelo.operation_definitions``'s
export operation) deliberately uses the broader :data:`SEALED_REVISION_STATES`
instead of this set, because a journalled export replay must reproduce its
own history even after the revision it names has been superseded. This
narrower set exists for the operator-facing surfaces that must not do that --
as one of them puts it, "a superseded revision is stale and must not be
handed to an accountant as current" (see
:mod:`application.modelo.review_package`)."""


_BINDING_ID_ADAPTER: TypeAdapter[BindingId] = TypeAdapter(BindingId)
_RELATION_ID_ADAPTER: TypeAdapter[RelationId] = TypeAdapter(RelationId)


def _validated_casilla_id(value: object, *, surface: str) -> CasillaId:
    try:
        return validated_casilla_id(value, surface=surface)
    except ValueError as exc:
        raise ModeloValidationError(f"{surface} contains non-canonical casilla.id {value!r}") from exc


def _validated_binding_id(value: object, *, surface: str) -> BindingId:
    try:
        return _BINDING_ID_ADAPTER.validate_python(value)
    except ValidationError as exc:
        raise ModeloValidationError(f"{surface} contains non-canonical binding id {value!r}") from exc


def _validated_relation_id(value: object, *, surface: str) -> RelationId:
    try:
        return _RELATION_ID_ADAPTER.validate_python(value)
    except ValidationError as exc:
        raise ModeloValidationError(f"{surface} contains non-canonical relation id {value!r}") from exc


def _canonical_detail_rows(rows: Sequence[ModeloDetailRow]) -> list[dict[str, object]]:
    """Stable, sort-canonical projection of detail rows for the hash payload.

    Each row is serialised as a sorted dict of its string/decimal fields.
    Rows are sorted by (row_type, nif-like) so insertion order does not affect
    the revision id — operators can supply rows in any order. The nif-like field
    varies by row type: nif (M184/M232/M347) or nif_comunitario (M349).

    Occurrence number established as presentation-only (S292): every
    row-producer resolver these detail rows correspond to sorts by an
    equivalent content key before assigning fichero occurrence numbers, so
    two supply orders render identical bytes, not merely the same id here.
    See :class:`~cadrumo.application.modelo._edit_models.
    ModeloEditDetailRowIntentKind` for why ``MOVE_ROW`` has no addressable
    effect for this row family.
    """

    def _row_payload(row: ModeloDetailRow) -> dict[str, object]:
        d: dict[str, object] = {}
        for field_name, field_value in row.model_dump().items():
            if isinstance(field_value, Decimal):
                d[field_name] = str(field_value.normalize())
            else:
                d[field_name] = str(field_value)
        return dict(sorted(d.items()))

    def _row_identity_key(row: ModeloDetailRow) -> str:
        if isinstance(row, Modelo210AgrupacionRentaRow):
            return row.source_id
        if isinstance(row, (Modelo349OperadorRow, Modelo349RectificacionRow)):
            return row.nif_comunitario
        return row.nif

    return [_row_payload(r) for r in sorted(rows, key=lambda r: (r.row_type, _row_identity_key(r)))]


def _validated_row_binding_index(value: object, *, surface: str) -> str:
    if isinstance(value, bool):
        raise ModeloValidationError(f"{surface} contains non-positive row index {value!r}")
    if isinstance(value, int):
        index = value
    elif isinstance(value, str):
        try:
            index = int(value)
        except ValueError as exc:
            raise ModeloValidationError(f"{surface} contains non-positive row index {value!r}") from exc
    else:
        raise ModeloValidationError(f"{surface} contains non-positive row index {value!r}")
    if index < 1:
        raise ModeloValidationError(f"{surface} contains non-positive row index {value!r}")
    return str(index)


def _canonical_row_binding_values(
    row_binding_values: Mapping[object, object],
    *,
    surface: str,
) -> dict[BindingId, dict[str, str]]:
    canonical: dict[BindingId, dict[str, str]] = {}
    for raw_binding_id, raw_rows in row_binding_values.items():
        binding_id = _validated_binding_id(raw_binding_id, surface=surface)
        if not isinstance(raw_rows, Mapping):
            raise ModeloValidationError(f"{surface} for binding {binding_id!r} must be a row-index mapping")
        typed_rows = TypeAdapter(dict[object, object]).validate_python(raw_rows)
        rows: dict[str, str] = {}
        for raw_row_index, raw_value in typed_rows.items():
            row_index = _validated_row_binding_index(raw_row_index, surface=f"{surface}[{binding_id!r}]")
            if row_index in rows:
                raise ModeloValidationError(
                    f"{surface} for binding {binding_id!r} contains duplicate row {row_index!r}",
                )
            rows[row_index] = str(raw_value).strip()
        if rows:
            canonical[binding_id] = dict(sorted(rows.items(), key=lambda item: int(item[0])))
    return dict(sorted(canonical.items()))


def _string_keyed_context(context: object) -> Mapping[str, object] | None:
    """Narrow a pydantic ``ValidationInfo``/serializer ``context`` to a string-keyed mapping.

    Every caller here reads the context by a literal string marker key
    (``"secure_calculation_revision"``); a context that is not a mapping at
    all carries none of those markers and is treated the same as absent.
    """
    if not isinstance(context, Mapping):
        return None
    return TypeAdapter(Mapping[str, object]).validate_python(context)


def _empty_row_source_identities() -> dict[RowBindingKey, RowSourceIdentity]:
    return {}


def _empty_row_casilla_values() -> dict[RowCasillaKey, Decimal]:
    return {}


def _empty_row_casilla_provenance() -> dict[RowCasillaKey, DirectRowMaterializationProvenance]:
    return {}


def _canonical_row_source_identities(
    value: Mapping[RowBindingKey, RowSourceIdentity],
) -> list[dict[str, object]]:
    canonical: list[dict[str, object]] = []
    for (binding_id, row_index), identity in sorted(value.items()):
        row_identity: dict[str, object] = {
            "binding_id": binding_id,
            "row_index": row_index,
            "source_kind": identity.source_kind.value,
            "source_row_identity": identity.source_row_identity,
            "fingerprint": identity.fingerprint,
        }
        if identity.row_set_grouping is not None:
            row_identity["row_set_grouping"] = identity.row_set_grouping
        canonical.append(row_identity)
    return canonical


def _canonical_row_casilla_values(value: Mapping[RowCasillaKey, Decimal]) -> list[dict[str, object]]:
    return [
        {"casilla_id": casilla_id, "row_index": row_index, "value": _canonical_decimal(amount)}
        for (casilla_id, row_index), amount in sorted(value.items())
    ]


def _canonical_row_casilla_provenance(
    value: Mapping[RowCasillaKey, DirectRowMaterializationProvenance],
) -> list[dict[str, object]]:
    return [
        {
            "casilla_id": casilla_id,
            "row_index": row_index,
            "source_binding_id": provenance.source_binding_id,
            "source_row_index": provenance.source_row_index,
            "source_identity": provenance.source_identity.model_dump(mode="json", exclude_none=True),
            "materialization_rule_id": provenance.materialization_rule_id,
            "materialization_rule_version": provenance.materialization_rule_version,
        }
        for (casilla_id, row_index), provenance in sorted(value.items())
    ]


def _base_revision_id_payload(
    *,
    work_unit_id: str,
    input_values_by_casilla_id: Mapping[CasillaId, str],
    binding_overrides: Mapping[BindingId, str],
    casilla_values: Mapping[CasillaId, Decimal],
    source_transaction_ids: Sequence[str],
) -> dict[str, object]:
    """Build the always-present payload keys for the revision-id hash."""
    return {
        "work_unit_id": work_unit_id.strip(),
        "inputs": dict(
            sorted(
                (_validated_casilla_id(k, surface="input_values_by_casilla_id"), v.strip())
                for k, v in input_values_by_casilla_id.items()
            ),
        ),
        "overrides": dict(
            sorted(
                (_validated_binding_id(k, surface="binding_overrides"), v.strip()) for k, v in binding_overrides.items()
            ),
        ),
        "outputs": _outputs_for_hash_from_mapping(casilla_values),
        "source_transaction_ids": tuple(sorted(item.strip() for item in source_transaction_ids)),
    }


def _cleared_casillas_revision_id_payload(
    cleared_casilla_ids: Sequence[CasillaId],
) -> dict[str, object]:
    """Build the optional explicit-clear payload key.

    An explicitly cleared casilla participates in identity as its own axis so
    that clearing a previously declared value is structurally distinguishable
    from a casilla that was simply never supplied: both are absent from
    ``input_values_by_casilla_id``, but only the cleared one appears here.
    """
    canonical_cleared = tuple(
        sorted(_validated_casilla_id(item, surface="cleared_casilla_ids") for item in cleared_casilla_ids)
    )
    if canonical_cleared:
        return {"cleared_casilla_ids": canonical_cleared}
    return {}


def _m210_revision_id_payload(
    m210_official_tipo_renta_code: str | None,
    m210_gross_income_source_mode: M210GrossIncomeSourceMode | None,
) -> dict[str, object]:
    """Build the optional Modelo 210 payload keys, validating the official code."""
    parts: dict[str, object] = {}
    if m210_official_tipo_renta_code is not None:
        code = m210_official_tipo_renta_code.strip()
        if code not in M210_TIPO_RENTA_CODE_PROJECTION:
            raise ModeloValidationError(
                f"m210_official_tipo_renta_code must be a registry-projected Modelo 210 code, got {code!r}",
            )
        parts["m210_official_tipo_renta_code"] = code
    if m210_gross_income_source_mode is not None:
        parts["m210_gross_income_source_mode"] = m210_gross_income_source_mode.value
    return parts


def _borrador_revision_id_payload(
    borrador_snapshot_id: str | None,
    bindings_sourced_from_borrador: Sequence[BindingId],
) -> dict[str, object]:
    """Build the optional borrador snapshot / sourced-binding payload keys."""
    parts: dict[str, object] = {}
    normalized_borrador_snapshot_id = borrador_snapshot_id.strip() if borrador_snapshot_id else None
    normalized_borrador_bindings = tuple(
        sorted(
            _validated_binding_id(item, surface="bindings_sourced_from_borrador")
            for item in bindings_sourced_from_borrador
        ),
    )
    if normalized_borrador_snapshot_id is not None:
        parts["borrador_snapshot_id"] = normalized_borrador_snapshot_id
    if normalized_borrador_bindings:
        parts["bindings_sourced_from_borrador"] = normalized_borrador_bindings
    return parts


def _source_issues_revision_id_payload(
    source_issues: Sequence[CalculationSourceIssue],
) -> dict[str, object]:
    """Build the optional unresolved-source-issue payload key."""
    canonical_source_issues = tuple(
        sorted(
            (
                issue.reason,
                issue.binding_source.value,
                issue.source_ref or "",
                issue.resolver_id or "",
                issue.message,
            )
            for issue in source_issues
        )
    )
    if canonical_source_issues:
        return {"source_issues": canonical_source_issues}
    return {}


def _source_provenance_revision_id_payload(
    source_provenance: Sequence[CalculationSourceRef],
) -> dict[str, object]:
    """Build the required, complete order-independent source identity payload."""
    canonical_source_provenance = tuple(
        sorted(
            (
                ref.resolver_id,
                ref.resolved_binding_source.value,
                ref.contributor_source_kind,
                ref.contributor_binding_source.value if ref.contributor_binding_source is not None else "",
                ref.lineage_role.value,
                ref.source_ref,
                ref.parent_source_ref or "",
                ref.fingerprint or "",
                tuple(sorted(ref.source_casilla_ids)),
                ref.dependency_treatment,
            )
            for ref in source_provenance
        )
    )
    return {"source_provenance": canonical_source_provenance}


def _filing_instance_evidence_revision_id_payload(
    evidence: FilingInstanceEvidence | None,
) -> dict[str, object]:
    """Build the immutable filing-instance evidence identity payload."""
    if evidence is None:
        return {}
    return {"filing_instance_evidence": evidence.model_dump(mode="json")}


def _m303_regimen_simplificado_annual_summary_handoff_revision_id_payload(
    handoff: M303RegimenSimplificadoAnnualSummaryHandoff | None,
) -> dict[str, object]:
    """Build the target-id-free immutable annual-summary identity payload."""
    if handoff is None:
        return {}
    return {"m303_regimen_simplificado_annual_summary_handoff": handoff.unsigned_identity_payload()}


class CalculationRevisionIdentityInputs(TypedDict):
    """The complete, target-id-free input set for a calculation revision hash."""

    work_unit_id: str
    input_values_by_casilla_id: Mapping[CasillaId, str]
    binding_overrides: Mapping[BindingId, str]
    row_binding_values: Mapping[BindingId, Mapping[str, str]] | None
    row_source_identities: Mapping[RowBindingKey, RowSourceIdentity]
    row_casilla_values: Mapping[RowCasillaKey, Decimal]
    row_casilla_provenance: Mapping[RowCasillaKey, DirectRowMaterializationProvenance]
    casilla_values: Mapping[CasillaId, Decimal]
    relation_overrides: Mapping[RelationId, str] | None
    source_transaction_ids: Sequence[str]
    m210_official_tipo_renta_code: str | None
    m210_gross_income_source_mode: M210GrossIncomeSourceMode | None
    borrador_snapshot_id: str | None
    bindings_sourced_from_borrador: Sequence[BindingId]
    detail_rows: Sequence[ModeloDetailRow]
    source_issues: Sequence[CalculationSourceIssue]
    source_provenance: Sequence[CalculationSourceRef]
    filing_instance_evidence: FilingInstanceEvidence | None
    m303_regimen_simplificado_annual_summary_handoff: M303RegimenSimplificadoAnnualSummaryHandoff | None
    amendment_identity: CalculationRevisionAmendmentIdentity | None
    cleared_casilla_ids: Sequence[CasillaId]


def calculation_revision_identity_inputs(
    *,
    work_unit_id: str,
    input_values_by_casilla_id: Mapping[CasillaId, str],
    binding_overrides: Mapping[BindingId, str],
    row_binding_values: Mapping[BindingId, Mapping[str, str]] | None = None,
    row_source_identities: Mapping[RowBindingKey, RowSourceIdentity] | None = None,
    row_casilla_values: Mapping[RowCasillaKey, Decimal] | None = None,
    row_casilla_provenance: Mapping[RowCasillaKey, DirectRowMaterializationProvenance] | None = None,
    casilla_values: Mapping[CasillaId, Decimal],
    relation_overrides: Mapping[RelationId, str] | None = None,
    source_transaction_ids: Sequence[str] = (),
    m210_official_tipo_renta_code: str | None = None,
    m210_gross_income_source_mode: M210GrossIncomeSourceMode | None = None,
    borrador_snapshot_id: str | None = None,
    bindings_sourced_from_borrador: Sequence[BindingId] = (),
    detail_rows: Sequence[ModeloDetailRow] = (),
    source_issues: Sequence[CalculationSourceIssue] = (),
    source_provenance: Sequence[CalculationSourceRef],
    filing_instance_evidence: FilingInstanceEvidence | None,
    m303_regimen_simplificado_annual_summary_handoff: M303RegimenSimplificadoAnnualSummaryHandoff | None = None,
    amendment_identity: CalculationRevisionAmendmentIdentity | None = None,
    cleared_casilla_ids: Sequence[CasillaId] = (),
) -> CalculationRevisionIdentityInputs:
    """Build the one complete target-id-free calculation-revision identity input.

    Every revision-id derivation flows through this builder.  The annual-summary
    handoff is deliberately represented here, rather than selectively added by
    its producer or read-side verifier, so a future identity consumer cannot
    silently omit the cross-model calculation input.
    """
    return {
        "work_unit_id": work_unit_id,
        "input_values_by_casilla_id": input_values_by_casilla_id,
        "binding_overrides": binding_overrides,
        "row_binding_values": row_binding_values,
        "row_source_identities": row_source_identities or {},
        "row_casilla_values": row_casilla_values or {},
        "row_casilla_provenance": row_casilla_provenance or {},
        "casilla_values": casilla_values,
        "relation_overrides": relation_overrides,
        "source_transaction_ids": source_transaction_ids,
        "m210_official_tipo_renta_code": m210_official_tipo_renta_code,
        "m210_gross_income_source_mode": m210_gross_income_source_mode,
        "borrador_snapshot_id": borrador_snapshot_id,
        "bindings_sourced_from_borrador": bindings_sourced_from_borrador,
        "detail_rows": detail_rows,
        "source_issues": source_issues,
        "source_provenance": source_provenance,
        "filing_instance_evidence": filing_instance_evidence,
        "m303_regimen_simplificado_annual_summary_handoff": (m303_regimen_simplificado_annual_summary_handoff),
        "amendment_identity": amendment_identity,
        "cleared_casilla_ids": cleared_casilla_ids,
    }


def derive_calculation_revision_id(
    *,
    work_unit_id: str,
    input_values_by_casilla_id: Mapping[CasillaId, str],
    binding_overrides: Mapping[BindingId, str],
    row_binding_values: Mapping[BindingId, Mapping[str, str]] | None = None,
    row_source_identities: Mapping[RowBindingKey, RowSourceIdentity] | None = None,
    row_casilla_values: Mapping[RowCasillaKey, Decimal] | None = None,
    row_casilla_provenance: Mapping[RowCasillaKey, DirectRowMaterializationProvenance] | None = None,
    casilla_values: Mapping[CasillaId, Decimal],
    relation_overrides: Mapping[RelationId, str] | None = None,
    source_transaction_ids: Sequence[str] = (),
    m210_official_tipo_renta_code: str | None = None,
    m210_gross_income_source_mode: M210GrossIncomeSourceMode | None = None,
    borrador_snapshot_id: str | None = None,
    bindings_sourced_from_borrador: Sequence[BindingId] = (),
    detail_rows: Sequence[ModeloDetailRow] = (),
    source_issues: Sequence[CalculationSourceIssue] = (),
    source_provenance: Sequence[CalculationSourceRef],
    filing_instance_evidence: FilingInstanceEvidence | None,
    m303_regimen_simplificado_annual_summary_handoff: M303RegimenSimplificadoAnnualSummaryHandoff | None = None,
    amendment_identity: CalculationRevisionAmendmentIdentity | None = None,
    cleared_casilla_ids: Sequence[CasillaId] = (),
) -> str:
    """Return the deterministic SHA-256 id for a calculation attempt."""
    return _derive_calculation_revision_id_from_identity_inputs(
        calculation_revision_identity_inputs(
            work_unit_id=work_unit_id,
            input_values_by_casilla_id=input_values_by_casilla_id,
            binding_overrides=binding_overrides,
            row_binding_values=row_binding_values,
            row_source_identities=row_source_identities,
            row_casilla_values=row_casilla_values,
            row_casilla_provenance=row_casilla_provenance,
            casilla_values=casilla_values,
            relation_overrides=relation_overrides,
            source_transaction_ids=source_transaction_ids,
            m210_official_tipo_renta_code=m210_official_tipo_renta_code,
            m210_gross_income_source_mode=m210_gross_income_source_mode,
            borrador_snapshot_id=borrador_snapshot_id,
            bindings_sourced_from_borrador=bindings_sourced_from_borrador,
            detail_rows=detail_rows,
            source_issues=source_issues,
            source_provenance=source_provenance,
            filing_instance_evidence=filing_instance_evidence,
            m303_regimen_simplificado_annual_summary_handoff=(m303_regimen_simplificado_annual_summary_handoff),
            amendment_identity=amendment_identity,
            cleared_casilla_ids=cleared_casilla_ids,
        ),
    )


def _derive_calculation_revision_id_from_identity_inputs(
    identity_inputs: CalculationRevisionIdentityInputs,
) -> str:
    """Hash a value returned only by :func:`calculation_revision_identity_inputs`.

    The id is content-addressed by the parent work unit plus the
    three payload mappings: input casilla values, scalar binding overrides, and
    computed casilla outputs. Row-indexed binding values are carried as their
    own nested map so repeating-record coordinates participate in identity
    without being flattened into synthetic binding ids. Two
    structurally identical re-runs produce the same id; the
    catalogue's content-addressing invariant then makes a second
    ``calculate`` call idempotent (the existing revision is
    returned, no duplicate is persisted).

    ``detail_rows`` carries typed row observations for informational
    modelos (M184, M232) that declare row-producer bindings. When rows
    are present they are serialised into the hash so structurally
    identical re-runs with the same rows produce the same id.

    ``source_issues`` carries unresolved source conditions that block
    verification. It participates in identity so distinct resolution outcomes
    cannot collapse to one revision. Typed filing-instance evidence likewise
    participates, so changing Modelo 303 joint-return or insolvency facts creates
    a distinct immutable revision rather than mutating a draft.
    """
    work_unit_id = identity_inputs["work_unit_id"]
    input_values_by_casilla_id = identity_inputs["input_values_by_casilla_id"]
    binding_overrides = identity_inputs["binding_overrides"]
    row_binding_values = identity_inputs["row_binding_values"]
    row_source_identities = identity_inputs["row_source_identities"]
    row_casilla_values = identity_inputs["row_casilla_values"]
    row_casilla_provenance = identity_inputs["row_casilla_provenance"]
    casilla_values = identity_inputs["casilla_values"]
    relation_overrides = identity_inputs["relation_overrides"]
    source_transaction_ids = identity_inputs["source_transaction_ids"]
    m210_official_tipo_renta_code = identity_inputs["m210_official_tipo_renta_code"]
    m210_gross_income_source_mode = identity_inputs["m210_gross_income_source_mode"]
    borrador_snapshot_id = identity_inputs["borrador_snapshot_id"]
    bindings_sourced_from_borrador = identity_inputs["bindings_sourced_from_borrador"]
    detail_rows = identity_inputs["detail_rows"]
    source_issues = identity_inputs["source_issues"]
    source_provenance = identity_inputs["source_provenance"]
    filing_instance_evidence = identity_inputs["filing_instance_evidence"]
    m303_regimen_simplificado_annual_summary_handoff = identity_inputs[
        "m303_regimen_simplificado_annual_summary_handoff"
    ]
    amendment_identity = identity_inputs["amendment_identity"]
    cleared_casilla_ids = identity_inputs["cleared_casilla_ids"]
    payload: dict[str, object] = _base_revision_id_payload(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id=input_values_by_casilla_id,
        binding_overrides=binding_overrides,
        casilla_values=casilla_values,
        source_transaction_ids=source_transaction_ids,
    )
    if relation_overrides:
        payload["relation_overrides"] = dict(
            sorted(
                (_validated_relation_id(k, surface="relation_overrides"), v.strip())
                for k, v in relation_overrides.items()
            ),
        )
    payload.update(
        _m210_revision_id_payload(m210_official_tipo_renta_code, m210_gross_income_source_mode),
    )
    raw_row_bindings: dict[object, object] = {
        binding_id: rows for binding_id, rows in (row_binding_values or {}).items()
    }
    canonical_row_bindings = _canonical_row_binding_values(
        raw_row_bindings,
        surface="row_binding_values",
    )
    if canonical_row_bindings:
        payload["row_binding_values"] = canonical_row_bindings
    canonical_row_identities = _canonical_row_source_identities(row_source_identities)
    if canonical_row_identities:
        payload["row_source_identities"] = canonical_row_identities
    canonical_row_casilla_values = _canonical_row_casilla_values(row_casilla_values)
    if canonical_row_casilla_values:
        payload["row_casilla_values"] = canonical_row_casilla_values
    canonical_row_casilla_provenance = _canonical_row_casilla_provenance(row_casilla_provenance)
    if canonical_row_casilla_provenance:
        payload["row_casilla_provenance"] = canonical_row_casilla_provenance
    payload.update(
        _borrador_revision_id_payload(borrador_snapshot_id, bindings_sourced_from_borrador),
    )
    canonical_rows = _canonical_detail_rows(tuple(detail_rows))
    if canonical_rows:
        payload["detail_rows"] = canonical_rows
    payload.update(_source_issues_revision_id_payload(source_issues))
    payload.update(_source_provenance_revision_id_payload(source_provenance))
    payload.update(_filing_instance_evidence_revision_id_payload(filing_instance_evidence))
    payload.update(
        _m303_regimen_simplificado_annual_summary_handoff_revision_id_payload(
            m303_regimen_simplificado_annual_summary_handoff,
        ),
    )
    if amendment_identity is not None:
        payload["amendment_identity"] = amendment_identity.model_dump(mode="json")
    payload.update(_cleared_casillas_revision_id_payload(cleared_casilla_ids))
    return content_hash_hex(payload)


def _outputs_for_hash_from_mapping(casilla_values: Mapping[CasillaId, Decimal]) -> dict[CasillaId, str]:
    """Canonical ``{casilla_id: canonical_decimal_str}`` projection from the flat mapping.

    Pure function — same input → same output, no side effects, no
    dependence on observation order. Used by
    :func:`derive_calculation_revision_id` to produce the ``outputs``
    payload key consumed by the SHA-256 hash, AND by
    :func:`_outputs_for_hash_from_observations` to project the typed
    envelope into the same canonical form so the validator's
    consistency check is byte-exact.

    Validated ``casilla_id`` keys, ``_canonical_decimal`` values, sorted by
    casilla_id — matches the original inline projection in
    :func:`derive_calculation_revision_id` byte-for-byte. The
    A hash-stability contract guards this projection.
    """
    return dict(
        sorted(
            (_validated_casilla_id(k, surface="casilla_values"), _canonical_decimal(v))
            for k, v in casilla_values.items()
        ),
    )


def _outputs_for_hash_from_observations(
    observations: Sequence[CasillaObservation],
) -> dict[CasillaId, str]:
    """Same canonical projection as :func:`_outputs_for_hash_from_mapping`, sourced from observations.

    The typed ``observations`` envelope is the logical source of truth for
    derivation. This helper materialises the same
    ``{casilla_id: canonical_decimal_str}`` projection the flat-mapping
    helper produces, sourced from ``CasillaObservation.value``. The
    validator uses this to assert the persisted ``casilla_values`` field
    is byte-identical to the projection of ``observations``.

    A future cycle drops the flat field and routes the hash directly through
    this helper; currently both fields are kept and this helper is used for
    the consistency check only.
    """
    return _outputs_for_hash_from_mapping(
        {obs.casilla_id: obs.value for obs in observations if isinstance(obs.value, Decimal)}
    )


class CalculationSourceRef(BaseModel):
    """One resolver-level source-object trace persisted on a calculation revision.

    The calculation source mesh (``cadrumo.application.aggregation``) resolves each
    registry binding source through an enrolled resolver and produces a typed
    ``CalculationSourceProvenance`` row per contributing source object. This is
    the DOMAIN-side, persistence-shaped projection of that provenance: it carries
    exactly the resolver→source-object→fingerprint trace that lets an audit reader
    reconstruct which resolver mesh and which upstream source objects produced a
    revision, and whether those objects have since drifted.

    It deliberately does NOT carry ``legal_refs`` / ``source_refs`` — those are the
    per-casilla regulatory grounding already carried by
    :class:`~cadrumo.domain.calculations.registry.CasillaObservation` on the same
    revision; duplicating them here would fragment the grounding across two
    surfaces.

    S290: ``source_casilla_ids`` is NOT grounding and the rationale above does
    not extend to it. It is a subject IDENTITY -- which casilla(s), if any,
    this source object's resolution feeds -- and nothing else on the revision
    carries it for the general (non-row-materialized) case; dropping it here
    was an omission the application-side
    :class:`~cadrumo.application.aggregation.CalculationSourceProvenance` did
    not itself make (it already carries the field). An empty tuple is honest
    when the originating resolver call site did not associate this row with a
    casilla — it is not fabricated as a claim of "no subject", only carried as
    "not linked at resolution time".

    Attributes:
        resolver_id: Exact canonical resolver identity that produced this row.
        resolved_binding_source: Canonical binding source owned by the resolver.
        contributor_source_kind: Upstream taxonomy token for this source node.
        contributor_binding_source: Canonical :class:`BindingSourceKind` when
            ``contributor_source_kind`` belongs to the binding taxonomy; ``None``
            for an external or non-binding contributor.
        lineage_role: Whether this row is the resolver-owned primary or supporting contributor.
        source_ref: Stable reference to the contributing source object
            (e.g. ``collectible_invoice:{invoice_id}``).
        fingerprint: Data-dependent digest of the contributing source object when
            the resolver produced one; ``None`` when the resolver emits a
            reference without a content digest.
        source_casilla_ids: Casilla identities this source object's resolution
            feeds, when the originating resolver associated one; empty when it
            did not. Carried straight from
            :attr:`~cadrumo.application.aggregation.CalculationSourceProvenance.source_casilla_ids`.
        dependency_treatment: The registry's declared dependency treatment for
            this carry, empty when the revision declares none. Unlike
            ``legal_refs`` / ``source_refs`` this carries no grounding duplicated
            elsewhere on the revision — it is the sole persisted trace of whether
            a carry is a ``factual_evidence`` fact to reconcile against or a
            ``direct_annual_settlement`` figure that settles the return, and an
            audit reader has no other way to recover that distinction after the
            fact. Carried here rather than gated here: the value is NOT withheld
            on the basis of its treatment.
    """

    model_config = STRICT_FROZEN_CONFIG

    resolver_id: str = Field(min_length=1, max_length=128)
    resolved_binding_source: BindingSourceKind
    contributor_source_kind: str = Field(min_length=1, max_length=64)
    contributor_binding_source: BindingSourceKind | None
    lineage_role: CalculationSourceLineageRole
    source_ref: str = Field(min_length=1, max_length=256)
    parent_source_ref: str | None = Field(min_length=1, max_length=256)
    fingerprint: str | None = Field(default=None, min_length=1, max_length=256)
    source_casilla_ids: tuple[CasillaId, ...] = ()
    dependency_treatment: str = ""

    @model_validator(mode="after")
    def _require_coherent_lineage(self) -> CalculationSourceRef:
        try:
            contributor_kind = BindingSourceKind(self.contributor_source_kind)
        except ValueError:
            contributor_kind = None
        if self.contributor_binding_source is None:
            if contributor_kind is not None:
                raise ModeloValidationError(
                    "source provenance contributor_binding_source is required when contributor_source_kind "
                    "is a binding source kind",
                )
        elif contributor_kind is not self.contributor_binding_source:
            raise ModeloValidationError(
                "source provenance contributor_binding_source must equal contributor_source_kind",
            )
        if self.lineage_role is CalculationSourceLineageRole.PRIMARY:
            if self.parent_source_ref is not None:
                raise ModeloValidationError("primary source provenance cannot have a parent")
        elif self.parent_source_ref is None:
            raise ModeloValidationError("contributor source provenance requires a parent")
        return self


class CalculationSourceIssue(BaseModel):
    """One durable unresolved source condition found while calculating a revision.

    Resolver diagnostics are useful calculate-time operator feedback, but a
    filing-grade verification runs later against the persisted calculation
    revision.  This narrow envelope carries a source condition that reached no
    binding, without misrepresenting it as source provenance for a computed
    output.

    Two conditions qualify, and both must survive to the persisted revision
    because both describe a value absent from the filing.
    ``unrouted_observation`` is a row no binding consumes at all.
    ``unrouted_declarable_quantity`` is an independent quantity that consumed
    rows carry and no binding drawing that quantity reaches — the row-keyed
    screens are silent on it by construction, so a verify or export gate that
    saw only the row condition would read their silence as confirmation.
    """

    model_config = STRICT_FROZEN_CONFIG

    reason: Literal["unrouted_observation", "unrouted_declarable_quantity"]
    binding_source: BindingSourceKind
    message: str = Field(min_length=1, max_length=512)
    resolver_id: str | None = Field(default=None, min_length=1, max_length=128)
    source_ref: str | None = Field(default=None, min_length=1, max_length=256)


def _validate_revision_identity(revision: CalculationRevision, derived: CalculationRevisionId) -> None:
    if derived != revision.calculation_revision_id:
        raise ModeloValidationError(
            f"calculation_revision_id {revision.calculation_revision_id!r} does not match "
            f"the derived id {derived!r} for work_unit_id={revision.work_unit_id!r}",
        )


def _validate_annual_summary_handoff_target(revision: CalculationRevision) -> None:
    handoff = revision.m303_regimen_simplificado_annual_summary_handoff
    if handoff is None:
        return
    if handoff.target_calculation_revision_id != revision.calculation_revision_id:
        raise ModeloValidationError(
            "M303 simplified annual-summary handoff target calculation revision id must equal its containing revision",
        )
    missing_outputs = tuple(
        casilla_id
        for casilla_id in M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS
        if casilla_id not in revision.casilla_values
    )
    if missing_outputs:
        raise ModeloValidationError(
            "M303 simplified annual-summary handoff target revision is missing its "
            f"Modelo 390 outputs: {missing_outputs!r}",
        )
    mismatched_outputs = tuple(
        casilla_id
        for casilla_id in M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS
        if revision.casilla_values[casilla_id] != handoff.values[casilla_id]
    )
    if mismatched_outputs:
        raise ModeloValidationError(
            "M303 simplified annual-summary handoff values disagree with the target "
            f"Modelo 390 outputs: {mismatched_outputs!r}",
        )


def _validate_replay_channel_overlap(
    left_name: str,
    left_values: Mapping[str, object],
    right_name: str,
    right_values: Mapping[str, object],
) -> None:
    overlapping_ids = sorted(set(left_values).intersection(right_values))
    if overlapping_ids:
        raise ModeloValidationError(
            "calculation revision replay ids must be channel-unique; "
            f"ids appear in both {left_name} and {right_name}: {overlapping_ids!r}",
        )


def _validate_replay_channels(revision: CalculationRevision) -> None:
    _validate_replay_channel_overlap(
        "binding_overrides",
        revision.binding_overrides,
        "relation_overrides",
        revision.relation_overrides,
    )
    _validate_replay_channel_overlap(
        "binding_overrides",
        revision.binding_overrides,
        "row_binding_values",
        revision.row_binding_values,
    )
    _validate_replay_channel_overlap(
        "row_binding_values",
        revision.row_binding_values,
        "relation_overrides",
        revision.relation_overrides,
    )


def _validate_observation_projection(revision: CalculationRevision) -> None:
    if revision.casilla_values and not revision.observations:
        raise ModeloValidationError(
            "calculation revision with casilla_values must carry typed observations; "
            "pass CasillaObservation rows as the canonical source so legal_refs, "
            "source_refs, and formula provenance survive the domain boundary.",
        )
    if revision.observations:
        projected = _outputs_for_hash_from_observations(revision.observations)
        persisted = _outputs_for_hash_from_mapping(revision.casilla_values)
        if projected != persisted:
            raise ModeloValidationError(
                "casilla_values is inconsistent with the typed observations envelope: "
                f"observations project to {projected!r} but casilla_values is {persisted!r}. "
                "Both fields must encode the same per-casilla outputs; pass observations "
                "as the canonical source and let casilla_values mirror its projection.",
            )


def _require_revision_fields(
    revision: CalculationRevision,
    names: tuple[str, ...],
    *,
    present: bool,
) -> None:
    for name in names:
        value_is_present = getattr(revision, name) is not None
        if value_is_present is present:
            continue
        requirement = "carry" if present else "not carry"
        raise ModeloValidationError(
            f"calculation revision in state {revision.state.value!r} must {requirement} {name!r}",
        )


def _validate_state_metadata(revision: CalculationRevision) -> None:
    if revision.state is CalculationRevisionState.BORRADOR:
        _require_revision_fields(
            revision,
            (
                "verified_at",
                "verified_by",
                "filed_at",
                "filed_by",
                "superseded_at",
                "discarded_at",
                "discarded_by",
                "discard_reason",
            ),
            present=False,
        )
    elif revision.state is CalculationRevisionState.VERIFICADO_COMPLETO:
        _require_revision_fields(revision, ("verified_at", "verified_by"), present=True)
        _require_revision_fields(
            revision,
            (
                "filed_at",
                "filed_by",
                "superseded_at",
                "discarded_at",
                "discarded_by",
                "discard_reason",
            ),
            present=False,
        )
    elif revision.state is CalculationRevisionState.PRESENTADO:
        _require_revision_fields(revision, ("verified_at", "verified_by", "filed_at", "filed_by"), present=True)
        _require_revision_fields(
            revision,
            ("superseded_at", "discarded_at", "discarded_by", "discard_reason"),
            present=False,
        )
    elif revision.state is CalculationRevisionState.PRESENTADO_SUPERSEDIDO:
        _require_revision_fields(
            revision,
            ("verified_at", "verified_by", "filed_at", "filed_by", "superseded_at"),
            present=True,
        )
        _require_revision_fields(
            revision,
            ("discarded_at", "discarded_by", "discard_reason"),
            present=False,
        )
    elif revision.state is CalculationRevisionState.DESCARTADO:
        _require_revision_fields(revision, ("discarded_at", "discarded_by"), present=True)
        _require_revision_fields(
            revision,
            ("verified_at", "verified_by", "filed_at", "filed_by", "superseded_at"),
            present=False,
        )


def _validate_amendment_metadata(revision: CalculationRevision) -> None:
    if (revision.amendment_identity is None) != (revision.amendment_reason is None):
        raise ModeloValidationError(
            "amendment_identity and amendment_reason must be set together or both be None",
        )


class CalculationRevision(BaseModel):
    """One calculation attempt attached to a work unit.

    Attributes:
        calculation_revision_id: Lowercase 64-char SHA-256 derived
            from the parent work_unit_id plus the inputs, overrides,
            and casilla outputs. Content-addressed: structurally
            identical re-runs produce the same id.
        work_unit_id: Parent work unit id (also content-addressed).
        state: Lifecycle state from
            :class:`CalculationRevisionState`.
        input_values_by_casilla_id: Mapping of canonical input casilla values
            captured at calculation time. The string values are
            decimal strings or short literals from the registry
            input contract.
        binding_overrides: Mapping of operator-supplied binding
            overrides applied during this calculation. Empty when
            no binding overrides were used.
        row_binding_values: Mapping of row-indexed binding values produced by
            source meshes for repeating export records. Kept separate from
            ``binding_overrides`` so the row coordinate remains structured.
        row_source_identities: Opaque source identities and content fingerprints
            keyed by the exact binding and row coordinate. Registry row-set
            identities additionally retain their exact selector grouping.
        relation_overrides: Mapping of relation values applied during
            this calculation. Kept separate from ``binding_overrides`` so
            BindingId-keyed snapshots never carry RelationId keys.
        source_transaction_ids: Stable ledger transaction ids that
            contributed to this revision through bucket-local
            aggregation. Empty for calculations that did not consume
            ledger transactions.
        m210_official_tipo_renta_code: The raw, official two-digit M210
            tipo-de-renta code selected for this revision's ledger projection.
            It remains distinct from the conceptual ``tipo_renta`` token used
            by the formula rate path, so an audit can distinguish official
            codes that share one rate concept.
        cleared_casilla_ids: Casillas the caller explicitly withdrew a
            previously declared MANUAL value from. Structurally distinct
            from a casilla that was simply never supplied, even though
            both are absent from ``input_values_by_casilla_id``.
        casilla_values: Mapping of computed casilla values (decimal
            output). The values that would be exported to AEAT if
            this revision were filed.
        created_at: UTC timestamp of revision creation.
        updated_at: UTC timestamp of the most recent state transition.
            Equals ``created_at`` on a fresh draft.
        verified_at: UTC timestamp at which the revision transitioned
            to ``VERIFICADO_COMPLETO``. ``None`` for non-verified
            revisions.
        verified_by: Actor label captured at verification time.
            ``None`` for non-verified revisions.
        filed_at: UTC timestamp at which the revision was filed.
            ``None`` for non-filed revisions.
        filed_by: Actor label captured at filing time. ``None``
            for non-filed revisions.
        superseded_at: UTC timestamp at which a later filed revision
            superseded this one. ``None`` unless ``state is
            PRESENTADO_SUPERSEDIDO``.
        discarded_at: UTC timestamp captured when the revision is moved
            to ``DESCARTADO``. ``None`` otherwise.
        discarded_by: Actor label captured when the revision is moved to
            ``DESCARTADO``. ``None`` otherwise.
        discard_reason: Audit reason captured when the revision is moved
            to ``DESCARTADO``. ``None`` otherwise.
    """

    model_config = STRICT_FROZEN_CONFIG

    calculation_revision_id: CalculationRevisionId
    work_unit_id: WorkUnitId
    state: CalculationRevisionState
    input_values_by_casilla_id: Mapping[CasillaId, str] = Field(default_factory=dict)
    binding_overrides: Mapping[BindingId, str] = Field(default_factory=dict)
    row_binding_values: Mapping[BindingId, Mapping[str, str]] = Field(default_factory=dict)
    row_source_identities: Mapping[RowBindingKey, RowSourceIdentity] = Field(
        default_factory=_empty_row_source_identities,
        repr=False,
    )
    row_casilla_values: Mapping[RowCasillaKey, Decimal] = Field(default_factory=_empty_row_casilla_values, repr=False)
    row_casilla_provenance: Mapping[RowCasillaKey, DirectRowMaterializationProvenance] = Field(
        default_factory=_empty_row_casilla_provenance,
        repr=False,
    )
    relation_overrides: Mapping[RelationId, str] = Field(default_factory=dict)
    source_transaction_ids: tuple[CalculationRevisionId, ...] = Field(default_factory=tuple)
    m210_official_tipo_renta_code: str | None = Field(default=None, min_length=2, max_length=2)
    m210_gross_income_source_mode: M210GrossIncomeSourceMode | None = None
    borrador_snapshot_id: SnapshotId | None = None
    bindings_sourced_from_borrador: tuple[BindingId, ...] = Field(default_factory=tuple)
    # Casillas the caller explicitly withdrew a previously declared MANUAL value
    # from. Kept as its own identity axis, separate from
    # ``input_values_by_casilla_id``, so an explicit clear is structurally
    # distinguishable from a casilla that was simply never supplied: both are
    # absent from ``input_values_by_casilla_id``, but only the cleared one
    # appears here.
    cleared_casilla_ids: tuple[CasillaId, ...] = Field(default_factory=tuple)
    casilla_values: Mapping[CasillaId, Decimal] = Field(default_factory=dict)
    # Typed envelope carrying formula provenance for every computed
    # casilla. Revisions with output values must populate this from the
    # engine's typed entries so operand_refs, operand_values, legal_refs,
    # and source_refs survive the domain boundary.
    observations: tuple[CasillaObservation, ...] = Field(default_factory=tuple)
    # Typed unresolved-outcome envelope carrying the casillas the engine could
    # NOT resolve to a Decimal value (an unresolvable IRNR rate omits its
    # casilla rather than emitting an in-band sentinel magnitude). Populated
    # from the engine result's ``unresolved_outcomes`` so the verification layer
    # can convert each into a BLOCKING finding post-persistence. Rides beside
    # ``observations`` and, like it, is deliberately NOT threaded into
    # ``derive_calculation_revision_id`` (it is derived from the same inputs, not
    # an independent identity axis).
    unresolved_outcomes: tuple[RegistryCalculationUnresolvedOutcome, ...] = Field(default_factory=tuple)
    # Immutable content-addressed snapshot of the ledger state this revision was
    # computed from. Captured at
    # verify/file time over ``source_transaction_ids``; ``None`` for unsnapshotted
    # revisions and for borradores not yet snapshotted. Deliberately NOT threaded
    # into ``derive_calculation_revision_id`` so the content-addressed id is
    # unaffected. A non-ledger modelo carries an empty-but-valid snapshot.
    ledger_filing_snapshot: LedgerFilingSnapshot | None = None
    # Bundled fact basis behind a ledger-derived revision: the typed
    # contributing-row evidence projections plus operator manual
    # fact-basis entries, pegged to the
    # snapshot's ``snapshot_fingerprint``. Where ``ledger_filing_snapshot`` proves
    # *whether* the ledger drifted, this carries *what the ledger said* so the
    # fact basis can be reconstituted and exported as filing evidence. Captured at
    # verify/file time; ``None`` for revisions without ledger evidence. Deliberately
    # NOT threaded into ``derive_calculation_revision_id``.
    ledger_filing_evidence: LedgerFilingEvidence | None = None
    # Complete filing-instance facts are selected before calculation and take
    # part in the content-addressed revision identity. They are never authored
    # or replaced on an existing BORRADOR. Stated explicitly at every
    # construction site, so "no filing facts" is a decision on the record rather
    # than a field nobody supplied.
    filing_instance_evidence: FilingInstanceEvidence | None
    # The one immutable 303 4T -> 390 0A simplified-regime handoff.  It is a
    # calculation input rather than an observation or filing projection, and
    # participates in the revision id through its target-id-free payload.  The
    # persisted carrier is stamped only after that id has been derived.
    m303_regimen_simplificado_annual_summary_handoff: M303RegimenSimplificadoAnnualSummaryHandoff | None = None
    # Resolver-level source-mesh provenance: the typed
    # resolver→source-object→fingerprint trace projected
    # from the mesh resolution's ``CalculationSourceProvenance`` rows at persist
    # time. Where ``observations`` carry the per-casilla legal/source grounding,
    # this carries WHICH resolver mesh and WHICH upstream source objects produced
    # the revision, and their content fingerprints, so an audit can trace source
    # connectivity and detect upstream drift. The complete canonical trace is an
    # immutable identity axis in ``derive_calculation_revision_id`` so rival source
    # facts cannot collide under first-write-wins catalogue persistence.
    source_provenance: tuple[CalculationSourceRef, ...]
    # Durable source-resolution conditions that prevented an observation from
    # reaching any declared binding.  These are distinct from provenance: an
    # unrouted observation did not produce a calculated output and therefore
    # must not be recorded as its source.  Verification consumes the typed
    # issue later, after calculation diagnostics have left the CLI surface.
    # It participates in the content-addressed identity because its presence
    # blocks verification.
    source_issues: tuple[CalculationSourceIssue, ...] = Field(default_factory=tuple)
    # Operator-supplied detail rows for informational modelos whose
    # content is a list of repeating records rather than scalar casilla
    # values (M184 atribución members, M232 operaciones vinculadas,
    # M349 operadores intracomunitarios, M347 contrapartes).
    # Defaults to () so existing persisted revisions load without schema
    # migration. Included in the content-addressed revision id so
    # structurally identical re-runs with the same rows are idempotent.
    detail_rows: tuple[ModeloDetailRow, ...] = Field(default_factory=tuple)
    created_at: datetime
    updated_at: datetime
    verified_at: datetime | None = None
    verified_by: ModeloActorLabel | None = None
    filed_at: datetime | None = None
    filed_by: ModeloActorLabel | None = None
    superseded_at: datetime | None = None
    discarded_at: datetime | None = None
    discarded_by: ModeloActorLabel | None = None
    discard_reason: OperatorReason | None = None
    amendment_identity: CalculationRevisionAmendmentIdentity | None = None
    amendment_reason: OperatorReason | None = None

    @field_validator(
        "created_at",
        "updated_at",
        "verified_at",
        "filed_at",
        "superseded_at",
        "discarded_at",
    )
    @classmethod
    def _lifecycle_instants_are_utc(cls, value: datetime | None) -> datetime | None:
        """Reject naive and non-UTC lifecycle instants before persistence or ordering."""
        if value is None:
            return None
        return validate_utc_aware(value)

    @model_validator(mode="after")
    def _enforce_invariants(self, info: ValidationInfo) -> CalculationRevision:
        validation_context = _string_keyed_context(info.context)
        if (
            validation_context is not None
            and validation_context.get("secure_calculation_revision") is True
            and not {"row_source_identities", "row_casilla_values", "row_casilla_provenance"}.issubset(
                self.model_fields_set
            )
        ):
            raise ModeloValidationError("secure calculation revision is missing required row materialization fields")
        primary_refs = tuple(
            row.source_ref for row in self.source_provenance if row.lineage_role is CalculationSourceLineageRole.PRIMARY
        )
        if len(primary_refs) != len(set(primary_refs)):
            raise ModeloValidationError("source provenance primary reference is ambiguous")
        primary_ref_set = frozenset(primary_refs)
        if any(
            row.parent_source_ref not in primary_ref_set
            for row in self.source_provenance
            if row.lineage_role is CalculationSourceLineageRole.CONTRIBUTOR
        ):
            raise ModeloValidationError("source provenance contributor parent does not resolve to a primary")
        derived = derive_calculation_revision_id_from_revision(self)
        _validate_revision_identity(self, derived)
        _validate_annual_summary_handoff_target(self)
        _validate_replay_channels(self)
        row_value_keys = {
            (binding_id, int(row_index)) for binding_id, rows in self.row_binding_values.items() for row_index in rows
        }
        if not set(self.row_source_identities).issubset(row_value_keys):
            raise ModeloValidationError("row source identity coordinate has no row binding value")
        if set(self.row_casilla_values) != set(self.row_casilla_provenance):
            raise ModeloValidationError("row casilla values and provenance must have exactly matching coordinates")
        source_coordinates: set[RowBindingKey] = set()
        for key, provenance in self.row_casilla_provenance.items():
            if key[1] != provenance.source_row_index:
                raise ModeloValidationError("row casilla index must match its direct source row index")
            source_key = (provenance.source_binding_id, provenance.source_row_index)
            if source_key in source_coordinates:
                raise ModeloValidationError("one source row cannot materialize more than one row casilla")
            source_coordinates.add(source_key)
            source_identity = self.row_source_identities.get(source_key)
            if source_identity is None:
                raise ModeloValidationError("row casilla provenance source coordinate has no row source identity")
            if source_identity != provenance.source_identity:
                raise ModeloValidationError("row casilla provenance source identity does not match its source row")
            source_value = self.row_binding_values.get(provenance.source_binding_id, {}).get(
                str(provenance.source_row_index)
            )
            try:
                source_decimal = Decimal(source_value) if source_value is not None else None
            except Exception as exc:
                raise ModeloValidationError("row casilla provenance source value is not decimal") from exc
            if source_decimal != self.row_casilla_values[key]:
                raise ModeloValidationError("row casilla value does not match its source row value")
        _validate_observation_projection(self)
        if self.updated_at < self.created_at:
            raise ModeloValidationError(
                f"updated_at {self.updated_at.isoformat()} precedes created_at {self.created_at.isoformat()}",
            )
        _validate_state_metadata(self)
        _validate_amendment_metadata(self)
        if (
            self.amendment_identity is not None
            and self.amendment_identity.kind is CalculationRevisionAmendmentKind.RECTIFICATIVA
        ):
            from .calculation_revision_aggregate import (
                CALCULATION_REVISION_AGGREGATE_CONTEXT_KEY,
                CalculationRevisionAggregateContext,
                validate_calculation_revision_aggregate,
            )

            raw_context: object = None
            if isinstance(validation_context, Mapping):
                typed_context = TypeAdapter(dict[str, object]).validate_python(validation_context)
                raw_context = typed_context.get(CALCULATION_REVISION_AGGREGATE_CONTEXT_KEY)
            if not isinstance(raw_context, CalculationRevisionAggregateContext):
                raise ModeloValidationError(
                    "rectificativa calculation revision requires context-bound aggregate validation",
                )
            validate_calculation_revision_aggregate(self, context=raw_context)
        return self

    @field_validator("source_transaction_ids", mode="before")
    @classmethod
    def _freeze_source_transaction_ids(cls, value: object) -> tuple[str, ...]:
        if not isinstance(value, Sequence) or isinstance(value, str | bytes):
            raise ModeloValidationError("source_transaction_ids must be a sequence")
        normalized: list[str] = []
        for item in TypeAdapter(tuple[object, ...]).validate_python(value):
            if not isinstance(item, str):
                raise ModeloValidationError("source_transaction_ids must contain strings")
            normalized.append(item)
        return tuple(normalized)

    @field_validator("source_transaction_ids")
    @classmethod
    def _normalise_source_transaction_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(sorted(item.strip().lower() for item in value))
        if len(set(normalized)) != len(normalized):
            raise ModeloValidationError("source_transaction_ids must not contain duplicates")
        return normalized

    @field_validator("m210_official_tipo_renta_code")
    @classmethod
    def _validate_m210_official_tipo_renta_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        code = value.strip()
        if code not in M210_TIPO_RENTA_CODE_PROJECTION:
            raise ModeloValidationError(
                f"m210_official_tipo_renta_code must be a registry-projected Modelo 210 code, got {code!r}",
            )
        return code

    @field_validator("row_binding_values", mode="before")
    @classmethod
    def _normalise_row_binding_values(cls, value: object) -> Mapping[BindingId, Mapping[str, str]]:
        if value is None:
            empty: dict[BindingId, Mapping[str, str]] = {}
            return empty
        if not isinstance(value, Mapping):
            raise ModeloValidationError("row_binding_values must be a binding -> row-index mapping")
        raw_mapping = TypeAdapter(dict[object, object]).validate_python(value)
        return _canonical_row_binding_values(
            raw_mapping,
            surface="row_binding_values",
        )

    @field_validator("row_source_identities", mode="before")
    @classmethod
    def _normalise_row_source_identities(
        cls, value: object, info: ValidationInfo
    ) -> Mapping[RowBindingKey, RowSourceIdentity]:
        # Secure persistence has one canonical, duplicate-detectable list form.
        # Ordinary in-process construction retains the ergonomic mapping form.
        validation_context = _string_keyed_context(info.context)
        if (
            validation_context is not None
            and validation_context.get("secure_calculation_revision") is True
            and not isinstance(value, list)
        ):
            raise ModeloValidationError("secure row source identities must use list wire form")
        typed: dict[RowBindingKey, RowSourceIdentity]
        if isinstance(value, Mapping):
            typed = TypeAdapter(dict[RowBindingKey, RowSourceIdentity]).validate_python(value)
        elif isinstance(value, (list, tuple)):
            typed = {}
            for raw in TypeAdapter(tuple[dict[str, object], ...]).validate_python(value):
                key = (raw.get("binding_id"), raw.get("row_index"))
                identity = RowSourceIdentity.model_validate(
                    {
                        "source_kind": raw.get("source_kind"),
                        "source_row_identity": raw.get("source_row_identity"),
                        "fingerprint": raw.get("fingerprint"),
                        "row_set_grouping": raw.get("row_set_grouping"),
                    },
                )
                parsed_key = TypeAdapter(tuple[BindingId, int]).validate_python(key)
                if parsed_key in typed:
                    raise ModeloValidationError("row source identities contain a duplicate coordinate")
                typed[parsed_key] = identity
        else:
            raise ModeloValidationError("row source identities must be a coordinate mapping")
        if any(row_index < 1 for _binding_id, row_index in typed):
            raise ModeloValidationError("row source identity contains a non-positive row index")
        return dict(sorted(typed.items()))

    @field_validator("row_casilla_values", mode="before")
    @classmethod
    def _normalise_row_casilla_values(cls, value: object, info: ValidationInfo) -> Mapping[RowCasillaKey, Decimal]:
        validation_context = _string_keyed_context(info.context)
        if (
            validation_context is not None
            and validation_context.get("secure_calculation_revision") is True
            and not isinstance(value, list)
        ):
            raise ModeloValidationError("secure row casilla values must use list wire form")
        typed: dict[RowCasillaKey, Decimal]
        if isinstance(value, Mapping):
            typed = TypeAdapter(dict[RowCasillaKey, Decimal]).validate_python(value)
        elif isinstance(value, list):
            typed = {}
            for raw in TypeAdapter(tuple[dict[str, object], ...]).validate_python(value):
                key = TypeAdapter(tuple[CasillaId, int]).validate_python((raw.get("casilla_id"), raw.get("row_index")))
                if key in typed:
                    raise ModeloValidationError("row casilla values contain a duplicate coordinate")
                typed[key] = TypeAdapter(Decimal).validate_python(raw.get("value"))
        else:
            raise ModeloValidationError("row casilla values must be a coordinate mapping")
        if any(row_index < 1 for _casilla_id, row_index in typed):
            raise ModeloValidationError("row casilla value contains a non-positive row index")
        return dict(sorted(typed.items()))

    @field_validator("row_casilla_provenance", mode="before")
    @classmethod
    def _normalise_row_casilla_provenance(
        cls, value: object, info: ValidationInfo
    ) -> Mapping[RowCasillaKey, DirectRowMaterializationProvenance]:
        validation_context = _string_keyed_context(info.context)
        if (
            validation_context is not None
            and validation_context.get("secure_calculation_revision") is True
            and not isinstance(value, list)
        ):
            raise ModeloValidationError("secure row casilla provenance must use list wire form")
        typed: dict[RowCasillaKey, DirectRowMaterializationProvenance]
        if isinstance(value, Mapping):
            typed = TypeAdapter(dict[RowCasillaKey, DirectRowMaterializationProvenance]).validate_python(value)
        elif isinstance(value, list):
            typed = {}
            for raw in TypeAdapter(tuple[dict[str, object], ...]).validate_python(value):
                key = TypeAdapter(tuple[CasillaId, int]).validate_python((raw.get("casilla_id"), raw.get("row_index")))
                if key in typed:
                    raise ModeloValidationError("row casilla provenance contains a duplicate coordinate")
                typed[key] = DirectRowMaterializationProvenance.model_validate(
                    {
                        "source_binding_id": raw.get("source_binding_id"),
                        "source_row_index": raw.get("source_row_index"),
                        "source_identity": raw.get("source_identity"),
                        "materialization_rule_id": raw.get("materialization_rule_id"),
                        "materialization_rule_version": raw.get("materialization_rule_version"),
                    }
                )
        else:
            raise ModeloValidationError("row casilla provenance must be a coordinate mapping")
        if any(row_index < 1 for _casilla_id, row_index in typed):
            raise ModeloValidationError("row casilla provenance contains a non-positive row index")
        return dict(sorted(typed.items()))

    @model_serializer(mode="wrap")
    def _redact_or_persist_row_materialization(
        self,
        handler: SerializerFunctionWrapHandler,
        info: SerializationInfo,
    ) -> object:
        handled = handler(self)
        if not isinstance(handled, dict):
            return handled
        payload = TypeAdapter(dict[str, object]).validate_python(handled)
        context = _string_keyed_context(getattr(info, "context", None))
        if context is None or context.get("secure_calculation_revision") is not True:
            payload.pop("row_source_identities", None)
            payload.pop("row_casilla_values", None)
            payload.pop("row_casilla_provenance", None)
            return payload
        payload["row_source_identities"] = _canonical_row_source_identities(self.row_source_identities)
        payload["row_casilla_values"] = _canonical_row_casilla_values(self.row_casilla_values)
        payload["row_casilla_provenance"] = _canonical_row_casilla_provenance(self.row_casilla_provenance)
        return payload


def calculation_revision_identity_inputs_from_revision(
    revision: CalculationRevision,
) -> CalculationRevisionIdentityInputs:
    """Project one persisted :class:`~CalculationRevision` through the sole hash-input builder.

    Read-side integrity checks and the model's own invariant both use this
    function.  It prevents those consumers from independently enumerating the
    identity fields and thereby omitting a newly added calculation input.
    """
    return calculation_revision_identity_inputs(
        work_unit_id=revision.work_unit_id,
        input_values_by_casilla_id=revision.input_values_by_casilla_id,
        binding_overrides=revision.binding_overrides,
        row_binding_values=revision.row_binding_values,
        row_source_identities=revision.row_source_identities,
        row_casilla_values=revision.row_casilla_values,
        row_casilla_provenance=revision.row_casilla_provenance,
        relation_overrides=revision.relation_overrides,
        casilla_values=revision.casilla_values,
        source_transaction_ids=revision.source_transaction_ids,
        m210_official_tipo_renta_code=revision.m210_official_tipo_renta_code,
        m210_gross_income_source_mode=revision.m210_gross_income_source_mode,
        borrador_snapshot_id=revision.borrador_snapshot_id,
        bindings_sourced_from_borrador=revision.bindings_sourced_from_borrador,
        detail_rows=revision.detail_rows,
        source_issues=revision.source_issues,
        source_provenance=revision.source_provenance,
        filing_instance_evidence=revision.filing_instance_evidence,
        m303_regimen_simplificado_annual_summary_handoff=(revision.m303_regimen_simplificado_annual_summary_handoff),
        amendment_identity=revision.amendment_identity,
        cleared_casilla_ids=revision.cleared_casilla_ids,
    )


def derive_calculation_revision_id_from_revision(revision: CalculationRevision) -> str:
    """Derive a :class:`~CalculationRevision` id from its complete canonical input set."""
    return _derive_calculation_revision_id_from_identity_inputs(
        calculation_revision_identity_inputs_from_revision(revision),
    )


class CalculationRevisionCatalogue(BaseModel):
    """Immutable catalogue of every calculation revision in storage."""

    model_config = STRICT_FROZEN_CONFIG

    revisions: Mapping[str, CalculationRevision] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _enforce_keys_match(self) -> CalculationRevisionCatalogue:
        for key, revision in self.revisions.items():
            if key != revision.calculation_revision_id:
                raise ModeloValidationError(
                    f"catalogue key {key!r} does not match "
                    f"calculation_revision_id {revision.calculation_revision_id!r}",
                )
        return self

    def get(self, calculation_revision_id: CalculationRevisionId) -> CalculationRevision | None:
        """Return the revision under this id, or ``None`` when the catalogue holds none.

        Returns:
            The :class:`CalculationRevision` for ``calculation_revision_id``,
            or ``None`` if the catalogue does not carry it.
        """
        return self.revisions.get(calculation_revision_id)

    def values(self):
        """Return a view of every revision in the catalogue.

        Returns:
            A view over the catalogue's :class:`CalculationRevision` records.
        """
        return self.revisions.values()

    def for_work_unit(self, work_unit_id: str) -> tuple[CalculationRevision, ...]:
        """Return every revision attached to one work unit.

        Returns:
            Tuple of :class:`CalculationRevision` records for the given work unit.
        """
        return tuple(rev for rev in self.revisions.values() if rev.work_unit_id == work_unit_id)

    @override
    def __iter__(self) -> Iterator[CalculationRevision]:  # pyright: ignore[reportIncompatibleMethodOverride]  # ty: ignore[invalid-method-override]  # pyrefly: ignore[bad-override]  # reason: intentional Pydantic catalogue iteration adapter; the established public API yields CalculationRevision records, not BaseModel field-value tuples
        return iter(self.revisions.values())

    def __len__(self) -> int:
        """Return how many revisions the catalogue holds."""
        return len(self.revisions)

    def __contains__(self, key: object) -> bool:
        """Report catalogue membership for a revision record or a bare revision id.

        Accepts either a :class:`CalculationRevision` or its id string so a
        caller holding only one of the two need not convert first; any other
        type is simply absent rather than an error.
        """
        if isinstance(key, CalculationRevision):
            return key.calculation_revision_id in self.revisions
        if isinstance(key, str):
            return key in self.revisions
        return False


class LedgerFilingCoverageError(ModeloError):
    """Raised when a persisted revision's snapshot and evidence contributor sets diverge.

    A ledger-derived revision bundles a ``ledger_filing_snapshot`` (the
    fingerprinted contributor set) and a ``ledger_filing_evidence`` (the typed
    fact basis). The two are projected from the same ``source_transaction_ids``
    and MUST cover the same contributors. A divergence on read-back means a
    contributor row was silently dropped after persistence; this gate surfaces it
    on load rather than letting the filing artefact ship an unexplainable casilla.
    """


def assert_revision_snapshot_evidence_coverage(revision: CalculationRevision) -> None:
    """Cross-check a loaded revision's snapshot and evidence contributor coverage.

    Args:
        revision: The :class:`CalculationRevision` loaded from persistence.

    Post-roundtrip validator (per the modelo-export-evidence-parity discipline):
    when both ``ledger_filing_snapshot`` and ``ledger_filing_evidence`` are
    present, their ``rows`` contributor (transaction_id) sets MUST be equal. A
    revision with neither (a non-ledger or borrador revision) passes trivially.
    Raises :class:`LedgerFilingCoverageError` naming the divergent contributors.
    """
    snapshot = revision.ledger_filing_snapshot
    evidence = revision.ledger_filing_evidence
    if snapshot is None or evidence is None:
        return
    snapshot_ids = {row.transaction_id for row in snapshot.rows}
    evidence_ids = {row.transaction_id for row in evidence.rows}
    if snapshot_ids != evidence_ids:
        missing = sorted(snapshot_ids - evidence_ids)
        extra = sorted(evidence_ids - snapshot_ids)
        raise LedgerFilingCoverageError(
            f"calculation revision {revision.calculation_revision_id!r} ledger evidence does not cover the "
            f"fingerprint snapshot: missing_from_evidence={missing} extra_in_evidence={extra}",
        )


__all__ = [
    "M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS",
    "CalculationRevision",
    "CalculationRevisionAmendmentIdentity",
    "CalculationRevisionAmendmentKind",
    "CalculationRevisionCatalogue",
    "CalculationRevisionState",
    "CalculationSourceRef",
    "FilingInstanceEvidence",
    "LedgerFilingCoverageError",
    "M303RegimenSimplificadoAnnualSummaryHandoff",
    "assert_revision_snapshot_evidence_coverage",
    "calculation_revision_identity_inputs",
    "calculation_revision_identity_inputs_from_revision",
    "derive_calculation_revision_id",
    "derive_calculation_revision_id_from_revision",
]
