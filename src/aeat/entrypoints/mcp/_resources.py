"""Operating-layer resource templates: pull the harness by ``aeat://`` URI.

ADR R4's second delivery channel above the tools-only floor: MCP resource
templates ``aeat://skill/{name}``, ``aeat://rule/{name}`` and
``aeat://persona/{name}`` let a resources-capable client enumerate and pull the
shipped operating layer verbatim as ``text/markdown``. The concrete resource set
and the read resolution are both DERIVED from the shipped ``aeat/_data/agent/``
tree through the ``aeat.agent`` package facade (``iter_skill_documents``,
``iter_operator_rules``, ``iter_personas``), never hand-listed, so a new skill,
rule, or persona ships as a new resource with zero registration and the surface
cannot drift from the data.

Like ``_tools`` / ``_meta_tools`` / ``_prompts``, this module is SDK-independent
pure functions over typed models: ``_server`` adapts :class:`HarnessResourceRef`
to the SDK ``Resource``, :class:`HarnessResourceTemplate` to ``ResourceTemplate``,
and :class:`HarnessResourceContent` to the read result, so this module imports
with or without the ``aeat-cli[agent]`` extra and is unit-tested directly.
"""

from __future__ import annotations

from collections.abc import Iterator
from enum import StrEnum
from importlib.resources.abc import Traversable  # nosem

from pydantic import BaseModel, ConfigDict, Field

from ...agent import iter_operator_rules, iter_personas, iter_skill_documents
from ...core.external_constants import UTF_8_ENCODING as _UTF_8

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

_URI_SCHEME = "aeat"
_URI_PREFIX = f"{_URI_SCHEME}://"
_MARKDOWN = "text/markdown"
_MARKDOWN_SUFFIX = ".md"


class HarnessResourceKind(StrEnum):
    """The operating-layer resource categories, matching the URI authority.

    ``SKILL`` / ``RULE`` / ``PERSONA`` enumerate the shipped agent tree;
    ``CORPUS`` is a template-only category resolving a citation id or
    ``corpus_ref`` to its verbatim bundled legal text (ADR R3).
    """

    SKILL = "skill"
    RULE = "rule"
    PERSONA = "persona"
    CORPUS = "corpus"


class HarnessResourceRef(BaseModel):
    """A concrete resource row for ``resources/list`` - no body text.

    Listing advertises the addressable set; the body is fetched separately by
    ``resources/read``, so a ref carries only the URI, name, kind, and label.
    """

    model_config = _STRICT_FROZEN

    uri: str = Field(min_length=1)
    name: str = Field(min_length=1)
    kind: HarnessResourceKind
    description: str = Field(min_length=1)
    mime_type: str = _MARKDOWN


class HarnessResourceTemplate(BaseModel):
    """One RFC 6570 resource template for ``resources/templates/list``."""

    model_config = _STRICT_FROZEN

    uri_template: str = Field(min_length=1)
    name: str = Field(min_length=1)
    kind: HarnessResourceKind
    description: str = Field(min_length=1)
    mime_type: str = _MARKDOWN


class HarnessResourceContent(BaseModel):
    """The resolved ``resources/read`` payload: a ref plus its verbatim text."""

    model_config = _STRICT_FROZEN

    ref: HarnessResourceRef
    text: str = Field(min_length=1)


class HarnessResourceNotFoundError(LookupError):
    """Raised when a ``resources/read`` URI does not resolve to a shipped document."""


def _skill_name(document: Traversable) -> str:
    """Derive a skill's name from its ``skills/<name>/SKILL.md`` traversable path."""
    parts = str(document).replace("\\", "/").split("/")
    return parts[-2] if len(parts) >= 2 else parts[-1]


def _stem(name: str) -> str:
    """Strip the ``.md`` suffix from a rule/persona file name."""
    return name[: -len(_MARKDOWN_SUFFIX)] if name.endswith(_MARKDOWN_SUFFIX) else name


def _iter_entries() -> Iterator[tuple[HarnessResourceKind, str, Traversable]]:
    """Yield every shipped ``(kind, name, document)`` triple, kind-then-name order.

    The single enumeration both ``list``/``templates`` and ``read`` derive from,
    read fresh from the shipped tree on each call so the surface tracks the data.
    """
    for document in iter_skill_documents():
        yield (HarnessResourceKind.SKILL, _skill_name(document), document)
    for document in iter_operator_rules():
        yield (HarnessResourceKind.RULE, _stem(document.name), document)
    for document in iter_personas():
        yield (HarnessResourceKind.PERSONA, _stem(document.name), document)


_DESCRIPTIONS: dict[HarnessResourceKind, str] = {
    HarnessResourceKind.SKILL: "aeat workflow skill",
    HarnessResourceKind.RULE: "aeat operator rule",
    HarnessResourceKind.PERSONA: "aeat operator persona",
    HarnessResourceKind.CORPUS: "aeat legal corpus reference",
}

