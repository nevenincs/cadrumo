"""Tests for the committed Modelo 222 IS-consolidación pago-fraccionado foundation.

Modelo 222 is the quarterly pago fraccionado a cuenta del Impuesto sobre
Sociedades for grupos fiscales que tributan en régimen de consolidación fiscal.
It is approved by Orden HFP/227/2017 art 2 (BOE-A-2017-2778) — the same orden
that approves Modelo 202 in art 1 — and its binding trimestral filing plazo is
grounded in art 5.2 of that orden: the first twenty natural days of April,
October and December of each natural year. This revision is scheduling/
applicability-grade (declaration-header casillas only); the numbered
money-closure casillas are deferred until an authoritative Modelo 222 diseño de
registro is bundled, so no casilla number is fabricated.
"""

from __future__ import annotations

from datetime import date

import pytest

from .....core.resources import bundled_path
from .._authority import bundled_authority
from .._validate import RegistryValidator
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _load_modelo_222():
    return _committed_modelo("222")


def test_modelo_222_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_222()
    assert modelo.id == "222"
    assert modelo.revisions, "222 must declare at least one revision"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_222_approval_and_plazo_are_orden_hfp_227_2017() -> None:
    """Approval (art 2) and plazo (art 5) resolve as legal authority in the catalogue.

    Both are cross-checked against the bundled BOE corpus at build via their
    required_text; here we pin their evidence tier and document id.
    """
    _, catalogues = _load_modelo_222()
    approval = catalogues.legal["orden-hfp-227-2017:art-2"]
    plazo = catalogues.legal["orden-hfp-227-2017:art-5"]
    assert approval.evidence_tier == "legal_authority"
    assert approval.document_id == "BOE-A-2017-2778"
    assert plazo.evidence_tier == "legal_authority"
    assert plazo.document_id == "BOE-A-2017-2778"


def test_modelo_222_deadline_provision_is_orden_hfp_227_2017_art_5() -> None:
    """Every trimestral window cites the binding Orden HFP/227/2017 art 5 plazo."""
    modelo, _ = _load_modelo_222()
    revision = modelo.revisions["2025-y-siguientes"]
    assert revision.deadline_windows, "222 must declare quarterly deadline windows"
    for window in revision.deadline_windows:
        assert window.period_kind == "quarterly"
        assert "orden-hfp-227-2017:art-5" in window.legal_refs


def test_modelo_222_trimestral_windows_open_and_close_on_day_20() -> None:
    """Orden HFP/227/2017 art 5.2: first twenty natural days of Apr/Oct/Dec.

    Derived strictly from the statutory plazo (the pago fraccionado filed in the
    first 20 natural days of April, October and December), not copied from any
    engine output.
    """
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


def test_modelo_222_is_registry_backed_and_out_of_unmodeled() -> None:
    """M222 is a loadable registry modelo and no longer a recognized-unmodeled obligation."""
    from .....core import UNMODELED_OBLIGATIONS
    from .....core.access_gate import CANONICAL_MODELO_FLEET

    assert "222" in CANONICAL_MODELO_FLEET
    assert all(str(m) != "222" for m in UNMODELED_OBLIGATIONS)
