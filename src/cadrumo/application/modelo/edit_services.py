"""Edit admission, schema projection, parsing, and preflight for the Modelo Edit Contract V1.

Behind :mod:`cadrumo.application.modelo`. This module owns the read-only half
of the edit contract: it independently re-resolves a target, projects the
registry-declared permitted surface, and rechecks a submission before
execution. It never writes -- persistence and the guarded compare-and-swap
commit belong to :mod:`._revision_persistence` and :mod:`._edit_execution`.

A :class:`~.workspace_models.ModeloWorkspaceBaselineV1` read-consistency token
is never accepted here as mutation authority: every coordinate below is
independently re-resolved from the target and the current catalogues, never
copied from a Workspace read.
"""

from __future__ import annotations

from datetime import timedelta

from ...core.decimal.coercion import normalize_decimal_separators
from ...core.decimal.grammar import european_thousands_reading_is_ambiguous, try_parse_canonical_decimal
from ...core.hashing import content_hash_hex
from ...core.parsing import parse_bool
from ...core.parsing.dates import parse_iso8601_date
from ...core.time.clock import now as clock_now
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.runtime_graph import revision_date_binding_ids
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.schema_input_kind import InputKind
from ...domain.calculations.registry.schema_surfaces import CalculationCompletenessManifest
from ...domain.filing.schema import ModeloScalar
from ...domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ...domain.modelos.row_models import ModeloDetailRow
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue
from ..operations.registry import OperationSchemaIdentityV1
from ._calculation_modelo_adjustments import DETAIL_ROW_OWNING_MODELO
from .calculation_source_policy import BUCKET_AGGREGATION_LOCK_SOURCES
from .edit_contract import ModeloEditCompatibilityTupleV1
from .edit_models import (
    ModeloEditAddressV1,
    ModeloEditAdmissionRequestV1,
    ModeloEditAdmissionResultV1,
    ModeloEditAdmittedV1,
    ModeloEditBaselineV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
    ModeloEditCompatibilityRefusalV1,
    ModeloEditDetailRowAddressV1,
    ModeloEditDetailRowIntentKind,
    ModeloEditDomainRefusalV1,
    ModeloEditExistingRowAddressV1,
    ModeloEditFindingV1,
    ModeloEditMutationResultReceiptV1,
    ModeloEditNonWritableBindingOverrideSurfaceEntryV1,
    ModeloEditNonWritableReason,
    ModeloEditNonWritableScalarSurfaceEntryV1,
    ModeloEditParsedValueV1,
    ModeloEditParseRequestV1,
    ModeloEditParseResultV1,
    ModeloEditPermittedSurfaceEntryV1,
    ModeloEditPreflightEvaluatedV1,
    ModeloEditPreflightRequestV1,
    ModeloEditPreflightResultV1,
    ModeloEditRefusalCode,
    ModeloEditRefusalV1,
    ModeloEditRefusedV1,
    ModeloEditRowAddressV1,
    ModeloEditRowIntentKind,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloEditSchemaIdentityV1,
    ModeloEditStaleBaselineRefusalV1,
    ModeloEditSubmissionV1,
    ModeloEditWritableBindingOverrideSurfaceEntryV1,
    ModeloEditWritableDetailRowSurfaceEntryV1,
    ModeloEditWritableRowGroupSurfaceEntryV1,
    ModeloEditWritableScalarSurfaceEntryV1,
)
from .work_addressing import (
    ModeloWorkAddressNotFoundError,
    ModeloWorkTarget,
    ModeloWorkUnitNotFoundError,
    law_selected_revision_for_work_target,
    resolve_modelo_work_address_unit,
    work_address_for_modelo_target,
)

_BASELINE_VALIDITY_WINDOW = timedelta(minutes=15)
RESPONSIBLE_OWNER = "modelo.edit"
"""The owner recorded on every refusal and advisory the modelo edit surface raises."""


def _target_absent_refusal() -> ModeloEditRefusalV1:
    return ModeloEditDomainRefusalV1(
        code=ModeloEditRefusalCode.TARGET_ABSENT,
        responsible_owner=RESPONSIBLE_OWNER,
        reconsideration_condition="resupply a target naming an existing, non-discarded work unit",
    )


