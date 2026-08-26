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

from datetime import UTC, date, datetime, timedelta

from ...core.decimal import (
    european_thousands_reading_is_ambiguous,
    normalize_decimal_separators,
    try_parse_canonical_decimal,
)
from ...core.hashing import content_hash_hex
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.schema import (
    CalculationCompletenessManifest,
    ModeloRevision,
)
from ...domain.calculations.registry.schema_input_kind import InputKind
from ...domain.filing import ModeloScalar
from ...domain.modelos import CalculationRevisionCatalogue, WorkUnit, WorkUnitCatalogue
from ._edit_models import (
    ModeloEditAddressV1,
    ModeloEditAdmissionRequestV1,
    ModeloEditAdmissionResultV1,
    ModeloEditAdmittedV1,
    ModeloEditBaselineV1,
    ModeloEditCompatibilityTupleV1,
    ModeloEditDomainRefusalV1,
    ModeloEditExistingRowAddressV1,
    ModeloEditFindingV1,
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
    ModeloEditStaleBaselineRefusalV1,
    ModeloEditSubmissionV1,
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
from .workspace_models import ModeloWorkspaceSchemaIdentityV1

_BASELINE_VALIDITY_WINDOW = timedelta(minutes=15)
_RESPONSIBLE_OWNER = "modelo.edit"

_MANUAL_INPUT_SOURCE = "manual_input"


def _target_absent_refusal() -> ModeloEditRefusalV1:
    return ModeloEditDomainRefusalV1(
        code=ModeloEditRefusalCode.TARGET_ABSENT,
        responsible_owner=_RESPONSIBLE_OWNER,
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
    """Surface exactly the taxpayer-entered repeated-row binding groups.

    ``BindingSourceKind.MANUAL_INPUT`` is the one registry-declared axis that
    distinguishes a row group the taxpayer types (donativo, invoice, and
    withholding rows among them) from a ledger- or profile-fed aggregation;
    every other binding source is out of scope for this row-group surface,
    not merely non-writable, so only manual-input bindings are listed.
    """
    entries: list[ModeloEditPermittedSurfaceEntryV1] = []
    for binding in revision.bindings:
        if binding.source.value != _MANUAL_INPUT_SOURCE:
            continue
        entries.append(
            ModeloEditWritableRowGroupSurfaceEntryV1(
                binding_id=binding.id,
                allowed_intents=(
                    ModeloEditRowIntentKind.ADD_ROW,
                    ModeloEditRowIntentKind.UPDATE_ROW,
                    ModeloEditRowIntentKind.DELETE_ROW,
                ),
                reorderable=False,
            )
        )
    return tuple(entries)


def _permitted_surface(revision: ModeloRevision) -> tuple[ModeloEditPermittedSurfaceEntryV1, ...]:
    return tuple(sorted(
        (*_writable_scalar_entries(revision), *_writable_row_group_entries(revision)),
        key=lambda entry: (entry.kind, getattr(entry, "casilla_id", getattr(entry, "binding_id", ""))),
    ))


def _field_manifest_digest(manifest: CalculationCompletenessManifest | None) -> str:
    if manifest is None:
        return content_hash_hex({"completeness_manifest": None})
    return content_hash_hex(manifest.model_dump(mode="json"))


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
    """
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
    permitted_surface = _permitted_surface(revision)
    permitted_surface_digest = content_hash_hex(
        [entry.model_dump(mode="json") for entry in permitted_surface]
    )
    schema_identity = ModeloWorkspaceSchemaIdentityV1(
        schema_id=f"modelo-{work_unit.modelo}-{revision.id}".lower(),
        schema_fingerprint=content_hash_hex(
            {"casillas": [c.id for c in revision.casillas], "bindings": [b.id for b in revision.bindings]}
        ),
        field_manifest_digest=_field_manifest_digest(revision.completeness_manifest),
    )
    issued_at = datetime.now(UTC)
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
    if datetime.now(UTC) >= baseline.expires_at:
        mismatches.append("baseline_expiry")
    if not mismatches:
        return None
    return ModeloEditStaleBaselineRefusalV1(
        baseline_id=baseline.baseline_id,
        mismatching_coordinates=tuple(mismatches),
        responsible_owner=_RESPONSIBLE_OWNER,
        reconsideration_condition="admit a fresh baseline and resubmit",
    )


def _writable_scalar_entry(
    baseline: ModeloEditBaselineV1, casilla_id: str
) -> ModeloEditWritableScalarSurfaceEntryV1 | None:
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


def _disallowed_intent_refusal(address: ModeloEditAddressV1) -> ModeloEditRefusalV1:
    return ModeloEditDomainRefusalV1(
        code=ModeloEditRefusalCode.DISALLOWED_INTENT,
        address=address,
        responsible_owner=_RESPONSIBLE_OWNER,
        reconsideration_condition="address only a casilla or row group the baseline's permitted surface admits",
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
        lowered = text.lower()
        if lowered in {"true", "1"}:
            return True
        if lowered in {"false", "0"}:
            return False
        raise ValueError("does not conform to the boolean grammar")
    if data_type == "date":
        try:
            return date.fromisoformat(text)
        except ValueError as error:
            raise ValueError("does not conform to the ISO date grammar") from error
    return text


def parse_modelo_edit_value(request: ModeloEditParseRequestV1) -> ModeloEditParseResultV1:
    """Parse one raw lexeme into its canonical typed value, never echoing it."""
    entry = _writable_scalar_entry(request.baseline, request.address.casilla_id)
    if entry is None:
        return ModeloEditRefusedV1(refusal=_disallowed_intent_refusal(request.address))
    try:
        value = _parse_scalar_lexeme(data_type=entry.data_type, raw_lexeme=request.raw_lexeme)
    except ValueError:
        return ModeloEditRefusedV1(
            refusal=ModeloEditDomainRefusalV1(
                code=ModeloEditRefusalCode.PARSE_FAILED,
                address=request.address,
                responsible_owner=_RESPONSIBLE_OWNER,
                reconsideration_condition="resupply a value conforming to the casilla's declared data type",
            )
        )
    return ModeloEditParsedValueV1(address=request.address, value=value)


def _validate_scalar_intent(
    baseline: ModeloEditBaselineV1, address: ModeloEditScalarAddressV1, kind: ModeloEditScalarIntentKind
) -> ModeloEditRefusalV1 | None:
    entry = _writable_scalar_entry(baseline, address.casilla_id)
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
        refusal = _validate_scalar_intent(baseline, intent.address, intent.kind)
        if refusal is not None:
            return ModeloEditRefusedV1(refusal=refusal)
    for row_intent in submission.row_intents:
        refusal = _validate_row_intent(baseline, row_intent.address, row_intent.kind)
        if refusal is not None:
            return ModeloEditRefusedV1(refusal=refusal)
    return ModeloEditPreflightEvaluatedV1(baseline_id=baseline.baseline_id, findings=tuple(findings))


__all__ = [
    "admit_modelo_edit",
    "parse_modelo_edit_value",
    "preflight_modelo_edit",
    "reconfirm_modelo_edit_baseline",
]
