"""Typed mutable state used by the development form-layout generator."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_exports import ExportRecordDefinition
from cadrumo.domain.calculations.registry.schema_form_layouts import FormDesignSource


@dataclass(slots=True)
class _Position:
    """One official position in form order: a design row or dictionary line."""

    page_key: str
    page_ref: str | None
    description: str | None
    box: str | None
    records: dict[str, ExportRecordDefinition] = field(default_factory=dict)
    casilla_ids: list[str] = field(default_factory=list)
    binding_ids: list[str] = field(default_factory=list)
    literal: str | None = None
    literal_decimals: int | None = None
    xml_container: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class _Item:
    """One thing a section shows: a casilla, a binding input, or a design constant."""

    position: int
    casilla_id: str | None = None
    binding_id: str | None = None
    literal: str | None = None
    literal_decimals: int | None = None


@dataclass(slots=True)
class _Build:
    """Mutable state of one revision's generation."""

    modelo_id: str
    revision: ModeloRevision
    positions: list[_Position] = field(default_factory=list)
    anchors: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list))
    ambiguous: set[str] = field(default_factory=set)
    binding_primary: dict[str, int] = field(default_factory=dict)
    design_sources: list[FormDesignSource] = field(default_factory=list)
    used_design: bool = False
    used_export: bool = False
    used_dictionary: bool = False
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class _SectionDraft:
    key: tuple[str, ...]
    heading: str | None
    positions: list[int] = field(default_factory=list)
    items: list[_Item] = field(default_factory=list)


@dataclass(slots=True)
class _RowDraft:
    stem: str
    columns: list[str]
    items: list[_Item]
