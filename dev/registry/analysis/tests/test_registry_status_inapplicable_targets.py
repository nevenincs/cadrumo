"""A target the registry places outside every generated tree is not an unreadable one.

A generated export tree is reproduced from an official record design for a filing
year the product supports. A revision whose declared years all lie below the
supported floor, or whose modelo has no record design at all, has nothing to
reproduce; counting it with the targets that failed to render hides the real
authoring gaps behind them. The classifier is pure over the modelo definition,
the source catalogue and the floor, so these cases pass abstract values for all
three.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import SimpleNamespace
from typing import Any, cast

import pytest

from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.schema_base import RegistrySourceKind
from cadrumo.domain.calculations.registry.schema_references import SourceReference

from ..registry_status import (
    INAPPLICABLE_BELOW_FLOOR,
    INAPPLICABLE_NO_RECORD_DESIGN,
    RegistryStatus,
    classify_inapplicable_target,
    project_target_states,
    registry_status_payload,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FLOOR = 100
_SOURCES = cast(
    Mapping[str, SourceReference],
    {
        "design": SimpleNamespace(kind=RegistrySourceKind.RECORD_DESIGN),
        "orden": SimpleNamespace(kind=RegistrySourceKind.INSTRUCTIONS),
    },
)


def _modelo(cited: str, **selectors: dict[str, object]) -> Any:
    """A modelo whose revisions carry the given period selectors and all cite one source."""
    return _modelo_citing(**{name: (cited, selector) for name, selector in selectors.items()})


def _modelo_citing(**revisions: tuple[str, dict[str, object]]) -> Any:
    """A modelo whose revisions each cite their own source."""
    built = {
        name: SimpleNamespace(source_refs=(cited,), period_selector=SimpleNamespace(**selector))
        for name, (cited, selector) in revisions.items()
    }
    return SimpleNamespace(id="999", source_refs=(), revisions=built)


def _classify(modelo: ModeloDefinition, revision: str, *, committed: bool = False) -> str | None:
    return classify_inapplicable_target(modelo, revision, _SOURCES, floor=_FLOOR, has_committed_tree=committed)


def test_a_revision_wholly_below_the_floor_is_not_applicable() -> None:
    modelo = _modelo("design", old={"years": (_FLOOR - 3, _FLOOR - 1), "year_to": None})
    reason = _classify(modelo, "old")
    assert reason is not None
    assert reason.startswith(INAPPLICABLE_BELOW_FLOOR)


def test_a_range_ending_below_the_floor_is_not_applicable() -> None:
    modelo = _modelo("design", old={"years": (), "year_to": _FLOOR - 1})
    assert (_classify(modelo, "old") or "").startswith(INAPPLICABLE_BELOW_FLOOR)


@pytest.mark.parametrize(
    "selector",
    [
        {"years": (_FLOOR - 1, _FLOOR), "year_to": None},
        {"years": (), "year_to": _FLOOR},
        {"years": (), "year_to": None},
    ],
    ids=["reaches the floor", "range ends at the floor", "open ended"],
)
def test_a_revision_reaching_the_floor_with_a_published_design_stays_a_gap(selector: dict[str, object]) -> None:
    modelo = _modelo("design", spans=selector)
    assert _classify(modelo, "spans") is None


def test_a_modelo_with_no_record_design_anywhere_is_not_applicable() -> None:
    modelo = _modelo("orden", current={"years": (_FLOOR, _FLOOR + 1), "year_to": None})
    assert (_classify(modelo, "current") or "").startswith(INAPPLICABLE_NO_RECORD_DESIGN)


def test_a_design_cited_by_a_sibling_revision_keeps_the_gap_open() -> None:
    open_selector: dict[str, object] = {"years": (), "year_to": None}
    modelo = _modelo_citing(current=("orden", open_selector), designed=("design", open_selector))
    assert _classify(modelo, "current") is None


def test_below_floor_wins_when_both_reasons_hold() -> None:
    modelo = _modelo("orden", old={"years": (_FLOOR - 1,), "year_to": None})
    assert (_classify(modelo, "old") or "").startswith(INAPPLICABLE_BELOW_FLOOR)


def test_a_revision_already_shipping_a_tree_is_never_not_applicable() -> None:
    modelo = _modelo("orden", old={"years": (_FLOOR - 1,), "year_to": None})
    assert _classify(modelo, "old", committed=True) is None


def _status(not_applicable: tuple[tuple[str, str, str], ...], unreadable: tuple[tuple[str, str, str], ...]):
    projected = project_target_states(
        (),
        unreadable,
        dispositions=(),
        declared_floor=lambda: _FLOOR,
        revision_filing_years=lambda _modelo, _revision: (),
        excluded_count=len(unreadable),
        not_applicable=not_applicable,
    )
    return projected, RegistryStatus(
        valid=True,
        oracles=True,
        targets=projected.counts,
        target_findings=projected.findings,
        authority="current",
        authority_recorded_digest=None,
        authority_candidate_digest=None,
        loadable=True,
        informational_bindings=(),
        details=projected.details,
    )


def test_only_not_applicable_targets_leave_the_coverage_lane_passed() -> None:
    projected, status = _status((("999", "old", f"{INAPPLICABLE_BELOW_FLOOR}: gone"),), ())
    payload = registry_status_payload(status, blocking=True)
    assert dict(projected.counts)["not-applicable"] == 1
    assert dict(projected.counts)["unreadable"] == 0
    assert cast("dict[str, str]", payload["lanes"])["target_coverage"] == "passed"
    assert cast("dict[str, object]", payload["target_findings"])["not-applicable"] is not None


def test_an_unreadable_target_still_marks_coverage_partial_beside_not_applicable_ones() -> None:
    _, status = _status(
        (("999", "old", f"{INAPPLICABLE_BELOW_FLOOR}: gone"),),
        (("999", "new", "999/new declares no export layout to render"),),
    )
    payload = registry_status_payload(status, blocking=True)
    assert cast("dict[str, str]", payload["lanes"])["target_coverage"] == "partial"
    assert cast("dict[str, dict[str, int]]", payload["target_findings"])["unreadable"]["count"] == 1