def _writable_scalar_entries(revision: ModeloRevision) -> tuple[ModeloEditPermittedSurfaceEntryV1, ...]:
    """Classify every declared casilla by its registry-declared input kind."""
    entries: list[ModeloEditPermittedSurfaceEntryV1] = []
    for casilla in revision.casillas:
        if casilla.input_kind is InputKind.MANUAL:
            entries.append(
                ModeloEditWritableScalarSurfaceEntryV1(
                    casilla_id=casilla.id,
                    data_type=casilla.data_type,
                    allowed_intents=(
                        ModeloEditScalarIntentKind.SET_TYPED_VALUE,
                        ModeloEditScalarIntentKind.CLEAR_DECLARED_VALUE,
                    ),
                )
            )
        else:
            reason = (
                ModeloEditNonWritableReason.COMPUTED_BY_FORMULA
                if casilla.input_kind is InputKind.COMPUTED
                else ModeloEditNonWritableReason.SCHEMA_DECLARED_READ_ONLY
            )
            entries.append(ModeloEditNonWritableScalarSurfaceEntryV1(casilla_id=casilla.id, reason=reason))
    return tuple(entries)


def _writable_row_group_entries(revision: ModeloRevision) -> tuple[ModeloEditPermittedSurfaceEntryV1, ...]:
    """Return no entries: no registry-declared ``manual_input`` binding is a real row set.

    This projection formerly classified EVERY ``BindingSourceKind.MANUAL_INPUT``
    binding as a repeatable row group admitting ``ADD_ROW``/``UPDATE_ROW``/
    ``DELETE_ROW``, on the theory that ``manual_input`` was the taxpayer-typed
    row axis (donativo, invoice, withholding rows among them). A registry-wide
    audit found no such binding: every ``manual_input`` binding across every
    modelo declares ``aggregation = {op = "copy"}`` (a 1:1 scalar copy) and
    none carries a row index -- most, including every one of modelo 131's
    ninety-seven, are static fichero-BOE record-field positions (e.g. a fixed
    "actividad-2-epigrafe" slot), not a dynamic set a taxpayer can add to,
    remove from, or reorder. Admitting ``ADD_ROW``/``DELETE_ROW`` against a
    static field position would let an intent address a preprinted form slot
    under a fabricated row semantic.

    The genuine repeatable, taxpayer-typed row mechanism this codebase already
    has is the per-modelo ``ModeloDetailRow`` discriminated union (M184
    member, M232 vinculada, M349 operador/rectificación, M347 contraparte,
    M210 agrupación renta), threaded through the calculate boundary's
    ``detail_rows`` and already content-addressed on the revision. It is NOT
    ``BindingId``-keyed and does not fit this function's shape; projecting it
    into a permitted-surface entry is out-of-scope future work, deferred
    because which detail-row kind a given modelo may accept is not yet a
    queryable registry authority (it is implicit in which CLI subcommand the
    operator invokes).

    Returns an empty tuple unconditionally so the row-intent admission path
    (:func:`_validate_row_intent`) refuses every row intent as
    ``DISALLOWED_INTENT`` against every current baseline -- correct, not
    dormant, because no registry data today makes a different answer honest.
    """
    return ()


