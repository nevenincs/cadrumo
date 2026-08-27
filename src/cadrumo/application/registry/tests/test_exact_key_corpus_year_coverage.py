"""Full-master-window coverage gate for the exact-year-keyed corpora.

A corpus enrolled here is resolved by **exact year key**: its loader builds a
``{year: payload}`` mapping from year-named TOML files and its resolver indexes
that mapping directly, raising when the key is absent. For such a corpus the
declared supported filing window is a coverage obligation -- a missing year is
not a value the resolver can interpolate, span-resolve or fall back for, so it
is either a refusal at runtime or, where a call site pins a literal year, a
silently wrong answer computed under another year's law.

Modelo revision directories are deliberately **not** enrolled. AEAT binds a
``(modelo, filing_year, period)`` triple to one revision by publishing orden, so
a revision legitimately spans several years and an absent year directory is
normal rather than a gap; their coverage claim is that ``select_revision``
resolves for every supported year, which the non-overlap window gate owns.
Asserting year-set equality on those directories would manufacture failures.

The master declaration is the single writable one in
``registry/aeat/legal/supported-filing-years.toml``, read here through the
registry loader rather than copied, so widening the window automatically widens
the obligation and no second horizon can drift from it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest

from cadrumo.core.resources import bundled_path
from cadrumo.domain.calculations.registry.loader import load_registry_tree
from cadrumo.domain.categories._registry import load_category_profile_registry, resolve_category_profiles
from cadrumo.domain.categories.errors import CategoryValidationError
from cadrumo.domain.iva._catalogue import load_iva_catalogues, resolve_catalogue
from cadrumo.domain.iva._place_of_supply import load_place_of_supply_rules, place_of_supply_rule
from cadrumo.domain.iva.errors import IvaCatalogueError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@dataclass(frozen=True)
class ExactKeyCorpus:
    """One corpus whose resolver does exact-year-key lookup and raises on miss.

    Attributes:
        name: Operator-facing corpus name, used in the failure enumeration.
        relative_root: Path under the bundled registry root holding the
            year-named TOML files, used to build the withheld-year bite proof.
        years_under: Loads the corpus from a root and returns the years it
            carries. Takes the root explicitly so the bite proof can point it
            at a deliberately incomplete tree.
        resolve: Exercises the production resolver for one year. Must raise
            ``raises`` when the year is absent.
        raises: The refusal the resolver is contracted to raise on a miss.
    """

    name: str
    relative_root: tuple[str, ...]
    years_under: Callable[[Path], frozenset[int]]
    resolve: Callable[[int], object]
    raises: type[Exception]

    def bundled_root(self) -> Path:
        return bundled_path(*self.relative_root)

    def bundled_years(self) -> frozenset[int]:
        return self.years_under(self.bundled_root())


def _category_profile_years(root: Path) -> frozenset[int]:
    return frozenset(load_category_profile_registry(root))


def _iva_catalogue_years(root: Path) -> frozenset[int]:
    return frozenset(load_iva_catalogues(root))


def _place_of_supply_years(root: Path) -> frozenset[int]:
    return frozenset(load_place_of_supply_rules(root))


def _resolve_any_place_of_supply_rule(year: int) -> object:
    """Resolve one grounded rule for ``year`` through the raising public resolver.

    The rule id is taken from the year's own table rather than pinned, so this
    stays honest when the rule set changes. When the year carries no table at
    all, ``load_place_of_supply_rules`` yields no entry and the resolver is
    still asked for a rule id that cannot resolve -- either path raises
    ``IvaCatalogueError``, which is the contract under test.
    """
    tables = load_place_of_supply_rules()
    year_rules = tables.get(year, {})
    rule_id = next(iter(sorted(year_rules)), "")
    return place_of_supply_rule(rule_id, on=date(year, 1, 1))


ENROLLED_EXACT_KEY_CORPORA: tuple[ExactKeyCorpus, ...] = (
    ExactKeyCorpus(
        name="spending-category profiles",
        relative_root=("registry", "aeat", "categories", "profiles"),
        years_under=_category_profile_years,
        resolve=resolve_category_profiles,
        raises=CategoryValidationError,
    ),
    ExactKeyCorpus(
        name="IVA catalogues",
        relative_root=("registry", "aeat", "iva", "catalogues"),
        years_under=_iva_catalogue_years,
        resolve=lambda year: resolve_catalogue(on=date(year, 1, 1)),
        raises=IvaCatalogueError,
    ),
    ExactKeyCorpus(
        name="IVA place-of-supply groundings",
        relative_root=("registry", "aeat", "iva", "place_of_supply"),
        years_under=_place_of_supply_years,
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
    """Each enrolled corpus must carry every year the master declaration admits.

    Property, not tally: the obligation is derived from the master declaration
    on every run, so no file count is encoded here and widening the declared
    window widens this gate without editing it.
    """
    master = master_supported_filing_years()
    assert master, "the master declaration carries no years; an empty window makes this gate vacuous"

    missing = sorted(set(master) - corpus.bundled_years())

    assert missing == [], (
        f"{corpus.name} does not cover the declared supported filing window: "
        f"missing year(s) {missing} under {Path(*corpus.relative_root).as_posix()}. "
        "Ground each missing year against BOE/AEAT and author it, or narrow the master "
        "declaration -- never mirror an adjacent year's values, and never add an allowlist."
    )


@pytest.mark.parametrize("corpus", ENROLLED_EXACT_KEY_CORPORA, ids=lambda c: c.name)
def test_every_enrolled_resolver_refuses_a_year_it_does_not_carry(corpus: ExactKeyCorpus) -> None:
    """Anchor: enrolment is only meaningful while the resolver still raises on a miss.

    Without this, a resolver that quietly gained a fallback would keep passing
    the coverage assertion above while no longer refusing anything, and the
    gate would measure a property the code no longer has.
    """
    absent_year = max(corpus.bundled_years()) + 1000

    with pytest.raises(corpus.raises):
        corpus.resolve(absent_year)


@pytest.mark.parametrize("corpus", ENROLLED_EXACT_KEY_CORPORA, ids=lambda c: c.name)
def test_the_coverage_gate_bites_when_a_year_is_withheld(corpus: ExactKeyCorpus, tmp_path: Path) -> None:
    """Anti-tautology: withhold one carried year and the coverage measure must lose it.

    The withholding happens in ``tmp_path`` built from the bundled files, so
    nothing under ``src`` is mutated: a crashed run leaves no residue and a
    peer's sweep cannot commit the mutation.
    """
    carried = sorted(corpus.bundled_years())
    assert carried, f"{corpus.name} carries no years at all; there is nothing to withhold"
    withheld = carried[-1]

    incomplete_root = tmp_path / "incomplete"
    incomplete_root.mkdir()
    for source in sorted(corpus.bundled_root().glob("*.toml")):
        if int(source.stem) == withheld:
            continue
        (incomplete_root / source.name).write_bytes(source.read_bytes())

    if len(carried) == 1:
        # Withholding the sole year leaves an empty tree, which every enrolled
        # loader refuses outright rather than reporting as zero years. That
        # refusal is the bite: the measure cannot silently report coverage it
        # does not have.
        with pytest.raises(corpus.raises):
            corpus.years_under(incomplete_root)
        return

    observed = corpus.years_under(incomplete_root)

    assert withheld not in observed, (
        f"the coverage measure for {corpus.name} still reported year {withheld} after its file was "
        "withheld; the measure is not reading the tree it claims to read"
    )
    assert observed == frozenset(carried) - {withheld}, (
        f"withholding one year from {corpus.name} changed the observed set by more than that year"
    )
