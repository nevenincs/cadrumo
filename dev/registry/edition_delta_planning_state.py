"""Mutable per-model planning state shared by revision planning stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision

from . import edition_delta_source as _edition_delta_source


@dataclass
class PlanningRun:
    """One modelo's ordered revisions, edition sources and the materialised rows and work planned so far."""

    modelo_dir: Path
    definition: ModeloDefinition
    ordered: tuple[ModeloRevision, ...]
    sources: dict[str, _edition_delta_source._EditionSource]
    already_delta_authored: bool
    materialised: dict[str, list[_edition_delta_source._Placed]] = field(default_factory=dict)
    order_normalised: set[str] = field(default_factory=set)
    work: list[_edition_delta_source._EditionWork] = field(default_factory=list)
