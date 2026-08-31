"""Closed wire-shape vocabulary for modelo registry export layouts.

Every :class:`~domain.calculations.registry.ExportLayoutDefinition` declares the
WIRE SHAPE its records take. :class:`ExportLayoutFormat` closes that value set so
loader hydration rejects an unknown token at registry-load time rather than at a
downstream branch on the string, and so the roughly twenty sites that switch on
the shape compare enum members instead of each re-spelling the same two tokens.

The value set lived as a bare ``Literal`` on the layout model, which is why every
consumer re-spelt it. Two of those consumers computed the SAME per-modelo
capability booleans from it, in two packages, and the pair diverged before either
was noticed; retiring the duplicate left the literal-level fork standing, and
this enum is what closes it. A closed value set belongs in ``core`` for exactly
that reason: a ``Literal`` has no home a consumer can import, so it grows a copy
at every call site.

Not to be confused with two same-shaped vocabularies that name different things:

- ``DeclaracionExportFormat`` in the filing surface is the OPERATOR-facing
  catalogue of export products (``fichero-boe``, ``xml-dictionary``). It names
  what a person asked the application to produce; this enum names how the
  registry declares the bytes are laid out. The two are one-to-one today and are
  still different subjects, so a rename of either must not be assumed to bind the
  other.
- :class:`~core.output_rendering.OutputFormat` is the CLI's own text-versus-JSON
  rendering switch and has nothing to do with AEAT filing artefacts.

Hydration happens at the registry boundary:
:func:`~domain.calculations.registry.load_registry_tree` hands the TOML token to
strict schema validation, which resolves it to a member here.
"""

from __future__ import annotations

from enum import StrEnum


class ExportLayoutFormat(StrEnum):
    """Wire shapes a modelo registry export layout may declare.

    Members carry the exact tokens the registry TOML stores, so hydration is a
    behaviour-preserving lift rather than a re-spelling: a member compares,
    hashes, and JSON-serialises identically to the string it replaces.
    """

    FIXED_WIDTH = "fixed_width"
    """Fixed-width fichero-BOE payload, laid out by the AEAT diseño de registros.

    Every casilla the layout covers occupies a declared byte range, so an absent
    value is a blank slot rather than an absent field — which is why the
    completeness gate binds this shape and not the other.
    """

    XML_DICTIONARY = "xml_dictionary"
    """XML payload driven by an AEAT-published dictionary and its XSD.

    Elements are optional by construction, so an absent casilla is a
    legitimately-absent element and carries no blank-slot hazard.
    """


__all__ = ["ExportLayoutFormat"]
