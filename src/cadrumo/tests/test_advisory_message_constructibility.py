"""Every advisory message must be constructible against its own declared cap.

An advisory that cannot be built is worse than one that is merely wrong,
because nothing crashes: no exception, no log, no operator report. The message
simply never exists, and any decision made on the promise that it would fire is
resting on nothing. That is not hypothetical here -- a campaign permitted a
legal state on exactly such a promise, and the advisory carried a static floor
of 528 characters against a 512-character cap. No input could ever have
produced it.

Two shapes cross the same cap and they fail differently:

* **Variable-length interpolation.** A list of ids or names grows with taxpayer
  data and crosses the cap at some item count. Loud, late, and findable -- it
  raises the moment a real household is big enough. Three shipped in one day.
* **Static over-cap.** The literal prose alone exceeds the cap, so the message
  is unconstructible at *any* input. Silent and permanent.

This gate targets the second, because it is the one no runtime signal can
surface and the one a length check on a constructed message can never see: you
cannot measure a string you were never able to build.

The instrument is a lower bound. For every f-string assigned to a
length-capped operator-prose field, the literal segments are summed and the
interpolated ones counted as zero. That total is the shortest the message can
possibly be, whatever the data. If the floor alone exceeds the cap the message
is unconstructible, and the finding is certain rather than probabilistic --
there is no input that rescues it.

The bound is deliberately generous: it under-reports (a message whose floor
fits may still overflow once its data arrives) and never over-reports. A gate
that cried wolf on messages that merely *might* be long would be switched off,
and the shape it exists to catch does not need the extra sensitivity.

Caps are read from the owning pydantic field, never restated. A gate carrying
its own copy of the limit stops agreeing with reality the moment the model
moves, and would then be measuring against a number nothing enforces.

See Also:
    :mod:`cadrumo.application.aggregation._source_mesh`
        Carries the one eliding validator, which retires the variable-length
        shape for its own model by making the cap a property of the type.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import pkgutil
import warnings
from typing import TYPE_CHECKING, NamedTuple

import pytest
from pydantic import BaseModel

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from pathlib import Path

#: Field names that carry prose an operator is meant to read. A cap on one of
#: these bounds a sentence, not an identifier, so a floor that breaches it
#: destroys meaning rather than truncating a token.
_PROSE_FIELDS: frozenset[str] = frozenset(
    {
        "message",
        "detail",
        "details",
        "note",
        "summary",
        "description",
        "suggestion",
    },
)


class _Builder(NamedTuple):
    """One site that assembles a capped prose field from an f-string."""

    model: str
    field: str
    cap: int
    static_floor: int
    interpolations: int
    location: str

    @property
    def is_constructible(self) -> bool:
        """Whether any input at all could satisfy the field's cap."""
        return self.static_floor <= self.cap

    @property
    def headroom(self) -> int:
        """Characters left for every interpolated term combined."""
        return self.cap - self.static_floor


def _prose_caps() -> Mapping[tuple[str, str], int]:
    """Return ``(model name, field name) -> max_length`` for every capped prose field.

    Read from the live pydantic models so the gate and the constraint can never
    disagree. Keyed on the bare class name because the AST scan sees a call
    target, not an import path; a name collision across modules would merely
    make the gate stricter, never blinder.
    """
    warnings.filterwarnings("ignore")
    from .. import __path__ as cadrumo_path

    caps: dict[tuple[str, str], int] = {}
    for module_info in pkgutil.walk_packages(cadrumo_path, "cadrumo."):
        if ".tests" in module_info.name:
            continue
        try:
            module = importlib.import_module(module_info.name)
        except Exception:  # noqa: S112 - see below
            # A module that will not import carries no discoverable cap, and an
            # optional-dependency import error is not this gate's business.
            # Swallowed rather than logged because the corpus-population and
            # multi-model controls above already fail loudly if enough modules
            # drop out for the scan to stop being tree-wide -- which is the only
            # consequence that matters here.
            continue
        for obj in vars(module).values():
            if not (inspect.isclass(obj) and issubclass(obj, BaseModel) and obj is not BaseModel):
                continue
            for field_name, field in obj.model_fields.items():
                if field_name not in _PROSE_FIELDS:
                    continue
                for meta in getattr(field, "metadata", []) or []:
                    max_length = getattr(meta, "max_length", None)
                    if max_length is not None:
                        caps[(obj.__name__, field_name)] = max_length
    return caps


