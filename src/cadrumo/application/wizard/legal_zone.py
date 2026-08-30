"""Flow-compile-time legal-grounding projection for the setup flow pages.

Every setup-flow page that binds a profile fact carries a derived legal
zone: the union of the schema field's own ``legal_refs`` and the registry
reverse-grounding index entry for the page's ``domain_key`` (the consuming
modelos plus their profile-binding ``legal_refs`` / ``source_refs``). The
zone is never authored — it is a projection over two authorities the rest
of the system already owns (the singleton
:class:`~cadrumo.domain.user_profile.schema.ProfileSchemaDefinition` and the
validated :class:`ValidatedRegistryAuthority`), computed once at flow
compile.

A page whose ``domain_key`` is absent from BOTH sources carries no legal
zone (nothing is invented); a UI-only page with no ``domain_key`` never
participates.

Render-slot note: the substrate :class:`FlowPage` / :class:`PageCopy`
copy family exposes no legal-provenance slot today (prompt, help,
format_hint, failure_modes, choices only). This module therefore produces
the typed per-page mapping as data a frontend can render; wiring it into a
concrete render slot is a substrate-contract decision left to the flow
frontend, not hacked into the copy family here.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, Field

from ...core.modelo import Modelo
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.calculations.registry.authority import ValidatedRegistryAuthority
from ...domain.calculations.registry.profile_grounding import build_profile_grounding_index
from ...domain.user_profile.errors import UserProfileError
from ...domain.user_profile.loader import load_user_profile_schema
from ...domain.user_profile.schema import ProfileSchemaDefinition
from ..flows.definition import FlowDefinition, FlowPage, FlowRepeatingGroup


class PageLegalZone(BaseModel):
    """Derived legal grounding for one profile-bound flow page.

    ``legal_refs`` is the sorted union of the schema field's declared
    refs and every consuming profile binding's refs; ``source_refs`` and
    ``modelos`` come from the registry grounding index. A page reaches
    this record only when at least one ref is present.
    """

    model_config = STRICT_FROZEN_CONFIG

    page_id: str = Field(min_length=1)
    profile_key: str = Field(min_length=1)
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    modelos: tuple[Modelo, ...]


def _iter_pages(definition: FlowDefinition) -> tuple[FlowPage, ...]:
    """Flatten a definition into every page, repeating-group instances included."""
    pages: list[FlowPage] = []
    for section in definition.sections:
        for item in section.items:
            if isinstance(item, FlowRepeatingGroup):
                pages.extend(item.pages)
            else:
                pages.append(item)
    return tuple(pages)


def _schema_legal_refs(schema: ProfileSchemaDefinition, profile_key: str) -> tuple[str, ...]:
    """Return a schema field's declared ``legal_refs``; empty if the path is absent."""
    if "." not in profile_key:
        return ()
    try:
        field = schema.field(profile_key)
    except UserProfileError:
        return ()
    return tuple(field.legal_refs)


def build_flow_legal_zones(
    definition: FlowDefinition,
    authority: ValidatedRegistryAuthority,
    *,
    schema: ProfileSchemaDefinition | None = None,
) -> Mapping[str, PageLegalZone]:
    """Project every profile-bound page onto its derived legal zone.

    Walks the definition's pages, unions each page's schema-declared
    ``legal_refs`` with the registry reverse-grounding index entry the
    supplied :class:`ValidatedRegistryAuthority` resolves for its
    ``domain_key``, and emits a :class:`PageLegalZone` only when the union
    is non-empty. The returned mapping is keyed by page id in walk order.
    """
    resolved_schema = schema or load_user_profile_schema()
    grounding_index = build_profile_grounding_index(authority)

    zones: dict[str, PageLegalZone] = {}
    for page in _iter_pages(definition):
        profile_key = page.domain_key
        if profile_key is None:
            continue

        legal_refs: set[str] = set(_schema_legal_refs(resolved_schema, profile_key))
        source_refs: set[str] = set()
        modelos: set[Modelo] = set()

        grounding = grounding_index.get(profile_key)
        if grounding is not None:
            legal_refs.update(grounding.legal_refs)
            source_refs.update(grounding.source_refs)
            modelos.update(grounding.modelos)

        if not (legal_refs or source_refs):
            continue

        zones[page.id] = PageLegalZone(
            page_id=page.id,
            profile_key=profile_key,
            legal_refs=tuple(sorted(legal_refs)),
            source_refs=tuple(sorted(source_refs)),
            modelos=tuple(sorted(modelos, key=lambda modelo: modelo.value)),
        )
    return zones


__all__ = [
    "PageLegalZone",
    "build_flow_legal_zones",
]