def _writable_binding_override_entries(revision: ModeloRevision) -> tuple[ModeloEditPermittedSurfaceEntryV1, ...]:
    """Classify every declared binding by its real ``--binding``-override eligibility.

    Corrects a category error: ``REMOVE_OVERRIDE`` was originally
    modelled as a casilla-addressed scalar intent, but the store it targets
    (``CalculationRevision.binding_overrides``) is keyed by ``BindingId``, and
    most eligible bindings -- a fichero-BOE record-field ``manual_input``
    binding, most notably -- have no casilla at all to address through.

    Eligibility is derived from the SAME real, already-tested gate the CLI's
    ``--binding KEY=VALUE`` override uses
    (``_reject_caller_overrides_of_source_bindings`` in
    ``_calculation_actions.py``): every declared binding whose source is NOT
    in :data:`BUCKET_AGGREGATION_LOCK_SOURCES` (the deterministic bucket-owned
    resolvers the caller may never override) is override-eligible, including
    ``manual_input``. A date-channel binding is excluded: the real CLI refuses
    ``--binding`` for a date-consumed binding and routes it through
    ``--casilla`` instead (:func:`_validated_binding_input_channel`), so this
    surface never admits one either.
    """
    date_channel_ids = revision_date_binding_ids(revision)
    entries: list[ModeloEditPermittedSurfaceEntryV1] = []
    for binding in revision.bindings:
        if binding.id in date_channel_ids:
            continue
        if binding.source in BUCKET_AGGREGATION_LOCK_SOURCES:
            entries.append(
                ModeloEditNonWritableBindingOverrideSurfaceEntryV1(
                    binding_id=binding.id,
                    reason=ModeloEditNonWritableReason.SCHEMA_DECLARED_READ_ONLY,
                )
            )
            continue
        entries.append(
            ModeloEditWritableBindingOverrideSurfaceEntryV1(
                binding_id=binding.id,
                allowed_intents=(
                    ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE,
                    ModeloEditBindingIntentKind.REMOVE_OVERRIDE,
                ),
            )
        )
    return tuple(entries)


def _writable_detail_row_entries(*, modelo: str) -> tuple[ModeloEditPermittedSurfaceEntryV1, ...]:
    """Classify every ``ModeloDetailRow`` kind this modelo owns as writable.

    Grounded in :data:`DETAIL_ROW_OWNING_MODELO`
    (`_calculation_modelo_adjustments.py`) -- the same real, enforced table
    :func:`~._calculation_modelo_adjustments.require_detail_rows_declared_for_their_owning_modelo`
    refuses a mismatched row against -- rather than a second, independently
    authored eligibility rule.
    """
    owned_kinds = sorted(
        {
            row_type.model_fields["row_type"].default
            for row_type, owner in DETAIL_ROW_OWNING_MODELO.items()
            if owner == modelo
        }
    )
    return tuple(
        ModeloEditWritableDetailRowSurfaceEntryV1(
            detail_row_kind=kind,
            allowed_intents=(
                ModeloEditDetailRowIntentKind.ADD_ROW,
                ModeloEditDetailRowIntentKind.UPDATE_ROW,
                ModeloEditDetailRowIntentKind.DELETE_ROW,
            ),
        )
        for kind in owned_kinds
    )


def _permitted_surface(revision: ModeloRevision, *, modelo: str) -> tuple[ModeloEditPermittedSurfaceEntryV1, ...]:
    return tuple(
        sorted(
            (
                *_writable_scalar_entries(revision),
                *_writable_row_group_entries(revision),
                *_writable_binding_override_entries(revision),
                *_writable_detail_row_entries(modelo=modelo),
            ),
            key=lambda entry: (
                entry.kind,
                getattr(entry, "casilla_id", getattr(entry, "binding_id", getattr(entry, "detail_row_kind", ""))),
            ),
        )
    )


def _completeness_manifest_digest(manifest: CalculationCompletenessManifest | None) -> str:
    if manifest is None:
        return content_hash_hex({"completeness_manifest": None})
    return content_hash_hex(manifest.model_dump(mode="json"))


def modelo_edit_request_schema_identity() -> OperationSchemaIdentityV1:
    """Return this consumer's own current identity for the edit submission schema.

    Computed directly from the model's JSON schema rather than through
    :meth:`OperationSchemaIdentityV1.from_model`, which additionally enforces
    the operations subsystem's own public-model-graph contract (e.g.
    ``validate_default=True``); the edit contract's models are governed by
    this ADR, not that one, so only the identity TYPE is reused here.
    """
    return OperationSchemaIdentityV1(
        schema_id="modelo.edit.submission",
        schema_version=1,
        schema_fingerprint=content_hash_hex(ModeloEditSubmissionV1.model_json_schema()),
    )


def modelo_edit_result_schema_identity() -> OperationSchemaIdentityV1:
    """Return this consumer's own current identity for the edit result-receipt schema.

    See :func:`modelo_edit_request_schema_identity` for why the fingerprint is
    computed directly rather than through ``from_model``.
    """
    return OperationSchemaIdentityV1(
        schema_id="modelo.edit.receipt",
        schema_version=1,
        schema_fingerprint=content_hash_hex(ModeloEditMutationResultReceiptV1.model_json_schema()),
    )