def _joined_str_floor(node: ast.JoinedStr) -> tuple[int, int]:
    """Return ``(literal characters, interpolation count)`` for an f-string.

    The literal total is the message's shortest possible length: every
    interpolated term is counted as contributing nothing, which is the only
    assumption that holds for all data.
    """
    literal = 0
    interpolations = 0
    for part in node.values:
        if isinstance(part, ast.Constant) and isinstance(part.value, str):
            literal += len(part.value)
        elif isinstance(part, ast.FormattedValue):
            interpolations += 1
    return literal, interpolations


def _concatenated_floor(node: ast.AST) -> tuple[int, int] | None:
    """Resolve implicit and explicit string concatenation into one floor.

    Long advisory prose is usually written as adjacent string literals across
    several lines, which the parser folds into one node, and sometimes as an
    explicit ``+`` chain. Both have to be measured or the gate would see a
    fraction of the real floor and report a message as constructible when its
    assembled form is not.
    """
    if isinstance(node, ast.JoinedStr):
        return _joined_str_floor(node)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return len(node.value), 0
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _concatenated_floor(node.left)
        right = _concatenated_floor(node.right)
        if left is None or right is None:
            return None
        return left[0] + right[0], left[1] + right[1]
    return None


def _builders(source_tree_ast: Mapping[Path, ast.AST]) -> Iterator[_Builder]:
    """Yield every site assembling a capped prose field, with its measured floor.

    Enumerates BUILDERS -- the expressions that assemble a message -- rather
    than the call sites that pass one around. A call site handling an
    already-built string cannot tell you whether it was buildable.
    """
    caps = _prose_caps()
    for path, tree in sorted(source_tree_ast.items()):
        if "/tests/" in path.as_posix() or path.name.startswith("test_"):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            target = node.func
            model_name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", None)
            if model_name is None:
                continue
            for keyword in node.keywords:
                if keyword.arg not in _PROSE_FIELDS:
                    continue
                cap = caps.get((model_name, keyword.arg))
                if cap is None:
                    continue
                measured = _concatenated_floor(keyword.value)
                if measured is None:
                    continue
                literal, interpolations = measured
                yield _Builder(
                    model=model_name,
                    field=keyword.arg,
                    cap=cap,
                    static_floor=literal,
                    interpolations=interpolations,
                    location=f"{path.as_posix().split('src/')[-1]}:{node.lineno}",
                )


@pytest.fixture(scope="module")
def advisory_builders(source_tree_ast: Mapping[Path, ast.AST]) -> tuple[_Builder, ...]:
    """The enumerated builder corpus, measured once for every assertion below."""
    return tuple(_builders(source_tree_ast))


def test_the_builder_corpus_is_populated(advisory_builders: tuple[_Builder, ...]) -> None:
    """The scan finds real builders.

    Without this the gate below passes vacuously the moment the walk breaks,
    an import fails, or a field is renamed -- an empty corpus satisfies every
    "all builders are constructible" assertion perfectly. This is the control
    that makes the rest of the module mean something.
    """
    assert advisory_builders, (
        "no advisory message builders were enumerated; the scan is broken and every "
        "constructibility assertion below is passing over an empty set"
    )


def test_the_corpus_covers_more_than_one_model(advisory_builders: tuple[_Builder, ...]) -> None:
    """Coverage is tree-wide, not one module that happens to match.

    A walk that silently narrowed to a single file would still populate the
    corpus and still pass the control above.
    """
    models = {builder.model for builder in advisory_builders}
    assert len(models) > 1, f"builders found for only one model ({models}); the scan is not tree-wide"


def test_the_floor_measurement_counts_multiline_prose(advisory_builders: tuple[_Builder, ...]) -> None:
    """At least one measured builder is long enough to prove concatenation is folded.

    Advisory prose is written as adjacent literals across several lines. If the
    measurement saw only the first fragment every floor would be a small
    fraction of the truth, the over-cap shape would be invisible, and the gate
    would report a clean tree while measuring almost nothing.
    """
    longest = max(builder.static_floor for builder in advisory_builders)
    assert longest > 200, (
        f"the longest measured static floor is {longest} characters, which is too short for "
        "real advisory prose -- string concatenation is probably not being folded"
    )


