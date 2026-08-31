"""Every classification rule cites the provision that places it.

Three properties. Each rule the decision table declares has a grounding row and
each row has a rule, in both directions, so a rule cannot ship ungrounded and a
row cannot outlive the rule it grounds. Every provision a row cites resolves to a
real entry in the legal catalogue. And the goods/services fork appears exactly
where the law forks -- on the cross-border branches -- while the domestic ones
stay silent, which is the laziness property expressed as data rather than as a
comment.

The natures are checked against the bundled consolidated text of the articles the
row itself cites, not against a literal typed beside the row. An expectation
copied from the row would pass whatever the row said.

See Also:
    :class:`~domain.iva.IvaCategory`
        The treatments these rules resolve into.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date

import pytest

from ....core.resources.bundled_data import bundled_path
from ..classification import _CLASSIFICATION_RULES, _R99_FALLTHROUGH_ID
from ..place_of_supply import (
    IvaPlaceOfSupplyRule,
    load_place_of_supply_table,
    place_of_supply_rule,
    required_supply_nature_for_rule,
)
from ..supply_nature import SupplyNature

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_YEAR = 2025
_ON = date(_YEAR, 6, 1)

# The consolidated law, read once. Every article this table cites is an anchor
# into this file rather than a per-article extract, which is the shape the
# grounding rule prefers over a hand-authored duplicate.
_LIVA = (bundled_path() / "corpus/normatives/html/ley-37-1992.html.extracted.md").read_text(
    encoding="utf-8",
    errors="replace",
)

# The rules the decision table resolves without crossing a border. Their
# treatment is settled by the rate tier, so their provisions are expected to be
# silent on the nature.
_DOMESTIC_RULE_IDS = frozenset(
    {
        "R01_construction_reverse_charge",
        "R02_waste_reverse_charge",
        "R03_electronics_reverse_charge",
        "R04_immovable_property_exempt",
        "R05_domestic_at_rate_tier",
    },
)


def _rules() -> Mapping[str, IvaPlaceOfSupplyRule]:
    return load_place_of_supply_table()


def _declared_rule_ids() -> frozenset[str]:
    """Every rule id a classification RESULT can carry.

    The decision table plus the fall-through id, which is emitted when no row
    matches and is therefore just as reachable by a caller inspecting a result.
    Taking only the table would leave the one id a reader is most likely to meet
    on an unclassifiable document outside the grounding contract entirely.
    """
    return frozenset(rule.rule_id for rule in _CLASSIFICATION_RULES) | {_R99_FALLTHROUGH_ID}


def test_every_declared_rule_is_grounded_and_every_row_grounds_a_rule() -> None:
    """Parity in both directions, stated as sets rather than as a count.

    A count would encode this moment and would be updated rather than
    investigated the next time a rule is added.
    """
    declared = _declared_rule_ids()
    grounded = frozenset(_rules())

    assert declared - grounded == frozenset(), "classification rules ship with no provision behind their placement"
    assert grounded - declared == frozenset(), "grounding rows name rules the decision table does not declare"


def test_every_cited_provision_resolves_in_the_legal_catalogue() -> None:
    """A row citing an article nobody defined is ungrounded and must not ship."""
    catalogue = (bundled_path() / "registry/aeat/legal/iva.toml").read_text(encoding="utf-8", errors="replace")
    flow = (bundled_path() / "registry/aeat/legal/iva-flow.toml").read_text(encoding="utf-8", errors="replace")
    defined = catalogue + flow

    for rule in _rules().values():
        for reference in rule.legal_references:
            assert f'[legal."{reference}"]' in defined, (
                f"{rule.rule_id} cites {reference}, which no legal catalogue entry defines"
            )


def test_the_establishing_provision_is_one_the_row_actually_reads() -> None:
    """Enforced by the model; asserted here so the invariant is visible at the data.

    The legal-basis-exempt sentinel is excluded because it cites nothing at all --
    and the exclusion is asserted rather than assumed, so this case cannot quietly
    become vacuous if every row were one day exempted.
    """
    grounded = [rule for rule in _rules().values() if not rule.legal_basis_exempt]

    assert grounded, "every row is legal-basis exempt; this case would pass over an ungrounded table"
    for rule in grounded:
        assert rule.establishing_reference in rule.legal_references


@pytest.mark.parametrize("rule_id", sorted(_DOMESTIC_RULE_IDS))
def test_a_domestic_rule_is_silent_on_the_nature(rule_id: str) -> None:
    """Laziness as data: the branches that do not fork must not demand the fact.

    A domestic operation is placed in the same territory by both placement rules,
    so its treatment turns on the rate tier. Declaring a nature here would make
    the axis eager and refuse invoices for a distinction their own treatment
    ignores.
    """
    assert required_supply_nature_for_rule(rule_id, on=_ON) is None


def test_the_cross_border_branches_are_where_the_fork_appears() -> None:
    """The mirror of the case above, so silence is not simply universal.

    Stated as a property of the partition rather than per rule: at least one
    cross-border rule fixes goods and at least one fixes services, and no
    domestic rule fixes anything.
    """
    cross_border = {rule_id: rule for rule_id, rule in _rules().items() if rule_id not in _DOMESTIC_RULE_IDS}
    fixed = {rule.supply_nature for rule in cross_border.values()}

    assert SupplyNature.GOODS in fixed
    assert SupplyNature.SERVICES in fixed
    assert all(_rules()[rule_id].supply_nature is None for rule_id in _DOMESTIC_RULE_IDS)


def test_a_row_fixing_goods_rests_on_an_article_the_statute_writes_for_goods() -> None:
    """Checked against the consolidated text, not against the row.

    LIVA art. 68 is titled for *entregas de bienes* and arts. 69 and 70 for
    *prestaciones de servicios*. A row claiming GOODS while resting only on the
    services placement articles has its fork backwards, and reading the statute
    is what can catch that.
    """
    assert "# Artículo 68. Lugar de realización de las entregas de bienes." in _LIVA
    assert "# Artículo 69. Lugar de realización de las prestaciones de servicios." in _LIVA

    goods_placement = "ley-37-1992:art-68"
    services_placement = {"ley-37-1992:art-69", "ley-37-1992:art-70"}

    for rule in _rules().values():
        if rule.supply_nature is SupplyNature.GOODS:
            assert not (set(rule.legal_references) & services_placement) or goods_placement in rule.legal_references, (
                f"{rule.rule_id} fixes GOODS while reading only the services placement articles"
            )
        if rule.supply_nature is SupplyNature.SERVICES:
            assert goods_placement not in rule.legal_references, (
                f"{rule.rule_id} fixes SERVICES while reading the goods placement article"
            )


def test_the_union_scheme_article_never_fixes_the_nature_on_its_own() -> None:
    """The correction that would otherwise have been inherited from prose.

    LIVA art. 163 unvicies reaches "presten servicios" and "ventas a distancia
    intracomunitarias de bienes" alike, so citing it alone determines nothing. The
    rules that ride it must fix the nature on a placement article instead.
    """
    union_scheme = "ley-37-1992:art-163-unvicies"
    riders = [rule for rule in _rules().values() if union_scheme in rule.legal_references]

    assert riders, "no rule cites the Union scheme; this guard would pass vacuously"
    for rule in riders:
        if rule.supply_nature is not None:
            assert rule.establishing_reference != union_scheme, (
                f"{rule.rule_id} fixes a nature on an article that reaches both limbs"
            )


def test_the_statute_itself_shows_the_union_scheme_article_reaching_both_limbs() -> None:
    """The claim above, checked against the law rather than restated.

    The case above pins the DATA. This pins the reason: art. 163 unvicies really
    does reach both limbs in the bundled consolidated text. Without it the guard
    rests on an assertion nobody re-derives, which is exactly how the enum's own
    prose came to describe the article as a goods provision.
    """
    heading = "# Artículo 163 unvicies."
    start = _LIVA.find(heading)
    assert start != -1, "the Union scheme article is not in the bundled consolidated text"

    # The scope paragraph, not the whole article: a long article mentions the
    # other limb incidentally further down, and reading to the end would make the
    # claim true of almost any provision.
    scope = _LIVA[start : start + 1200]
    assert "presten servicios" in scope
    assert "ventas a distancia intracomunitarias de bienes" in scope


def test_the_enum_prose_does_not_attribute_a_nature_to_the_union_scheme_article() -> None:
    """The docstring is a source readers trust, so it is gated like the data.

    Two readers derived the wrong nature from this prose before going to the
    statute, and one nearly shipped a row establishing GOODS from it. The check is
    narrow on purpose: it does not police wording, only the specific attribution
    that misled -- a member described as a goods-or-services kind whose stated
    authority is the article that establishes neither.
    """
    from ..classification import TransactionKind

    doc = TransactionKind.__doc__ or ""
    assert doc, "the enum lost its docstring; this guard would pass vacuously"

    # The defect is an attribution, so the check is an attribution: no sentence
    # may say the operation is LOCATED by art. 163 unvicies. Naming the article
    # beside a placement article is correct and must stay allowed -- that is
    # precisely what the corrected prose does.
    flattened = " ".join(doc.split())
    misattribution = re.compile(r"locat\w*[^.]*163\s+unvicies", re.IGNORECASE)
    offender = misattribution.search(flattened)

    assert offender is None, (
        f"the enum prose attributes placement to art. 163 unvicies: {offender.group(0)!r}" if offender else ""
    )

    assert "Admitted to the scheme by" in doc or "Admitted by" in doc, (
        "the enum no longer distinguishes admission to the Union scheme from placement, "
        "which is the distinction two readers previously missed"
    )


def test_an_ungrounded_rule_refuses_rather_than_returning_a_default() -> None:
    """Refusal is the contract: a placement with no provision is not answerable."""
    from ..errors import IvaCatalogueError

    with pytest.raises(IvaCatalogueError, match="not grounded"):
        place_of_supply_rule("RZZ_no_such_rule", on=_ON)

    with pytest.raises(IvaCatalogueError, match="no place-of-supply grounding for year"):
        place_of_supply_rule("R05_domestic_at_rate_tier", on=date(1990, 1, 1))
