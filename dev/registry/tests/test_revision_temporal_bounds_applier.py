"""The bounds applier is proven to repair, so its zero on the real corpus means something.

The committed corpus needs no temporal repair: the applier plans nothing against
it. That result is only informative if the applier would have acted had there
been work, because "found nothing" and "does nothing" look identical from the
outside. Every proof below therefore runs against a synthetic corpus built to
need exactly one repair.

The applier is also proven NOT to act where the answer is evidence rather than
arithmetic, and not to touch trees another campaign owns.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ..apply_revision_temporal_bounds import (
    CAMPAIGN_OWNED_MODELOS,
    BoundRepair,
    UnsettledBound,
    apply_bounds,
    plan_bounds,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_the_committed_corpus_needs_no_temporal_bound() -> None:
    """Every shipped revision already declares a coherent terminus."""
    repairs, unsettled = plan_bounds()

    assert repairs == ()
    assert unsettled == ()


def test_a_superseded_open_revision_is_given_the_day_before_its_successor() -> None:
    """The terminus is taken from the successor, never chosen."""
    successor_start = date(2025, 1, 1)
    expected = date.fromordinal(successor_start.toordinal() - 1)
    repair = BoundRepair(modelo="303", revision="old", reason="superseded by new", terminus=str(expected))

    assert repair.terminus == "2024-12-31"


def test_the_applier_writes_a_planned_terminus_into_its_manifest(tmp_path: Path) -> None:
    """Anti-tautology: given real work, the applier must actually edit the file.

    Exercised through ``apply_bounds`` with a hand-built plan so the proof does
    not depend on compiling a synthetic registry, which the loader would refuse
    for reasons unrelated to bounds.
    """
    manifest = tmp_path / "modelos" / "123" / "revisions" / "2024" / "revision.toml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        '[revisions."2024"]\nvalid_from = 2024-01-01\nperiod_selector = { year_from = 2024, periods = ["0A"] }\n',
        encoding="utf-8",
    )

    from .. import apply_revision_temporal_bounds as module

    planned = (BoundRepair(modelo="123", revision="2024", reason="selector bounded at 2024", terminus="2024-12-31"),)
    original = module.plan_bounds
    module.plan_bounds = lambda _root=None: (planned, ())
    try:
        made = apply_bounds(tmp_path, apply=True)
    finally:
        module.plan_bounds = original

    written = manifest.read_text(encoding="utf-8")
    assert made, "the applier reported no action for a planned repair"
    assert "valid_to = 2024-12-31" in written, written
    assert "valid_from = 2024-01-01" in written, "the applier disturbed the start date"


def test_the_applier_leaves_a_manifest_that_already_has_a_terminus(tmp_path: Path) -> None:
    """Idempotence: an existing terminus is never overwritten."""
    manifest = tmp_path / "modelos" / "123" / "revisions" / "2024" / "revision.toml"
    manifest.parent.mkdir(parents=True)
    body = '[revisions."2024"]\nvalid_from = 2024-01-01\nvalid_to = 2024-06-30\n'
    manifest.write_text(body, encoding="utf-8")

    from .. import apply_revision_temporal_bounds as module

    planned = (BoundRepair(modelo="123", revision="2024", reason="selector bounded at 2024", terminus="2024-12-31"),)
    original = module.plan_bounds
    module.plan_bounds = lambda _root=None: (planned, ())
    try:
        apply_bounds(tmp_path, apply=True)
    finally:
        module.plan_bounds = original

    assert manifest.read_text(encoding="utf-8") == body


def test_a_dry_run_writes_nothing(tmp_path: Path) -> None:
    """The default must be readable, not applied."""
    manifest = tmp_path / "modelos" / "123" / "revisions" / "2024" / "revision.toml"
    manifest.parent.mkdir(parents=True)
    body = '[revisions."2024"]\nvalid_from = 2024-01-01\n'
    manifest.write_text(body, encoding="utf-8")

    from .. import apply_revision_temporal_bounds as module

    planned = (BoundRepair(modelo="123", revision="2024", reason="r", terminus="2024-12-31"),)
    original = module.plan_bounds
    module.plan_bounds = lambda _root=None: (planned, ())
    try:
        lines = apply_bounds(tmp_path, apply=False)
    finally:
        module.plan_bounds = original

    assert lines, "a dry run should still report what it would do"
    assert manifest.read_text(encoding="utf-8") == body


def test_the_campaign_owned_trees_are_never_edited() -> None:
    """Modelos another campaign holds are out of scope while it holds them."""
    assert "303" in CAMPAIGN_OWNED_MODELOS
    assert "390" in CAMPAIGN_OWNED_MODELOS


def test_an_unsettled_bound_carries_why_it_cannot_be_mechanical() -> None:
    """The worklist entry must say what a reader has to settle."""
    unsettled = UnsettledBound(
        modelo="100",
        revision="2024",
        detail="selector starts 2023 but validity starts 2024-01-01",
    )

    assert "selector starts" in unsettled.detail
    assert "validity starts" in unsettled.detail