def test_every_advisory_message_is_constructible(advisory_builders: tuple[_Builder, ...]) -> None:
    """No advisory may carry a static floor above its own cap.

    A breach here is certain, not suspected: the floor counts every
    interpolated term as empty, so a message whose literals alone exceed the
    cap cannot be produced by any input. It is not a message that sometimes
    fails -- it is a message that has never existed, and anything relying on it
    firing has been relying on nothing.
    """
    unconstructible = [builder for builder in advisory_builders if not builder.is_constructible]
    assert unconstructible == [], "\n".join(
        [
            f"{len(unconstructible)} advisory message(s) cannot be constructed at any input:",
            *(
                f"  {builder.location} -> {builder.model}.{builder.field} "
                f"floor {builder.static_floor} > cap {builder.cap} "
                f"(over by {builder.static_floor - builder.cap})"
                for builder in unconstructible
            ),
        ],
    )


#: Builders whose prose already leaves too little room for the data they
#: interpolate, recorded so the ratchet below can only shrink. Each is a real
#: variable-length exposure found when this gate first ran, not an exemption:
#: they are listed because fixing them means editing another campaign's module,
#: and a gate held back until someone does that protects nothing in the
#: meantime.
#:
#: Both remaining entries build ``CalculationSourceDiagnostic``, which elides on
#: overflow, so neither can crash a filing; they truncate silently instead,
#: losing whichever interpolated term falls off the end. That is a
#: message-quality defect rather than a safety one -- shorten the prose to
#: retire them.
#:
#: The two ``ModeloVerificationFinding`` entries this list used to carry were
#: the sharp case: that model had no eliding validator, so its cramped builders
#: RAISED out of ``verify``. Both were measured against the data they actually
#: interpolate -- the 8-term one could reach roughly 190 characters against 176
#: of headroom, so it was a live crash rather than a theoretical one -- and both
#: had their prose shortened until the data fits with room to spare. The model
#: now elides as well, so the shape cannot return silently.
_KNOWN_CRAMPED_BUILDERS: frozenset[str] = frozenset(
    {
        "cadrumo/application/modelo/_prior_payment_advisory.py:184",
        "cadrumo/application/modelo/_prorrata_regularizacion_advisory.py:333",
    },
)

#: Characters an interpolated term is assumed to need. Deliberately low: it
#: passes anything with genuine room and fails only builders with effectively
#: none, so the gate stays quiet enough to be trusted rather than muted.
_HEADROOM_PER_TERM = 30


def _cramped(builders: tuple[_Builder, ...]) -> list[_Builder]:
    return [
        builder
        for builder in builders
        if builder.interpolations and builder.headroom < _HEADROOM_PER_TERM * builder.interpolations
    ]


def test_no_new_builder_leaves_too_little_room_for_its_data(advisory_builders: tuple[_Builder, ...]) -> None:
    """The variable-length shape, caught at authoring time rather than at the item count that trips it.

    A builder interpolating taxpayer data with a handful of characters left is
    not broken yet and cannot survive contact with a real household. Reporting
    it now beats discovering it when someone's triplets cross the boundary,
    which is exactly how the three that shipped in one day were found.

    A ratchet rather than a hard assertion, because the four already present
    live in other campaigns' modules. Shrink-only: a new one fails immediately.
    """
    offenders = {builder.location for builder in _cramped(advisory_builders)}
    introduced = sorted(offenders - _KNOWN_CRAMPED_BUILDERS)
    assert introduced == [], "\n".join(
        [
            f"{len(introduced)} advisory message(s) newly leave too little room for interpolated data:",
            *(f"  {location}" for location in introduced),
            "Shorten the prose or raise the field's cap; do not add it to the known list.",
        ],
    )


def test_the_known_cramped_list_does_not_outlive_its_entries(advisory_builders: tuple[_Builder, ...]) -> None:
    """A fixed builder must be struck from the list, not left to rot in it.

    Without this the ratchet only ever loosens: an entry whose prose was
    shortened, or whose line moved, would sit in the list forever quietly
    exempting whatever now occupies that location.
    """
    offenders = {builder.location for builder in _cramped(advisory_builders)}
    stale = sorted(_KNOWN_CRAMPED_BUILDERS - offenders)
    assert stale == [], "\n".join(
        [
            f"{len(stale)} known-cramped entr(y/ies) no longer match a cramped builder:",
            *(f"  {location}" for location in stale),
            "Remove them from _KNOWN_CRAMPED_BUILDERS -- the ratchet must shrink.",
        ],
    )
