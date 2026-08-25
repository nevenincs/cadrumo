"""The render-time copy assembler: references in, display copy out.

Every copy slot on a flow definition is a :class:`CopyRef`, never a
literal string; this module resolves those references against the
bundled sources at render time and composes the per-page copy bundle
both frontends consume. Locale keys resolve through the canonical
:func:`~cadrumo.core.i18n.tr` catalogue lookup built in; the
``SCHEMA_FIELD`` and ``TERMINOLOGY_CONCEPT`` kinds resolve through
resolvers a domain flow registers at import time, keeping the substrate
blind to which schema or concept corpus backs them.

Resolution is loud: an unresolvable reference raises
:class:`FlowCopyResolutionError` naming the reference kind and id — a
page never renders a silent blank or a raw key leak.
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from ...core import STRICT_FROZEN_CONFIG
from ...core.flows import CopyRefKind
from ...core.i18n import tr
from .definition import CopyRef, FlowDefinition, FlowPage
from .errors import FlowCopyResolutionError

type CopySourceResolver = Callable[[str], "str | None"]
"""Resolver for one :class:`CopyRefKind`: reference id in, display text or None."""

_UNRESOLVED_SENTINEL = "\x00cadrumo-flows-copy-unresolved\x00"

_SOURCE_RESOLVERS: dict[CopyRefKind, list[CopySourceResolver]] = {}


def register_copy_source(kind: CopyRefKind, resolver: CopySourceResolver) -> None:
    """Register a resolver for a non-locale copy source kind.

    ``LOCALE_KEY`` is built in and may not be overridden. A kind may
    carry several resolvers — distinct domains legitimately serve
    disjoint reference namespaces of the same kind (profile schema
    fields and modelo casilla labels are both ``SCHEMA_FIELD``) — and
    resolution tries them in registration order, first non-``None``
    winning. Registering the same resolver object twice is refused so
    an accidental double import surfaces loudly.
    """
    if kind is CopyRefKind.LOCALE_KEY:
        raise FlowCopyResolutionError(
            translated_message="application.flows.errors.copy_source_locale_builtin",
        )
    resolvers = _SOURCE_RESOLVERS.setdefault(kind, [])
    if any(existing is resolver for existing in resolvers):
        raise FlowCopyResolutionError(
            translated_message="application.flows.errors.copy_source_duplicate",
            context={"kind": kind.value},
        )
    resolvers.append(resolver)


def resolve_copy(ref: CopyRef) -> str:
    """Resolve one reference to display copy, or refuse loudly."""
    if ref.kind is CopyRefKind.LOCALE_KEY:
        rendered = tr(ref.ref, default=_UNRESOLVED_SENTINEL)
        if rendered == _UNRESOLVED_SENTINEL:
            raise FlowCopyResolutionError(
                translated_message="application.flows.errors.copy_locale_key_unresolved",
                context={"ref": ref.ref},
            )
        return rendered
    resolvers = _SOURCE_RESOLVERS.get(ref.kind)
    if not resolvers:
        raise FlowCopyResolutionError(
            translated_message="application.flows.errors.copy_source_unregistered",
            context={"kind": ref.kind.value, "ref": ref.ref},
        )
    for resolver in resolvers:
        rendered = resolver(ref.ref)
        if rendered is not None:
            return rendered
    raise FlowCopyResolutionError(
        translated_message="application.flows.errors.copy_ref_unresolved",
        context={"kind": ref.kind.value, "ref": ref.ref, "resolver_count": len(resolvers)},
    )


def resolve_optional_copy(ref: CopyRef | None) -> str | None:
    """Resolve an optional copy slot; ``None`` stays ``None``."""
    return None if ref is None else resolve_copy(ref)


class ChoiceCopy(BaseModel):
    """Rendered copy for one choice row."""

    model_config = STRICT_FROZEN_CONFIG

    value: str
    label: str
    description: str | None = None
    provenance: str | None = None


class LegalRefCopy(BaseModel):
    """Resolved copy for one legal citation on the provenance zone.

    ``ref`` is the registry legal-ref token, carried through verbatim;
    ``label`` is the resolved display text, or ``None`` when the citation
    declared no label. The pairing is structured, not pre-rendered prose —
    how a ``ref``/``label`` pair reads on screen is the frontend's concern.
    """

    model_config = STRICT_FROZEN_CONFIG

    ref: str
    label: str | None = None


class PageCopy(BaseModel):
    """The fully-assembled display bundle for one page.

    Frontends render this bundle and nothing else — no frontend ever
    resolves a reference itself, so page copy is identical across the
    full-screen, line-mode, and any future surface by construction.
    """

    model_config = STRICT_FROZEN_CONFIG

    prompt: str
    help: str | None = None
    format_hint: str | None = None
    failure_modes: tuple[str, ...] = ()
    legal_zone: tuple[LegalRefCopy, ...] = ()
    choices: tuple[ChoiceCopy, ...] = ()


def assemble_page_copy(page: FlowPage) -> PageCopy:
    """Resolve every copy slot on ``page`` into one display bundle."""
    return PageCopy(
        prompt=resolve_copy(page.prompt),
        help=resolve_optional_copy(page.help),
        format_hint=resolve_optional_copy(page.format_hint),
        failure_modes=tuple(resolve_copy(ref) for ref in page.failure_modes),
        legal_zone=tuple(
            LegalRefCopy(ref=legal_ref.ref, label=resolve_optional_copy(legal_ref.label))
            for legal_ref in page.legal_zone
        ),
        choices=tuple(
            ChoiceCopy(
                value=choice.value,
                label=resolve_copy(choice.label),
                description=resolve_optional_copy(choice.description),
                provenance=resolve_optional_copy(choice.provenance),
            )
            for choice in page.choices
        ),
    )


def assemble_section_titles(definition: FlowDefinition) -> dict[str, str]:
    """Resolve every section's title copy, keyed by section id.

    A section id is an internal slug (``residence``, ``identidad``) that
    is never display copy; :attr:`FlowSection.title` is the reference
    that carries the operator-facing, locale-resolved title. Every
    frontend that shows a section — the question panel's group-box
    title, the progress header, the review grouping — resolves it here
    so no surface can fall back to rendering the slug.
    """
    return {section.id: resolve_copy(section.title) for section in definition.sections}


__all__ = [
    "ChoiceCopy",
    "CopySourceResolver",
    "LegalRefCopy",
    "PageCopy",
    "assemble_page_copy",
    "assemble_section_titles",
    "register_copy_source",
    "resolve_copy",
    "resolve_optional_copy",
]
