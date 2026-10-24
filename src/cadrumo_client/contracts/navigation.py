"""The navigation register behind ``cadrumo://view/{id}`` links and every palette.

The register is neutral data in ``navigation.toml``, packaged beside this
module: each element has an id that is also its link path, an optional parent,
one label locale key, search keywords and the surfaces that implement it
(``gui`` for the window, ``tui`` for the terminal workbench). An element may
also declare link parameters, each taking values of one register-declared
value kind, such as ``select`` taking an invoice id. The register never says
how a surface implements an element; each surface keeps its own id table.

Parameters are presentation only: they show, select or focus something. No
parameter edits, submits, confirms or answers anything, and a link grants
nothing. A link carries no profile.

This module is the one reader of that file and the one spelling of its links.
:func:`load_navigation_register` validates the whole file or refuses it.
:func:`view_link` formats a link for a registered element, :func:`parse_view_link`
reads one strictly, and :func:`resolve_view` chooses where it opens.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from functools import cached_property, lru_cache
from importlib.resources import files  # nosemgrep
from pathlib import Path
from types import MappingProxyType
from typing import Final, Literal, Self

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from cadrumo.core.models import STRICT_FROZEN_CONFIG
from cadrumo.core.toml import TomlDecodeError, parse_toml
from cadrumo.core.type_guards import is_object_list

NAVIGATION_SCHEMA_VERSION: Final = 1
"""The register layout this loader reads; any other ``schema`` is refused."""

VIEW_LINK_PREFIX: Final = "cadrumo://view/"
"""The scheme and namespace every view link starts with."""

MAX_VIEW_LINK_LENGTH: Final = 512
"""The longest link, in characters, the parser reads."""

MAX_VIEW_ID_SEGMENTS: Final = 4
"""The deepest element path a register id or link may name."""

MAX_VALUE_LENGTH: Final = 256
"""The longest value a value kind may declare."""

PREFER_KEY: Final = "prefer"
"""The link query key, reserved on every element, that names the surface the link asks for."""

_SEGMENT: Final = r"[a-z0-9]+(?:-[a-z0-9]+)*"
_VIEW_ID: Final = re.compile(rf"{_SEGMENT}(?:/{_SEGMENT}){{0,{MAX_VIEW_ID_SEGMENTS - 1}}}")
_NAME: Final = re.compile(_SEGMENT)
_LABEL_KEY: Final = re.compile(r"[a-z0-9_]+(?:\.[a-z0-9_]+)+")
# A value travels unescaped in a lowercase link, so a value alphabet holds only
# characters that are lowercase and carry no meaning in the link syntax.
_VALUE_ALPHABET: Final = frozenset("abcdefghijklmnopqrstuvwxyz0123456789-_.~")
_PRINTABLE_ASCII: Final = re.compile(r"[!-~]+")
_REGISTER_RESOURCE: Final = "navigation.toml"


class NavigationSurface(StrEnum):
    """An interface that can open a register element."""

    GUI = "gui"
    TUI = "tui"


class NavigationRegisterError(ValueError):
    """The register file is unreadable or breaks one of its rules."""


def _tuple_from_toml(value: object) -> object:
    """Turn a TOML array into the tuple a strict frozen field requires."""
    return tuple(value) if is_object_list(value) else value


class ValueKind(BaseModel):
    """A kind of link parameter value and its exact shape: an alphabet and a fixed length."""

    model_config = STRICT_FROZEN_CONFIG

    name: str
    alphabet: str = Field(min_length=1)
    length: int = Field(ge=1, le=MAX_VALUE_LENGTH)

    @field_validator("name")
    @classmethod
    def _name_grammar(cls, value: str) -> str:
        if _NAME.fullmatch(value) is None:
            raise ValueError(f"value kind {value!r} is not a lowercase hyphenated word")
        return value

    @field_validator("alphabet")
    @classmethod
    def _link_safe_alphabet(cls, value: str) -> str:
        unsafe = sorted(set(value) - _VALUE_ALPHABET)
        if unsafe:
            raise ValueError(f"value alphabet carries characters a link cannot hold unescaped: {unsafe!r}")
        if len(set(value)) != len(value):
            raise ValueError("a value alphabet lists each character once")
        return value

    def admits(self, value: str) -> bool:
        """Whether ``value`` has exactly this kind's shape."""
        return len(value) == self.length and set(value) <= set(self.alphabet)


