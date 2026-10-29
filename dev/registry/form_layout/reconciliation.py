"""Explicit reconciliation of an authored draft after its first export is authored.

This prepares and installs presentation data through the form owner. The export
owner must still validate its generated candidate, and complete registry
validation must precede publication. Runtime authority is not written here.
"""

from hashlib import sha256
from pathlib import Path
from typing import cast

from cadrumo.core.atomic_write import hardened_staged_bytes_publication
from cadrumo.core.link_safety import is_link_like
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_field_casilla import derive_casilla_export_refs
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormContextFieldBlock,
    FormLayoutDefinition,
    FormLayoutReviewState,
    FormLayoutSeedSource,
)
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from ..compiler.form_layout_integrity import form_layout_failures, form_layout_source_digest
from ..compiler.loader import load_modelo_directory
from .row_binding_reconciliation import reconcile_export_row_bindings
from .scalar_source_reconciliation import reconcile_scalar_export_sources
from .serialization import form_layout_fragment_path, render_form_layout_toml


def reconcile_export_casilla_splits(before: ModeloRevision, after: ModeloRevision) -> FormLayoutDefinition:
    """Preserve a draft while reviewed composite export fields become typed parts.

    All casillas and presentation must already be authored. This only refreshes
    their export dependency after exact, gapless subdivision of text fields;
    source correctness remains the publisher's separately pinned obligation.
    """
    layout = _validated_split_form(before, after)
    prior = before.model_dump(mode="json")
    current = after.model_dump(mode="json")
    referenced = _referenced_export_fields(layout)
    changed = _reconcile_split_layouts(prior, current, referenced)
    _strip_split_references(before, prior)
    _strip_split_references(after, current)
    if not changed or prior != current:
        raise RegistryValidationError("casilla split reconciliation refuses unrelated source changes")
    reconciled = layout.model_copy(update={"source_state_digest": form_layout_source_digest(after)})
    failures = form_layout_failures(after.model_copy(update={"form_layouts": (reconciled,)}))
    if failures:
        raise RegistryValidationError("casilla split reconciliation failed: " + "; ".join(failures))
    return reconciled


def _strip_split_references(revision: ModeloRevision, dump: dict[str, object]) -> None:
    references = derive_casilla_export_refs(revision.export_layouts, revision.bindings)
    if set(references) - {c.id for c in revision.casillas} or any(
        tuple(c.export_refs) != tuple(references.get(c.id, ())) for c in revision.casillas
    ):
        raise RegistryValidationError("casilla split reconciliation refuses inconsistent reverse references")
    dump["casillas"] = [c.model_dump(mode="json", exclude={"export_refs"}) for c in revision.casillas]


def _reconcile_split_layouts(
    prior: dict[str, object], current: dict[str, object], referenced: set[tuple[str, str, str]]
) -> int:
    old_layouts = cast("list[dict[str, object]]", prior["export_layouts"])
    new_layouts = cast("list[dict[str, object]]", current["export_layouts"])
    if len(old_layouts) != len(new_layouts):
        raise RegistryValidationError("casilla split reconciliation refuses layout changes")
    changed = 0
    for old_layout, new_layout in zip(old_layouts, new_layouts, strict=True):
        old_records = cast("list[dict[str, object]]", old_layout["records"])
        new_records = cast("list[dict[str, object]]", new_layout["records"])
        if len(old_records) != len(new_records):
            raise RegistryValidationError("casilla split reconciliation refuses record changes")
        for old_record, new_record in zip(old_records, new_records, strict=True):
            changed += _reconcile_split_record(old_layout, old_record, new_record, referenced)
    return changed


def _reconcile_split_record(
    old_layout: dict[str, object],
    old_record: dict[str, object],
    new_record: dict[str, object],
    referenced: set[tuple[str, str, str]],
) -> int:
    remaining = list(cast("list[dict[str, object]]", new_record["fields"]))
    changed = 0
    for old_field in cast("list[dict[str, object]]", old_record["fields"]):
        if remaining and remaining[0] == old_field:
            remaining.pop(0)
            continue
        address = (cast("str", old_layout["id"]), cast("str", old_record["id"]), cast("str", old_field["id"]))
        _reconcile_split_field(old_field, remaining, address, referenced)
        changed += 1
    if remaining:
        raise RegistryValidationError("casilla split reconciliation refuses extra fields")
    old_record["fields"] = new_record["fields"]
    return changed


