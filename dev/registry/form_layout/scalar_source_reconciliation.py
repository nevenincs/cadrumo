"""Reconcile explicitly correlated export inputs with existing scalar casillas."""

from collections.abc import Mapping

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_field_casilla import derive_casilla_export_refs
from cadrumo.domain.calculations.registry.ledger_iva_bindings import LedgerIvaProvider
from cadrumo.domain.calculations.registry.manual_input_selector import ManualInputProvider
from cadrumo.domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormLayoutDefinition,
    FormLayoutReviewState,
    FormLayoutSeedSource,
)
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from ..compiler.form_layout_integrity import form_layout_failures, form_layout_source_digest


def reconcile_scalar_export_sources(
    before: ModeloRevision,
    after: ModeloRevision,
    *,
    replacements: Mapping[str, tuple[str, str]],
) -> FormLayoutDefinition:
    """Admit named manual-input or blind-to-rate-box scalar source corrections.

    The caller must establish official same-box semantics and pin the mapping
    with the publication inputs. This function never infers equivalence from
    labels or amounts. It preserves the casilla's calculation and provenance,
    all record geometry and the draft presentation. Removing obsolete inputs
    or changing presentation is a separate authoring operation.
    """
    if not replacements or not before.export_layouts:
        raise RegistryValidationError("scalar source reconciliation requires explicit replacements and exports")
    if len(before.form_layouts) != 1 or before.form_layouts != after.form_layouts:
        raise RegistryValidationError("scalar source reconciliation requires one unchanged form")
    form = before.form_layouts[0]
    if (
        form.seed_source is not FormLayoutSeedSource.AUTHORED
        or form.review.state is not FormLayoutReviewState.GENERATED
    ):
        raise RegistryValidationError("scalar source reconciliation requires an unreviewed authored draft")
    if form_layout_failures(before):
        raise RegistryValidationError("scalar source reconciliation refuses a stale source form")

    prior, current = before.model_dump(mode="json"), after.model_dump(mode="json")
    bindings = {str(binding.id): binding for binding in before.bindings}
    casillas = {str(casilla.id): casilla for casilla in before.casillas}
    seen: set[str] = set()
    for layout in prior["export_layouts"]:
        for record in layout["records"]:
            for field in record["fields"]:
                field_id = field["id"]
                if field_id not in replacements:
                    continue
                binding_id, casilla_id = replacements[field_id]
                binding = bindings.get(binding_id)
                casilla = casillas.get(casilla_id)
                if field["kind"] == "casilla":
                    if (
                        field_id in seen
                        or record["repeat"] is not None
                        or record["binding_record"] is not None
                        or record["row_field_casilla_ids"]
                        or field["casilla_id"] != binding_id
                        or field["offset"] is None
                        or field["length"] is None
                        or not _is_rate_box_source(casillas.get(binding_id), casilla, bindings)
                        or casilla is None
                        or field["data_type"] != casilla.data_type.value
                    ):
                        raise RegistryValidationError("scalar source reconciliation refuses an uncorrelated rate box")
                    field["casilla_id"] = casilla_id
                    seen.add(field_id)
                    continue
                if (
                    field_id in seen
                    or record["repeat"] is not None
                    or record["binding_record"] is not None
                    or record["row_field_casilla_ids"]
                    or field["kind"] != "binding"
                    or field["binding"] != binding_id
                    or field["offset"] is None
                    or field["length"] is None
                    or binding is None
                    or not isinstance(binding.provider, ManualInputProvider)
                    or binding.aggregation is not None
                    or casilla is None
                    or field["data_type"] != casilla.data_type.value
                    or binding.provider.offset != field["offset"]
                    or binding.provider.length != field["length"]
                    or binding.provider.data_type != casilla.data_type
                    or binding.provider.decimals != field["decimals"]
                    or binding.provider.signed != field["signed"]
                ):
                    raise RegistryValidationError("scalar source reconciliation refuses an uncorrelated scalar source")
                field.update(kind="casilla", binding=None, casilla_id=casilla_id)
                seen.add(field_id)
    if seen != set(replacements):
        raise RegistryValidationError("scalar source reconciliation refuses missing replacement fields")

    # Reverse references are derived by the loader, never an additional waiver
    # for changing calculation sources or other authored casilla properties.
    for revision, data in ((before, prior), (after, current)):
        references = derive_casilla_export_refs(revision.export_layouts, revision.bindings)
        if set(references) - {casilla.id for casilla in revision.casillas} or any(
            tuple(casilla.export_refs) != tuple(references.get(casilla.id, ())) for casilla in revision.casillas
        ):
            raise RegistryValidationError("scalar source reconciliation refuses inconsistent reverse references")
        data["casillas"] = [casilla.model_dump(mode="json", exclude={"export_refs"}) for casilla in revision.casillas]
    if prior != current:
        raise RegistryValidationError(
            "scalar source reconciliation refuses changes outside explicit source replacements"
        )
    result = form.model_copy(update={"source_state_digest": form_layout_source_digest(after)})
    failures = form_layout_failures(after.model_copy(update={"form_layouts": (result,)}))
    if failures:
        raise RegistryValidationError("scalar source reconciliation failed: " + "; ".join(failures))
    return result


def _is_rate_box_source(
    old: CasillaDefinition | None,
    new: CasillaDefinition | None,
    bindings: Mapping[str, BindingDefinition],
) -> bool:
    """Require the same observed quantity, narrowed only by a stated rate.

    Official box correspondence belongs to the reviewed semantic map. This
    structural check cannot establish that correspondence from labels or values.
    """
    if old is None or new is None or old.id == new.id or old.data_type != new.data_type or new.export_refs:
        return False
    old_binding = bindings.get(str(old.binding))
    new_binding = bindings.get(str(new.binding))
    if old_binding is None or new_binding is None:
        return False
    old_provider, new_provider = old_binding.provider, new_binding.provider
    return bool(
        isinstance(old_provider, LedgerIvaProvider)
        and isinstance(new_provider, LedgerIvaProvider)
        and not old_provider.applied_rates
        and bool(new_provider.applied_rates)
        and old_binding.aggregation == new_binding.aggregation
        and old_binding.value == new_binding.value
        and old_provider.model_dump(exclude={"applied_rates"}) == new_provider.model_dump(exclude={"applied_rates"})
    )