class NavigationElement(BaseModel):
    """One navigable element: its link path, place in the tree, label, surfaces and link parameters."""

    model_config = STRICT_FROZEN_CONFIG

    id: str
    parent: str | None = None
    label: str
    keywords: str
    surfaces: tuple[NavigationSurface, ...] = Field(min_length=1)
    params: Mapping[str, str] = Field(default_factory=lambda: MappingProxyType({}))

    @field_validator("id")
    @classmethod
    def _id_grammar(cls, value: str) -> str:
        if _VIEW_ID.fullmatch(value) is None:
            raise ValueError(f"element id {value!r} is not one to four lowercase segments joined by '/'")
        return value

    @field_validator("label")
    @classmethod
    def _label_key_grammar(cls, value: str) -> str:
        if _LABEL_KEY.fullmatch(value) is None:
            raise ValueError(f"label {value!r} is not a dotted locale key")
        return value

    @field_validator("surfaces", mode="before")
    @classmethod
    def _surfaces_from_toml(cls, value: object) -> object:
        # Strict mode admits only enum members, so map the known spellings and
        # leave anything else for the strict check to refuse.
        if is_object_list(value):
            members = {surface.value: surface for surface in NavigationSurface}
            return tuple(members.get(item, item) if isinstance(item, str) else item for item in value)
        return value

    @field_validator("surfaces")
    @classmethod
    def _surfaces_unique(cls, value: tuple[NavigationSurface, ...]) -> tuple[NavigationSurface, ...]:
        if len(set(value)) != len(value):
            raise ValueError("an element names each surface at most once")
        return value

    @field_validator("params")
    @classmethod
    def _param_names(cls, value: Mapping[str, str]) -> Mapping[str, str]:
        if PREFER_KEY in value:
            raise ValueError(f"parameter {PREFER_KEY!r} is reserved for every element")
        malformed = sorted(name for name in value if _NAME.fullmatch(name) is None)
        if malformed:
            raise ValueError(f"parameter names {malformed!r} are not lowercase hyphenated words")
        return MappingProxyType(dict(value))

    @model_validator(mode="after")
    def _parent_is_the_enclosing_path(self) -> Self:
        enclosing, _, _ = self.id.rpartition("/")
        if not enclosing and self.parent is not None:
            raise ValueError(f"root element {self.id!r} names a parent")
        if enclosing and self.parent != enclosing:
            raise ValueError(f"element {self.id!r} must name its enclosing path {enclosing!r} as parent")
        return self


class NavigationRegister(BaseModel):
    """The whole register: schema version, retired ids, value kinds and elements in declaration order."""

    model_config = STRICT_FROZEN_CONFIG

    schema_version: int = Field(alias="schema")
    retired: tuple[str, ...]
    kinds: tuple[ValueKind, ...] = Field(default=(), alias="kind")
    elements: tuple[NavigationElement, ...] = Field(alias="element", min_length=1)

    @field_validator("retired", "kinds", "elements", mode="before")
    @classmethod
    def _arrays_from_toml(cls, value: object) -> object:
        return _tuple_from_toml(value)

    @field_validator("schema_version")
    @classmethod
    def _known_schema(cls, value: int) -> int:
        if value != NAVIGATION_SCHEMA_VERSION:
            raise ValueError(f"register schema {value} is not {NAVIGATION_SCHEMA_VERSION}")
        return value

    @field_validator("retired")
    @classmethod
    def _retired_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        malformed = [item for item in value if _VIEW_ID.fullmatch(item) is None]
        if malformed:
            raise ValueError(f"retired ids {malformed!r} are not register ids")
        if len(set(value)) != len(value):
            raise ValueError("a retired id is listed once")
        return value

    @field_validator("kinds")
    @classmethod
    def _unique_kinds(cls, value: tuple[ValueKind, ...]) -> tuple[ValueKind, ...]:
        names = [kind.name for kind in value]
        duplicated = sorted({name for name in names if names.count(name) > 1})
        if duplicated:
            raise ValueError(f"value kinds {duplicated!r} are declared more than once")
        return value

    @model_validator(mode="after")
    def _closed_tree(self) -> Self:
        ids = [element.id for element in self.elements]
        duplicated = sorted({item for item in ids if ids.count(item) > 1})
        if duplicated:
            raise ValueError(f"element ids {duplicated!r} are declared more than once")
        reused = sorted(set(ids) & set(self.retired))
        if reused:
            raise ValueError(f"retired ids {reused!r} are declared again")
        declared = set(ids)
        orphans = sorted(
            element.id for element in self.elements if element.parent is not None and element.parent not in declared
        )
        if orphans:
            raise ValueError(f"elements {orphans!r} name a parent the register does not declare")
        kinds = {kind.name for kind in self.kinds}
        undeclared = sorted(
            element.id for element in self.elements if any(kind not in kinds for kind in element.params.values())
        )
        if undeclared:
            raise ValueError(f"elements {undeclared!r} take a value kind the register does not declare")
        return self

    @cached_property
    def _by_id(self) -> Mapping[str, NavigationElement]:
        return MappingProxyType({element.id: element for element in self.elements})

    @cached_property
    def _kinds_by_name(self) -> Mapping[str, ValueKind]:
        return MappingProxyType({kind.name: kind for kind in self.kinds})

    @cached_property
    def param_names(self) -> frozenset[str]:
        """Every parameter name some element declares."""
        return frozenset(name for element in self.elements for name in element.params)

    def element(self, view_id: str) -> NavigationElement | None:
        """Return the element ``view_id`` names, or ``None`` when it names none."""
        return self._by_id.get(view_id)

    def value_kind(self, name: str) -> ValueKind:
        """Return a declared value kind.

        Raises:
            KeyError: No value kind of that name is declared.
        """
        return self._kinds_by_name[name]

    def ids_for(self, surface: NavigationSurface) -> frozenset[str]:
        """Return every id whose element the given surface implements."""
        return frozenset(element.id for element in self.elements if surface in element.surfaces)

    def lineage(self, view_id: str) -> tuple[NavigationElement, ...]:
        """Return the element and then its ancestors, nearest first.

        Raises:
            KeyError: ``view_id`` names no element.
        """
        chain: list[NavigationElement] = []
        current: str | None = view_id
        while current is not None:
            element = self._by_id[current]
            chain.append(element)
            current = element.parent
        return tuple(chain)