def _reconcile_split_field(
    old_field: dict[str, object],
    remaining: list[dict[str, object]],
    address: tuple[str, str, str],
    referenced: set[tuple[str, str, str]],
) -> None:
    if address in referenced or old_field["kind"] != "casilla" or old_field["data_type"] != "text":
        raise RegistryValidationError("casilla split reconciliation refuses non-composite or context changes")
    start, length = old_field["offset"], old_field["length"]
    if start is None or length is None:
        raise RegistryValidationError("casilla split reconciliation requires fixed-width fields")
    start, length = cast("int", start), cast("int", length)
    cursor = start
    parts: list[dict[str, object]] = []
    while remaining and cursor < start + length:
        part = remaining.pop(0)
        if not _valid_split_part(part, old_field, cursor):
            raise RegistryValidationError("casilla split reconciliation refuses gaps or ungrounded parts")
        cursor += cast("int", part["length"])
        parts.append(part)
    _validate_split_parts(cursor, start, length, parts, old_field)


def _validate_split_parts(
    cursor: int, start: int, length: int, parts: list[dict[str, object]], old_field: dict[str, object]
) -> None:
    if (
        cursor != start + length
        or len(parts) < 2
        or sum(part["id"] == old_field["id"] and part["casilla_id"] == old_field["casilla_id"] for part in parts) != 1
    ):
        raise RegistryValidationError("casilla split reconciliation requires exact subdivision and retained identity")


def _valid_split_part(part: dict[str, object], old_field: dict[str, object], cursor: int) -> bool:
    length = part["length"]
    return (
        part["offset"] == cursor
        and length is not None
        and cast("int", length) > 0
        and part["kind"] == "casilla"
        and part["source_refs"] == old_field["source_refs"]
        and part["legal_refs"] == old_field["legal_refs"]
    )


def _validated_split_form(before: ModeloRevision, after: ModeloRevision) -> FormLayoutDefinition:
    if not before.export_layouts or len(before.form_layouts) != 1 or before.form_layouts != after.form_layouts:
        raise RegistryValidationError("casilla split reconciliation requires existing exports and one unchanged form")
    layout = before.form_layouts[0]
    if (
        layout.seed_source is not FormLayoutSeedSource.AUTHORED
        or layout.review.state is not FormLayoutReviewState.GENERATED
    ):
        raise RegistryValidationError("casilla split reconciliation requires an unreviewed authored draft")
    if form_layout_failures(before):
        raise RegistryValidationError("casilla split reconciliation refuses a stale source form")
    return layout


def reconcile_unreferenced_export_producers(before: ModeloRevision, after: ModeloRevision) -> FormLayoutDefinition:
    """Preserve a draft after an unseen header or explicit marker owner correction.

    This proves presentation equivalence, not correctness of the export change.
    The export publisher must separately admit its source-pinned record drift.
    A computed X-or-blank marker may become an already displayed manual casilla;
    all geometry, constraints, sources and other declarations must stay identical.
    """
    layout = _validated_producer_form(before, after)
    referenced = _referenced_export_fields(layout)
    prior = before.model_dump(mode="json")
    current = after.model_dump(mode="json")
    changed = _reconcile_producer_layouts(prior, current, before, layout, referenced)
    _strip_producer_references(before, prior)
    _strip_producer_references(after, current)
    if not changed or prior != current:
        raise RegistryValidationError("producer reconciliation refuses changes beyond unreferenced header producers")
    reconciled = layout.model_copy(update={"source_state_digest": form_layout_source_digest(after)})
    failures = form_layout_failures(after.model_copy(update={"form_layouts": (reconciled,)}))
    if failures:
        raise RegistryValidationError("producer reconciliation failed: " + "; ".join(failures))
    return reconciled


def _strip_producer_references(revision: ModeloRevision, dump: dict[str, object]) -> None:
    references = derive_casilla_export_refs(revision.export_layouts, revision.bindings)
    if any(tuple(c.export_refs) != tuple(references.get(c.id, ())) for c in revision.casillas):
        raise RegistryValidationError("producer reconciliation refuses inconsistent reverse references")
    dump["casillas"] = [c.model_dump(mode="json", exclude={"export_refs"}) for c in revision.casillas]


def _validated_producer_form(before: ModeloRevision, after: ModeloRevision) -> FormLayoutDefinition:
    if not before.export_layouts or len(before.form_layouts) != 1 or before.form_layouts != after.form_layouts:
        raise RegistryValidationError("producer reconciliation requires existing exports and one unchanged form")
    layout = before.form_layouts[0]
    if (
        layout.seed_source is not FormLayoutSeedSource.AUTHORED
        or layout.review.state is not FormLayoutReviewState.GENERATED
    ):
        raise RegistryValidationError("producer reconciliation requires an unreviewed authored draft")
    if form_layout_failures(before):
        raise RegistryValidationError("producer reconciliation refuses a stale source form")
    return layout


