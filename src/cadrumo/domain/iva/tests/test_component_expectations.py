"""Gates for the Axis-A per-category component-expectation table.

The table declares, per :class:`~domain.iva.IvaCategory`, which invoice
components exist. Three properties make it safe to consume, and each has a gate
here:

* **Completeness** — every enum member has a row, so a new category cannot ship
  without declaring its components.
* **Non-divergence** — the cuota-less predicate derived from the table equals
  the canonical :data:`~domain.iva.CUOTA_LESS_M303_IVA_CATEGORIES` frozenset,
  category by category. The two sides are independent declarations (a hand
  maintained frozenset versus per-row columns), so editing either one alone
  reds the gate; this is what stops the table from becoming a third inline set.
* **Grounding honesty** — every ``legal_refs`` id resolves in the bundled legal
  catalogue, every ``pending_legal_refs`` id does *not*, and any expectation
  that is not bundled-corpus grounded carries its caveat. The pending gate is
  self-retiring: bundling a pending provision turns it red until the author
  promotes the row.

No test here asserts a Decimal produced by the rule under test — the table
carries no amounts. The assertions are structural, referential, and
cross-declaration, per ``no-tautological-calculation-tests``.

See Also:
    :mod:`domain.iva._components`
        The table under test.
    :mod:`domain.iva._schema`
        Owns the canonical frozensets this module cross-checks the table
        against.
"""