def _incompatible_axis(compatibility: ModeloEditCompatibilityTupleV1) -> str | None:
    """Return the name of the first stale compatibility axis, or ``None`` when current.

    Only the two axes this consumer owns and can independently recompute
    (its own submission and receipt schemas) are checked; the workspace,
    observation, REVIEW, refresh-target, and financial-operand axes are
    owned by other contracts and are carried through unchecked here.
    """
    if compatibility.request_schema != modelo_edit_request_schema_identity():
        return "request_schema"
    if compatibility.result_schema != modelo_edit_result_schema_identity():
        return "result_schema"
    return None


def admit_modelo_edit(
    request: ModeloEditAdmissionRequestV1,
    *,
    bucket_id: str,
    work_catalogue: WorkUnitCatalogue,
    calculation_catalogue: CalculationRevisionCatalogue,
    compatibility: ModeloEditCompatibilityTupleV1,
) -> ModeloEditAdmissionResultV1:
    """Independently re-resolve a target into an exact compare-and-swap baseline.

    Never treats a Workspace safe-read baseline as authority: the target's
    natural coordinates are the only carried-over input, and the work unit,
    registry revision, and permitted surface are all re-resolved here.

    Refuses ``unsupported_edit_compatibility`` before resolving any secure
    state (D1) when the caller's request/result schema identities do not
    match this consumer's own current schemas -- a stale compatibility tuple
    cached from before a contract schema changed.
    """
    incompatible = _incompatible_axis(compatibility)
    if incompatible is not None:
        return ModeloEditRefusedV1(
            refusal=ModeloEditCompatibilityRefusalV1(
                requested_axis=incompatible,
                responsible_owner=RESPONSIBLE_OWNER,
                reconsideration_condition="re-fetch the current compatibility tuple and resubmit",
            ),
        )
    domain_target: ModeloWorkTarget = request.target.target
    try:
        work_unit: WorkUnit = resolve_modelo_work_address_unit(
            work_address_for_modelo_target(domain_target),
            catalogue=work_catalogue,
            bucket_id=bucket_id,
        )
    except (ModeloWorkAddressNotFoundError, ModeloWorkUnitNotFoundError):
        return ModeloEditRefusedV1(refusal=_target_absent_refusal())

    law_selected_revision_id = law_selected_revision_for_work_target(
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        stored_revision_id=work_unit.revision_id,
    )
    snapshot = bundled_authority().snapshot(
        work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
        revision_id=law_selected_revision_id,
    )
    revision = snapshot.revision
    permitted_surface = _permitted_surface(revision, modelo=str(work_unit.modelo))
    permitted_surface_digest = content_hash_hex([entry.model_dump(mode="json") for entry in permitted_surface])
    schema_identity = ModeloEditSchemaIdentityV1(
        schema_id=f"modelo-{work_unit.modelo}-{revision.id}".lower(),
        schema_fingerprint=content_hash_hex(
            {"casillas": [c.id for c in revision.casillas], "bindings": [b.id for b in revision.bindings]}
        ),
        completeness_manifest_digest=_completeness_manifest_digest(revision.completeness_manifest),
    )
    issued_at = clock_now()
    coordinate_seed = {
        "bucket_id": bucket_id,
        "work_unit_id": work_unit.work_unit_id,
        "law_selected_revision_id": law_selected_revision_id,
        "schema_fingerprint": schema_identity.schema_fingerprint,
        "permitted_surface_digest": permitted_surface_digest,
        "mutation_family": request.mutation_family.value,
        "issued_at": issued_at.isoformat(),
    }
    baseline = ModeloEditBaselineV1(
        compatibility=compatibility,
        bucket_id=bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        work_unit_id=work_unit.work_unit_id,
        work_catalogue_revision=content_hash_hex(work_catalogue.model_dump(mode="json")),
        calculation_catalogue_revision=content_hash_hex(calculation_catalogue.model_dump(mode="json")),
        current_calculation_revision_id=work_unit.current_calculation_revision_id,
        law_selected_revision_id=law_selected_revision_id,
        schema_identity=schema_identity,
        schema_version=1,
        permitted_surface=permitted_surface,
        permitted_surface_digest=permitted_surface_digest,
        mutation_family=request.mutation_family,
        issued_at=issued_at,
        expires_at=issued_at + _BASELINE_VALIDITY_WINDOW,
        baseline_id=content_hash_hex(coordinate_seed),
    )
    return ModeloEditAdmittedV1(baseline=baseline)


