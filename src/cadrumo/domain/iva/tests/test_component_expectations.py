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
cross-declaration, per ``aeat-quality-gates``.

See Also:
    :mod:`domain.iva.components`
        The table under test.
    :mod:`domain.iva.schema`
        Owns the canonical frozensets this module cross-checks the table
        against.
"""

from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING, Any

import pytest
from pydantic import ValidationError

from ....core.directory_scan import scan_directory
from ....core.resources import bundled_path
from ..classification import InvoiceKind
from ..components import (
    IVA_CATEGORY_COMPONENTS,
    IvaCategoryComponents,
    IvaComponentPresence,
    IvaCuotaSettlement,
    IvaGroundingConfidence,
    IvaKindApplicability,
    IvaRetencionExpectation,
    IvaRetencionRole,
    category_bears_taxable_base,
    category_components,
    category_cuota_is_zero_by_law,
    cuota_less_m303_categories_from_table,
)
from ..schema import CUOTA_LESS_M303_IVA_CATEGORIES, EVIDENCE_EXEMPT_IVA_CATEGORIES, IvaCategory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


if TYPE_CHECKING:
    from collections.abc import Iterable

#: Sentinel categories that declare no IVA treatment at all. They are the only
#: rows permitted to answer ``UNKNOWN``; every other category must commit.
_SENTINEL_CATEGORIES: frozenset[IvaCategory] = frozenset(
    {IvaCategory.UNKNOWN, IvaCategory.ERRONEOUS_INVOICE},
)


def _category_id(category: IvaCategory) -> str:
    """Return the parametrize id for *category*.

    A named function rather than a lambda: pytest types its ``ids`` callable
    loosely, so an inline lambda's parameter infers as ``object`` and every
    attribute read off it is reported unresolved.
    """
    return category.value


def _bundled_legal_ref_ids() -> frozenset[str]:
    """Return every legal-reference id declared in the bundled legal catalogue.

    Reads the authoring tree directly rather than through the registry loader
    so the gate stays fast and reports drift against the committed TOML the
    author actually edits.
    """
    legal_root = bundled_path("registry", "aeat", "legal")
    ids: set[str] = set()
    for path in scan_directory(legal_root, pattern="*.toml"):
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

    This is the gate the governing decision asks for: component existence becomes declared
    data, so adding a category forces the author to state what it carries
    rather than leaving each decomposition site to guess.
    """
    declared = {category for category, _kind in IVA_CATEGORY_COMPONENTS}
    undeclared = sorted(category.value for category in IvaCategory if category not in declared)
    assert undeclared == [], f"IvaCategory members without an Axis-A row: {undeclared}"


def test_table_declares_no_category_outside_the_enum() -> None:
    """Every table key is a live enum member, and its row agrees with its key."""
    for (category, kind), row in IVA_CATEGORY_COMPONENTS.items():
        assert isinstance(category, IvaCategory)
        assert isinstance(kind, InvoiceKind)
        assert row.category is category, f"row keyed {category.value!r} declares {row.category.value!r}"
        assert row.kind is kind, f"row keyed {kind.value!r} declares {row.kind.value!r}"


def test_lookup_returns_the_keyed_row_for_every_member() -> None:
    """The public accessor resolves every member without falling through."""
    for category in IvaCategory:
        for kind in InvoiceKind:
            assert category_components(category, kind) is IVA_CATEGORY_COMPONENTS[(category, kind)]


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


