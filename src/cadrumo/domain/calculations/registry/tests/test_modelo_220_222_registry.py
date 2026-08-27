"""Tests for committed Modelo 220/222 IS-consolidation registry foundations.

See Also:
    :func:`~domain.calculations.registry.tests._registry_schema_support._committed_modelo`
        Bundled-registry loader used to inspect the promoted definitions.
    :class:`~domain.calculations.registry.RegistryValidator`
        Registry integrity gate proving the committed Modelo 220/222 TOML is
        loadable.
    :func:`~domain.calculations.registry.bundled_authority`
        Deadline-window authority used for the legal plazo assertions.
    :data:`~core.UNMODELED_OBLIGATIONS`
        Central set these promoted IS-consolidation modelos must leave.
    :data:`~core.access_gate.CANONICAL_MODELO_FLEET`
        Canonical modeled-obligation fleet that must include both forms.
    :class:`~domain.calculations.registry.ModeloEntry`
        Support-matrix row type that reports registry-backed modelo coverage.
"""

from __future__ import annotations

from datetime import date
from typing import NamedTuple

import pytest

from .....core import RegistryAuthorityGrade
from .....core.resources import bundled_path
from .._validate import RegistryValidator
from ..authority import bundled_authority
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class _ModeloCase(NamedTuple):
    """One modelo's approval and plazo expectations.

    ``revision_id`` names the era these expectations were authored against. It is
    NOT used to look a revision up: this test pinned an id, and modelo 220's id
    stopped existing the moment its span was split at the 2024/2025 re-layout --
    the windows neither moved nor changed, but the lookup raised ``KeyError`` and
    the modelo went unchecked. That is the same failure the sibling
    ``test_modelo_490_604_763_registry`` module already recorded for modelos 490
    and 604. Every window of every revision is checked instead, so a split cannot
    silently drop coverage, and the assertions name the revision they fired on.
    """

    modelo_id: str
    revision_id: str
    approval_ref: str
    plazo_ref: str
    approval_document_id: str
    plazo_document_id: str
    period_kind: str


_CASES = (
    _ModeloCase(
        modelo_id="220",
        revision_id="2024-y-siguientes",
        approval_ref="orden-hac-657-2025:art-3",
        plazo_ref="ley-27-2014:art-124",
        approval_document_id="BOE-A-2025-12818",
        plazo_document_id="BOE-A-2014-12328",
        period_kind="annual",
    ),
    _ModeloCase(
        modelo_id="222",
        revision_id="2025-y-siguientes",
        approval_ref="orden-hfp-227-2017:art-2",
        plazo_ref="orden-hfp-227-2017:art-5",
        approval_document_id="BOE-A-2017-2778",
        plazo_document_id="BOE-A-2017-2778",
        period_kind="quarterly",
    ),
)


@pytest.mark.parametrize("case", _CASES, ids=[case.modelo_id for case in _CASES])
def test_modelo_220_222_validators_accept_committed_definitions(case: _ModeloCase) -> None:
    modelo, catalogues = _committed_modelo(case.modelo_id)
    assert modelo.id == case.modelo_id
    assert modelo.revisions, f"{case.modelo_id} must declare at least one revision"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


@pytest.mark.parametrize("case", _CASES, ids=[case.modelo_id for case in _CASES])
def test_modelo_220_222_approval_and_plazo_resolve_as_legal_authority(case: _ModeloCase) -> None:
    _, catalogues = _committed_modelo(case.modelo_id)
    approval = catalogues.legal[case.approval_ref]
    plazo = catalogues.legal[case.plazo_ref]
    assert approval.evidence_tier == "legal_authority"
    assert approval.document_id == case.approval_document_id
    assert plazo.evidence_tier == "legal_authority"
    assert plazo.document_id == case.plazo_document_id


@pytest.mark.parametrize("case", _CASES, ids=[case.modelo_id for case in _CASES])
def test_modelo_220_222_deadline_provision_is_cited_by_every_window(case: _ModeloCase) -> None:
    modelo, _ = _committed_modelo(case.modelo_id)
    declared = [
        (revision_id, window)
        for revision_id, revision in modelo.revisions.items()
        for window in revision.deadline_windows
    ]
    assert declared, f"{case.modelo_id} must declare deadline windows"
    for revision_id, window in declared:
        assert window.period_kind == case.period_kind, f"{case.modelo_id}/{revision_id} {window.id}"
        assert case.plazo_ref in window.legal_refs, f"{case.modelo_id}/{revision_id} {window.id}"


def test_modelo_220_annual_window_opens_july_and_closes_after_25_natural_days() -> None:
    """LIS art. 124.1: 25 natural days after six months from period close."""
    authority = bundled_authority()
    windows = {w.id: w for _, _, w in authority.deadline_windows(2024, modelos=("220",))}
    assert "modelo-220-2024-0a" in windows
    window = windows["modelo-220-2024-0a"]
    assert window.opens_on == date(2025, 7, 1)
    assert window.closes_on == date(2025, 7, 25)


def test_modelo_220_2025_sources_match_the_revision_window() -> None:
    """The 2025 revision cites its own design and period-scoped approving order."""
    modelo, catalogues = _committed_modelo("220")
    revision = modelo.revisions["2025"]

    assert (revision.valid_from, revision.valid_to) == (date(2025, 1, 1), date(2025, 12, 31))
    assert revision.authority_grade is RegistryAuthorityGrade.APPLICABILITY
    assert "boe-modelo-220-2026-form" not in catalogues.sources
    assert set(revision.source_refs) >= {
        "aeat-dr-220-2025",
        "boe-modelo-220-2025-form",
    }
    for source_id in ("aeat-dr-220-2025", "boe-modelo-220-2025-form"):
        source = catalogues.sources[source_id]
        assert (source.applies_from, source.applies_to) == (
            revision.valid_from,
            revision.valid_to,
        )

    snapshot = bundled_authority().snapshot(
        "220",
        filing_year=2025,
        period="0A",
        revision_id=revision.id,
        grade=RegistryAuthorityGrade.APPLICABILITY,
    )
    assert snapshot.revision.id == revision.id


def test_modelo_222_trimestral_windows_open_and_close_on_day_20() -> None:
    """Orden HFP/227/2017 art. 5.2: first 20 natural days of Apr/Oct/Dec."""
    authority = bundled_authority()
    windows = {w.id: w for _, _, w in authority.deadline_windows(2025, modelos=("222",))}
    expected = {
        "modelo-222-2025-1p": (date(2025, 4, 1), date(2025, 4, 20)),
        "modelo-222-2025-2p": (date(2025, 10, 1), date(2025, 10, 20)),
        "modelo-222-2025-3p": (date(2025, 12, 1), date(2025, 12, 20)),
    }
    assert set(expected) <= set(windows)
    for window_id, (opens, closes) in expected.items():
        assert windows[window_id].opens_on == opens
        assert windows[window_id].closes_on == closes


def test_modelo_220_222_are_registry_backed() -> None:
    from .....core.access_gate import CANONICAL_MODELO_FLEET

    for modelo_id in ("220", "222"):
        assert modelo_id in CANONICAL_MODELO_FLEET