from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from ....core.resources import bundled_path
from .. import (
    CUOTA_LESS_M303_IVA_CATEGORIES,
    EVIDENCE_EXEMPT_IVA_CATEGORIES,
    IVA_CATEGORY_COMPONENTS,
    IvaCategory,
    IvaCategoryComponents,
    IvaComponentPresence,
    IvaCuotaSettlement,
    IvaGroundingConfidence,
    IvaRetencionExpectation,
    category_bears_taxable_base,
    category_cuota_is_zero_by_law,
    cuota_less_m303_categories_from_table,
    iva_category_components,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


#: Sentinel categories that declare no IVA treatment at all. They are the only
#: rows permitted to answer ``UNKNOWN``; every other category must commit.
_SENTINEL_CATEGORIES: frozenset[IvaCategory] = frozenset(
    {IvaCategory.UNKNOWN, IvaCategory.ERRONEOUS_INVOICE},
)


def _bundled_legal_ref_ids() -> frozenset[str]:
    """Return every legal-reference id declared in the bundled legal catalogue.

    Reads the authoring tree directly rather than through the registry loader
    so the gate stays fast and reports drift against the committed TOML the
    author actually edits.
    """
    legal_root = bundled_path("registry", "aeat", "legal")
    ids: set[str] = set()
    for path in sorted(legal_root.glob("*.toml")):
        with path.open("rb") as handle:
            payload = tomllib.load(handle)
        legal_table = payload.get("legal")
        if isinstance(legal_table, dict):
            ids.update(legal_table)
    return frozenset(ids)


def _rows() -> Iterable[IvaCategoryComponents]:
    return IVA_CATEGORY_COMPONENTS.values()


# --------------------------------------------------------------------------- #
# Completeness
# --------------------------------------------------------------------------- #


def test_every_iva_category_declares_its_components() -> None:
    """A new IvaCategory member cannot ship without an Axis-A row.

    This is the gate the ADR asks for: component existence becomes declared
    data, so adding a category forces the author to state what it carries
    rather than leaving each decomposition site to guess.
    """
    undeclared = sorted(category.value for category in IvaCategory if category not in IVA_CATEGORY_COMPONENTS)
    assert undeclared == [], f"IvaCategory members without an Axis-A row: {undeclared}"


def test_table_declares_no_category_outside_the_enum() -> None:
    """Every table key is a live enum member, and its row agrees with its key."""
    for category, row in IVA_CATEGORY_COMPONENTS.items():
        assert isinstance(category, IvaCategory)
        assert row.category is category, f"row keyed {category.value!r} declares {row.category.value!r}"


def test_lookup_returns_the_keyed_row_for_every_member() -> None:
    """The public accessor resolves every member without falling through."""
    for category in IvaCategory:
        assert iva_category_components(category) is IVA_CATEGORY_COMPONENTS[category]


# --------------------------------------------------------------------------- #
# Non-divergence against the canonical frozensets
# --------------------------------------------------------------------------- #


def test_derived_cuota_less_set_equals_the_canonical_frozenset() -> None:
    """The table is a second view of the cuota-less fact, never a second declaration."""
    derived = cuota_less_m303_categories_from_table()
    assert derived == CUOTA_LESS_M303_IVA_CATEGORIES, (
        "Axis-A table and CUOTA_LESS_M303_IVA_CATEGORIES disagree — "
        f"table-only: {sorted(c.value for c in derived - CUOTA_LESS_M303_IVA_CATEGORIES)}; "
        f"frozenset-only: {sorted(c.value for c in CUOTA_LESS_M303_IVA_CATEGORIES - derived)}"
    )


@pytest.mark.parametrize("category", tuple(IvaCategory), ids=lambda c: c.value)
def test_per_category_cuota_columns_agree_with_the_frozenset(category: IvaCategory) -> None:
    """Editing one row's cuota columns alone flips exactly this category's gate.

    The per-category form is what gives the non-divergence gate its teeth: the
    set-level assertion above would also pass if two rows were edited in
    compensating directions, while this one names the drifted category.
    """
    row = IVA_CATEGORY_COMPONENTS[category]
    declared_cuota_less = (
        row.cuota is IvaComponentPresence.ZERO_BY_LAW or row.cuota_settlement is IvaCuotaSettlement.REGIMEN_ESPECIAL
    )
    assert declared_cuota_less is (category in CUOTA_LESS_M303_IVA_CATEGORIES), (
        f"{category.value}: table says cuota-less={declared_cuota_less}, "
        f"frozenset says {category in CUOTA_LESS_M303_IVA_CATEGORIES}"
    )


def test_the_cuota_less_partition_is_non_trivial() -> None:
    """Both sides of the partition are populated.

    Guards the degenerate failure where a column rename silently collapses the
    derivation to "everything" or "nothing" while the set comparison still
    passes against an equally-collapsed frozenset.
    """
    derived = cuota_less_m303_categories_from_table()
    assert 0 < len(derived) < len(IVA_CATEGORY_COMPONENTS)


def test_evidence_exempt_extends_the_cuota_less_set_by_the_three_sentinels() -> None:
    """The evidence-exempt set stays a derived extension, not a parallel list."""
    assert CUOTA_LESS_M303_IVA_CATEGORIES <= EVIDENCE_EXEMPT_IVA_CATEGORIES
    assert (
        frozenset(
            {
                IvaCategory.RECARGO_EQUIVALENCIA,
                IvaCategory.ERRONEOUS_INVOICE,
                IvaCategory.UNKNOWN,
            },
        )
        == EVIDENCE_EXEMPT_IVA_CATEGORIES - CUOTA_LESS_M303_IVA_CATEGORIES
    )


# --------------------------------------------------------------------------- #
# Cuota-less is not substrate-less
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "category",
    tuple(sorted(CUOTA_LESS_M303_IVA_CATEGORIES, key=lambda c: c.value)),
    ids=lambda c: c.value,
)
def test_cuota_less_categories_still_require_a_taxable_base(category: IvaCategory) -> None:
    """An exempt or export operation carries a real base that feeds base-only casillas.

    This is the ADR's load-bearing distinction: a base-less row in one of these
    categories is ungrounded, not legitimately empty, and that is precisely
    what a bare cash amount cannot tell you.
    """
    assert category_bears_taxable_base(category), f"{category.value} is cuota-less but must still carry a taxable base"


def test_only_sentinel_categories_answer_unknown() -> None:
    """Every real category commits to an expectation; only sentinels may abstain."""
    for category, row in IVA_CATEGORY_COMPONENTS.items():
        abstains = (
            row.base is IvaComponentPresence.UNKNOWN
            or row.cuota is IvaComponentPresence.UNKNOWN
            or row.retencion is IvaRetencionExpectation.UNKNOWN
        )
        if category in _SENTINEL_CATEGORIES:
            assert abstains, f"{category.value} is a sentinel and must declare UNKNOWN components"
        else:
            assert not abstains, f"{category.value} must commit to its component expectations"