def reconfirm_modelo_edit_baseline(
    baseline: ModeloEditBaselineV1,
    *,
    work_catalogue: WorkUnitCatalogue,
    calculation_catalogue: CalculationRevisionCatalogue,
) -> ModeloEditRefusalV1 | None:
    """Recheck every baseline coordinate against the current catalogues.

    Returns ``None`` when nothing has drifted, or the exact typed
    compare-and-swap refusal naming every coordinate that disagreed. Shared by
    preflight (D3) and, once execution lands, the guarded commit point (D6) so
    both recheck through one comparison.
    """
    mismatches: list[str] = []
    if content_hash_hex(work_catalogue.model_dump(mode="json")) != baseline.work_catalogue_revision:
        mismatches.append("work_catalogue_revision")
    if content_hash_hex(calculation_catalogue.model_dump(mode="json")) != baseline.calculation_catalogue_revision:
        mismatches.append("calculation_catalogue_revision")
    work_unit = work_catalogue.work_units.get(baseline.work_unit_id)
    if work_unit is None or work_unit.current_calculation_revision_id != baseline.current_calculation_revision_id:
        mismatches.append("current_calculation_revision_id")
    if clock_now() >= baseline.expires_at:
        mismatches.append("baseline_expiry")
    if not mismatches:
        return None
    return ModeloEditStaleBaselineRefusalV1(
        baseline_id=baseline.baseline_id,
        mismatching_coordinates=tuple(mismatches),
        responsible_owner=RESPONSIBLE_OWNER,
        reconsideration_condition="admit a fresh baseline and resubmit",
    )


def writable_scalar_entry(
    baseline: ModeloEditBaselineV1, casilla_id: str
) -> ModeloEditWritableScalarSurfaceEntryV1 | None:
    """Return the baseline's writable-scalar surface entry for ``casilla_id``, or ``None``."""
    for entry in baseline.permitted_surface:
        if isinstance(entry, ModeloEditWritableScalarSurfaceEntryV1) and entry.casilla_id == casilla_id:
            return entry
    return None


def _writable_row_group_entry(
    baseline: ModeloEditBaselineV1, binding_id: str
) -> ModeloEditWritableRowGroupSurfaceEntryV1 | None:
    for entry in baseline.permitted_surface:
        if isinstance(entry, ModeloEditWritableRowGroupSurfaceEntryV1) and entry.binding_id == binding_id:
            return entry
    return None


def _writable_binding_override_entry(
    baseline: ModeloEditBaselineV1, binding_id: str
) -> ModeloEditWritableBindingOverrideSurfaceEntryV1 | None:
    for entry in baseline.permitted_surface:
        if isinstance(entry, ModeloEditWritableBindingOverrideSurfaceEntryV1) and entry.binding_id == binding_id:
            return entry
    return None


def _writable_detail_row_entry(
    baseline: ModeloEditBaselineV1, detail_row_kind: str
) -> ModeloEditWritableDetailRowSurfaceEntryV1 | None:
    for entry in baseline.permitted_surface:
        if isinstance(entry, ModeloEditWritableDetailRowSurfaceEntryV1) and entry.detail_row_kind == detail_row_kind:
            return entry
    return None


DETAIL_ROW_NATURAL_KEY_SEPARATOR = "|"
"""The one separator a compound detail-row natural key is joined on.

Declared once because both the key derivation here and the operation wire
form that carries the key's components must agree on it exactly; two
literals would be free to drift into addressing different rows.
"""