def _reconcile_producer_layouts(
    prior: dict[str, object],
    current: dict[str, object],
    before: ModeloRevision,
    layout: FormLayoutDefinition,
    referenced: set[tuple[str, str, str]],
) -> int:
    old_layouts = cast("list[dict[str, object]]", prior["export_layouts"])
    new_layouts = cast("list[dict[str, object]]", current["export_layouts"])
    if len(old_layouts) != len(new_layouts):
        raise RegistryValidationError("producer reconciliation refuses export geometry changes")
    changed = 0
    for old_layout, new_layout in zip(old_layouts, new_layouts, strict=True):
        old_records = cast("list[dict[str, object]]", old_layout["records"])
        new_records = cast("list[dict[str, object]]", new_layout["records"])
        if len(old_records) != len(new_records):
            raise RegistryValidationError("producer reconciliation refuses record changes")
        for old_record, new_record in zip(old_records, new_records, strict=True):
            changed += _reconcile_producer_record(old_layout, old_record, new_record, before, layout, referenced)
    return changed


def _reconcile_producer_record(
    old_layout: dict[str, object],
    old_record: dict[str, object],
    new_record: dict[str, object],
    before: ModeloRevision,
    layout: FormLayoutDefinition,
    referenced: set[tuple[str, str, str]],
) -> int:
    old_fields = cast("list[dict[str, object]]", old_record["fields"])
    new_fields = cast("list[dict[str, object]]", new_record["fields"])
    if len(old_fields) != len(new_fields):
        raise RegistryValidationError("producer reconciliation refuses field changes")
    changed = 0
    for old_field, new_field in zip(old_fields, new_fields, strict=True):
        address = (cast("str", old_layout["id"]), cast("str", old_record["id"]), cast("str", old_field["id"]))
        changed += _reconcile_producer_field(old_field, new_field, address, before, layout, referenced)
    return changed


def _reconcile_producer_field(
    old_field: dict[str, object],
    new_field: dict[str, object],
    address: tuple[str, str, str],
    before: ModeloRevision,
    layout: FormLayoutDefinition,
    referenced: set[tuple[str, str, str]],
) -> int:
    changed = 0
    if old_field["kind"] == "computed" and new_field["kind"] == "casilla":
        _validate_marker_owner(old_field, new_field, address, before, layout, referenced)
        old_field.update(kind="casilla", casilla_id=new_field["casilla_id"], computed_key=None)
        changed += 1
    if old_field["producer_key"] == new_field["producer_key"]:
        return changed
    if address in referenced or old_field["kind"] != "header" or new_field["kind"] != "header":
        raise RegistryValidationError("producer reconciliation refuses a displayed or non-header change")
    old_field["producer_key"] = new_field["producer_key"]
    return changed + 1


def _validate_marker_owner(
    old_field: dict[str, object],
    new_field: dict[str, object],
    address: tuple[str, str, str],
    before: ModeloRevision,
    layout: FormLayoutDefinition,
    referenced: set[tuple[str, str, str]],
) -> None:
    owner = next((c for c in before.casillas if c.id == new_field["casilla_id"]), None)
    if address in referenced or old_field["data_type"] != "text" or old_field["length"] != 1:
        raise RegistryValidationError("producer reconciliation refuses an unowned or displayed marker")
    if not _marker_owner_matches(owner, layout):
        raise RegistryValidationError("producer reconciliation refuses an unowned or displayed marker")


def _marker_owner_matches(owner: CasillaDefinition | None, layout: FormLayoutDefinition) -> bool:
    return (
        owner is not None
        and owner.input_kind == "manual"
        and owner.formula is None
        and owner.binding is None
        and owner.constraints is not None
        and set(owner.constraints.enum or ()) == {"X", ""}
        and any(p.casilla_id == owner.id and p.kind == "on_form" for p in layout.placements)
    )


def _referenced_export_fields(layout: FormLayoutDefinition) -> set[tuple[str, str, str]]:
    referenced = {
        (block.export_layout_id, block.export_record_id, block.export_field_id)
        for page in layout.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormContextFieldBlock)
    }
    return referenced


def reconcile_authored_export_addition(before: ModeloRevision, after: ModeloRevision) -> FormLayoutDefinition:
    """Preserve an authored draft when the only source change is its first export.

    Replacing existing export semantics, changing casillas or bindings, revising
    presentation, or carrying forward human review requires separate authoring.
    This function deliberately cannot bless those changes by refreshing a hash.
    """
    layout = _validated_authored_form(before, after)
    excluded = {"export_layouts", "form_layouts"}
    prior = before.model_dump(mode="json", exclude=excluded)
    current = after.model_dump(mode="json", exclude=excluded)
    # The loader derives these reverse edges from the new export. Prove them
    # against their canonical owner before excluding them from authored facts.
    _check_authored_references(before)
    _check_authored_references(after)
    prior["casillas"] = [casilla.model_dump(mode="json", exclude={"export_refs"}) for casilla in before.casillas]
    current["casillas"] = [casilla.model_dump(mode="json", exclude={"export_refs"}) for casilla in after.casillas]
    changed = sorted(key for key in prior if prior[key] != current[key])
    if changed:
        raise RegistryValidationError(
            "authored form reconciliation refuses changes outside the first export: " + ", ".join(changed)
        )
    reconciled = layout.model_copy(update={"source_state_digest": form_layout_source_digest(after)})
    failures = form_layout_failures(after.model_copy(update={"form_layouts": (reconciled,)}))
    if failures:
        raise RegistryValidationError("authored form reconciliation failed: " + "; ".join(failures))
    return reconciled


