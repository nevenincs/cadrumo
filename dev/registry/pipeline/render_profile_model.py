"""Canonical immutable aggregate model and exact indexes for reviewed render profiles."""

from __future__ import annotations

from collections.abc import Mapping
from functools import cached_property
from typing import Literal

from pydantic import model_validator

from .render_profile_model_base import RenderProfileAnchor, RenderProfileDesignIdentity, _StrictModel
from .render_profile_rules import (
    LiteralNumericRule,
    SignedMonetaryCompositeRule,
    SingletonNumericRule,
    TelematicTransportChoiceRule,
    Width17MembershipRule,
)
from .render_profile_validation import _duplicates


class RenderProfile(_StrictModel):
    """Deterministically compiled complete profile for one official design."""

    schema_version: Literal[1]
    design_identity: RenderProfileDesignIdentity
    fragment_ids: tuple[str, ...]
    width_17_rules: tuple[Width17MembershipRule, ...]
    singleton_rules: tuple[SingletonNumericRule, ...]
    signed_composite_rules: tuple[SignedMonetaryCompositeRule, ...] = ()
    literal_numeric_rules: tuple[LiteralNumericRule, ...] = ()
    telematic_transport_choice_rules: tuple[TelematicTransportChoiceRule, ...] = ()
    empty_rule_assertion: Literal["canonical_eligibility_empty"] | None = None

    @cached_property
    def telematic_transport_choice_rule_by_anchor(self) -> Mapping[RenderProfileAnchor, TelematicTransportChoiceRule]:
        """Return each source-anchored transport choice by its exact field."""
        return {rule.anchor: rule for rule in self.telematic_transport_choice_rules}

    @cached_property
    def literal_numeric_rule_by_anchor(self) -> Mapping[RenderProfileAnchor, LiteralNumericRule]:
        """Exact constant anchors carrying an authored numeric scale."""
        return {rule.anchor: rule for rule in self.literal_numeric_rules}

    @cached_property
    def signed_composite_rule_by_anchor(self) -> Mapping[RenderProfileAnchor, SignedMonetaryCompositeRule]:
        """The signed monetary composite governing each anchor, whatever naturaleza AEAT printed for it."""
        return {rule.anchor: rule for rule in self.signed_composite_rules}

    @cached_property
    def width_17_rule_by_anchor(self) -> Mapping[RenderProfileAnchor, Width17MembershipRule]:
        """The width-17 rule covering each anchor, indexed rather than scanned.

        The renderer asks this per FIELD, and a scan answered it by comparing
        the field's anchor against every anchor of every rule in turn. Anchors
        are frozen models, so ``in`` over a rule's tuple runs pydantic's
        ``BaseModel.__eq__`` per element: generating one modelo's export tree
        issued 32.5 million of those comparisons, 41% of its runtime. The
        anchors are hashable, so the same answer is one dict lookup.

        First anchor wins, matching the scan it replaces: ``next()`` returned
        the first rule whose anchors contained the field's, so a later rule
        claiming the same anchor was already unreachable.
        """
        index: dict[RenderProfileAnchor, Width17MembershipRule] = {}
        for rule in self.width_17_rules:
            for anchor in rule.anchors:
                index.setdefault(anchor, rule)
        return index

    @cached_property
    def singleton_rule_by_anchor(self) -> Mapping[RenderProfileAnchor, SingletonNumericRule]:
        """The singleton numeric rule for each anchor, indexed rather than scanned.

        First rule wins, matching the ``next()`` scan it replaces.
        """
        index: dict[RenderProfileAnchor, SingletonNumericRule] = {}
        for rule in self.singleton_rules:
            index.setdefault(rule.anchor, rule)
        return index

    @model_validator(mode="after")
    def _require_unique_fragment_ids(self) -> RenderProfile:
        duplicate_ids = _duplicates(self.fragment_ids)
        if duplicate_ids:
            raise ValueError(f"render profile contains duplicate fragment ids: {duplicate_ids!r}")
        return self
