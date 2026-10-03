"""Schema-derived casilla facts, modelo overviews, and rendered page inventories."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.schema_surfaces import CasillaConstraints


class CasillaReferenceError(RuntimeError):
    """Raised when a modelo page would emit an ambiguous anchor.

    A named, actionable boundary: two casilla ids - or two registry section
    paths - on one page folding to the same HTML anchor would ship a page whose
    ``#`` fragment is ambiguous and red the ``-n -W`` build. The generator
    refuses to write it.
    """


@dataclass(frozen=True)
class CasillaFacts:
    """How one casilla is filled, compiled from its registry definition.

    The substance of an entry. Read from the exact
    :class:`~cadrumo.domain.calculations.registry.CasillaDefinition` the search
    record was projected from, so the page and the search card can never
    disagree about which revision they describe.
    """

    #: ``BindingSourceKind`` values that may fill this casilla, primary first.
    binding_sources: tuple[str, ...] = ()
    #: Casilla ids this casilla's formula derives from, in expression order.
    formula_inputs: tuple[str, ...] = ()
    constraints: CasillaConstraints | None = None
    #: The printed form number where it differs from the canonical ``number``.
    form_number: str | None = None
    #: An app-internal computed casilla absent from the AEAT record design.
    internal_only: bool = False


@dataclass(frozen=True)
class ModeloOverview:
    """What a modelo IS, compiled from the registry plus the Terminology Handbook.

    ``definition`` is curated Handbook prose and is present only for an approved
    concept that authored it IN THE BUILD LANGUAGE; everything else is compiled
    from the schema, so a modelo with no curated definition still says what it
    is rather than opening on a bare list.
    """

    title: str
    official_name: str
    #: Curated Handbook definition in the build language, or ``None``.
    definition: str | None
    tax_domain: str
    cadence: str
    legal_refs: tuple[str, ...]


@dataclass(frozen=True)
class CompiledSchema:
    """The schema-compiled substance behind the pages, injectable for tests."""

    casillas: Mapping[tuple[str, str], CasillaFacts]
    modelos: Mapping[str, ModeloOverview]


#: Renders a page from the records alone, with no registry read. The shape a
#: narrowed test drives; the real build always compiles the schema.
EMPTY_SCHEMA: Final[CompiledSchema] = CompiledSchema(casillas={}, modelos={})


@dataclass(frozen=True)
class CasillaPage:
    """One rendered modelo page and its anchor / grounding inventory (for the gate)."""

    modelo: str
    output_relpath: str
    rst: str
    #: The ``casilla-<slug>`` anchor id emitted for each casilla, in page order.
    anchors: tuple[str, ...]
    #: ``anchor -> the legal_refs read back out of the markup that entry
    #: emitted`` (grounding coverage). Never the record's own ``legal_refs``:
    #: an echoed input cannot witness a ref the renderer dropped.
    rendered_legal_refs: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class CasillaReferenceResult:
    """Outcome of a casilla-reference generation pass."""

    pages: tuple[CasillaPage, ...]
    index_relpath: str
    modelo_count: int
    casilla_count: int
    legal_links: int
