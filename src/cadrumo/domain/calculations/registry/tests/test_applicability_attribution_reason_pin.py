"""The attribution pass-through reason resolves on the caller's pinned authority.

The verdict reason for an attribution entity asked for a cuota
self-assessment is the one applicability answer the rule reads from the
registry rather than from its own already-resolved fields, so it is the
one place where the rule can reach past the caller's pinned generation.

See Also:
    :meth:`~domain.calculations.registry.applicability_models.ModeloApplicabilityRule.evaluate`
        Takes the pinned operation this module checks is used.
"""

from __future__ import annotations

import pytest

from cadrumo.core.modelo import Modelo
from cadrumo.domain.contribuyente.entity_type import entity_type_attribution_entity_token
from cadrumo.domain.deadlines.models import IVARegime, TaxpayerProfile

from .. import authority as authority_module
from ..applicability import derive_modelo_applicability, iter_modelo_applicability_rules
from ..applicability_models import (
    ApplicabilityVerdict,
    ModeloApplicabilityRule,
    registry_applicability_reason,
)
from ..authority import PinnedAuthorityOperation

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

# Modelo 130 is a cuota-bearing self-assessment, which is what makes an
# attribution entity reach the pass-through verdict rather than a plain
# NOT_APPLICABLE: the régimen de atribución de rentas (LIRPF art. 86/87)
# taxes the income in the members' own returns.
_CUOTA_BEARING_MODELO = "130"


def _attribution_entity_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="E00000000",
        entity_type=entity_type_attribution_entity_token(),
        iva_regime=IVARegime("GENERAL"),
    )


def _cuota_bearing_rule(operation: PinnedAuthorityOperation) -> ModeloApplicabilityRule:
    rule = next(
        candidate
        for candidate in iter_modelo_applicability_rules(operation=operation)
        if candidate.modelo == Modelo(_CUOTA_BEARING_MODELO)
    )
    assert rule.cuota_bearing
    return rule


def _refuse_bundled_lease(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any fresh bundled authority lease fail instead of succeeding quietly.

    The lease is the defect: it answers correctly while reading a
    generation the caller did not pin, so only refusing it can tell a
    threaded pin from a second generation that happens to agree.
    """

    def _unreachable() -> object:
        message = "the pinned operation must answer; no fresh bundled authority may be leased"
        raise AssertionError(message)

    monkeypatch.setattr(authority_module, "bundled_indexed_authority", _unreachable)


def test_attribution_pass_through_reason_reads_the_pinned_operation(
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The rule resolves the pass-through reason without leasing a second generation."""
    expected = registry_applicability_reason("attribution_pass_through.reason", operation=operation)
    rule = _cuota_bearing_rule(operation)
    _refuse_bundled_lease(monkeypatch)

    result = rule.evaluate(_attribution_entity_profile(), operation=operation)

    assert result.verdict is ApplicabilityVerdict.ATTRIBUTION_PASS_THROUGH
    assert result.reason == expected


def test_derive_modelo_applicability_passes_its_pin_down_to_the_rule(
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The public entry point hands its own pin to the rule it evaluates."""
    expected = registry_applicability_reason("attribution_pass_through.reason", operation=operation)
    _refuse_bundled_lease(monkeypatch)

    result = derive_modelo_applicability(
        _attribution_entity_profile(),
        _CUOTA_BEARING_MODELO,
        operation=operation,
    )

    assert result.verdict is ApplicabilityVerdict.ATTRIBUTION_PASS_THROUGH
    assert result.reason == expected


def test_an_omitted_pin_still_answers_from_the_bundled_generation(
    operation: PinnedAuthorityOperation,
) -> None:
    """Threading the pin is an addition: a caller that holds none keeps its answer.

    ``operation`` is requested so the rule table itself is read from the
    pinned generation; the evaluation deliberately omits it.
    """
    rule = _cuota_bearing_rule(operation)

    result = rule.evaluate(_attribution_entity_profile())

    assert result.verdict is ApplicabilityVerdict.ATTRIBUTION_PASS_THROUGH
    assert result.reason == registry_applicability_reason("attribution_pass_through.reason", operation=operation)
