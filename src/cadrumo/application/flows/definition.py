"""Descriptor models for the paged interactive-flow substrate.

The strict frozen pydantic v2 records below compose a closed,
declarative description of a paged operator-facing flow: a
:class:`FlowDefinition` is a tuple of :class:`FlowSection` records; a
section holds :class:`FlowPage` and :class:`FlowRepeatingGroup` items;
each page declares exactly one :class:`FlowWidgetKind`, its copy
*references*, its validators by registered id, and the optional
declarative :class:`FlowCondition` gate over earlier answers.

Copy slots are :class:`CopyRef` references, never literal prose: the
render-time copy assembler resolves each reference against the bundled
locale catalogues, the profile/modelo schema definitions, or the
terminology concepts. The definition is the single source of truth read
by the flow engine, every frontend, and the domain-key projections; it
deliberately carries the one-shot wizard descriptor's vocabulary forward
(page ids, canonical-token answers, choice records, equals/contains
gates) so existing catalogues migrate by extension.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union, cast

from pydantic import BaseModel, Field, model_validator

from ...core.flows import (
    DEFER_TOKEN,
    CheckpointAvailability,
    CopyRefKind,
    FlowMode,
    FlowWidgetKind,
)
from ...core.hashing import content_hash_hex
from ...core.models import STRICT_FROZEN_CONFIG

_CHOICE_WIDGETS = frozenset(
    {FlowWidgetKind.SELECT, FlowWidgetKind.CHECKBOX, FlowWidgetKind.COMPARE_SELECT},
)


class CopyRef(BaseModel):
    """One reference into the bundled copy sources, resolved at render time.

    ``ref`` is a locale key (``wizard.setup.profile.tax-id.prompt``), a
    schema field path (``identity.tax_id``), or a terminology concept id
    (``tema-profile``) depending on ``kind``. The reference is resolved
    by the copy assembler; an unresolvable reference is a loud render
    failure, never a silent blank.
    """

    model_config = STRICT_FROZEN_CONFIG

    kind: CopyRefKind
    ref: str = Field(min_length=1)


class FlowLegalRef(BaseModel):
    """One structured legal citation shown on a page's provenance zone.

    ``ref`` is the registry legal-ref token (``ley-35-2006:art-27``); the
    optional ``label`` is a copy reference resolving to display text for
    the citation. The consuming domain stamps these at definition-build
    time — the substrate never derives a page's legal zone, it only
    resolves and renders what the definition carries.
    """

    model_config = STRICT_FROZEN_CONFIG

    ref: str = Field(min_length=1)
    label: CopyRef | None = None


class FlowCondition(BaseModel):
    """Single-clause predicate naming one earlier page's answer.

    Exactly one of ``equals`` / ``contains`` is set. ``equals`` tests
    the canonical token exactly; ``contains`` splits the parent's
    comma-joined CHECKBOX answer into a token set and tests membership.
    """

    model_config = STRICT_FROZEN_CONFIG

    page_id: str = Field(min_length=1)
    equals: str | None = None
    contains: str | None = None

    @model_validator(mode="after")
    def _validate_exactly_one_clause(self) -> FlowCondition:
        declared = [name for name, value in (("equals", self.equals), ("contains", self.contains)) if value is not None]
        if len(declared) != 1:
            raise ValueError(
                f"FlowCondition on {self.page_id!r} must declare exactly one of 'equals' / 'contains'; "
                f"got {declared or ['none']}",
            )
        return self


class FlowVisibility(BaseModel):
    """Disjunction of :class:`FlowCondition` clauses; visible when any holds."""

    model_config = STRICT_FROZEN_CONFIG

    any_of: tuple[FlowCondition, ...] = Field(min_length=1)


class FlowChoice(BaseModel):
    """One entry in a SELECT / CHECKBOX / COMPARE_SELECT closed choice set.

    For COMPARE_SELECT the choice is a labelled candidate value and
    ``provenance`` names where the candidate came from; the reserved
    defer arm is engine-provided and never declared as a choice.
    """

    model_config = STRICT_FROZEN_CONFIG

    value: str = Field(min_length=1)
    label: CopyRef
    description: CopyRef | None = None
    provenance: CopyRef | None = None

    @model_validator(mode="after")
    def _reject_reserved_defer_token(self) -> FlowChoice:
        if self.value == DEFER_TOKEN:
            raise ValueError(f"FlowChoice value {DEFER_TOKEN!r} is reserved for the engine's defer arm")
        return self


class FlowPage(BaseModel):
    """One full-page question in a flow.

    ``domain_key`` generalises the wizard's ``profile_key``: the
    dot-path the answer binds to in the consuming domain's schema, or
    ``None`` for a UI-only page. ``answer_validator_ids`` name
    registered pure validators run at commit time on top of the
    widget-level validation; ``failure_modes`` are rendered on the page
    so the operator sees how the input can go wrong before typing.
    """

    model_config = STRICT_FROZEN_CONFIG

    id: str = Field(min_length=1)
    widget: FlowWidgetKind
    prompt: CopyRef
    help: CopyRef | None = None
    format_hint: CopyRef | None = None
    failure_modes: tuple[CopyRef, ...] = ()
    legal_zone: tuple[FlowLegalRef, ...] = ()
    choices: tuple[FlowChoice, ...] = ()
    default: str | None = None
    required: bool = True
    visible_when: FlowCondition | FlowVisibility | None = None
    answer_type: type[str] | type[bool] | type[int] | type[Path]
    domain_key: str | None = None
    answer_validator_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate_choice_widgets(self) -> FlowPage:
        if self.widget in _CHOICE_WIDGETS and not self.choices:
            raise ValueError(f"FlowPage {self.id!r} declares {self.widget} but no choices")
        if self.widget not in _CHOICE_WIDGETS and self.choices:
            raise ValueError(f"FlowPage {self.id!r} declares choices for non-choice widget {self.widget}")
        if self.widget is FlowWidgetKind.COMPARE_SELECT:
            missing = [choice.value for choice in self.choices if choice.provenance is None]
            if missing:
                raise ValueError(
                    f"FlowPage {self.id!r} COMPARE_SELECT candidates without provenance: {', '.join(missing)}",
                )
        return self


class FlowRepeatingGroup(BaseModel):
    """A sub-page group instantiated N times (descendientes, actividades, ...).

    ``count_from`` names an earlier INTEGER page whose answer drives the
    instance count; the review surface may also add and remove
    instances. Instance answers key the canonical map as
    ``<group-id>#<index>.<page-id>`` and participate individually in
    validation, staleness, and review.
    """

    model_config = STRICT_FROZEN_CONFIG

    id: str = Field(min_length=1)
    title: CopyRef
    count_from: str = Field(min_length=1)
    pages: tuple[FlowPage, ...] = Field(min_length=1)
    max_instances: int = Field(default=50, ge=1)


type FlowItem = Union[FlowPage, FlowRepeatingGroup]  # noqa: UP007 - pydantic discriminates the runtime union


class FlowSection(BaseModel):
    """One grouped sequence of pages inside a flow.

    ``exit_validator_ids`` name registered cross-field validators run
    when the operator leaves the section; a failing verdict blocks
    forward navigation with a typed, rendered result.
    """

    model_config = STRICT_FROZEN_CONFIG

    id: str = Field(min_length=1)
    title: CopyRef
    items: tuple[FlowItem, ...] = Field(min_length=1)
    exit_validator_ids: tuple[str, ...] = ()


class FlowDefinition(BaseModel):
    """The top-level descriptor for one paged flow surface.

    ``intro`` is an optional opening-copy slot the line-mode frontend
    renders before the first page; ``None`` is a definition-level decision
    that the flow opens with no preamble, never a silent humanised key.
    ``checkpoint`` is the per-mode declaration: ``UNAVAILABLE`` is the
    declared no-op arm the frontend must surface honestly.
    ``flow_validator_ids`` name registered flow-scope cross-field
    validators run at the review surface; submission requires every one
    to pass alongside the per-page and staleness gates.
    """

    model_config = STRICT_FROZEN_CONFIG

    id: str = Field(min_length=1)
    title: CopyRef
    description: CopyRef
    intro: CopyRef | None = None
    sections: tuple[FlowSection, ...] = Field(min_length=1)
    answers_model: type[BaseModel]
    checkpoint: dict[FlowMode, CheckpointAvailability]
    flow_validator_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate_checkpoint_covers_modes(self) -> FlowDefinition:
        missing = [mode.value for mode in FlowMode if mode not in self.checkpoint]
        if missing:
            raise ValueError(f"FlowDefinition {self.id!r} missing checkpoint declaration for modes: {missing}")
        return self

    @model_validator(mode="after")
    def _validate_unique_ids(self) -> FlowDefinition:
        seen: set[str] = set()
        duplicates: list[str] = []
        for identifier in _iter_page_ids(self):
            if identifier in seen:
                duplicates.append(identifier)
            seen.add(identifier)
        if duplicates:
            raise ValueError(f"FlowDefinition {self.id!r} has duplicate page ids: {', '.join(sorted(duplicates))}")
        return self

    @model_validator(mode="after")
    def _validate_visible_when_targets(self) -> FlowDefinition:
        """Every gate clause must name an earlier page so the engine holds the parent answer.

        The same invariant is enforced over a different model by the wizard
        catalogue's ``WizardFlow._validate_visible_when_targets``. The two exist
        because the models differ, not by oversight: that one runs at
        catalogue-authoring time and names the offending QUESTIONS, before the
        bridge into this definition, so it reports against the vocabulary the
        author wrote. This one is the only check that sees pages spliced in
        after the bridge — a repeating group authored directly in
        :class:`FlowPage` vocabulary never passed through a ``WizardFlow``.

        Change the rule here and the sibling silently keeps enforcing the old
        one; they are linked by this note and nothing else.
        """
        order: dict[str, int] = {}
        for index, (page, _group) in enumerate(_iter_pages_with_group(self)):
            order[page.id] = index

        bad: list[str] = []
        for position, (page, _group) in enumerate(_iter_pages_with_group(self)):
            for clause in iter_flow_conditions(page.visible_when):
                target = order.get(clause.page_id)
                if target is None or target >= position:
                    bad.append(f"{page.id}->{clause.page_id}")
        if bad:
            raise ValueError(
                f"FlowDefinition {self.id!r} has visible_when references that do not resolve to earlier pages: "
                f"{', '.join(bad)}",
            )
        return self

    @model_validator(mode="after")
    def _validate_repeating_count_sources(self) -> FlowDefinition:
        """A repeating group's count source is an earlier top-level INTEGER page."""
        integer_pages_seen: set[str] = set()
        bad: list[str] = []
        for section in self.sections:
            for item in section.items:
                if isinstance(item, FlowPage):
                    if item.widget is FlowWidgetKind.INTEGER:
                        integer_pages_seen.add(item.id)
                    continue
                if item.count_from not in integer_pages_seen:
                    bad.append(f"{item.id}->{item.count_from}")
        if bad:
            raise ValueError(
                f"FlowDefinition {self.id!r} has repeating groups whose count_from does not name an earlier "
                f"INTEGER page: {', '.join(bad)}",
            )
        return self

    @property
    def fingerprint(self) -> str:
        """Stable content identity of the declarative definition.

        A convenience identity for callers that want to label or compare
        definitions (diagnostics, caching). Resume deliberately does
        NOT consume it: definition change is detected by re-validating
        every persisted answer against the current definition, so no
        fingerprint is ever stored. Hashes the declarative content only;
        the ``answers_model`` type is identified by its qualified name
        so two builds of the same definition fingerprint identically.
        """
        payload = self.model_dump(mode="python", exclude={"answers_model"})
        payload["answers_model"] = f"{self.answers_model.__module__}.{self.answers_model.__qualname__}"
        return content_hash_hex(_normalise_fingerprint_types(payload))


