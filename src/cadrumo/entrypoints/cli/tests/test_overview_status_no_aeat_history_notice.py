"""The no-AEAT-history advisory reaches the ``overview status`` envelope.

The builder (:func:`~cadrumo.application.overview.no_aeat_history_notice`)
long had no production caller reaching the machine-facing ``overview
status`` command: it fired only on the ``config profile status``
full-screen surface. These tests drive the real shipped CLI — a real
isolated encrypted profile, the real registry, the real observation
store — end to end and prove the notice now reaches the envelope, is not
silenced by an unrelated observation from another modelo, and recommends
no verb for a Sociedades filer the bulk history sweep structurally cannot
serve.
"""

from __future__ import annotations

import pytest

from ....core import STR_KEYED_MAPPING_ADAPTER
from ....tests.cli_runner import invoke_cached_cli
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_profile_storage

__all__ = ["isolated_profile_storage"]
from ....tests.cli_envelope import unwrap_envelope_notices
from ._profile_cli_support import seed_profile as _seed_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_NOTICE_CODE = "overview.no_aeat_history"
# The profile facts a filer needs to be readiness-complete for M303 work.
# The wizard ``create`` arm refuses unconditionally -- credential
# registration is the only creation door -- so these are seeded as facts
# rather than passed as create flags. The notice, not the seeding, is the
# subject of every test below.
_M303_READY_FACTS = {
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
    "activities.description": "consultoria informatica",
}
_LEGAL_ENTITY_FACTS = {
    "taxpayer_type.entity_type": "legal_entity",
    "taxpayer_type.legal_entity_form": "sl",
    "identity.tax_id": "B66012345",
    "identity.legal_name": "Webco SL",
    "identity.name": "",
    "identity.surnames": "",
    "taxpayer_type.irpf_income_categories": "",
    "irpf.estimation_regime": "",
}


def _status_notices() -> list[dict[str, object]]:
    result = invoke_cached_cli(["--format", "json", "app", "overview", "status"])
    assert result.exit_code == 0, result.output
    return [STR_KEYED_MAPPING_ADAPTER.validate_python(notice) for notice in unwrap_envelope_notices(result.output)]


def _history_notice(notices: list[dict[str, object]]) -> dict[str, object]:
    matches = [notice for notice in notices if notice.get("code") == _NOTICE_CODE]
    assert len(matches) == 1, f"expected exactly one {_NOTICE_CODE!r} notice, found {len(matches)}: {notices}"
    return matches[0]


def test_a_fresh_natural_person_profile_gets_the_history_notice_with_the_sweep_action() -> None:
    """The measured defect: the envelope now carries the notice at all."""
    _seed_profile(
        "freelancer",
        **_M303_READY_FACTS,
        **{"taxpayer_type.entity_type": "natural_person", "identity.tax_id": "12345678Z"},
    )

    notice = _history_notice(_status_notices())
    assert notice["severity"] == "info"
    action = notice.get("action")
    assert isinstance(action, dict)
    assert action["action"]["action"]["action_id"] == "operator.live.filed.pull_all"


def test_a_fresh_sociedades_profile_gets_the_history_notice_with_no_action() -> None:
    """A Sociedades filer's own direct-tax modelos (200/202) the sweep cannot fetch.

    Measured over a real isolated encrypted profile holding a Sociedades
    taxpayer and zero calculation observations: the notice fires (the gap is
    real) but carries no action (the whole-history sweep is not a fix for it).
    """
    _seed_profile("webco", **_M303_READY_FACTS, **_LEGAL_ENTITY_FACTS)

    notice = _history_notice(_status_notices())
    assert notice["severity"] == "info"
    assert notice.get("action") is None


def test_one_pulled_observation_from_any_modelo_silences_the_sociedades_notice_too() -> None:
    """The predicate stays official-source membership, not a Sociedades-only exemption."""
    from ....application.calculations import CalculationObservationRepository
    from cadrumo.application.workflow.profile_bucket_scan import read_profile_bucket
    from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation

    _seed_profile("webco-with-history", **_M303_READY_FACTS, **_LEGAL_ENTITY_FACTS)

    pointer = read_profile_bucket("webco-with-history")
    assert pointer is not None
    with open_test_profile_session(pointer.bucket_id):
        repository = CalculationObservationRepository()
        repository.save(
            repository.prepare_observation_envelope(
                RegistryModeloObservation(modelo="303", filing_year=2025, period="1T"),
                source_kind="aeat_sede_justificante",
            ),
        )

    notices = _status_notices()
    assert not [notice for notice in notices if notice.get("code") == _NOTICE_CODE], notices