_DETAIL_ROW_NATURAL_KEY_FIELDS: dict[str, tuple[str, ...]] = {
    "miembro": ("nif", "clave", "subclave"),
    "vinculada": ("nif",),
    "operador": ("nif_comunitario", "clave_operacion"),
    "rectificacion": ("nif_comunitario", "clave_operacion"),
    "contraparte": ("nif",),
    "agrupacion_renta": ("source_id",),
}


def detail_row_identity_components(row: ModeloDetailRow) -> tuple[str, ...]:
    """Return the row's declared identity fields, unjoined and in declared order.

    The components and the joined key are the SAME facts read from the same
    declaration, which is why they live together: a caller that needs the
    parts must never obtain them by splitting the key. Splitting cannot be
    made correct -- a component containing the separator is indistinguishable
    from a boundary once joined -- so the only safe direction is components
    first, key derived.
    """
    fields = _DETAIL_ROW_NATURAL_KEY_FIELDS[row.row_type]
    return tuple(str(getattr(row, field)) for field in fields)


def detail_row_natural_key(row: ModeloDetailRow) -> str:
    """Return the row's own already-declared business key, joined for compound keys.

    Never a minted or positional identity -- see :class:`ModeloEditDetailRowAddressV1`.
    """
    return DETAIL_ROW_NATURAL_KEY_SEPARATOR.join(detail_row_identity_components(row))


def _disallowed_intent_refusal(address: ModeloEditAddressV1) -> ModeloEditRefusalV1:
    return ModeloEditDomainRefusalV1(
        code=ModeloEditRefusalCode.DISALLOWED_INTENT,
        address=address,
        responsible_owner=RESPONSIBLE_OWNER,
        reconsideration_condition=(
            "address only a casilla, binding override, detail row, or row group the baseline's permitted surface admits"
        ),
    )


def _parse_scalar_lexeme(*, data_type: str, raw_lexeme: str) -> ModeloScalar:
    """Parse one raw lexeme per its registry-declared data type, or raise.

    Locale is accepted by the request contract but does not branch this
    grammar: both dot-decimal and comma-decimal spellings are accepted for
    every numeric data type, so a caller's declared locale changes no parsed
    value, per D3's "locale is an input grammar only" constraint.
    """
    text = raw_lexeme.strip()
    if not text:
        raise ValueError("empty lexeme")
    if data_type in {"decimal", "money", "ratio"}:
        if european_thousands_reading_is_ambiguous(text):
            raise ValueError("ambiguous thousands reading")
        candidate = normalize_decimal_separators(text, strip_thousands="." in text) if "," in text else text
        max_fraction_digits = 2 if data_type == "money" else None
        parsed = try_parse_canonical_decimal(candidate, max_fraction_digits=max_fraction_digits)
        if parsed is None:
            raise ValueError("does not conform to the canonical decimal grammar")
        return parsed
    if data_type in {"integer", "year"}:
        try:
            return int(text)
        except ValueError as error:
            raise ValueError("does not conform to the integer grammar") from error
    if data_type == "boolean":
        parsed_bool = parse_bool(text)
        if parsed_bool is None:
            raise ValueError("does not conform to the boolean grammar")
        return parsed_bool
    if data_type == "date":
        parsed_date = parse_iso8601_date(text)
        if parsed_date is None:
            raise ValueError("does not conform to the ISO date grammar")
        return parsed_date
    return text


def parse_modelo_edit_value(request: ModeloEditParseRequestV1) -> ModeloEditParseResultV1:
    """Parse one raw lexeme into its canonical typed value, never echoing it."""
    entry = writable_scalar_entry(request.baseline, request.address.casilla_id)
    if entry is None:
        return ModeloEditRefusedV1(refusal=_disallowed_intent_refusal(request.address))
    try:
        value = _parse_scalar_lexeme(data_type=entry.data_type, raw_lexeme=request.raw_lexeme)
    except ValueError:
        return ModeloEditRefusedV1(
            refusal=ModeloEditDomainRefusalV1(
                code=ModeloEditRefusalCode.PARSE_FAILED,
                address=request.address,
                responsible_owner=RESPONSIBLE_OWNER,
                reconsideration_condition="resupply a value conforming to the casilla's declared data type",
            )
        )
    return ModeloEditParsedValueV1(address=request.address, value=value)