def test_zero_by_law_cuota_is_exactly_the_determinable_zero_predicate() -> None:
    """The inference helper reports zero exactly for the zero-by-law rows.

    Consumed by the retención-inference precondition, which needs "cuota
    determinable from the declared category" rather than "explicit iva_amount
    recorded" so a declared-exempt invoice can recover its retención.
    """
    for category, row in IVA_CATEGORY_COMPONENTS.items():
        assert category_cuota_is_zero_by_law(category) is (row.cuota is IvaComponentPresence.ZERO_BY_LAW)


# --------------------------------------------------------------------------- #
# Legal grounding
# --------------------------------------------------------------------------- #


def test_every_cited_legal_ref_resolves_in_the_bundled_catalogue() -> None:
    """A row may not cite a provision the legal catalogue does not carry.

    An ungrounded regulatory citation is worse than none: the reader treats a
    resolvable-looking id as verified.
    """
    catalogued = _bundled_legal_ref_ids()
    unresolved = sorted(
        {ref for row in _rows() for ref in row.legal_refs if ref not in catalogued},
    )
    assert unresolved == [], f"Axis-A legal_refs absent from the legal catalogue: {unresolved}"


def test_pending_legal_refs_are_genuinely_unbundled() -> None:
    """The pending marker retires itself once its provision is bundled.

    ``pending_legal_refs`` records a provision verified against live BOE text
    but absent from the catalogue. Bundling it makes this gate fail, forcing
    the author to promote the id into ``legal_refs`` and upgrade the row's
    grounding marker from live-source-only to bundled-corpus — rather than
    leaving a stale "pending" claim that has quietly become true.
    """
    catalogued = _bundled_legal_ref_ids()
    now_bundled = sorted(
        {ref for row in _rows() for ref in row.pending_legal_refs if ref in catalogued},
    )
    assert now_bundled == [], (
        "these pending legal refs are now in the bundled catalogue — promote them into "
        f"legal_refs and upgrade the row grounding to bundled_corpus: {now_bundled}"
    )


def test_bundled_corpus_grounding_requires_a_citation() -> None:
    """A row cannot claim bundled grounding while citing nothing."""
    for category, row in IVA_CATEGORY_COMPONENTS.items():
        claims_bundled = IvaGroundingConfidence.BUNDLED_CORPUS in (
            row.cuota_grounding,
            row.recargo_grounding,
            row.retencion_grounding,
        )
        if claims_bundled:
            assert row.legal_refs, f"{category.value} claims bundled grounding but cites no legal_refs"


def test_weakly_grounded_retencion_expectations_carry_their_caveat() -> None:
    """A reasoned or live-source-only expectation never travels without its note.

    An unmarked guess in a legal table is worse than a gap: the next reader
    treats it as verified. The note is where the carve-outs live.
    """
    for category, row in IVA_CATEGORY_COMPONENTS.items():
        if row.retencion_grounding is IvaGroundingConfidence.BUNDLED_CORPUS:
            continue
        assert row.retencion_note.strip(), (
            f"{category.value}: retención grounding is {row.retencion_grounding.value!r} "
            "and must state its caveat in retencion_note"
        )


def test_live_source_only_rows_name_the_unbundled_provision() -> None:
    """Live-source-only grounding must point at the provision still to be bundled."""
    for category, row in IVA_CATEGORY_COMPONENTS.items():
        if IvaGroundingConfidence.LIVE_SOURCE_ONLY not in (
            row.cuota_grounding,
            row.recargo_grounding,
            row.retencion_grounding,
        ):
            continue
        assert row.pending_legal_refs, (
            f"{category.value} claims live-source-only grounding but names no pending provision"
        )


def test_sentinel_rows_declare_their_grounding_as_ungrounded() -> None:
    """A sentinel abstains honestly rather than borrowing someone else's citation."""
    for category in sorted(_SENTINEL_CATEGORIES, key=lambda c: c.value):
        row = IVA_CATEGORY_COMPONENTS[category]
        assert row.cuota_grounding is IvaGroundingConfidence.UNGROUNDED
        assert row.recargo_grounding is IvaGroundingConfidence.UNGROUNDED
        assert row.retencion_grounding is IvaGroundingConfidence.UNGROUNDED
        assert row.legal_refs == ()


def test_no_row_cites_the_same_ref_as_both_bundled_and_pending() -> None:
    """A provision is either in the catalogue or it is not."""
    for category, row in IVA_CATEGORY_COMPONENTS.items():
        overlap = sorted(set(row.legal_refs) & set(row.pending_legal_refs))
        assert overlap == [], f"{category.value} cites {overlap} as both bundled and pending"


