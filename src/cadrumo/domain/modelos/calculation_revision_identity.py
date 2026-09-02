"""Private canonicalization and hashing mechanics for calculation revisions.

The public construction and derivation functions remain canonical in
:mod:`cadrumo.domain.modelos.calculation_revision`. This module owns only the
private deterministic projections they use.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import TypeAdapter, ValidationError

from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.hashing import content_hash_hex
from ...core.irnr import M210_TIPO_RENTA_CODE_PROJECTION, M210GrossIncomeSourceMode
from ..calculations.registry.bindings import CasillaObservation
from ..calculations.registry.ids import BindingId, RelationId
from ..calculations.row_casilla import DirectRowMaterializationProvenance, RowCasillaKey
from ..calculations.row_source_identity import RowBindingKey, RowSourceIdentity
from ..identifiers import canonical_decimal_string as _canonical_decimal
from .calculation_revision_m303_handoff import FilingInstanceEvidence, M303RegimenSimplificadoAnnualSummaryHandoff
from .errors import ModeloValidationError
from .row_models import Modelo210AgrupacionRentaRow, Modelo349OperadorRow, Modelo349RectificacionRow, ModeloDetailRow

if TYPE_CHECKING:
    from .calculation_revision import CalculationRevisionIdentityInputs, CalculationSourceIssue, CalculationSourceRef

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
    the revision id â€” operators can supply rows in any order. The nif-like field
    varies by row type: nif (M184/M232/M347) or nif_comunitario (M349).

    Occurrence number established as presentation-only: every
    row-producer resolver these detail rows correspond to sorts by an
    equivalent content key before assigning fichero occurrence numbers, so
    two supply orders render identical bytes, not merely the same id here.
    See :class:`~cadrumo.application.modelo.edit_models.
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


def canonical_row_binding_values(
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


def canonical_row_source_identities(
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


def canonical_row_casilla_values(value: Mapping[RowCasillaKey, Decimal]) -> list[dict[str, object]]:
    return [
        {"casilla_id": casilla_id, "row_index": row_index, "value": _canonical_decimal(amount)}
        for (casilla_id, row_index), amount in sorted(value.items())
    ]


def canonical_row_casilla_provenance(
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
        "outputs": outputs_for_hash_from_mapping(casilla_values),
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


def derive_calculation_revision_id_from_identity_inputs(
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
    canonical_row_bindings = canonical_row_binding_values(
        raw_row_bindings,
        surface="row_binding_values",
    )
    if canonical_row_bindings:
        payload["row_binding_values"] = canonical_row_bindings
    canonical_row_identities = canonical_row_source_identities(row_source_identities)
    if canonical_row_identities:
        payload["row_source_identities"] = canonical_row_identities
    canonical_casilla_values = canonical_row_casilla_values(row_casilla_values)
    if canonical_casilla_values:
        payload["row_casilla_values"] = canonical_casilla_values
    canonical_casilla_provenance = canonical_row_casilla_provenance(row_casilla_provenance)
    if canonical_casilla_provenance:
        payload["row_casilla_provenance"] = canonical_casilla_provenance
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


def outputs_for_hash_from_mapping(casilla_values: Mapping[CasillaId, Decimal]) -> dict[CasillaId, str]:
    """Canonical ``{casilla_id: canonical_decimal_str}`` projection from the flat mapping.

    Pure function â€” same input â†’ same output, no side effects, no
    dependence on observation order. Used by
    :func:`derive_calculation_revision_id` to produce the ``outputs``
    payload key consumed by the SHA-256 hash, AND by
    :func:`outputs_for_hash_from_observations` to project the typed
    envelope into the same canonical form so the validator's
    consistency check is byte-exact.

    Validated ``casilla_id`` keys, ``_canonical_decimal`` values, sorted by
    casilla_id â€” matches the original inline projection in
    :func:`derive_calculation_revision_id` byte-for-byte. The
    A hash-stability contract guards this projection.
    """
    return dict(
        sorted(
            (_validated_casilla_id(k, surface="casilla_values"), _canonical_decimal(v))
            for k, v in casilla_values.items()
        ),
    )


def outputs_for_hash_from_observations(
    observations: Sequence[CasillaObservation],
) -> dict[CasillaId, str]:
    """Same canonical projection as :func:`outputs_for_hash_from_mapping`, sourced from observations.

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
    return outputs_for_hash_from_mapping(
        {obs.casilla_id: obs.value for obs in observations if isinstance(obs.value, Decimal)}
    )