def _normalise_fingerprint_types(value: object) -> object:
    """Replace the definition's type declarations with their stable domain tokens."""
    if isinstance(value, type):
        return f"{value.__module__}.{value.__qualname__}"
    if isinstance(value, dict):
        payload = cast(dict[str, object], value)
        return {key: _normalise_fingerprint_types(item) for key, item in payload.items()}
    if isinstance(value, tuple):
        values = cast(tuple[object, ...], value)
        return tuple(_normalise_fingerprint_types(item) for item in values)
    if isinstance(value, list):
        values = cast(list[object], value)
        return [_normalise_fingerprint_types(item) for item in values]
    return value


def iter_flow_conditions(
    visible_when: FlowCondition | FlowVisibility | None,
) -> tuple[FlowCondition, ...]:
    """Normalise the three ``visible_when`` shapes into a flat clause tuple."""
    if visible_when is None:
        return ()
    if isinstance(visible_when, FlowCondition):
        return (visible_when,)
    return visible_when.any_of


def _iter_pages_with_group(
    definition: FlowDefinition,
) -> tuple[tuple[FlowPage, FlowRepeatingGroup | None], ...]:
    """Flatten the definition into ``(page, owning-group-or-None)`` pairs in walk order."""
    result: list[tuple[FlowPage, FlowRepeatingGroup | None]] = []
    for section in definition.sections:
        for item in section.items:
            if isinstance(item, FlowPage):
                result.append((item, None))
            else:
                result.extend((page, item) for page in item.pages)
    return tuple(result)