@pytest.mark.parametrize("category", tuple(IvaCategory), ids=_category_id)
def test_per_category_cuota_columns_agree_with_the_frozenset(category: IvaCategory) -> None:
    """Editing one row's cuota columns alone flips exactly this category's gate.

    The per-category form is what gives the non-divergence gate its teeth: the
    set-level assertion above would also pass if two rows were edited in
    compensating directions, while this one names the drifted category.
    """
    arising = [
        row
        for kind in InvoiceKind
        for row in (IVA_CATEGORY_COMPONENTS[(category, kind)],)
        if row.applicability is IvaKindApplicability.ARISES
    ]
    assert arising, f"{category.value} declares no arising kind at all"
    # Mirrors the derivation's quantifier: a category is cuota-less only when
    # NO arising kind of it produces a general-303 cuota. Reading a single
    # fixed kind here would disagree with the derivation for a category whose
    # sides differ, and DOMESTIC_REVERSE_CHARGE is exactly that category.
    declared_cuota_less = all(
        row.cuota is IvaComponentPresence.ZERO_BY_LAW or row.cuota_settlement is IvaCuotaSettlement.REGIMEN_ESPECIAL
        for row in arising
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
    tuple(sorted(CUOTA_LESS_M303_IVA_CATEGORIES, key=_category_id)),
    ids=_category_id,
)
def test_cuota_less_categories_still_require_a_taxable_base(category: IvaCategory) -> None:
    """An exempt or export operation carries a real base that feeds base-only casillas.

    This is the governing decision's load-bearing distinction: a base-less row in one of these
    categories is ungrounded, not legitimately empty, and that is precisely
    what a bare cash amount cannot tell you.
    """
    for kind in InvoiceKind:
        row = IVA_CATEGORY_COMPONENTS[(category, kind)]
        if row.applicability is IvaKindApplicability.DOES_NOT_ARISE:
            continue
        assert category_bears_taxable_base(category, kind), (
            f"{category.value}/{kind.value} is cuota-less but must still carry a taxable base"
        )


def test_only_sentinel_categories_answer_unknown() -> None:
    """Every real category commits to an expectation; only sentinels may abstain."""
    for (category, kind), row in IVA_CATEGORY_COMPONENTS.items():
        if row.applicability is IvaKindApplicability.DOES_NOT_ARISE:
            continue
        del kind
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
    for (category, kind), row in IVA_CATEGORY_COMPONENTS.items():
        assert category_cuota_is_zero_by_law(category, kind) is (row.cuota is IvaComponentPresence.ZERO_BY_LAW)


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
    for (category, _kind), row in IVA_CATEGORY_COMPONENTS.items():
        claims_bundled = IvaGroundingConfidence.BUNDLED_CORPUS in (
            row.cuota_grounding,
            row.recargo_grounding,
            row.retencion_grounding,
        )
        if claims_bundled:
            assert row.legal_refs, f"{category.value} claims bundled grounding but cites no legal_refs"


def test_every_retencion_expectation_carries_its_caveat() -> None:
    """No retención expectation travels without its note, however well grounded.

    An unmarked guess in a legal table is worse than a gap: the next reader
    treats it as verified. The note is where the carve-outs live.

    This gate used to skip bundled-corpus rows, on the reasoning that a cited
    provision speaks for itself. It does not. When the seven cross-border rows
    were promoted from live-source-only to bundled-corpus after RIRPF art. 76
    was bundled, that skip silently made the carve-out disclosure optional on
    exactly the rows whose "no retención" is a default rather than a rule — a
    grounding upgrade must never be able to switch a disclosure off. The skip is
    gone, so coverage cannot leak out of this gate through the grounding column
    again.
    """
    for (category, kind), row in IVA_CATEGORY_COMPONENTS.items():
        assert row.retencion_note.strip(), (
            f"{category.value}/{kind.value}: retención expectation is "
            f"{row.retencion.value!r} at grounding {row.retencion_grounding.value!r} "
            "and must state its caveat in retencion_note"
        )


def test_live_source_only_rows_name_the_unbundled_provision() -> None:
    """Live-source-only grounding must point at the provision still to be bundled."""
    for (category, _kind), row in IVA_CATEGORY_COMPONENTS.items():
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
    for category in sorted(_SENTINEL_CATEGORIES, key=_category_id):
        row = IVA_CATEGORY_COMPONENTS[(category, InvoiceKind.RECEIVED)]
        assert row.cuota_grounding is IvaGroundingConfidence.UNGROUNDED
        assert row.recargo_grounding is IvaGroundingConfidence.UNGROUNDED
        assert row.retencion_grounding is IvaGroundingConfidence.UNGROUNDED
        assert row.legal_refs == ()