def _check_authored_references(revision: ModeloRevision) -> None:
    references = derive_casilla_export_refs(revision.export_layouts, revision.bindings)
    if set(references) - {casilla.id for casilla in revision.casillas} or any(
        tuple(casilla.export_refs) != tuple(references.get(casilla.id, ())) for casilla in revision.casillas
    ):
        raise RegistryValidationError("authored form reconciliation refuses inconsistent derived export references")


def _validated_authored_form(before: ModeloRevision, after: ModeloRevision) -> FormLayoutDefinition:
    if before.export_layouts or len(after.export_layouts) != 1:
        raise RegistryValidationError("authored form reconciliation requires exactly one first export addition")
    if len(before.form_layouts) != 1 or before.form_layouts != after.form_layouts:
        raise RegistryValidationError("authored form reconciliation requires one unchanged form declaration")
    layout = before.form_layouts[0]
    if (
        layout.seed_source is not FormLayoutSeedSource.AUTHORED
        or layout.review.state is not FormLayoutReviewState.GENERATED
    ):
        raise RegistryValidationError("authored form reconciliation requires an unreviewed authored draft")
    if form_layout_failures(before):
        raise RegistryValidationError("authored form reconciliation refuses an already stale or invalid source form")
    return layout


def install_authored_export_reconciliation(
    modelo_root: Path,
    *,
    before: ModeloRevision,
    expected_old_sha256: str,
    expected_new_sha256: str,
    unreferenced_producers: bool = False,
    casilla_splits: bool = False,
    row_bindings: bool = False,
    scalar_sources: dict[str, tuple[str, str]] | None = None,
) -> None:
    """Finish a prevalidated first-export source interval through the form owner.

    The caller retains source-publication ownership and checks its complete
    captured corpus before and after this operation. This owner rechecks the
    live revision and both form byte receipts, never writes a caller-supplied
    form, and does not publish runtime authority.
    """
    if sum((unreferenced_producers, casilla_splits, row_bindings, scalar_sources is not None)) > 1:
        raise RegistryValidationError("choose one authored form reconciliation mode")
    modelo = load_modelo_directory(modelo_root)
    after = modelo.revisions[str(before.id)]
    path = form_layout_fragment_path(modelo_root / "revisions" / str(before.id))
    if is_link_like(path) or is_link_like(path.parent) or not path.is_file():
        raise RegistryValidationError("authored form owner requires a regular form fragment")
    if tuple(path.parent.iterdir()) != (path,):
        raise RegistryValidationError("authored form owner refuses unknown fragment ownership")
    old_bytes = path.read_bytes()
    if sha256(old_bytes).hexdigest() != expected_old_sha256:
        raise RegistryValidationError("authored form owner old fragment changed")
    layout = _selected_reconciliation(
        before, after, unreferenced_producers, casilla_splits, row_bindings, scalar_sources
    )
    new_bytes = render_form_layout_toml(str(before.id), layout).encode("utf-8")
    if sha256(new_bytes).hexdigest() != expected_new_sha256:
        raise RegistryValidationError("authored form owner output differs from the prevalidated candidate")
    _publish_reconciled_form(path, old_bytes, new_bytes)


def _publish_reconciled_form(path: Path, old_bytes: bytes, new_bytes: bytes) -> None:
    with hardened_staged_bytes_publication(path, new_bytes) as staged:
        if is_link_like(path) or is_link_like(path.parent) or path.read_bytes() != old_bytes:
            raise RegistryValidationError("authored form owner fragment changed before write")
        staged.publish()


def _selected_reconciliation(
    before: ModeloRevision,
    after: ModeloRevision,
    unreferenced_producers: bool,
    casilla_splits: bool,
    row_bindings: bool,
    scalar_sources: dict[str, tuple[str, str]] | None,
) -> FormLayoutDefinition:
    layout = (
        reconcile_scalar_export_sources(before, after, replacements=scalar_sources)
        if scalar_sources is not None
        else reconcile_export_row_bindings(before, after)
        if row_bindings
        else reconcile_export_casilla_splits(before, after)
        if casilla_splits
        else (
            reconcile_unreferenced_export_producers(before, after)
            if unreferenced_producers
            else reconcile_authored_export_addition(before, after)
        )
    )
    return layout