def _iter_page_ids(definition: FlowDefinition) -> tuple[str, ...]:
    ids: list[str] = []
    for section in definition.sections:
        for item in section.items:
            if isinstance(item, FlowPage):
                ids.append(item.id)
            else:
                ids.append(item.id)
                ids.extend(page.id for page in item.pages)
    return tuple(ids)


def iter_flow_pages(definition: FlowDefinition) -> tuple[FlowPage, ...]:
    """Return every page in a definition, flattening repeating groups in order.

    Lives with the types it walks. Two wizard modules each carried this loop,
    which meant two places had to agree that a repeating group contributes its
    pages rather than itself.
    """
    pages: list[FlowPage] = []
    for section in definition.sections:
        for item in section.items:
            if isinstance(item, FlowRepeatingGroup):
                pages.extend(item.pages)
            else:
                pages.append(item)
    return tuple(pages)


def locale_copy_ref(key: str) -> CopyRef:
    """Return the copy reference for a locale key.

    Lives with :class:`CopyRef` because four modules each built this same
    two-field construction, which meant four places encoded that a locale key is
    carried by the LOCALE_KEY kind.
    """
    return CopyRef(kind=CopyRefKind.LOCALE_KEY, ref=key)


__all__ = [
    "CopyRef",
    "FlowChoice",
    "FlowCondition",
    "FlowDefinition",
    "FlowItem",
    "FlowLegalRef",
    "FlowPage",
    "FlowRepeatingGroup",
    "FlowSection",
    "FlowVisibility",
    "iter_flow_conditions",
    "iter_flow_pages",
    "locale_copy_ref",
]
