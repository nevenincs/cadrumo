"""Validate workbook output identifiers and reference coverage."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.ids import (
    WorkbookOutputId,
    is_registry_id,
)

if TYPE_CHECKING:
    # Annotation-only: ``from __future__ import annotations`` above makes every
    # annotation a string, so these need not exist at runtime. openpyxl is one of
    # the heaviest third-party imports in the tree and this module is imported
    # eagerly by the registry facade, so the symbols that ARE needed at runtime
    # (``load_workbook``, ``Tokenizer``, and the ``TokenizerError`` /
    # ``InvalidFileException`` handler types) are imported inside the functions
    # that use them -- a taxpayer calculation must not load a spreadsheet engine.
    pass


def _missing_or_empty_output_refs(
    expected_ids: frozenset[WorkbookOutputId],
    refs: Mapping[WorkbookOutputId, tuple[str, ...]],
) -> tuple[WorkbookOutputId, ...]:
    return tuple(sorted(output_id for output_id in expected_ids if not refs.get(output_id)))


def _workbook_output_id_set(
    surface: str,
    values: Mapping[WorkbookOutputId, object],
) -> frozenset[WorkbookOutputId]:
    invalid = sorted(repr(output_id) for output_id in values if not is_registry_id(output_id))
    if invalid:
        raise RegistryValidationError(f"{surface} contains invalid workbook output ids: {invalid!r}")
    return frozenset(values)


def _require_matching_output_ids(
    left_name: str,
    left: Mapping[WorkbookOutputId, object],
    right_name: str,
    right: Mapping[WorkbookOutputId, object],
) -> None:
    left_ids = _workbook_output_id_set(left_name, left)
    right_ids = _workbook_output_id_set(right_name, right)
    if left_ids != right_ids:
        _raise_output_id_mismatch(left_name, left_ids, right_name, right_ids)


def _raise_output_id_mismatch(
    left_name: str,
    left_ids: frozenset[WorkbookOutputId],
    right_name: str,
    right_ids: frozenset[WorkbookOutputId],
) -> None:
    missing_from_left = sorted(right_ids.difference(left_ids))
    missing_from_right = sorted(left_ids.difference(right_ids))
    raise RegistryValidationError(
        "workbook parity output ids must match exactly; "
        f"{left_name} missing {missing_from_left!r}; "
        f"{right_name} missing {missing_from_right!r}",
    )
