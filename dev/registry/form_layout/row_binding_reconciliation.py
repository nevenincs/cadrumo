"""Preserve authored drafts when fixed official fields gain repeated row sources."""

from collections.abc import Mapping
from typing import cast

from cadrumo.core.aggregation import BindingAggregationOp
from cadrumo.domain.calculations.registry.binding_aggregation import binding_aggregation_op
from cadrumo.domain.calculations.registry.binding_selector_utils import (
    BindingRowSetSelector,
    binding_row_set_selector,
    selector_as_dict,
)
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_field_casilla import derive_casilla_export_refs
from cadrumo.domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormLayoutDefinition,
    FormLayoutReviewState,
    FormLayoutSeedSource,
)

from ..compiler.form_layout_integrity import form_layout_failures, form_layout_source_digest


def reconcile_export_row_bindings(before: ModeloRevision, after: ModeloRevision) -> FormLayoutDefinition:
    """Admit only source-preserving scalar-to-row field changes, without moving bytes.

    Bindings and human presentation must already exist. Official record geometry
    remains authoritative: this cannot introduce binding-derived field positions.
    Full candidate validation remains the publication owner's responsibility.
    """
    form = _validated_row_form(before, after)
    prior, current = before.model_dump(mode="json"), after.model_dump(mode="json")
    bindings = {binding.id: binding for binding in before.bindings}
    changed = _reconcile_row_layouts(prior, current, bindings)
    if not changed or prior != current:
        raise RegistryValidationError("row binding reconciliation refuses unrelated source changes")
    _check_reverse_references(before)
    _check_reverse_references(after)
    result = form.model_copy(update={"source_state_digest": form_layout_source_digest(after)})
    failures = form_layout_failures(after.model_copy(update={"form_layouts": (result,)}))
    if failures:
        raise RegistryValidationError("row binding reconciliation failed: " + "; ".join(failures))
    return result


def _check_reverse_references(revision: ModeloRevision) -> None:
    refs = derive_casilla_export_refs(revision.export_layouts, revision.bindings)
    if set(refs) - {c.id for c in revision.casillas} or any(
        tuple(c.export_refs) != tuple(refs.get(c.id, ())) for c in revision.casillas
    ):
        raise RegistryValidationError("row binding reconciliation refuses inconsistent reverse references")


def _validated_row_form(before: ModeloRevision, after: ModeloRevision) -> FormLayoutDefinition:
    if not before.export_layouts or len(before.form_layouts) != 1 or before.form_layouts != after.form_layouts:
        raise RegistryValidationError("row binding reconciliation requires existing exports and one unchanged form")
    form = before.form_layouts[0]
    if (
        form.seed_source is not FormLayoutSeedSource.AUTHORED
        or form.review.state is not FormLayoutReviewState.GENERATED
    ):
        raise RegistryValidationError("row binding reconciliation requires an unreviewed authored draft")
    if form_layout_failures(before):
        raise RegistryValidationError("row binding reconciliation refuses a stale source form")
    return form


def _reconcile_row_layouts(
    prior: dict[str, object], current: dict[str, object], bindings: Mapping[str, BindingDefinition]
) -> int:
    old_layouts = cast("list[dict[str, object]]", prior["export_layouts"])
    new_layouts = cast("list[dict[str, object]]", current["export_layouts"])
    if len(old_layouts) != len(new_layouts):
        raise RegistryValidationError("row binding reconciliation refuses layout changes")
    changed = 0
    for old_layout, new_layout in zip(old_layouts, new_layouts, strict=True):
        old_records = cast("list[dict[str, object]]", old_layout["records"])
        new_records = cast("list[dict[str, object]]", new_layout["records"])
        if len(old_records) != len(new_records):
            raise RegistryValidationError("row binding reconciliation refuses record changes")
        for old_record, new_record in zip(old_records, new_records, strict=True):
            if old_record != new_record:
                _reconcile_row_record(old_record, new_record, bindings)
                changed += 1
    return changed


def _reconcile_row_record(
    old_record: dict[str, object], new_record: dict[str, object], bindings: Mapping[str, BindingDefinition]
) -> None:
    old_fields = cast("list[dict[str, object]]", old_record["fields"])
    new_fields = cast("list[dict[str, object]]", new_record["fields"])
    if not _singleton_record_matches(old_record, new_record) or len(old_fields) != len(new_fields):
        raise RegistryValidationError("row binding reconciliation requires an unmapped singleton record")
    mapping: dict[str, object] = {}
    groups: set[str] = set()
    for old_field, new_field in zip(old_fields, new_fields, strict=True):
        _reconcile_row_field(old_field, new_field, old_record, bindings, mapping, groups)
    if not mapping or len(groups) != 1 or mapping != new_record["row_field_casilla_ids"]:
        raise RegistryValidationError("row binding reconciliation requires one exact member mapping")
    old_record.update(repeat="binding_rows", row_field_casilla_ids=mapping)


def _singleton_record_matches(old_record: dict[str, object], new_record: dict[str, object]) -> bool:
    return (
        old_record["repeat"] is None
        and old_record["binding_record"] is None
        and not old_record["row_field_casilla_ids"]
        and new_record["repeat"] == "binding_rows"
        and new_record["binding_record"] is None
    )


def _reconcile_row_field(
    old_field: dict[str, object],
    new_field: dict[str, object],
    old_record: dict[str, object],
    bindings: Mapping[str, BindingDefinition],
    mapping: dict[str, object],
    groups: set[str],
) -> None:
    if old_field == new_field:
        if old_field["kind"] == "casilla":
            raise RegistryValidationError("row binding reconciliation refuses residual singleton casillas")
        return
    binding = bindings.get(cast("str", new_field["binding"]))
    selector = binding_row_set_selector(binding) if binding is not None else None
    if (
        binding is None
        or selector is None
        or not _row_source_matches(old_field, new_field, old_record, binding, selector, mapping)
    ):
        raise RegistryValidationError("row binding reconciliation refuses uncorrelated row sources")
    mapping[selector.row_field] = old_field["casilla_id"]
    groups.add(selector.grouping)
    old_field.update(kind="binding", binding=binding.id, casilla_id=None)
    if old_field != new_field:
        raise RegistryValidationError("row binding reconciliation refuses changed field geometry or policy")


def _row_source_matches(
    old_field: dict[str, object],
    new_field: dict[str, object],
    old_record: dict[str, object],
    binding: BindingDefinition | None,
    selector: BindingRowSetSelector | None,
    mapping: Mapping[str, object],
) -> bool:
    return not (
        old_field["kind"] != "casilla"
        or old_field["offset"] is None
        or old_field["length"] is None
        or new_field["kind"] != "binding"
        or binding is None
        or binding_aggregation_op(binding) != BindingAggregationOp.ROWS
        or selector is None
        or selector.record != old_record["record_type"]
        or selector.row_field in mapping
        or selector_as_dict(binding).get("target_casilla_id") != old_field["casilla_id"]
    )