@lru_cache(maxsize=1)
def load_navigation_register(path: Path | None = None) -> NavigationRegister:
    """Return the validated register, read once per process.

    The packaged ``navigation.toml`` is read through ``importlib.resources``
    so editable installs and wheels resolve it the same way. ``path`` is for
    tests and tools that validate another file against the same rules.

    Raises:
        NavigationRegisterError: The file cannot be read or breaks a register rule.
    """
    try:
        if path is None:
            text = files(__package__).joinpath(_REGISTER_RESOURCE).read_text(encoding="utf-8")
        else:
            text = path.read_text(encoding="utf-8")
        return NavigationRegister.model_validate(parse_toml(text))
    except (OSError, UnicodeDecodeError, TomlDecodeError, ValidationError) as error:
        raise NavigationRegisterError(f"navigation register refused: {error}") from error


type ViewParams = tuple[tuple[str, str], ...]
"""Link parameters as ``(name, value)`` pairs sorted by name."""


class ViewLinkRefusal(StrEnum):
    """Why a text is not a view link the window or the TUI may open."""

    TOO_LONG = "too_long"
    MALFORMED = "malformed"
    UPPERCASE = "uppercase"
    NOT_A_VIEW_LINK = "not_a_view_link"
    CREDENTIALS = "credentials"
    PERCENT_ENCODING = "percent_encoding"
    FRAGMENT = "fragment"
    QUERY = "query"
    TOO_MANY_SEGMENTS = "too_many_segments"
    UNKNOWN_VIEW = "unknown_view"
    UNKNOWN_PARAM = "unknown_param"
    PARAM_NOT_ACCEPTED = "param_not_accepted"
    PARAM_MALFORMED = "param_malformed"


def _param_refusal(register: NavigationRegister, view_id: str, params: ViewParams) -> ViewLinkRefusal | None:
    """Return the first rule the parameters break for this element, checked in name order."""
    element = register.element(view_id)
    if element is None:
        return ViewLinkRefusal.UNKNOWN_VIEW
    for name, value in params:
        if name not in register.param_names:
            return ViewLinkRefusal.UNKNOWN_PARAM
        kind = element.params.get(name)
        if kind is None:
            return ViewLinkRefusal.PARAM_NOT_ACCEPTED
        if not register.value_kind(kind).admits(value):
            return ViewLinkRefusal.PARAM_MALFORMED
    return None


def view_request_refusal(
    view_id: str, params: Mapping[str, str], *, register: NavigationRegister | None = None
) -> ViewLinkRefusal | None:
    """Return the first rule a request for ``view_id`` with ``params`` breaks, as a parsed link is checked.

    The element must be registered, and each parameter, in name order, must
    be one some element declares, one this element takes, and a value of its
    kind. ``None`` means the register admits the request.
    """
    return _param_refusal(register or load_navigation_register(), view_id, tuple(sorted(params.items())))


