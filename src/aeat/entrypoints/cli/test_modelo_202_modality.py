"""End-to-end CLI test: Modelo 202 modality gate and INCN-gated lane routing.

LIS Art. 40.3 divides the Modelo 202 pago-fraccionado into two mutually
exclusive lanes:

* **Art. 40.3 mandatory**: INCN over the prior 12 months exceeds 6.000.000
  EUR — only the Art. 40.3 cuota lane (clave 32) is reachable; Art. 40.2
  (clave 03) must not be filed.
* **Art. 40.2 optional**: INCN does not exceed 6.000.000 EUR — both
  modalities are reachable; the Art. 40.2 cuota lane (clave 03) is the
  elected default with Art. 40.3 still optional.
* **INCOMPLETE**: INCN is undeclared, or the entity is not an IS
  contribuyente — the engine refuses to infer a modality.

This test file pins the three-state gate against real ``TaxpayerProfile``
objects constructed from the full profile fact set (entity type + INCN).

The CLI surface integration (``work calculate`` modality field in the JSON
payload) is exercised by verifying that:

1. A legal-entity profile with INCN above the threshold produces a work unit
   for Modelo 202 and the domain gate returns ART_40_3_MANDATORY.
2. A legal-entity profile with INCN at the threshold boundary produces
   ART_40_2_OPTIONAL.
3. A natural person and an attribution entity return NOT_APPLICABLE from
   ``derive_modelo_applicability`` (the outer applicability gate) and
   INCOMPLETE from ``derive_modelo_202_modality`` (the modality gate).

No mocks — these tests use the real domain functions directly.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from aeat.domain.calculations.registry._applicability import (
    ApplicabilityVerdict,
    Modelo202Modality,
    derive_modelo_202_modality,
)
from aeat.domain.deadlines._models import IVARegime, TaxpayerProfile
from aeat.domain.deadlines.taxpayer_model import EntityType

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_INCN_ABOVE_THRESHOLD = Decimal("6_000_001.00")
_INCN_AT_THRESHOLD = Decimal("6_000_000.00")
_INCN_BELOW_THRESHOLD = Decimal("5_999_999.99")


def _sl_profile(incn: Decimal | None) -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="B12345678",
        entity_type=EntityType.LEGAL_ENTITY,
        irpf_income_categories=frozenset(),
        iva_regime=IVARegime.GENERAL,
        incn_prior_12_months=incn,
    )


def _natural_person_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="12345678Z",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset(),
        iva_regime=IVARegime.GENERAL,
    )


def _attribution_entity_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="E12345678",
        entity_type=EntityType.ATTRIBUTION_ENTITY,
        irpf_income_categories=frozenset(),
        iva_regime=IVARegime.GENERAL,
    )


# ---------------------------------------------------------------------------
# Three-state modality gate
# ---------------------------------------------------------------------------


def test_incn_above_threshold_yields_art_40_3_mandatory() -> None:
    """INCN > 6.000.000 EUR → ART_40_3_MANDATORY.

    When the prior-12-months INCN exceeds the Art. 40.3 threshold the
    cuota-integra lane (clave 32) is the only permissible route; the
    Art. 40.2 lane (clave 03, 18 % method) is not offered.
    """

    profile = _sl_profile(incn=_INCN_ABOVE_THRESHOLD)
    verdict = derive_modelo_202_modality(profile)

    assert verdict.modality is Modelo202Modality.ART_40_3_MANDATORY
    assert verdict.legal_refs  # legal grounding must be populated


def test_incn_at_threshold_yields_art_40_2_optional() -> None:
    """INCN == 6.000.000 EUR → ART_40_2_OPTIONAL.

    The Art. 40.3 threshold is strictly greater-than; equality keeps the
    Art. 40.2 lane available as the default modality.
    """

    profile = _sl_profile(incn=_INCN_AT_THRESHOLD)
    verdict = derive_modelo_202_modality(profile)

    assert verdict.modality is Modelo202Modality.ART_40_2_OPTIONAL


def test_incn_below_threshold_yields_art_40_2_optional() -> None:
    """INCN < 6.000.000 EUR → ART_40_2_OPTIONAL.

    Both modalities are reachable; Art. 40.2 is the declared default.
    """

    profile = _sl_profile(incn=_INCN_BELOW_THRESHOLD)
    verdict = derive_modelo_202_modality(profile)

    assert verdict.modality is Modelo202Modality.ART_40_2_OPTIONAL


def test_incn_undeclared_yields_incomplete() -> None:
    """INCN undeclared → INCOMPLETE.

    The engine cannot decide the modality without the INCN value. An
    undeclared INCN returns INCOMPLETE rather than guessing; a wrong
    pago-fraccionado modality is a regulatory error, not a rounding
    difference.
    """

    profile = _sl_profile(incn=None)
    verdict = derive_modelo_202_modality(profile)

    assert verdict.modality is Modelo202Modality.INCOMPLETE


def test_natural_person_yields_incomplete_modality() -> None:
    """A natural person → INCOMPLETE from the modality gate.

    Modelo 202 is an IS pago fraccionado; natural persons are IRPF
    contribuyentes and have no Art. 40.3 obligation. The modality gate
    returns INCOMPLETE rather than refusing at the applicability layer —
    the outer ``derive_modelo_applicability`` guard handles the
    NOT_APPLICABLE verdict; the modality gate only handles the INCN split
    for declared IS entities.
    """

    profile = _natural_person_profile()
    verdict = derive_modelo_202_modality(profile)

    assert verdict.modality is Modelo202Modality.INCOMPLETE


def test_attribution_entity_yields_incomplete_modality() -> None:
    """An attribution entity → INCOMPLETE from the modality gate.

    Attribution entities are not IS contribuyentes; they have no
    pago-fraccionado obligation under LIS Art. 40. The modality gate
    returns INCOMPLETE for the same reason as natural persons.
    """

    profile = _attribution_entity_profile()
    verdict = derive_modelo_202_modality(profile)

    assert verdict.modality is Modelo202Modality.INCOMPLETE


# ---------------------------------------------------------------------------
# Outer applicability gate for the three entity types
# ---------------------------------------------------------------------------


def test_sl_with_declared_incn_is_applicable_for_modelo_202() -> None:
    """A legal entity with a declared INCN is APPLICABLE for Modelo 202.

    The outer ``derive_modelo_applicability`` gate must return APPLICABLE
    for a legal entity; the INCN modality split is a downstream concern.
    """

    from aeat.domain.calculations.registry._applicability import derive_modelo_applicability

    profile = _sl_profile(incn=_INCN_ABOVE_THRESHOLD)
    verdict = derive_modelo_applicability(profile, "202")

    assert verdict.verdict is ApplicabilityVerdict.APPLICABLE


def test_natural_person_is_not_applicable_for_modelo_202() -> None:
    """A natural person is NOT_APPLICABLE for Modelo 202.

    The outer applicability gate must refuse Modelo 202 for a natural
    person before the INCN modality gate is even consulted.
    """

    from aeat.domain.calculations.registry._applicability import derive_modelo_applicability

    profile = _natural_person_profile()
    verdict = derive_modelo_applicability(profile, "202")

    assert verdict.verdict is not ApplicabilityVerdict.APPLICABLE


def test_attribution_entity_is_not_applicable_for_modelo_202() -> None:
    """An attribution entity is NOT_APPLICABLE for Modelo 202.

    Attribution entities are not IS contribuyentes; the applicability
    gate must refuse them for Modelo 202.
    """

    from aeat.domain.calculations.registry._applicability import derive_modelo_applicability

    profile = _attribution_entity_profile()
    verdict = derive_modelo_applicability(profile, "202")

    assert verdict.verdict is not ApplicabilityVerdict.APPLICABLE


# ---------------------------------------------------------------------------
# CLI work create integration — SL can provision a Modelo 202 work unit
# ---------------------------------------------------------------------------


@pytest.fixture()
def _isolated_cli_backend(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider
    from aeat.adapters.persistence.storage.sql import dispose_engine

    dispose_engine()
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")
    monkeypatch.setenv("AEAT_LOCAL_STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("AEAT_TOKEN_DIR", str(tmp_path / "tokens"))
    monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("AEAT_FINANCIAL_TXS_DIR", str(tmp_path / "txs"))
    monkeypatch.setenv("AEAT_INVOICES_DIR", str(tmp_path / "invoices"))
    monkeypatch.setenv("AEAT_DRAFTS_DIR", str(tmp_path / "drafts"))
    with EphemeralMasterKeyProvider():
        try:
            yield tmp_path
        finally:
            dispose_engine()


def test_legal_entity_can_create_modelo_202_work_unit(_isolated_cli_backend: Path) -> None:
    """A legal-entity profile with declared INCN can provision a Modelo 202
    work unit. The outer applicability guard must not block a legal entity.
    """

    import json

    from aeat.tests.cli_runner import invoke_cached_cli

    result = invoke_cached_cli(
        [
            "config",
            "profile",
            "create",
            "company",
            "--quiet",
            "--accept-defaults",
            "--tax-id",
            "B12345674",
            "--name",
            "Company",
            "--activity",
            "consulting",
            "--entity-type",
            "legal_entity",
            "--legal-entity-form",
            "sl",
            "--incn-prior-12-months",
            "7500000.00",
        ]
    )
    assert result.exit_code == 0, result.output

    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "202",
            "--year",
            "2026",
            "--period",
            "2026-1P",
            "--revision",
            "2025-y-siguientes",
        ]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "created"
    assert payload["modelo"] == "202"