_TEMPLATE_DESCRIPTIONS: dict[HarnessResourceKind, str] = {
    HarnessResourceKind.SKILL: "Workflow skill playbooks, addressed by skill name.",
    HarnessResourceKind.RULE: "Operator operating-rule documents, addressed by rule name.",
    HarnessResourceKind.PERSONA: "Tax-advisor persona documents, addressed by persona name.",
    HarnessResourceKind.CORPUS: (
        "Verbatim BOE/AEAT legal text, addressed by citation id or corpus_ref (e.g. ley-58-2003:art-27.2)."
    ),
}


def resource_uri(kind: HarnessResourceKind, name: str) -> str:
    """Render the ``aeat://<kind>/<name>`` URI for one operating-layer document."""
    return f"{_URI_PREFIX}{kind.value}/{name}"


def _ref_for(kind: HarnessResourceKind, name: str) -> HarnessResourceRef:
    return HarnessResourceRef(
        uri=resource_uri(kind, name),
        name=name,
        kind=kind,
        description=f"{_DESCRIPTIONS[kind]}: {name}",
    )


def list_harness_resources() -> tuple[HarnessResourceRef, ...]:
    """Return every concrete operating-layer resource, kind-then-name ordered.

    One row per shipped skill, operator rule, and persona - the addressable set
    a ``resources/list`` advertises.

    Returns:
        A :class:`HarnessResourceRef`.
    """
    return tuple(_ref_for(kind, name) for kind, name, _document in _iter_entries())


def list_harness_resource_templates() -> tuple[HarnessResourceTemplate, ...]:
    """Return the three ``aeat://<kind>/{name}`` resource templates.

    Returns:
        A :class:`HarnessResourceTemplate`.
    """
    return tuple(
        HarnessResourceTemplate(
            uri_template=f"{_URI_PREFIX}{kind.value}/{{name}}",
            name=f"aeat-{kind.value}",
            kind=kind,
            description=_TEMPLATE_DESCRIPTIONS[kind],
        )
        for kind in HarnessResourceKind
    )


def _parse_uri(uri: str) -> tuple[HarnessResourceKind, str]:
    """Parse an ``aeat://<kind>/<name>`` URI into its kind and name.

    Raises:
        HarnessResourceNotFoundError: The URI is not a well-formed
            ``aeat://<kind>/<name>`` reference (wrong scheme, unknown kind, or a
            missing name segment).
    """
    if not uri.startswith(_URI_PREFIX):
        raise HarnessResourceNotFoundError(f"not an aeat resource URI: {uri!r}")
    kind_token, _, name = uri[len(_URI_PREFIX) :].partition("/")
    if not name:
        raise HarnessResourceNotFoundError(f"resource URI carries no name: {uri!r}")
    try:
        kind = HarnessResourceKind(kind_token)
    except ValueError as exc:
        accepted = ", ".join(member.value for member in HarnessResourceKind)
        raise HarnessResourceNotFoundError(
            f"unknown resource kind {kind_token!r} in {uri!r}; accepted: {accepted}",
        ) from exc
    return kind, name


def read_harness_resource(uri: str) -> HarnessResourceContent:
    """Resolve an ``aeat://<kind>/<name>`` URI to its shipped document text.

    Raises:
        HarnessResourceNotFoundError: The URI is malformed or names a document
            that is not in the shipped tree.

    Returns:
        A :class:`HarnessResourceContent`.
    """
    kind, name = _parse_uri(uri)
    if kind is HarnessResourceKind.CORPUS:
        return _read_corpus_resource(name, uri)
    for entry_kind, entry_name, document in _iter_entries():
        if entry_kind is kind and entry_name == name:
            return HarnessResourceContent(
                ref=_ref_for(kind, name),
                text=document.read_text(encoding=_UTF_8),
            )
    raise HarnessResourceNotFoundError(f"no shipped {kind.value} named {name!r} ({uri})")


def _read_corpus_resource(ref: str, uri: str) -> HarnessResourceContent:
    """Resolve an ``aeat://corpus/<ref>`` URI to verbatim bundled legal text.

    ``ref`` is a citation id or a retrieval ``corpus_ref``; resolution routes
    through the registry legal catalogue (the single citation authority).
    """
    from ...application.corpus_search import CorpusSearchInputError, bundled_citation_lookup

    try:
        text = bundled_citation_lookup().resolve_corpus_text(ref)
    except CorpusSearchInputError as exc:
        raise HarnessResourceNotFoundError(f"no corpus text for {ref!r} ({uri})") from exc
    return HarnessResourceContent(ref=_ref_for(HarnessResourceKind.CORPUS, ref), text=text)


__all__ = [
    "HarnessResourceContent",
    "HarnessResourceKind",
    "HarnessResourceNotFoundError",
    "HarnessResourceRef",
    "HarnessResourceTemplate",
    "list_harness_resource_templates",
    "list_harness_resources",
    "read_harness_resource",
    "resource_uri",
]