def test_no_row_cites_the_same_ref_as_both_bundled_and_pending() -> None:
    """A provision is either in the catalogue or it is not."""
    for (category, _kind), row in IVA_CATEGORY_COMPONENTS.items():
        overlap = sorted(set(row.legal_refs) & set(row.pending_legal_refs))
        assert overlap == [], f"{category.value} cites {overlap} as both bundled and pending"


# --------------------------------------------------------------------------- #
# Row-model refusals — proof the validators can fail, not just pass
# --------------------------------------------------------------------------- #


def _valid_row_kwargs() -> dict[str, Any]:
    return {
        "category": IvaCategory.DOMESTIC_EXEMPT,
        "kind": InvoiceKind.ISSUED,
        "applicability": IvaKindApplicability.ARISES,
        # POSSIBLE retención on an ISSUED invoice: withheld from the taxpayer,
        # so a credit. The role validator is exercised directly below.
        "retencion_role": IvaRetencionRole.TAXPAYER_CREDIT,
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
    kwargs: dict[str, Any] = _valid_row_kwargs() | {"cuota_settlement": IvaCuotaSettlement.REPERCUTIDA}
    with pytest.raises(ValidationError, match="zero-by-law cuota"):
        IvaCategoryComponents(**kwargs)


def test_a_settled_cuota_cannot_be_declared_zero_by_law() -> None:
    """The coherence check binds in both directions."""
    kwargs: dict[str, Any] = _valid_row_kwargs() | {
        "cuota": IvaComponentPresence.REQUIRED,
        "cuota_settlement": IvaCuotaSettlement.NONE,
    }
    with pytest.raises(ValidationError, match="zero-by-law cuota"):
        IvaCategoryComponents(**kwargs)


def test_weak_retencion_grounding_without_a_note_is_refused() -> None:
    """The honesty requirement is enforced by the model, not only by a test."""
    kwargs: dict[str, Any] = _valid_row_kwargs() | {
        "retencion_grounding": IvaGroundingConfidence.REASONED,
        "retencion_note": "   ",
    }
    with pytest.raises(ValidationError, match="requires a retencion_note"):
        IvaCategoryComponents(**kwargs)


def test_live_source_only_grounding_without_a_pending_ref_is_refused() -> None:
    """A live-only claim must name the provision it is waiting on."""
    kwargs: dict[str, Any] = _valid_row_kwargs() | {
        "retencion_grounding": IvaGroundingConfidence.LIVE_SOURCE_ONLY,
        "retencion_note": "verified live, provision not yet bundled",
        "pending_legal_refs": (),
    }
    with pytest.raises(ValidationError, match="no pending_legal_refs"):
        IvaCategoryComponents(**kwargs)


def test_bundled_grounding_without_legal_refs_is_refused() -> None:
    """A bundled-corpus claim must cite the corpus it claims."""
    kwargs: dict[str, Any] = _valid_row_kwargs() | {"legal_refs": ()}
    with pytest.raises(ValidationError, match="claims bundled corpus"):
        IvaCategoryComponents(**kwargs)


def test_not_expected_retencion_without_a_note_is_refused_even_when_bundled() -> None:
    """Grounding a "no retención" expectation does not make it unconditional.

    The reference row is POSSIBLE at bundled-corpus grounding with an empty
    note, and is accepted — proof this test discriminates the expectation and
    not merely the empty string. Flipping only the expectation to NOT_EXPECTED
    must refuse, because RIRPF art. 76.1 restores the obligation for a payer
    with a Spanish permanent establishment (letra c) and for rendimientos del
    trabajo and the TRLIRNR art. 24.2 deducible-gasto rendimientos (letra d).
    Without the note the row reads as a prohibition rather than a default.
    """
    accepted = _valid_row_kwargs()
    assert accepted["retencion_note"] == "", "positive control must carry no note"
    assert accepted["retencion_grounding"] is IvaGroundingConfidence.BUNDLED_CORPUS
    IvaCategoryComponents(**accepted)

    refused = accepted | {
        "retencion": IvaRetencionExpectation.NOT_EXPECTED,
        # NOT_EXPECTED forces role NONE; without this the role validator fires
        # first and the note check under test would never be reached.
        "retencion_role": IvaRetencionRole.NONE,
    }
    with pytest.raises(ValidationError, match="not-expected retención requires a retencion_note"):
        IvaCategoryComponents(**refused)

    restored = refused | {"retencion_note": "RIRPF art. 76.1.c/d carve-outs restore the obligation."}
    IvaCategoryComponents(**restored)


def test_duplicate_legal_refs_are_refused() -> None:
    """Duplicate citations would inflate an apparent grounding breadth."""
    kwargs: dict[str, Any] = _valid_row_kwargs() | {
        "legal_refs": ("ley-37-1992:art-20", "ley-37-1992:art-20"),
    }
    with pytest.raises(ValidationError, match="legal_refs must be unique"):
        IvaCategoryComponents(**kwargs)


def test_a_ref_cannot_be_both_bundled_and_pending_on_one_row() -> None:
    """The model refuses the contradiction the table-level gate also checks."""
    kwargs: dict[str, Any] = _valid_row_kwargs() | {"pending_legal_refs": ("ley-37-1992:art-20",)}
    with pytest.raises(ValidationError, match="both bundled and pending"):
        IvaCategoryComponents(**kwargs)


# --------------------------------------------------------------------------- #
# The kind axis — completeness, non-triviality, and role coherence
# --------------------------------------------------------------------------- #


def test_every_category_kind_pair_declares_a_row() -> None:
    """Completeness now means every PAIR, not merely every category.

    The category-level gate above is deliberately kept rather than replaced:
    losing it while adding this one would be a silent coverage reduction, since
    a table could satisfy "every pair present" while dropping a category
    entirely from both kinds.
    """
    missing = sorted(
        f"{category.value}/{kind.value}"
        for category in IvaCategory
        for kind in InvoiceKind
        if (category, kind) not in IVA_CATEGORY_COMPONENTS
    )
    assert missing == [], f"(category, kind) pairs without an Axis-A row: {missing}"


def test_the_kind_axis_actually_bifurcates_at_least_one_category() -> None:
    """A 32-row table that ignored kind would satisfy completeness identically.

    This is the assertion that gives the re-key its meaning. Completeness can
    only count rows; it cannot see whether the second key does any work. If
    every category declared the same columns and the same retención role on
    both sides, the pair key would be ceremony and this test says so.

    Do not delete this as redundant with the completeness gate. It is the only
    gate that fails when the kind axis is present but inert.
    """
    bifurcated = [
        category.value
        for category in IvaCategory
        if _kind_distinguishing_columns(IVA_CATEGORY_COMPONENTS[(category, InvoiceKind.ISSUED)])
        != _kind_distinguishing_columns(IVA_CATEGORY_COMPONENTS[(category, InvoiceKind.RECEIVED)])
    ]
    assert bifurcated, (
        "no category differs across ISSUED and RECEIVED — the (category, kind) key is doing no "
        "work, so the table is a category-keyed table wearing a pair-shaped key"
    )


def _kind_distinguishing_columns(row: IvaCategoryComponents) -> tuple[object, ...]:
    """The columns whose divergence across kinds is what the pair key exists for."""
    return (row.applicability, row.retencion_role, row.cuota, row.cuota_settlement)


def test_retencion_role_is_the_credit_liability_inversion_the_kind_dictates() -> None:
    """Every row's role matches its kind, so the column can be read without re-deriving.

    The inversion is the whole reason the table is keyed on the pair: the same
    withheld euro is the taxpayer's credit on an invoice they issued (RIRPF
    art. 110.3.a) and their liability to AEAT on one they received. A row that
    got this backwards would invert a deduction into a debt.
    """
    for (category, kind), row in IVA_CATEGORY_COMPONENTS.items():
        label = f"{category.value}/{kind.value}"
        if row.retencion is IvaRetencionExpectation.UNKNOWN:
            assert row.retencion_role is IvaRetencionRole.UNKNOWN, label
        elif row.retencion is IvaRetencionExpectation.NOT_EXPECTED:
            assert row.retencion_role is IvaRetencionRole.NONE, label
        elif kind is InvoiceKind.ISSUED:
            assert row.retencion_role is IvaRetencionRole.TAXPAYER_CREDIT, label
        else:
            assert row.retencion_role is IvaRetencionRole.TAXPAYER_LIABILITY, label


def test_both_retencion_roles_are_actually_used() -> None:
    """Neither role is dead data.

    A table that only ever declared one role would pass the coherence gate
    above trivially — that gate checks agreement, not that both branches occur.
    """
    roles = {row.retencion_role for row in IVA_CATEGORY_COMPONENTS.values()}
    assert IvaRetencionRole.TAXPAYER_CREDIT in roles
    assert IvaRetencionRole.TAXPAYER_LIABILITY in roles


def test_non_arising_pairs_are_a_strict_nonempty_subset() -> None:
    """Directional categories are declared one-sided, and most pairs still arise.

    Both bounds matter. Zero non-arising pairs would mean the directional
    categories were never declared one-sided, so an "import" the taxpayer
    issued would read as a real operation. Everything non-arising would mean
    the table describes nothing.
    """
    non_arising = {
        (category.value, kind.value)
        for (category, kind), row in IVA_CATEGORY_COMPONENTS.items()
        if row.applicability is IvaKindApplicability.DOES_NOT_ARISE
    }
    assert non_arising, "no pair is declared non-arising, so no category is treated as directional"
    assert len(non_arising) < len(IVA_CATEGORY_COMPONENTS), "every pair is non-arising; the table describes nothing"


def test_a_role_contradicting_its_kind_is_refused() -> None:
    """The role is validated, not trusted — a received credit cannot be authored."""
    kwargs = _valid_row_kwargs()
    kwargs["kind"] = InvoiceKind.RECEIVED
    kwargs["retencion_role"] = IvaRetencionRole.TAXPAYER_CREDIT
    with pytest.raises(ValidationError, match="requires role"):
        IvaCategoryComponents(**kwargs)


def test_a_non_arising_pair_asserting_components_is_refused() -> None:
    """A pair that cannot occur cannot also claim a required base."""
    kwargs = _valid_row_kwargs()
    kwargs["applicability"] = IvaKindApplicability.DOES_NOT_ARISE
    kwargs["retencion"] = IvaRetencionExpectation.UNKNOWN
    kwargs["retencion_role"] = IvaRetencionRole.UNKNOWN
    kwargs["retencion_note"] = "counterpart named here"
    with pytest.raises(ValidationError, match="cannot assert"):
        IvaCategoryComponents(**kwargs)


def test_a_non_arising_pair_without_a_counterpart_note_is_refused() -> None:
    """The only useful thing a non-arising row carries is which category IS this side."""
    kwargs = _valid_row_kwargs()
    kwargs["applicability"] = IvaKindApplicability.DOES_NOT_ARISE
    kwargs["base"] = IvaComponentPresence.UNKNOWN
    kwargs["cuota"] = IvaComponentPresence.UNKNOWN
    kwargs["cuota_settlement"] = IvaCuotaSettlement.UNKNOWN
    kwargs["cuota_grounding"] = IvaGroundingConfidence.UNGROUNDED
    kwargs["recargo"] = IvaComponentPresence.UNKNOWN
    kwargs["recargo_grounding"] = IvaGroundingConfidence.UNGROUNDED
    kwargs["retencion"] = IvaRetencionExpectation.UNKNOWN
    kwargs["retencion_grounding"] = IvaGroundingConfidence.UNGROUNDED
    kwargs["retencion_role"] = IvaRetencionRole.UNKNOWN
    kwargs["retencion_note"] = "   "
    kwargs["legal_refs"] = ()
    with pytest.raises(ValidationError, match="counterpart"):
        IvaCategoryComponents(**kwargs)
