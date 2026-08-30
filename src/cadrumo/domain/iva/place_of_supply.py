"""Which provision places an operation, and whether it fixes the supply's nature.

The classification rules decide WHERE an operation is located and therefore how
it is treated. Until now they carried none of the law that establishes those
decisions: the predicates encoded the conditions in Python and the regulatory
content -- which article places the operation, and whether that article speaks to
goods or to services -- existed nowhere. A predicate is logic and belongs in
Python; the provision behind it is regulatory content, versioned by filing year,
and belongs in the registry.

**The goods/services fork is why this is not the per-category table.** LIVA art.
68 locates *entregas de bienes*; arts. 69 and 70 locate *prestaciones de
servicios*. On a cross-border branch the same two parties, the same amount and
the same day are placed by different articles and can reach different treatments.
Several rules share one category while resting on different provisions -- three
separate reverse-charge rules all resolve to ``DOMESTIC_REVERSE_CHARGE`` -- so a
table keyed by category cannot express what establishes each one.

**An absent nature is a finding, not a blank.** A rule whose provisions do not fix
whether goods or services were supplied omits ``supply_nature``, and that omission
means the articles are silent. It never means the row is unfinished. The worked
case is the Union scheme: LIVA art. 163 unvicies reaches "presten servicios"
*and* "ventas a distancia intracomunitarias de bienes", so citing it alone
determines nothing -- the goods rules that ride it are fixed by art. 68 instead,
and the services rule by art. 69.

**The domestic rules omit it deliberately.** Both placement rules put a domestic
operation in the same territory, so its treatment is settled by the rate tier
rather than by what was supplied. Demanding the distinction there would refuse
invoices for a fact their own treatment ignores, which is the laziness property
the supply-nature axis exists to keep.

**Refusal rather than a guess.** :func:`place_of_supply_rule` raises for a rule
with no row, and :func:`required_supply_nature_for_rule` returns ``None`` for a
rule whose provisions are silent. Neither substitutes a default; a caller that
cannot determine the placement is expected to say so.

See Also:
    :class:`~domain.iva.IvaCategory`
        The treatments these rules resolve into.
    :class:`~domain.iva.SupplyNature`
        The axis a cross-border rule's provisions may or may not fix.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import TypeGuard

from pydantic import BaseModel, Field, model_validator

from ...core import read_toml
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.resources import bundled_path
from ...core.validity_window import ValidityWindow, years_covered_by_every_group
from ._grounding import verify_table_legal_refs
from .errors import IvaCatalogueError
from .supply_nature import SupplyNature

__all__ = [
    "IvaPlaceOfSupplyRule",
    "load_place_of_supply_table",
    "place_of_supply_rule",
    "place_of_supply_years",
    "required_supply_nature_for_rule",
]


class IvaPlaceOfSupplyRule(BaseModel):
    """The legal grounding of one classification rule's placement.

    Attributes:
        rule_id: The classification rule this grounds, matching the id the
            decision table declares. A parity gate proves the two sets are equal
            in both directions, so a rule cannot ship ungrounded and a row cannot
            outlive its rule.
        supply_nature: The nature the cited provisions fix, or ``None`` when they
            are silent on it. ``None`` is a statement about the statute.
        legal_references: Every provision the rule rests on, in reading order.
            At least one.
        establishing_reference: The one provision that establishes the treatment,
            which must also appear in :attr:`legal_references`. Citing the whole
            reading list leaves unanswered which article actually decides.
        notes: Reviewer prose in Spanish, matching the sibling catalogue.
        valid_from: First date this grounding is asserted to hold. Required on a
            grounded row, absent on a legal-basis-exempt one.
        valid_to: Last date, inclusive. Same rule.

    The window attaches to the RULE rather than to a citation because the rule is
    the grounding-bearing row here: its provisions are bare reference ids with no
    table of their own to carry a span. The bounds are closed and a gate holds
    them inside the intersection of the cited provisions' effective spans.
    """

    model_config = STRICT_FROZEN_CONFIG

    rule_id: str = Field(min_length=1)
    supply_nature: SupplyNature | None = None
    legal_references: tuple[str, ...] = ()
    establishing_reference: str = ""
    notes: str = ""
    legal_basis_exempt: bool = False
    valid_from: date | None = None
    valid_to: date | None = None

    @property
    def window(self) -> ValidityWindow | None:
        """Return the span this grounding is asserted over, or ``None`` when exempt.

        Returns:
            The declared :class:`~core.validity_window.ValidityWindow`, or
            ``None`` for a legal-basis-exempt row, which grounds nothing and so
            is asserted over nothing.
        """
        if self.valid_from is None or self.valid_to is None:
            return None
        return ValidityWindow(valid_from=self.valid_from, valid_to=self.valid_to)

    @model_validator(mode="after")
    def _each_row_carries_exactly_what_its_kind_claims(self) -> IvaPlaceOfSupplyRule:
        """Refuse a row whose citations do not match the kind of rule it grounds.

        A grounded row must cite at least one provision and must name a deciding
        one among them; the two fields would otherwise drift apart silently,
        leaving a row that calls an article decisive while reading a different
        set. An exempt row must cite nothing at all, which is what keeps the
        exemption from becoming a place to park a half-filled row.

        A rule that codifies no tax treatment cannot be grounded, and demanding an
        article for it would manufacture the appearance of a legal basis it has
        none of by design. That is the same distinction the sibling regulation
        table draws, and it is narrow: it is not an escape for a rule that DOES
        need grounding and has not been given it yet.
        """
        if self.legal_basis_exempt:
            if self.legal_references or self.establishing_reference:
                raise IvaCatalogueError(
                    f"place-of-supply rule {self.rule_id!r}: a legal-basis-exempt row cites no provision, "
                    "because it codifies no tax treatment to ground",
                )
            if self.supply_nature is not None:
                raise IvaCatalogueError(
                    f"place-of-supply rule {self.rule_id!r}: a legal-basis-exempt row fixes no supply nature",
                )
            if self.valid_from is not None or self.valid_to is not None:
                raise IvaCatalogueError(
                    f"place-of-supply rule {self.rule_id!r}: a legal-basis-exempt row declares no validity "
                    "window, because a row that grounds nothing is asserted over nothing",
                )
            return self
        if self.valid_from is None or self.valid_to is None:
            raise IvaCatalogueError(
                f"place-of-supply rule {self.rule_id!r}: a grounded row must declare both validity bounds; "
                "an absent bound would read as effective from the beginning of time or until further "
                "notice, and neither is a claim anybody made",
            )
        # Constructing the window is the validation: an inverted span covers no
        # year and would make the rule vanish from every filing year instead of
        # failing where it was written.
        _ = self.window
        if not self.legal_references:
            raise IvaCatalogueError(
                f"place-of-supply rule {self.rule_id!r}: must cite the provision that establishes its placement",
            )
        if self.establishing_reference not in self.legal_references:
            raise IvaCatalogueError(
                f"place-of-supply rule {self.rule_id!r}: establishing_reference "
                f"{self.establishing_reference!r} is not among its legal_references",
            )
        return self


def load_place_of_supply_table(path: Path | None = None) -> Mapping[str, IvaPlaceOfSupplyRule]:
    """Load the undated place-of-supply grounding table.

    Args:
        path: The corpus file. Defaults to the bundled one, resolved through the
            same boundary the sibling catalogue uses.

    Returns:
        Rules keyed by rule id, each carrying the span it is asserted over.

    Raises:
        IvaCatalogueError: When the file is unreadable, malformed, or carries a
            duplicate rule id.
    """
    target = path if path is not None else bundled_path("registry", "aeat", "iva", "place_of_supply.toml")
    resolved = target.resolve()
    try:
        stat = resolved.stat()
    except OSError as exc:
        raise IvaCatalogueError(f"{resolved}: cannot stat place-of-supply table: {exc}") from exc
    return _load_cached(str(resolved), stat.st_size, stat.st_mtime_ns)


def place_of_supply_years(path: Path | None = None) -> frozenset[int]:
    """Return every filing year the table can be resolved for.

    A year counts only when EVERY grounded rule is asserted over it. A rule whose
    provisions stop earlier stops the table, because a classification answered
    from a rule that does not apply is worse than a refusal. Legal-basis-exempt
    rows ground nothing and are excluded rather than treated as covering
    everything or nothing.

    Returns:
        The derived set of resolvable filing years.
    """
    windows = [rule.window for rule in load_place_of_supply_table(path).values() if rule.window is not None]
    return years_covered_by_every_group([window] for window in windows)


def _is_object_list(value: object) -> TypeGuard[list[object]]:
    """Narrow an unparameterized runtime list to untrusted object entries."""
    return isinstance(value, list)


def _is_str_keyed_mapping(value: object) -> TypeGuard[Mapping[str, object]]:
    """Narrow an unparameterized runtime dict to a string-keyed mapping.

    True by construction for a table parsed from TOML: ``tomllib`` always
    produces string keys.
    """
    return isinstance(value, dict)


def _hydrated_rule(raw_rule: object, *, path: Path, index: int) -> IvaPlaceOfSupplyRule:
    """Hydrate one ``[[place_of_supply_rules]]`` table into its typed row.

    Registry TOML stays free-form and the typed axes are hydrated here, at the
    boundary: the model is strict, so a raw list and a raw token are both
    refused rather than silently coerced further in.
    """
    if not _is_str_keyed_mapping(raw_rule):
        raise IvaCatalogueError(f"{path}: place_of_supply_rules[{index}] must be a table")
    # Shape only. WHETHER a row may cite nothing is the model's call, so
    # that the legal-basis exemption is decided in one place rather than
    # half here and half there.
    raw_references = raw_rule.get("legal_references", [])
    if not _is_object_list(raw_references):
        raise IvaCatalogueError(
            f"{path}: place_of_supply_rules[{index}] legal_references must be an array",
        )
    raw_nature = raw_rule.get("supply_nature")
    try:
        nature = SupplyNature(raw_nature) if raw_nature is not None else None
    except ValueError as exc:
        accepted = ", ".join(sorted(member.value for member in SupplyNature))
        raise IvaCatalogueError(
            f"{path}: place_of_supply_rules[{index}] supply_nature {raw_nature!r} is not one of: {accepted}",
        ) from exc
    return IvaPlaceOfSupplyRule.model_validate(
        {**raw_rule, "legal_references": tuple(raw_references), "supply_nature": nature},
    )


def _rules_in_table(path: Path) -> dict[str, IvaPlaceOfSupplyRule]:
    """Read the place-of-supply TOML into its ``rule_id``-keyed table.

    A duplicate id refuses rather than last-write-wins: two rows claiming one id
    is an authoring error, and silently keeping the later one would ground a
    classification on a provision the author did not mean to apply.
    """
    payload = read_toml(path, error_factory=IvaCatalogueError)
    raw_rules = payload.get("place_of_supply_rules")
    if not _is_object_list(raw_rules) or not raw_rules:
        raise IvaCatalogueError(f"{path}: missing [[place_of_supply_rules]] entries")
    rules: dict[str, IvaPlaceOfSupplyRule] = {}
    for index, raw_rule in enumerate(raw_rules, start=1):
        rule = _hydrated_rule(raw_rule, path=path, index=index)
        if rule.rule_id in rules:
            raise IvaCatalogueError(f"{path}: duplicate place-of-supply rule {rule.rule_id!r}")
        rules[rule.rule_id] = rule
    return rules


@lru_cache(maxsize=8)
def _load_cached(
    path: str,
    byte_count: int,
    modified_ns: int,
) -> Mapping[str, IvaPlaceOfSupplyRule]:
    del byte_count, modified_ns
    target = Path(path)
    rules = _rules_in_table(target)
    # Only ``legal_references`` is verified. ``establishing_reference`` is
    # required by the model to be a member of it, so verifying both would
    # re-resolve the same provision under a second label and report one broken
    # citation twice.
    verify_table_legal_refs(
        str(target),
        [(rule.rule_id, rule.legal_references) for rule in rules.values()],
    )
    return MappingProxyType(rules)


def place_of_supply_rule(rule_id: str, *, on: date) -> IvaPlaceOfSupplyRule:
    """Return the grounding for ``rule_id`` in the filing year of ``on``.

    Args:
        rule_id: The classification rule's declared id.
        on: A date in the filing year whose table applies.

    Returns:
        :class:`IvaPlaceOfSupplyRule`: The grounding row.

    Raises:
        IvaCatalogueError: When the table grounds no such year, or carries no row
            for the rule, or the row is not asserted over that year. Raising is
            correct rather than returning a permissive default: an ungrounded
            placement has no provision behind it, and answering anyway would
            manufacture one.
    """
    rules = load_place_of_supply_table()
    grounded_years = place_of_supply_years()
    if on.year not in grounded_years:
        raise IvaCatalogueError(
            f"no place-of-supply grounding for year={on.year}; the table grounds "
            f"{sorted(grounded_years)}. Ground the year against BOE or AEAT -- never widen a rule's "
            "window to admit it.",
        )
    rule = rules.get(rule_id)
    if rule is None or (rule.window is not None and not rule.window.covers_year(on.year)):
        raise IvaCatalogueError(
            f"place-of-supply rule {rule_id!r} is not grounded for year={on.year}; "
            "every classification rule must cite the provision that establishes its placement",
        )
    return rule


def required_supply_nature_for_rule(rule_id: str, *, on: date) -> SupplyNature | None:
    """Return the nature this rule's provisions fix, or ``None`` when silent.

    Args:
        rule_id: The classification rule's declared id.
        on: A date in the filing year whose table applies.

    Returns:
        The fixed :class:`~domain.iva.SupplyNature`, or ``None`` when the cited
        provisions do not determine it -- a domestic rule settled by its rate
        tier, or a territorial rule that reaches both limbs alike.

    Raises:
        IvaCatalogueError: When the rule is not grounded at all, which is a
            different condition from being grounded and silent.
    """
    return place_of_supply_rule(rule_id, on=on).supply_nature