def validate_scalar_intent(
    baseline: ModeloEditBaselineV1, address: ModeloEditScalarAddressV1, kind: ModeloEditScalarIntentKind
) -> ModeloEditRefusalV1 | None:
    """Return a refusal when ``kind`` is not a permitted intent for the addressed casilla, else ``None``."""
    entry = writable_scalar_entry(baseline, address.casilla_id)
    if entry is None or kind not in entry.allowed_intents:
        return _disallowed_intent_refusal(address)
    return None


def _validate_row_intent(
    baseline: ModeloEditBaselineV1, address: ModeloEditRowAddressV1, kind: ModeloEditRowIntentKind
) -> ModeloEditRefusalV1 | None:
    entry = _writable_row_group_entry(baseline, address.binding_id)
    if entry is None or kind not in entry.allowed_intents:
        return _disallowed_intent_refusal(address)
    if kind is ModeloEditRowIntentKind.UPDATE_ROW and not isinstance(address, ModeloEditExistingRowAddressV1):
        return _disallowed_intent_refusal(address)
    return None


def _validate_binding_intent(
    baseline: ModeloEditBaselineV1, address: ModeloEditBindingAddressV1, kind: ModeloEditBindingIntentKind
) -> ModeloEditRefusalV1 | None:
    entry = _writable_binding_override_entry(baseline, address.binding_id)
    if entry is None or kind not in entry.allowed_intents:
        return _disallowed_intent_refusal(address)
    return None


def _validate_detail_row_intent(
    baseline: ModeloEditBaselineV1, address: ModeloEditDetailRowAddressV1, kind: ModeloEditDetailRowIntentKind
) -> ModeloEditRefusalV1 | None:
    entry = _writable_detail_row_entry(baseline, address.detail_row_kind)
    if entry is None or kind not in entry.allowed_intents:
        return _disallowed_intent_refusal(address)
    return None


def preflight_modelo_edit(
    request: ModeloEditPreflightRequestV1,
    *,
    work_catalogue: WorkUnitCatalogue,
    calculation_catalogue: CalculationRevisionCatalogue,
) -> ModeloEditPreflightResultV1:
    """Recheck a submission's baseline and every intent's admitted address.

    A green result is review material, not authorization: execution
    independently repeats every concurrency and capability check at the
    guarded commit point.
    """
    submission: ModeloEditSubmissionV1 = request.submission
    baseline = submission.baseline
    stale = reconfirm_modelo_edit_baseline(
        baseline, work_catalogue=work_catalogue, calculation_catalogue=calculation_catalogue
    )
    if stale is not None:
        return ModeloEditRefusedV1(refusal=stale)

    findings: list[ModeloEditFindingV1] = []
    for intent in submission.scalar_intents:
        refusal = validate_scalar_intent(baseline, intent.address, intent.kind)
        if refusal is not None:
            return ModeloEditRefusedV1(refusal=refusal)
    for binding_intent in submission.binding_intents:
        refusal = _validate_binding_intent(baseline, binding_intent.address, binding_intent.kind)
        if refusal is not None:
            return ModeloEditRefusedV1(refusal=refusal)
    for row_intent in submission.row_intents:
        refusal = _validate_row_intent(baseline, row_intent.address, row_intent.kind)
        if refusal is not None:
            return ModeloEditRefusedV1(refusal=refusal)
    for detail_row_intent in submission.detail_row_intents:
        refusal = _validate_detail_row_intent(baseline, detail_row_intent.address, detail_row_intent.kind)
        if refusal is not None:
            return ModeloEditRefusedV1(refusal=refusal)
    return ModeloEditPreflightEvaluatedV1(baseline_id=baseline.baseline_id, findings=tuple(findings))


__all__ = [
    "admit_modelo_edit",
    "detail_row_identity_components",
    "detail_row_natural_key",
    "modelo_edit_request_schema_identity",
    "modelo_edit_result_schema_identity",
    "parse_modelo_edit_value",
    "preflight_modelo_edit",
    "reconfirm_modelo_edit_baseline",
    "validate_scalar_intent",
    "writable_scalar_entry",
]
