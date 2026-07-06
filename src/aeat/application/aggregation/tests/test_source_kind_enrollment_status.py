"""Enrollment-status gate for deferred binding source kinds.

Every deferred source kind must be governed rather than merely enumerated: the
governing decision record for source-kind deferrals re-ratifies each kind with
a typed promotion target (owning decision-record stem + trigger) instead of a
free-prose comment. This gate reads that declaration
(:data:`DEFERRED_SOURCE_KIND_TARGETS`) and asserts:

* every deferred kind carries a promotion target whose owning decision-record
  stem resolves to a real decision record and whose trigger is stated; and
* no deferred kind's trigger has already fired — a kind gated on another source
  kind that has since been promoted out of the deferred set, yet which remains
  deferred, is a mechanically-detectable finding surfaced at the swarm-audit
  cadence.

The advisory safety floor is invariant and asserted elsewhere: every deferred
kind keeps its standing calculate-path advisory and none enters the
manual-input allowlist. This gate governs the deferral set's metadata, not the
calculate path — there is no calculate-path behaviour here.
"""

from __future__ import annotations

import pytest

from ....core import BindingSourceKind
from ....tests import REPO_ROOT
from ...aggregation import (
    DEFERRED_SOURCE_KIND_TARGETS,
    DEFERRED_SOURCE_KINDS,
    DeferredSourceTarget,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ADR_DIR = REPO_ROOT / ".vault" / "adr"


def test_deferred_membership_is_derived_from_the_targets_mapping() -> None:
    """``DEFERRED_SOURCE_KINDS`` equals the targets mapping's keys — they cannot drift.

    Deriving the membership frozenset from the annotated mapping is what makes a
    new deferred kind without an owning decision record + trigger impossible: a
    kind is deferred only by being a key in ``DEFERRED_SOURCE_KIND_TARGETS``.
    """
    assert frozenset(DEFERRED_SOURCE_KIND_TARGETS) == DEFERRED_SOURCE_KINDS


def test_every_deferred_kind_carries_an_owning_decision_record_and_trigger() -> None:
    """Each deferred kind names the decision that owns it and its promotion trigger."""
    offences: list[str] = []
    for kind, target in DEFERRED_SOURCE_KIND_TARGETS.items():
        if not isinstance(target, DeferredSourceTarget):
            offences.append(f"{kind.value}: target is not a DeferredSourceTarget")
            continue
        if not target.owning_adr.strip():
            offences.append(f"{kind.value}: empty owning_adr")
        if not target.trigger.strip():
            offences.append(f"{kind.value}: empty trigger")
    assert not offences, "Deferred kinds missing governance metadata:\n" + "\n".join(f"  * {o}" for o in offences)


def test_every_owning_decision_record_resolves_to_a_real_decision_record() -> None:
    """Each deferred kind's owning decision-record stem resolves to a shipped decision-record file.

    A typo'd or dangling owning stem is caught here rather than being
    accepted as governance that points nowhere.
    """
    missing: list[str] = []
    for kind, target in DEFERRED_SOURCE_KIND_TARGETS.items():
        adr_path = _ADR_DIR / f"{target.owning_adr}.md"
        if not adr_path.is_file():
            missing.append(f"{kind.value}: owning_adr '{target.owning_adr}' has no file at {adr_path}")
    assert not missing, "Deferred kinds citing an unresolvable owning decision record:\n" + "\n".join(
        f"  * {m}" for m in missing
    )


def test_no_deferred_kind_has_a_fired_trigger() -> None:
    """A deferred kind whose named dependency has been promoted must not stay deferred.

    For a dependency-triggered kind (``promotion_depends_on`` set), the trigger
    has FIRED once that dependency is no longer in the deferred set — it has been
    promoted to a live resolver. A kind whose trigger has fired but which remains
    deferred is a governance finding: promote it, or re-ratify with a new trigger.
    Kinds with no ``promotion_depends_on`` (the informativa human-review triggers)
    are never flagged here — their review is a human cadence, not a mechanical
    dependency.
    """
    fired: list[str] = []
    for kind, target in DEFERRED_SOURCE_KIND_TARGETS.items():
        dependency = target.promotion_depends_on
        if dependency is None:
            continue
        if dependency not in DEFERRED_SOURCE_KINDS:
            fired.append(
                f"{kind.value}: its promotion dependency '{dependency.value}' has been promoted out of the "
                f"deferred set, so its trigger has FIRED — promote {kind.value} to a live mesh binding or "
                f"re-ratify its deferral with a new trigger (owning decision record {target.owning_adr})."
            )
    assert not fired, "Deferred kinds with a fired promotion trigger:\n" + "\n".join(f"  * {f}" for f in fired)


def test_dependency_triggers_reference_a_real_deferred_or_enrolled_kind() -> None:
    """A ``promotion_depends_on`` names a genuine source kind, not a dangling reference.

    Anti-tautology guard for the fired-trigger check: if a dependency named a
    kind that never existed in the deferred set, the fired-trigger test would be
    vacuous. Every declared dependency must currently be a deferred kind (the
    pre-fire state this test suite ships in), so the check stays live.
    """
    for kind, target in DEFERRED_SOURCE_KIND_TARGETS.items():
        dependency = target.promotion_depends_on
        if dependency is None:
            continue
        assert dependency in DEFERRED_SOURCE_KINDS, (
            f"{kind.value} declares promotion_depends_on '{dependency.value}', which is not a deferred kind — "
            f"the fired-trigger check would be vacuous. Point it at a real deferred dependency."
        )


def test_bienes_inversion_deferral_is_re_ratified_after_prorrata_promotion() -> None:
    """The casilla-43 source no longer waits only on prorrata_regularizacion."""
    target = DEFERRED_SOURCE_KIND_TARGETS[BindingSourceKind.BIENES_INVERSION_REGULARIZACION]

    assert target.promotion_depends_on is None
    assert "bienes-inversion source resolver" in target.trigger
    assert "Modelo 303 casilla 43 / Modelo 390 regularizacion binding targets" in target.trigger
    assert "LIVA arts. 107-110" in target.trigger
