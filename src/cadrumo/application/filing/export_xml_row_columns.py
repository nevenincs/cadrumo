"""Where a row binding's values go in an XML-dictionary export, and the totals its rows must state.

A row binding fills one column of a repeating element: the dictionary row of the
box it targets, or the dictionary field it names. The element and its bound come
from the edition's XSD. Where a family declares a box to be the total of row
columns, the rows must add up to the box, or the export is refused rather than
filing a box that no occurrence accounts for.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal

from ...core.aggregation import BindingAggregationOp
from ...core.decimal.coercion import coerce_decimal
from ...domain.calculations.registry.binding_aggregation import binding_aggregation_op
from ...domain.calculations.registry.binding_selector_utils import selector_as_dict
from ...domain.calculations.registry.binding_targets import revision_bindings_by_id, sole_bound_casilla
from ...domain.calculations.registry.export_xml_dictionary import XmlDictionaryEntry
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.profile_bindings import ProfileProvider
from ...domain.calculations.registry.row_column_totals import RowColumnTotal, revision_row_column_totals
from ...domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from ...domain.filing.errors import FilingExportDesignIntegrityError
from ...domain.filing.schema import ModeloDraft
from .errors import casilla_value_refusal

__all__ = [
    "nearest_repeating_element_path",
    "require_row_totals_stated",
    "row_column_entry",
]


def nearest_repeating_element_path(path: str, repeating: Mapping[str, int | None]) -> str | None:
    """Return the innermost repeating element that encloses ``path``, or ``None`` when none does."""
    parts = path.split("/")
    return next(
        (candidate for end in range(len(parts) - 1, 0, -1) if (candidate := "/".join(parts[:end])) in repeating),
        None,
    )


def _row_column_undeclared(binding: BindingDefinition) -> FilingExportDesignIntegrityError:
    return FilingExportDesignIntegrityError(
        f"binding {binding.id!r} carries rows but declares no row column",
        translated_message="errors.integrity.filing_export_xml_row_column_undeclared",
        context={"binding": binding.id},
    )


def _column_filter(binding: BindingDefinition) -> tuple[str, Callable[[XmlDictionaryEntry], bool]]:
    """Name the column a row binding fills and how to recognise its dictionary row.

    A profile row object and a source row column that name a dictionary field are
    placed by that field; a profile row object must also sit at the schema path it
    declares. Any other row binding is placed by the box it targets.
    """
    provider = binding.provider
    selector = selector_as_dict(binding)
    expected_path = provider.xsd_path if isinstance(provider, ProfileProvider) else None
    field = selector.get("dictionary_field")
    if isinstance(field, str):
        return field, lambda entry: entry.field_id == field and expected_path in {None, entry.path}
    target = selector.get("target_casilla_id")
    if target is None:
        raise _row_column_undeclared(binding)
    return str(target), lambda entry: entry.casilla_id == target


def row_column_entry(
    binding: BindingDefinition,
    entries: tuple[XmlDictionaryEntry, ...],
    repeating: Mapping[str, int | None],
) -> tuple[str, XmlDictionaryEntry]:
    """Find the one dictionary row a row binding fills, and the repeating element around it.

    Raises:
        FilingExportDesignIntegrityError: The binding is not a row column, or not
            exactly one repeating dictionary row answers it.
    """
    if binding_aggregation_op(binding) is not BindingAggregationOp.ROWS:
        raise _row_column_undeclared(binding)
    column, fills = _column_filter(binding)
    placed = tuple(
        (element, entry)
        for entry in entries
        if fills(entry) and (element := nearest_repeating_element_path(entry.path, repeating)) is not None
    )
    if len(placed) != 1:
        raise FilingExportDesignIntegrityError(
            f"row column {binding.id!r} needs one repeating dictionary row for {column}, found {len(placed)}",
            translated_message="errors.integrity.filing_export_xml_row_column_occurrence",
            context={"binding": binding.id, "column": column, "found": len(placed)},
        )
    return placed[0]


def _stated_by_rows(draft: ModeloDraft) -> dict[BindingId, Decimal]:
    """Add up each row column's values over the draft's rows; a column with no row is absent."""
    stated: dict[BindingId, Decimal] = {}
    for value in draft.binding_values:
        if value.row_index is None or value.value is None or value.value == "":
            continue
        amount = coerce_decimal(value.value)
        if amount is not None:
            stated[value.binding_id] = stated.get(value.binding_id, Decimal(0)) + amount
    return stated


def _total_box(revision: ModeloRevision, total: RowColumnTotal) -> str:
    casilla = sole_bound_casilla(revision, total.total_binding_id)
    if casilla is None:
        raise FilingExportDesignIntegrityError(
            f"binding {total.total_binding_id!r} totals row columns but fills no single box",
            translated_message="errors.integrity.filing_export_xml_row_total_box_unresolved",
            context={"binding": total.total_binding_id},
        )
    return casilla


def require_row_totals_stated(
    revision: ModeloRevision,
    draft: ModeloDraft,
    *,
    entries: tuple[XmlDictionaryEntry, ...],
    repeating: Mapping[str, int | None],
) -> None:
    """Refuse a box its row columns do not add up to, once any of those columns has a row.

    A box no column has a row for is left as it is: it was entered or calculated
    without occurrences, and the rows say nothing about it.

    Args:
        revision: The :class:`ModeloRevision` whose families declare the totals.
        draft: The :class:`ModeloDraft` holding the boxes and the rows.
        entries: Every dictionary row the layout places, to name the elements.
        repeating: The repeating elements of the edition's XSD with their bounds.

    Raises:
        FilingExportCasillaValueRefusedError: A box differs from the sum of its rows.
    """
    stated = _stated_by_rows(draft)
    if not stated:
        return
    bindings = revision_bindings_by_id(revision)
    boxes = {value.casilla_id: value.value for value in draft.values}
    for total in revision_row_column_totals(revision):
        present = tuple(column for column in total.column_binding_ids if column in stated)
        if not present:
            continue
        casilla = _total_box(revision, total)
        box = coerce_decimal(boxes.get(casilla), default=Decimal("0"))
        if box == sum((stated[column] for column in present), Decimal("0")):
            continue
        elements = sorted({row_column_entry(bindings[column], entries, repeating)[0] for column in present})
        raise casilla_value_refusal(
            casilla,
            translated_message="application.filing.export.errors.box_not_stated_by_rows",
            context={"element_path": ", ".join(elements), "value": format(box, "f")},
        )
