"""Cite the provisions behind the registry parameters a schedule authority rests on."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from ...domain.calculations.registry.actividad_asset_bindings import activity_asset_parameter_of_reference
from ...domain.calculations.registry.errors import RegistryError
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.schema_references import LegalReference
from ..modelo.casilla_help import legal_citation_text
from .activity_asset_read_models import ActivityAssetLegalCitation


@dataclass(frozen=True, slots=True)
class ResolvedLegalCitations:
    """The citations that resolved, and whether every cited registry parameter resolved."""

    citations: tuple[ActivityAssetLegalCitation, ...] = ()
    complete: bool = True


def resolve_legal_citations(
    source_references: Iterable[str],
    *,
    modelo: ModeloRevision,
    legal_reference: Callable[[str], LegalReference],
) -> ResolvedLegalCitations:
    """Resolve a schedule authority's source references to the provisions the registry declares for them.

    An entry naming a registry parameter yields that parameter's legal references.  An entry
    that names no parameter, such as operator-supplied plan or useful-life evidence, cites no
    provision and is left out without making the result incomplete.  A parameter the revision
    does not declare, or a provision the authority cannot load, is left out and marks the
    result incomplete; the read never fails for it.

    Args:
        source_references: The schedule authority's registry parameter and supporting evidence references.
        modelo: The :class:`ModeloRevision` whose parameters declare the cited provisions.
        legal_reference: Resolve a provision identifier against the pinned authority.

    Returns:
        The citations in first-cited order, each provision once.
    """
    parameters = {parameter.id: parameter for parameter in modelo.parameters}
    seen: set[str] = set()
    citations: list[ActivityAssetLegalCitation] = []
    complete = True
    for entry in source_references:
        parameter_id = activity_asset_parameter_of_reference(entry, revision_id=modelo.id)
        if parameter_id is None:
            continue
        parameter = parameters.get(parameter_id)
        if parameter is None:
            complete = False
            continue
        for reference_id in parameter.legal_refs:
            if reference_id in seen:
                continue
            seen.add(reference_id)
            try:
                reference = legal_reference(reference_id)
            except (LookupError, RegistryError):
                complete = False
                continue
            citations.append(
                ActivityAssetLegalCitation(text=legal_citation_text(reference), permalink=reference.permalink),
            )
    return ResolvedLegalCitations(citations=tuple(citations), complete=complete)
