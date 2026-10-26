"""Preserve authored drafts when fixed official fields gain repeated row sources."""

from cadrumo.core.aggregation import BindingAggregationOp
from cadrumo.domain.calculations.registry.binding_aggregation import binding_aggregation_op
from cadrumo.domain.calculations.registry.binding_selector_utils import binding_row_set_selector, selector_as_dict
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_field_casilla import derive_casilla_export_refs
from cadrumo.domain.calculations.registry.schema import ModeloRevision
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
    prior, current = before.model_dump(mode="json"), after.model_dump(mode="json")
    bindings = {binding.id: binding for binding in before.bindings}
    changed = 0
    if len(prior["export_layouts"]) != len(current["export_layouts"]):
        raise RegistryValidationError("row binding reconciliation refuses layout changes")
    for old_layout, new_layout in zip(prior["export_layouts"], current["export_layouts"], strict=True):
        if len(old_layout["records"]) != len(new_layout["records"]):
            raise RegistryValidationError("row binding reconciliation refuses record changes")
        for old_record, new_record in zip(old_layout["records"], new_layout["records"], strict=True):
            if old_record == new_record:
                continue
            if (
                old_record["repeat"] is not None
                or old_record["binding_record"] is not None
                or old_record["row_field_casilla_ids"]
                or new_record["repeat"] != "binding_rows"
                or new_record["binding_record"] is not None
                or len(old_record["fields"]) != len(new_record["fields"])
            ):
                raise RegistryValidationError("row binding reconciliation requires an unmapped singleton record")
            mapping = {}
            groups = set()
            for old_field, new_field in zip(old_record["fields"], new_record["fields"], strict=True):
                if old_field == new_field:
                    if old_field["kind"] == "casilla":
                        raise RegistryValidationError("row binding reconciliation refuses residual singleton casillas")
                    continue
                binding = bindings.get(new_field["binding"])
                selector = binding_row_set_selector(binding) if binding is not None else None
                if (
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
                ):
                    raise RegistryValidationError("row binding reconciliation refuses uncorrelated row sources")
                mapping[selector.row_field] = old_field["casilla_id"]
                groups.add(selector.grouping)
                old_field.update(kind="binding", binding=binding.id, casilla_id=None)
                if old_field != new_field:
                    raise RegistryValidationError("row binding reconciliation refuses changed field geometry or policy")
            if not mapping or len(groups) != 1 or mapping != new_record["row_field_casilla_ids"]:
                raise RegistryValidationError("row binding reconciliation requires one exact member mapping")
            old_record.update(repeat="binding_rows", row_field_casilla_ids=mapping)
            changed += 1
    if not changed or prior != current:
        raise RegistryValidationError("row binding reconciliation refuses unrelated source changes")
    for revision in (before, after):
        refs = derive_casilla_export_refs(revision.export_layouts, revision.bindings)
        if set(refs) - {c.id for c in revision.casillas} or any(
            tuple(c.export_refs) != tuple(refs.get(c.id, ())) for c in revision.casillas
        ):
            raise RegistryValidationError("row binding reconciliation refuses inconsistent reverse references")
    result = form.model_copy(update={"source_state_digest": form_layout_source_digest(after)})
    failures = form_layout_failures(after.model_copy(update={"form_layouts": (result,)}))
    if failures:
        raise RegistryValidationError("row binding reconciliation failed: " + "; ".join(failures))
    return result