def view_link(
    view_id: str,
    params: Mapping[str, str] | None = None,
    prefer: NavigationSurface | None = None,
    *,
    register: NavigationRegister | None = None,
) -> str:
    """Spell the link that opens one registered element with its parameters and a preferred surface.

    Parameters are written in name order, then ``prefer``.

    Raises:
        ValueError: ``view_id`` names no registered element, or a parameter
            is not one the element declares with a value of its kind.
    """
    pairs: ViewParams = () if params is None else tuple(sorted(params.items()))
    refusal = _param_refusal(register or load_navigation_register(), view_id, pairs)
    if refusal is not None:
        raise ValueError(f"cannot link to view {view_id!r}: {refusal.value}")
    query = [f"{name}={value}" for name, value in pairs]
    if prefer is not None:
        query.append(f"{PREFER_KEY}={prefer.value}")
    link = f"{VIEW_LINK_PREFIX}{view_id}"
    return f"{link}?{'&'.join(query)}" if query else link


@dataclass(frozen=True, slots=True)
class ViewLink:
    """A view request: the element, its parameters in name order, and the surface it asks for, if any."""

    view_id: str
    params: ViewParams = ()
    prefer: NavigationSurface | None = None


@dataclass(frozen=True, slots=True)
class ViewLinkRefused:
    """A text the parser refused, with the first rule it broke."""

    reason: ViewLinkRefusal


def parse_view_link(text: str, *, register: NavigationRegister | None = None) -> ViewLink | ViewLinkRefused:
    """Read one ``cadrumo://view/{id}`` link and its query, or refuse it.

    The query holds at most one of each key the element declares plus
    ``prefer``, in any order. Checks run in a fixed order and the first
    broken rule is the reason, so every implementation of this grammar
    refuses a text for the same reason: whole-text rules, then the query's
    shape and ``prefer`` value, then the path, then each parameter in name
    order against the element.
    """
    refusal = _link_syntax_refusal(text)
    if refusal is not None:
        return ViewLinkRefused(refusal)
    path, has_query, query = text.removeprefix(VIEW_LINK_PREFIX).partition("?")
    pairs = _query_pairs(query) if has_query else {}
    if pairs is None:
        return ViewLinkRefused(ViewLinkRefusal.QUERY)
    if len(path.split("/")) > MAX_VIEW_ID_SEGMENTS:
        return ViewLinkRefused(ViewLinkRefusal.TOO_MANY_SEGMENTS)
    if _VIEW_ID.fullmatch(path) is None:
        return ViewLinkRefused(ViewLinkRefusal.MALFORMED)
    prefer = pairs.pop(PREFER_KEY, None)
    params: ViewParams = tuple(sorted(pairs.items()))
    refusal = _param_refusal(register or load_navigation_register(), path, params)
    if refusal is not None:
        return ViewLinkRefused(refusal)
    return ViewLink(view_id=path, params=params, prefer=None if prefer is None else NavigationSurface(prefer))


def _link_syntax_refusal(text: str) -> ViewLinkRefusal | None:
    """Return the first whole-text rule ``text`` breaks, before its path is read."""
    if len(text) > MAX_VIEW_LINK_LENGTH:
        return ViewLinkRefusal.TOO_LONG
    if _PRINTABLE_ASCII.fullmatch(text) is None:
        return ViewLinkRefusal.MALFORMED
    if text != text.lower():
        return ViewLinkRefusal.UPPERCASE
    if not text.startswith("cadrumo://"):
        return ViewLinkRefusal.NOT_A_VIEW_LINK
    authority = text.removeprefix("cadrumo://").partition("/")[0]
    if "@" in authority:
        return ViewLinkRefusal.CREDENTIALS
    if not text.startswith(VIEW_LINK_PREFIX):
        return ViewLinkRefusal.NOT_A_VIEW_LINK
    if "%" in text:
        return ViewLinkRefusal.PERCENT_ENCODING
    if "#" in text:
        return ViewLinkRefusal.FRAGMENT
    return None


def _query_pairs(query: str) -> dict[str, str] | None:
    """Return the query's ``key=value`` pairs, or ``None`` when it breaks the query's shape.

    Every pair has a key in the name grammar and a non-empty value; no key
    repeats; ``prefer`` names a surface. Whether the element takes a key and
    its value's kind are checked later, against the element.
    """
    pairs: dict[str, str] = {}
    for pair in query.split("&"):
        key, has_value, value = pair.partition("=")
        if not has_value or not value or "=" in value or "?" in value:
            return None
        if _NAME.fullmatch(key) is None or key in pairs:
            return None
        pairs[key] = value
    surface = pairs.get(PREFER_KEY)
    if surface is not None and surface not in {member.value for member in NavigationSurface}:
        return None
    return pairs


