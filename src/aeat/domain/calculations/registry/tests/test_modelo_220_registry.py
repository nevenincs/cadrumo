"""Tests for the committed Modelo 220 IS-consolidación annual-declaration foundation.

Modelo 220 is the annual declaración del Impuesto sobre Sociedades of the grupo
fiscal en régimen de consolidación fiscal, filed by the sociedad representante.
The IS declaration models for períodos impositivos iniciados en 2024 are approved
by Orden HAC/657/2025 (BOE-A-2025-12818); its bundled art 3 names "Modelos 200 y
220" verbatim, evidencing that Modelo 220 is one of the approved models. The
filing plazo is the general IS declaration plazo of art. 124.1 LIS: the 25 natural
days following the six months after the close of the período impositivo. This
revision is scheduling/applicability-grade (declaration-header casillas only); the
money-closure casillas of the group declaration are deferred until an
authoritative Modelo 220 diseño de registro is bundled, so no casilla number is
fabricated.
"""

from __future__ import annotations

from datetime import date

import pytest

from .....core.resources import bundled_path
from .._authority import bundled_authority
from .._validate import RegistryValidator
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _load_modelo_220():
    return _committed_modelo("220")


def test_modelo_220_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_220()
    assert modelo.id == "220"
    assert modelo.revisions, "220 must declare at least one revision"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_220_grounding_is_orden_hac_657_2025_and_lis_art_124() -> None:
    """Orden coverage (art 3, naming 220) and plazo (LIS art 124) resolve as authority.

    Both are cross-checked against the bundled BOE corpus at build via their
    required_text; here we pin their evidence tier and document id.
    """
    _, catalogues = _load_modelo_220()
    coverage = catalogues.legal["orden-hac-657-2025:art-3"]
    plazo = catalogues.legal["ley-27-2014:art-124"]
    assert coverage.evidence_tier == "legal_authority"
    assert coverage.document_id == "BOE-A-2025-12818"
    assert plazo.evidence_tier == "legal_authority"
    assert plazo.document_id == "BOE-A-2014-12328"


def test_modelo_220_deadline_provision_is_lis_art_124() -> None:
    """Every annual window cites the binding art. 124 LIS declaration plazo."""
    modelo, _ = _load_modelo_220()
    revision = modelo.revisions["2024-y-siguientes"]
    assert revision.deadline_windows, "220 must declare annual deadline windows"
    for window in revision.deadline_windows:
        assert window.period_kind == "annual"
        assert "ley-27-2014:art-124" in window.legal_refs


def test_modelo_220_annual_window_opens_july_closes_25_natural_days() -> None:
    """LIS art 124.1: 25 natural days after the 6 months following the period close.

    For a calendar-year período impositivo the plazo runs from 1 July and closes
    on the 25th natural day (advanced to the next business day at year end),
    mirroring the sibling Modelo 200 window and derived from the statute, not from
    any engine output.
    """
    authority = bundled_authority()
    windows = {w.id: w for _, _, w in authority.deadline_windows(2024, modelos=("220",))}
    assert "modelo-220-2024-0a" in windows
    window = windows["modelo-220-2024-0a"]
    assert window.opens_on == date(2025, 7, 1)
    assert window.closes_on == date(2025, 7, 25)


def test_modelo_220_is_registry_backed_and_out_of_unmodeled() -> None:
    """M220 is a loadable registry modelo and no longer a recognized-unmodeled obligation."""
    from .....core import UNMODELED_OBLIGATIONS
    from .....core.access_gate import CANONICAL_MODELO_FLEET

    assert "220" in CANONICAL_MODELO_FLEET
    assert all(str(m) != "220" for m in UNMODELED_OBLIGATIONS)
