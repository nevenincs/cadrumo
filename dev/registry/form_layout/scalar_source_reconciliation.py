"""Reconcile explicitly correlated export inputs with existing scalar casillas."""

from collections.abc import Mapping
from typing import cast

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
    form = _validated_scalar_source_form(before, after, replacements)

    prior, current = before.model_dump(mode="json"), after.model_dump(mode="json")
    bindings = {str(binding.id): binding for binding in before.bindings}
    casillas = {str(casilla.id): casilla for casilla in before.casillas}
    seen: set[str] = set()
    _apply_scalar_replacements(prior, replacements, bindings, casillas, seen)
    if seen != set(replacements):
        raise RegistryValidationError("scalar source reconciliation refuses missing replacement fields")

    # Reverse references are derived by the loader, never an additional waiver
    # for changing calculation sources or other authored casilla properties.
    _remove_checked_reverse_references(before, prior)
    _remove_checked_reverse_references(after, current)
    if prior != current:
        raise RegistryValidationError(
            "scalar source reconciliation refuses changes outside explicit source replacements"
        )
    result = form.model_copy(update={"source_state_digest": form_layout_source_digest(after)})
    failures = form_layout_failures(after.model_copy(update={"form_layouts": (result,)}))
    if failures:
        raise RegistryValidationError("scalar source reconciliation failed: " + "; ".join(failures))
    return result


def _validated_scalar_source_form(
    before: ModeloRevision, after: ModeloRevision, replacements: Mapping[str, tuple[str, str]]
) -> FormLayoutDefinition:
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

    return form


def _remove_checked_reverse_references(revision: ModeloRevision, data: dict[str, object]) -> None:
    references = derive_casilla_export_refs(revision.export_layouts, revision.bindings)
    if set(references) - {casilla.id for casilla in revision.casillas} or any(
        tuple(casilla.export_refs) != tuple(references.get(casilla.id, ())) for casilla in revision.casillas
    ):
        raise RegistryValidationError("scalar source reconciliation refuses inconsistent reverse references")
    data["casillas"] = [casilla.model_dump(mode="json", exclude={"export_refs"}) for casilla in revision.casillas]


def _apply_scalar_replacements(
    prior: dict[str, object],
    replacements: Mapping[str, tuple[str, str]],
    bindings: Mapping[str, BindingDefinition],
    casillas: Mapping[str, CasillaDefinition],
    seen: set[str],
) -> None:
    for layout in cast("list[dict[str, object]]", prior["export_layouts"]):
        for record in cast("list[dict[str, object]]", layout["records"]):
            for field in cast("list[dict[str, object]]", record["fields"]):
                field_id = cast("str", field["id"])
                if field_id in replacements:
                    _apply_scalar_field(field, record, replacements[field_id], bindings, casillas, seen)


def _apply_scalar_field(
    field: dict[str, object],
    record: dict[str, object],
    replacement: tuple[str, str],
    bindings: Mapping[str, BindingDefinition],
    casillas: Mapping[str, CasillaDefinition],
    seen: set[str],
) -> None:
    field_id = cast("str", field["id"])
    binding_id, casilla_id = replacement
    binding, casilla = bindings.get(binding_id), casillas.get(casilla_id)
    if field["kind"] == "casilla":
        if (
            not _scalar_geometry_matches(field, record, field_id, seen)
            or field["casilla_id"] != binding_id
            or not _is_rate_box_source(casillas.get(binding_id), casilla, bindings)
            or casilla is None
            or field["data_type"] != casilla.data_type.value
        ):
            raise RegistryValidationError("scalar source reconciliation refuses an uncorrelated rate box")
        field["casilla_id"] = casilla_id
    else:
        if not _scalar_geometry_matches(field, record, field_id, seen) or not _manual_scalar_matches(
            field, binding_id, binding, casilla
        ):
            raise RegistryValidationError("scalar source reconciliation refuses an uncorrelated scalar source")
        field.update(kind="casilla", binding=None, casilla_id=casilla_id)
    seen.add(field_id)


def _scalar_geometry_matches(
    field: dict[str, object], record: dict[str, object], field_id: str, seen: set[str]
) -> bool:
    return (
        field_id not in seen
        and record["repeat"] is None
        and record["binding_record"] is None
        and not record["row_field_casilla_ids"]
        and field["offset"] is not None
        and field["length"] is not None
    )


def _manual_scalar_matches(
    field: dict[str, object],
    binding_id: str,
    binding: BindingDefinition | None,
    casilla: CasillaDefinition | None,
) -> bool:
    if field["kind"] != "binding" or field["binding"] != binding_id or binding is None or casilla is None:
        return False
    provider = binding.provider
    if not isinstance(provider, ManualInputProvider) or binding.aggregation is not None:
        return False
    return _manual_scalar_provider_matches(field, provider, casilla)


def _manual_scalar_provider_matches(
    field: dict[str, object], provider: ManualInputProvider, casilla: CasillaDefinition
) -> bool:
    return (
        field["data_type"] == casilla.data_type.value
        and provider.offset == field["offset"]
        and provider.length == field["length"]
        and provider.data_type == casilla.data_type
        and provider.decimals == field["decimals"]
        and provider.signed == field["signed"]
    )


def _rate_boxes_compatible(old: CasillaDefinition, new: CasillaDefinition) -> bool:
    return old.id != new.id and old.data_type == new.data_type and not new.export_refs


def _is_rate_box_source(
    old: CasillaDefinition | None,
    new: CasillaDefinition | None,
    bindings: Mapping[str, BindingDefinition],
) -> bool:
    """Require the same observed quantity, narrowed only by a stated rate.

    Official box correspondence belongs to the reviewed semantic map. This
    structural check cannot establish that correspondence from labels or values.
    """
    if old is None or new is None or not _rate_boxes_compatible(old, new):
        return False
    old_binding = bindings.get(str(old.binding))
    new_binding = bindings.get(str(new.binding))
    if old_binding is None or new_binding is None:
        return False
    return _rate_providers_compatible(old_binding, new_binding)


def _rate_providers_compatible(old_binding: BindingDefinition, new_binding: BindingDefinition) -> bool:
    old_provider, new_provider = old_binding.provider, new_binding.provider
    return bool(
        isinstance(old_provider, LedgerIvaProvider)
        and isinstance(new_provider, LedgerIvaProvider)
        and not (old_provider.applied_rates is not None and old_provider.applied_rates)
        and bool(new_provider.applied_rates)
        and old_binding.aggregation == new_binding.aggregation
        and old_binding.value == new_binding.value
        and old_provider.model_dump(exclude={"applied_rates"}) == new_provider.model_dump(exclude={"applied_rates"})
    )