@dataclass(frozen=True, slots=True)
class SurfaceImplementation:
    """What one surface can open now: element ids, and per element the parameter names it honours."""

    views: frozenset[str]
    params: Mapping[str, frozenset[str]] = field(default_factory=lambda: MappingProxyType({}))

    def honours(self, view_id: str, names: frozenset[str]) -> bool:
        """Whether this surface opens ``view_id`` honouring every named parameter."""
        return view_id in self.views and names <= self.params.get(view_id, frozenset())


type ViewFallback = Literal["none", "other_surface", "ancestor"]
"""Which element and surface opened compared with the request: as asked, the other surface, or an ancestor."""


@dataclass(frozen=True, slots=True)
class ViewOpened:
    """Where a view request opens, the parameters passed on, and how that differs from the request."""

    requested: ViewLink
    opened: str
    surface: NavigationSurface
    fallback: ViewFallback
    params: ViewParams

    @property
    def notice_due(self) -> bool:
        """Whether the person must be told the view opened other than asked."""
        return self.fallback != "none" or self.params != self.requested.params


type ViewRefusalReason = Literal[
    "unknown_view", "unknown_param", "param_not_accepted", "param_malformed", "not_implemented"
]
"""Why no surface opens a request: it breaks the register, or nothing on its path is implemented."""


_REGISTER_REFUSALS: Final[Mapping[ViewLinkRefusal, ViewRefusalReason]] = MappingProxyType(
    {
        ViewLinkRefusal.UNKNOWN_VIEW: "unknown_view",
        ViewLinkRefusal.UNKNOWN_PARAM: "unknown_param",
        ViewLinkRefusal.PARAM_NOT_ACCEPTED: "param_not_accepted",
        ViewLinkRefusal.PARAM_MALFORMED: "param_malformed",
    }
)


@dataclass(frozen=True, slots=True)
class ViewRefused:
    """A view request no surface can open, with the reason the person is told."""

    requested: ViewLink
    reason: ViewRefusalReason


def resolve_view(
    request: ViewLink,
    implemented: Mapping[NavigationSurface, SurfaceImplementation] | None = None,
    *,
    register: NavigationRegister | None = None,
) -> ViewOpened | ViewRefused:
    """Choose the surface and element a view request opens.

    The preferred surface is the window unless the request asks for the TUI.
    In order, the first that applies opens:

    1. the preferred surface, honouring the element and every parameter;
    2. the other surface, honouring them all, with a notice;
    3. the element without its parameters, on the preferred surface and then
       the other, with a notice that they were dropped;
    4. the nearest ancestor, on the preferred surface and then the other,
       without parameters and with a notice.

    Otherwise the request is refused. ``implemented`` says what each surface
    can open now; it defaults to the surfaces the register declares, each
    honouring every parameter its elements declare. A surface missing from
    the mapping implements nothing.
    """
    active = register or load_navigation_register()
    refusal = _param_refusal(active, request.view_id, request.params)
    if refusal is not None:
        return ViewRefused(requested=request, reason=_REGISTER_REFUSALS[refusal])
    surfaces = implemented if implemented is not None else _declared_implementation(active)
    first = request.prefer or NavigationSurface.GUI
    order = (first, NavigationSurface.TUI if first is NavigationSurface.GUI else NavigationSurface.GUI)
    names = frozenset(name for name, _ in request.params)

    def honours(surface: NavigationSurface, view_id: str, wanted: frozenset[str]) -> bool:
        implementation = surfaces.get(surface)
        return implementation is not None and implementation.honours(view_id, wanted)

    def same_element(surface: NavigationSurface, params: ViewParams) -> ViewOpened:
        fallback: ViewFallback = "none" if surface is first else "other_surface"
        return ViewOpened(request, request.view_id, surface, fallback, params)

    for surface in order:
        if honours(surface, request.view_id, names):
            return same_element(surface, request.params)
    if names:
        for surface in order:
            if honours(surface, request.view_id, frozenset()):
                return same_element(surface, ())
    for ancestor in active.lineage(request.view_id)[1:]:
        for surface in order:
            if honours(surface, ancestor.id, frozenset()):
                return ViewOpened(request, ancestor.id, surface, "ancestor", ())
    return ViewRefused(requested=request, reason="not_implemented")


def _declared_implementation(register: NavigationRegister) -> Mapping[NavigationSurface, SurfaceImplementation]:
    """Return what each surface implements according to the register alone."""
    return {
        surface: SurfaceImplementation(
            views=register.ids_for(surface),
            params=MappingProxyType(
                {element.id: frozenset(element.params) for element in register.elements if surface in element.surfaces}
            ),
        )
        for surface in NavigationSurface
    }