# --------------------------------------------------------------------------- #
# Row-model refusals — proof the validators can fail, not just pass
# --------------------------------------------------------------------------- #


def _valid_row_kwargs() -> dict[str, object]:
    return {
        "category": IvaCategory.DOMESTIC_EXEMPT,
        "base": IvaComponentPresence.REQUIRED,
        "cuota": IvaComponentPresence.ZERO_BY_LAW,
        "cuota_settlement": IvaCuotaSettlement.NONE,
        "cuota_grounding": IvaGroundingConfidence.BUNDLED_CORPUS,
        "recargo": IvaComponentPresence.ZERO_BY_LAW,
        "recargo_grounding": IvaGroundingConfidence.REASONED,
        "retencion": IvaRetencionExpectation.POSSIBLE,
        "retencion_grounding": IvaGroundingConfidence.BUNDLED_CORPUS,
        "retencion_note": "",
        "legal_refs": ("ley-37-1992:art-20",),
        "pending_legal_refs": (),
    }


def test_the_reference_row_kwargs_build_a_valid_row() -> None:
    """Positive control: the refusal cases below differ from this by one field only."""
    assert IvaCategoryComponents(**_valid_row_kwargs()).category is IvaCategory.DOMESTIC_EXEMPT


def test_zero_by_law_cuota_must_declare_no_settlement() -> None:
    """A structurally-zero cuota cannot also name someone who settles it."""
    kwargs = _valid_row_kwargs() | {"cuota_settlement": IvaCuotaSettlement.REPERCUTIDA}
    with pytest.raises(ValidationError, match="zero-by-law cuota"):
        IvaCategoryComponents(**kwargs)


def test_a_settled_cuota_cannot_be_declared_zero_by_law() -> None:
    """The coherence check binds in both directions."""
    kwargs = _valid_row_kwargs() | {
        "cuota": IvaComponentPresence.REQUIRED,
        "cuota_settlement": IvaCuotaSettlement.NONE,
    }
    with pytest.raises(ValidationError, match="zero-by-law cuota"):
        IvaCategoryComponents(**kwargs)


def test_weak_retencion_grounding_without_a_note_is_refused() -> None:
    """The honesty requirement is enforced by the model, not only by a test."""
    kwargs = _valid_row_kwargs() | {
        "retencion_grounding": IvaGroundingConfidence.REASONED,
        "retencion_note": "   ",
    }
    with pytest.raises(ValidationError, match="requires a retencion_note"):
        IvaCategoryComponents(**kwargs)


def test_live_source_only_grounding_without_a_pending_ref_is_refused() -> None:
    """A live-only claim must name the provision it is waiting on."""
    kwargs = _valid_row_kwargs() | {
        "retencion_grounding": IvaGroundingConfidence.LIVE_SOURCE_ONLY,
        "retencion_note": "verified live, provision not yet bundled",
        "pending_legal_refs": (),
    }
    with pytest.raises(ValidationError, match="no pending_legal_refs"):
        IvaCategoryComponents(**kwargs)


def test_bundled_grounding_without_legal_refs_is_refused() -> None:
    """A bundled-corpus claim must cite the corpus it claims."""
    kwargs = _valid_row_kwargs() | {"legal_refs": ()}
    with pytest.raises(ValidationError, match="claims bundled corpus"):
        IvaCategoryComponents(**kwargs)


def test_duplicate_legal_refs_are_refused() -> None:
    """Duplicate citations would inflate an apparent grounding breadth."""
    kwargs = _valid_row_kwargs() | {
        "legal_refs": ("ley-37-1992:art-20", "ley-37-1992:art-20"),
    }
    with pytest.raises(ValidationError, match="legal_refs must be unique"):
        IvaCategoryComponents(**kwargs)


def test_a_ref_cannot_be_both_bundled_and_pending_on_one_row() -> None:
    """The model refuses the contradiction the table-level gate also checks."""
    kwargs = _valid_row_kwargs() | {"pending_legal_refs": ("ley-37-1992:art-20",)}
    with pytest.raises(ValidationError, match="both bundled and pending"):
        IvaCategoryComponents(**kwargs)
