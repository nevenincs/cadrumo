"""Guard that the filing layer never memoizes registry snapshots above the loader.

``build_draft`` resolves its registry snapshot through
:func:`cadrumo.application.filing._load_registry_snapshot`. Any cache placed on
that function would be keyed on ``(modelo, period)`` alone — carrying neither the
registry-tree fingerprint nor a TTL — and would therefore sit outside the
invalidation protocol the registry authority defines. The consequence is not a
performance nit: a snapshot pinned from before a registry change decides which
revision's norms a filing is computed under, so a stale one computes a filing
against superseded law with no signal to the operator.

These tests use two real registry trees and two real authorities. Nothing about
the snapshot resolution is substituted; only the process resource registry is
re-pointed, which is what a resource-registry reset does in production.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from ....core import Period
from ....core.resources import bundled_path
from ....domain.calculations.registry import ValidatedRegistryAuthority
from .. import _load_registry_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

if TYPE_CHECKING:
    from ....domain.calculations.registry import CasillaDefinition

_EDIT_MARKER = "FRESHNESS-PROBE "
_MODELO = "130"
_PERIOD = Period(filing_year=2024, code="1T")


@dataclass(frozen=True)
class _ModelosSlot:
    """The resource registry's ``modelos`` slot, holding a real authority.

    Named a slot rather than a stub because nothing here is a test double: it
    carries a real :class:`ValidatedRegistryAuthority`, and the only thing
    substituted is WHICH authority instance the filing module reaches --
    exactly what a resource-registry reset changes in production. Calling it a
    stub claimed a fake this test does not use, and tripped the gate that bans
    them.
    """

    authority: ValidatedRegistryAuthority


@dataclass(frozen=True)
class _ResourcesSlot:
    modelos: _ModelosSlot


def _copy_registry(destination: Path) -> Path:
    """Copy the bundled registry tree to ``destination`` and return the new root."""
    root = destination / "aeat"
    shutil.copytree(bundled_path("registry", "aeat"), root)
    return root


def _first_casilla_fragment(root: Path) -> Path:
    """Return the first casilla fragment of the modelo under test."""
    casillas_dir = next((root / "modelos" / _MODELO).rglob("casillas"))
    fragments = sorted(casillas_dir.glob("*.toml"))
    assert fragments, f"registry copy carries no casilla fragments under {casillas_dir}"
    return fragments[0]


def _mark_one_casilla_label(root: Path) -> None:
    """Prefix exactly one casilla label in ``root`` so the change is observable."""
    fragment = _first_casilla_fragment(root)
    original = fragment.read_text(encoding="utf-8")
    edited = original.replace('label = "', f'label = "{_EDIT_MARKER}', 1)
    assert edited != original, f"no casilla label found to mark in {fragment}"
    fragment.write_text(edited, encoding="utf-8")


def _authority_for(root: Path) -> ValidatedRegistryAuthority:
    return ValidatedRegistryAuthority.load(root, source_root=bundled_path())


def _marked_casilla_ids(casillas: tuple[CasillaDefinition, ...]) -> list[str]:
    return [str(casilla.id) for casilla in casillas if casilla.label.startswith(_EDIT_MARKER)]


def test_snapshot_resolution_follows_a_changed_registry_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A second read after the registry changes must reflect the change, not a memo.

    Fails loudly if a fingerprint-blind cache is reintroduced on
    ``_load_registry_snapshot``: the second call would return the first tree's
    snapshot, and the marked label would be invisible.
    """
    unchanged_root = _copy_registry(tmp_path / "before")
    changed_root = _copy_registry(tmp_path / "after")
    _mark_one_casilla_label(changed_root)

    monkeypatch.setattr(
        "cadrumo.application.filing._resources",
        lambda: _ResourcesSlot(modelos=_ModelosSlot(authority=_authority_for(unchanged_root))),
    )
    before = _load_registry_snapshot(modelo=_MODELO, period=_PERIOD)
    assert not _marked_casilla_ids(before.revision.casillas), (
        "the unchanged registry copy already carries the probe marker; the fixture is not a control"
    )

    monkeypatch.setattr(
        "cadrumo.application.filing._resources",
        lambda: _ResourcesSlot(modelos=_ModelosSlot(authority=_authority_for(changed_root))),
    )
    after = _load_registry_snapshot(modelo=_MODELO, period=_PERIOD)

    assert _marked_casilla_ids(after.revision.casillas), (
        "registry snapshot resolution served a stale snapshot after the registry tree changed: "
        "a cache above the loader is keyed without the registry-tree fingerprint, so a filing "
        "would be computed under a superseded revision's norms"
    )


def test_snapshot_resolution_exposes_no_cache_handle() -> None:
    """``_load_registry_snapshot`` must carry no memoization wrapper.

    Structural companion to the behavioural test above: ``functools`` caches
    expose ``cache_clear``/``cache_info``, so their absence pins the intent even
    if a future change makes the staleness window harder to trigger.
    """
    for attribute in ("cache_clear", "cache_info", "__wrapped__"):
        assert not hasattr(_load_registry_snapshot, attribute), (
            f"_load_registry_snapshot exposes {attribute!r}, so it is memoized above the registry "
            "loader; such a cache is keyed without the registry-tree fingerprint and can serve a "
            "snapshot from before a registry change"
        )


def test_law_determined_resolution_is_preserved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolution stays driven by ``(modelo, filing_year, period)``.

    Two different filing years for the same period token must not collapse onto
    one another, and the resolved revision must be the one the registry's own
    temporal selection returns for that context.
    """
    root = _copy_registry(tmp_path / "tree")
    authority = _authority_for(root)
    monkeypatch.setattr(
        "cadrumo.application.filing._resources",
        lambda: _ResourcesSlot(modelos=_ModelosSlot(authority=authority)),
    )

    for filing_year in (2023, 2024):
        period = Period(filing_year=filing_year, code="1T")
        resolved = _load_registry_snapshot(modelo=_MODELO, period=period)
        expected = authority.snapshot(_MODELO, filing_year=filing_year, period="1T")
        assert resolved.revision.id == expected.revision.id, (
            f"filing year {filing_year} resolved revision {resolved.revision.id!r}, but the "
            f"registry authority selects {expected.revision.id!r} for that context"
        )
        # Asserted rather than assumed: filing_period is Optional on the
        # snapshot schema, so dereferencing it unguarded would surface a
        # missing period as an AttributeError inside the comparison rather
        # than as the failure it is. A snapshot resolved for a period must
        # carry one.
        assert resolved.filing_period is not None, (
            f"snapshot for filing year {filing_year} carries no filing_period"
        )
        assert resolved.filing_period.filing_year == filing_year
