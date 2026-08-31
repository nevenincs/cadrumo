"""Profile-flow copy-source resolvers for the paged setup flow.

The paged setup flow authored on the :mod:`cadrumo.application.flows.definition`
substrate carries every copy slot as a :class:`CopyRef`, resolved at
render time. Locale keys are built in; this module supplies the two
non-locale resolvers the profile flow registers, each owning a
namespace-prefixed reference space and returning ``None`` for anything
outside it so it composes cleanly with any other resolver sharing the
same :class:`~cadrumo.core.flows.CopyRefKind`.

- ``profile-schema:<schema-path>`` resolves a :class:`SCHEMA_FIELD`
  reference to the profile schema field's declared description plus its
  legal-ref citations (the field authority is the singleton
  :class:`~cadrumo.domain.user_profile.schema.ProfileSchemaDefinition`; the TOML
  is never re-read here).
- ``profile-terminology:<concept_id>`` resolves a
  :class:`TERMINOLOGY_CONCEPT` reference to the ``approved`` Terminology
  Handbook fragment's locale-matched short description and definition,
  read through the shipped product-side Handbook loader.

Both resolvers are total and quiet: they never raise and never guess. A
reference outside the resolver's namespace, an unknown schema path, an
unknown concept, or a non-``approved`` concept all resolve to ``None``,
which lets the substrate assembler own the single loud unresolved-copy
refusal (naming the reference kind and id) rather than each resolver
inventing its own error surface.
"""

from __future__ import annotations

from ...core.concept_lifecycle import ConceptLifecycle
from ...core.flows import CopyRefKind
from ...core.i18n import output_language
from ...domain.user_profile.errors import UserProfileError
from ...domain.user_profile.loader import load_user_profile_schema
from ..corpus_search.errors import CorpusSearchInputError
from ..corpus_search.terminology import lookup_terminology
from ..flows.copy import register_copy_source

_SCHEMA_NAMESPACE = "profile-schema:"
_TERMINOLOGY_NAMESPACE = "profile-terminology:"

_registered = False


def resolve_profile_schema_copy(ref: str) -> str | None:
    """Resolve a ``profile-schema:<schema-path>`` reference to display copy.

    Projects the field's declared ``description`` and, when present, its
    ``legal_refs`` citation tokens. Returns ``None`` for any reference
    outside the ``profile-schema:`` namespace or naming a path the schema
    does not declare.
    """
    if not ref.startswith(_SCHEMA_NAMESPACE):
        return None
    path = ref[len(_SCHEMA_NAMESPACE) :]
    if "." not in path:
        return None
    schema = load_user_profile_schema()
    try:
        field = schema.field(path)
    except UserProfileError:
        return None
    description = field.description.strip()
    if not description:
        return None
    if field.legal_refs:
        citations = "; ".join(field.legal_refs)
        return f"{description} ({citations})"
    return description


def resolve_profile_terminology_copy(ref: str) -> str | None:
    """Resolve a ``profile-terminology:<concept_id>`` reference to display copy.

    Projects the locale-matched ``short_description`` and ``definition``
    of an ``approved`` Handbook concept. Returns ``None`` for any
    reference outside the ``profile-terminology:`` namespace, an unknown
    concept id, or a concept whose lifecycle is not ``approved`` (a
    ``draft`` or ``deprecated`` concept never renders as taxpayer-facing
    copy).
    """
    if not ref.startswith(_TERMINOLOGY_NAMESPACE):
        return None
    concept_id = ref[len(_TERMINOLOGY_NAMESPACE) :]
    if not concept_id:
        return None
    try:
        concept = lookup_terminology(concept_id, locale=output_language())
    except CorpusSearchInputError:
        return None
    if concept.lifecycle is not ConceptLifecycle.APPROVED:
        return None
    parts = [text for text in (concept.short_description.strip(), concept.definition.strip()) if text]
    if not parts:
        return None
    return "\n\n".join(parts)


def register_profile_copy_sources() -> None:
    """Register both profile copy-source resolvers, once per process.

    The substrate copy-source registry is process-global with no
    unregister verb and refuses a duplicate resolver object, so this
    guards on a module flag to stay safe under repeated import or an
    explicit second call.
    """
    global _registered
    if _registered:
        return
    register_copy_source(CopyRefKind.SCHEMA_FIELD, resolve_profile_schema_copy)
    register_copy_source(CopyRefKind.TERMINOLOGY_CONCEPT, resolve_profile_terminology_copy)
    _registered = True


register_profile_copy_sources()


__all__ = [
    "register_profile_copy_sources",
    "resolve_profile_schema_copy",
    "resolve_profile_terminology_copy",
]
