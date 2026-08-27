"""Full-master-window coverage gate for the exact-year-resolved corpora.

A corpus enrolled here is resolved by **exact filing year**: its resolver
answers for a year it grounds and raises for one it does not. For such a corpus
the declared supported filing window is a coverage obligation -- a missing year
is not a value the resolver can interpolate, span-resolve or fall back for, so
it is either a refusal at runtime or, where a call site pins a literal year, a
silently wrong answer computed under another year's law.

**Coverage is derived, never read off a filename.** These corpora used to be
year-named files, and this gate used to glob them and parse ``int(path.stem)``.
That premise is gone: a corpus is one undated file whose grounded records each
declare the closed span they are asserted over, and the resolvable years are the
years every record has evidence for. Reading a filename measured the shape of
the directory; reading the windows measures the grounding, which is what the
obligation is actually about.

Modelo revision directories are deliberately **not** enrolled. AEAT binds a
``(modelo, filing_year, period)`` triple to one revision by publishing orden, so
a revision legitimately spans several years and an absent year directory is
normal rather than a gap; their coverage claim is that ``select_revision``
resolves for every supported year, which the non-overlap window gate owns.

The master declaration is the single writable one in
``registry/aeat/legal/supported-filing-years.toml``, read here through the
registry loader rather than copied, so widening the window automatically widens
the obligation and no second horizon can drift from it.
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest

from ....core.resources import bundled_path
from ....domain.calculations.registry.loader import load_registry_tree
from ....domain.categories._registry import category_profile_years, resolve_category_profiles
from ....domain.categories.errors import CategoryValidationError
from ....domain.iva._catalogue import iva_catalogue_years, resolve_catalogue
from ....domain.iva._place_of_supply import load_place_of_supply_table, place_of_supply_rule, place_of_supply_years
from ....domain.iva.errors import IvaCatalogueError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@dataclass(frozen=True)
class ExactKeyCorpus:
    """One corpus whose resolver answers by exact filing year and raises on a miss.

    Attributes:
        name: Operator-facing corpus name, used in the failure enumeration.
        relative_source: Path under the bundled registry root holding the
            corpus, used to build the narrowed-grounding bite proof.
        years_under: Returns the filing years the corpus at a given source
            grounds. Takes the source explicitly so the bite proof can point it
            at a deliberately narrowed copy.
        narrow: Removes one year's grounding from a copy of the corpus, in
            place. It is a per-corpus callable so a corpus that later carries a
            different shape can supply its own narrowing without this gate
            assuming one.
        resolve: Exercises the production resolver for one year. Must raise
            ``raises`` when the year is not grounded.
        raises: The refusal the resolver is contracted to raise on a miss.
    """

    name: str
    relative_source: tuple[str, ...]
    years_under: Callable[[Path], frozenset[int]]
    narrow: Callable[[Path, int], None]
    resolve: Callable[[int], object]
    raises: type[Exception]

    def bundled_source(self) -> Path:
        return bundled_path(*self.relative_source)

    def bundled_years(self) -> frozenset[int]:
        return self.years_under(self.bundled_source())

    def copy_into(self, destination_root: Path) -> Path:
        """Copy the bundled corpus under ``destination_root`` and return the copy.

        The copy is what the bite proof narrows, so nothing under ``src`` is
        mutated: a crashed run leaves no residue and a peer's sweep cannot
        commit the mutation.
        """
        source = self.bundled_source()
        destination = destination_root / source.name
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            destination.write_bytes(source.read_bytes())
        return destination


def _narrow_by_rewriting_citation_windows(source: Path, year: int) -> None:
    """Pull every validity window in a corpus copy back off ``year``.

    Rewriting the declared span is the only way to remove a year's grounding
    from a corpus that carries no year-named files, and it is the same edit an
    author would make when they discover a citation does not reach as far as
    they thought.

    The rewrite stays a NARROWING rather than a corruption: a window that ends
    in ``year`` is pulled back to the end of the year before, and one that is
    exactly ``year`` is moved wholesale to a year no supported window contains.
    Inverting the span instead would make the corpus refuse to load, which
    proves the model validator works rather than proving the coverage measure
    reads the corpus.
    """
    pair = re.compile(
        r"valid_from = (?P<from_year>\d{4})-(?P<from_rest>\d{2}-\d{2})\n"
        r"(?P<gap>[ \t]*)valid_to = (?P<to_year>\d{4})-(?P<to_rest>\d{2}-\d{2})",
    )

    def narrow_one(match: re.Match[str]) -> str:
        from_year = int(match["from_year"])
        to_year = int(match["to_year"])
        if from_year == year and to_year == year:
            from_year = to_year = 1900
        elif to_year == year:
            to_year = year - 1
        elif from_year == year:
            from_year = year + 1
        return (
            f"valid_from = {from_year:04d}-{match['from_rest']}\n"
            f"{match['gap']}valid_to = {to_year:04d}-{match['to_rest']}"
        )

    text = source.read_text(encoding="utf-8")
    narrowed = pair.sub(narrow_one, text)
    if narrowed == text:
        message = f"{source}: no validity window mentions {year}, so this bite proof would prove nothing"
        raise AssertionError(message)
    source.write_text(narrowed, encoding="utf-8")


def _category_profile_years(source: Path) -> frozenset[int]:
    return category_profile_years(source)


def _iva_catalogue_years(source: Path) -> frozenset[int]:
    return iva_catalogue_years(source)


def _place_of_supply_years(source: Path) -> frozenset[int]:
    return place_of_supply_years(source)


def _resolve_any_place_of_supply_rule(year: int) -> object:
    """Resolve one grounded rule for ``year`` through the raising public resolver.

    The rule id is taken from the table rather than pinned, so this stays honest
    when the rule set changes. A year the table does not ground refuses before
    the rule id is even consulted, which is the contract under test.
    """
    rule_id = next(iter(sorted(load_place_of_supply_table())), "")
    return place_of_supply_rule(rule_id, on=date(year, 1, 1))


ENROLLED_EXACT_KEY_CORPORA: tuple[ExactKeyCorpus, ...] = (
    ExactKeyCorpus(
        name="spending-category profiles",
        relative_source=("registry", "aeat", "categories", "profiles.toml"),
        years_under=_category_profile_years,
        narrow=_narrow_by_rewriting_citation_windows,
        resolve=resolve_category_profiles,
        raises=CategoryValidationError,
    ),
    ExactKeyCorpus(
        name="IVA catalogues",
        relative_source=("registry", "aeat", "iva", "catalogues.toml"),
        years_under=_iva_catalogue_years,
        narrow=_narrow_by_rewriting_citation_windows,
        resolve=lambda year: resolve_catalogue(on=date(year, 1, 1)),
        raises=IvaCatalogueError,
    ),
    ExactKeyCorpus(
        name="IVA place-of-supply groundings",
        relative_source=("registry", "aeat", "iva", "place_of_supply.toml"),
        years_under=_place_of_supply_years,
        narrow=_narrow_by_rewriting_citation_windows,
        resolve=_resolve_any_place_of_supply_rule,
        raises=IvaCatalogueError,
    ),
)


def master_supported_filing_years() -> tuple[int, ...]:
    """Return the years the one writable master declaration carries."""
    _modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    declaration = catalogues.supported_filing_years
    assert declaration is not None, (
        "the bundled registry declares no supported_filing_years catalogue; "
        "this gate has no master window to measure against"
    )
    return tuple(declaration.years)


@pytest.mark.parametrize("corpus", ENROLLED_EXACT_KEY_CORPORA, ids=lambda c: c.name)
def test_every_exact_key_corpus_covers_the_whole_master_filing_window(corpus: ExactKeyCorpus) -> None:
    """Each enrolled corpus must ground every year the master declaration admits.

    Property, not tally: the obligation is derived from the master declaration
    on every run, so no file count and no year count is encoded here, and
    widening the declared window widens this gate without editing it.
    """
    master = master_supported_filing_years()
    assert master, "the master declaration carries no years; an empty window makes this gate vacuous"

    missing = sorted(set(master) - corpus.bundled_years())

    assert missing == [], (
        f"{corpus.name} resolves by exact filing year but grounds no evidence for "
        f"year(s) {missing} under {Path(*corpus.relative_source).as_posix()}. "
        "Ground each missing year against BOE/AEAT and add its citations, or narrow the master "
        "declaration -- never widen an existing citation's window to admit a year nobody read, "
        "never mirror an adjacent year's values, and never add an allowlist."
    )


@pytest.mark.parametrize("corpus", ENROLLED_EXACT_KEY_CORPORA, ids=lambda c: c.name)
def test_every_enrolled_resolver_refuses_a_year_it_does_not_ground(corpus: ExactKeyCorpus) -> None:
    """Anchor: enrolment is only meaningful while the resolver still raises on a miss.

    Without this, a resolver that quietly gained a fallback would keep passing
    the coverage assertion above while no longer refusing anything, and the
    gate would measure a property the code no longer has.
    """
    absent_year = max(corpus.bundled_years()) + 1000

    with pytest.raises(corpus.raises):
        corpus.resolve(absent_year)


@pytest.mark.parametrize("corpus", ENROLLED_EXACT_KEY_CORPORA, ids=lambda c: c.name)
def test_the_coverage_gate_bites_when_a_years_grounding_is_narrowed(
    corpus: ExactKeyCorpus,
    tmp_path: Path,
) -> None:
    """Anti-tautology: remove one year's grounding and the measure must lose it.

    If this ever passes with the year still reported, the coverage measure is
    not reading the corpus it claims to read, and every assertion above it is
    vacuous.
    """
    grounded = sorted(corpus.bundled_years())
    assert grounded, f"{corpus.name} grounds no years at all; there is nothing to narrow"
    narrowed_year = grounded[-1]

    copy_root = tmp_path / "narrowed"
    copy_root.mkdir()
    copy = corpus.copy_into(copy_root)
    corpus.narrow(copy, narrowed_year)

    try:
        observed = corpus.years_under(copy)
    except corpus.raises:
        # Narrowing the sole grounded year can leave a corpus the loader
        # refuses outright rather than one reporting zero years. That refusal
        # is the bite: the measure cannot report coverage it does not have.
        return

    assert narrowed_year not in observed, (
        f"the coverage measure for {corpus.name} still reported year {narrowed_year} after its "
        "grounding was removed; the measure is not reading the corpus it claims to read"
    )
