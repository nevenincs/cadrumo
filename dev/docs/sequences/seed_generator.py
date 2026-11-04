"""Generate the persona-derived profile-setup frames of the seed recipes, and check them for drift.

A seed recipe (``docs/_sequences/seeds/<name>.seq``) opens with directive lines
that declare where its profile comes from, then holds a generated region and
the recipe's own authored frames::

    :persona: asalariada-familia
    :profile: irpf-income-categories taxpayer-birth-date
    @step State the taxpayer's Renta profile.
    :generated: begin
    @setup aeat config profile edit docs-sequence-sandbox --quiet --irpf-income-categories trabajo ...
    :generated: end
    @step ...authored frames...

``:persona:`` names the catalogue persona and ``:profile:`` the wizard questions
the recipe states: the persona supplies every value, the recipe only chooses
which answers its page needs. An optional ``:identities:`` line lists the
catalogue identity roles the authored frames name; the check refuses a recipe
whose text no longer states a listed identity's value and name as the
catalogue does. The generator renders the one ``config profile
edit`` ``@setup`` frame between the markers, under the authored ``@step``
narration. The frame is an ordinary executed frame, so its output is
golden-gated like any other; the authored frames below the region (ledger
entries, work units, invoices) are flow steps no persona states and stay
hand-written.

The directive lines are blanked by the recipe loader before the frame grammar
runs, so a recipe without them is still an ordinary recipe.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from dev._paths import UTF_8

from ._seeds import SEED_SUFFIX, default_seeds_root
from .persona_profile import pinned_persona, profile_option_arguments
from .sandbox import SANDBOX_PROFILE_LABEL

__all__ = ["SeedHeader", "check_seeds", "parse_seed_header", "render_seed", "write_seeds"]

_DIRECTIVE: Final = re.compile(r"^:(?P<name>persona|profile|identities|generated):[ \t]*(?P<value>.*?)[ \t]*$")
_BEGIN: Final = "begin"
_END: Final = "end"


@dataclass(frozen=True, slots=True)
class SeedHeader:
    """The declared persona inputs of one seed recipe and where its generated region sits."""

    persona: str
    questions: tuple[str, ...]
    identities: tuple[str, ...]
    """Identity roles the recipe's authored frames name; their catalogue values must appear in the text."""
    begin: int
    """Index of the ``:generated: begin`` line."""
    end: int
    """Index of the ``:generated: end`` line."""


def parse_seed_header(text: str, *, name: str) -> SeedHeader | None:
    """Return the recipe's persona header, ``None`` for a recipe that declares no persona.

    Raises:
        ValueError: When the header is incomplete, repeated or its region is not one begin/end pair.
    """
    lines = text.splitlines()
    declared: dict[str, str] = {}
    markers: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        matched = _DIRECTIVE.match(line)
        if matched is None:
            continue
        directive, value = matched["name"], matched["value"]
        if directive == "generated":
            markers.append((index, value))
        elif directive in declared:
            raise ValueError(f"seed:{name} line {index + 1}: ':{directive}:' is declared twice")
        else:
            declared[directive] = value
    if not declared and not markers:
        return None
    missing = {"persona", "profile"} - declared.keys()
    if missing:
        raise ValueError(
            f"seed:{name}: a persona recipe also declares {', '.join(f':{item}:' for item in sorted(missing))}"
        )
    if [value for _, value in markers] != [_BEGIN, _END]:
        raise ValueError(f"seed:{name}: expected exactly one ':generated: begin' then one ':generated: end' line")
    questions = tuple(declared["profile"].split())
    if not questions or not declared["persona"]:
        raise ValueError(f"seed:{name}: ':persona:' and ':profile:' must each carry a value")
    return SeedHeader(
        persona=declared["persona"],
        questions=questions,
        identities=tuple(declared.get("identities", "").split()),
        begin=markers[0][0],
        end=markers[1][0],
    )


def render_seed(text: str, *, name: str) -> str:
    """Return ``text`` with its generated region rendered from the declared persona."""
    header = parse_seed_header(text, name=name)
    if header is None:
        return text
    with pinned_persona(header.persona) as (persona, envelope):
        options = profile_option_arguments(persona, envelope, header.questions)
    for role in header.identities:
        identity = persona.identities.role(role)
        stated = [identity.value, identity.legal_name or " ".join(filter(None, (identity.name, identity.surnames)))]
        absent = [value for value in stated if value not in text]
        if absent:
            raise ValueError(f"seed:{name}: the authored frames do not state {role} as the catalogue does ({absent})")
    frame = " ".join(("aeat config profile edit", SANDBOX_PROFILE_LABEL, "--quiet", *options))
    lines = text.splitlines()
    region = [lines[header.begin], f"@setup {frame}", lines[header.end]]
    rendered = [*lines[: header.begin], *region, *lines[header.end + 1 :]]
    return "\n".join(rendered) + "\n"


def _recipes(seeds_root: Path) -> list[Path]:
    return sorted(seeds_root.glob(f"*{SEED_SUFFIX}"))


def check_seeds(*, seeds_root: Path | None = None) -> tuple[str, ...]:
    """Return one problem per recipe whose committed text differs from its regeneration."""
    root = seeds_root if seeds_root is not None else default_seeds_root()
    problems: list[str] = []
    for recipe in _recipes(root):
        committed = recipe.read_text(encoding=UTF_8)
        try:
            expected = render_seed(committed, name=recipe.stem)
        except ValueError as error:
            problems.append(str(error))
            continue
        if committed != expected:
            problems.append(
                f"seed:{recipe.stem}: the generated region differs from the persona it declares; "
                "regenerate it with: python -m dev.docs.sequences seeds"
            )
    return tuple(problems)


def write_seeds(*, seeds_root: Path | None = None) -> tuple[Path, ...]:
    """Rewrite every recipe whose generated region is stale; return the recipes written."""
    root = seeds_root if seeds_root is not None else default_seeds_root()
    written: list[Path] = []
    for recipe in _recipes(root):
        committed = recipe.read_text(encoding=UTF_8)
        expected = render_seed(committed, name=recipe.stem)
        if committed != expected:
            recipe.write_text(expected, encoding=UTF_8, newline="\n")
            written.append(recipe)
    return tuple(written)
