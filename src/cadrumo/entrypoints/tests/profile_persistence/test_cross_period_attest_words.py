"""The words of a blocked prior-period dependency name the statement of its figure only where it is admitted.

A first-quarter Modelo 130 reads the previous ejercicio's net income from a Modelo 100. While the
application holds nothing of that return, inside or outside the support envelope, the operator may
state the figure, so the served finding names that command beside the door it routes to. Once the
source is held the declaration follows it and the words say nothing of a statement.

Real behaviour throughout: an isolated encrypted profile, the bundled authority, the production
verification, with every year taken from the published support envelope.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....adapters.persistence.storage.operator_scope import build_operator_scope_ports
from ....application.calculations.cross_period_clean_state import cross_period_dependency_requirements
from ....application.modelo.edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
)
from ....application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from ....core.authority_grade import RegistryAuthorityGrade
from ....core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from ....core.i18n.render import lookup_translation
from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ....domain.calculations.registry.tests.registry_observations import registry_grounded_modelo_observation
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ....domain.modelos.verification_report import ModeloVerificationFinding, ModeloVerificationFindingKind
from ...adapter_composition import profile_adapter_composition
from ..modelo_operator_work_storage import SeededOperatorWork, seeded_operator_work
from .observation_seeding_support import save_stamped_observation
from .verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BINDING = "irpf.previous_year_economic_activity_net_income"
_PLAIN_KEY = "application.modelo.findings.cross_period_dependency_unclean"
_ATTESTABLE_KEY = "application.modelo.findings.cross_period_dependency_unclean_attestable"
_COMMAND = "attest-prior-value"
_HELD = Decimal(500)


def _unclean(work: SeededOperatorWork, typed_figure: Decimal = Decimal(100)) -> list[ModeloVerificationFinding]:
    """Verify a calculation whose carry is merely typed; the blocked source findings."""
    typed = ModeloBindingEditIntentV1(
        address=ModeloEditBindingAddressV1(binding_id=_BINDING),
        kind=ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE,
        value=typed_figure,
    )
    assert work.apply(binding=(typed,)).refusal is None
    result = verify_modelo_revision_with_preconditions(
        work.require_head().calculation_revision_id,
        certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
        verification_repositories=build_test_verification_repository_bundle(),
        actor="operator-test",
        workflow_profile=TaxpayerProfile(tax_id="X0001500M", iva_regime=IVARegime("GENERAL")),
        operator_scope_ports=build_operator_scope_ports(),
        operation=work.operation,
    )
    return [
        finding
        for finding in result.report.findings
        if finding.kind is ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN
        and finding.message_facts.get("source_modelo") == "100"
    ]


def _hold_the_source(work: SeededOperatorWork) -> None:
    snapshot = work.operation.snapshot(
        "130",
        filing_year=work.work_unit.filing_year,
        period="1T",
        grade=RegistryAuthorityGrade.CALCULATION,
    )
    (requirement,) = [item for item in cross_period_dependency_requirements(snapshot) if _BINDING in item.origin_ids]
    save_stamped_observation(
        CalculationObservationRepository(),
        registry_grounded_modelo_observation(
            modelo=requirement.source_modelo,
            filing_year=requirement.filing_year,
            period=requirement.period.registry_token,
            casilla_values={requirement.source_casilla_ids[0]: _HELD},
        ),
        source_kind="app_filing",
    )


def _floor() -> int:
    support = published_supported_filing_years()
    assert support is not None
    return support.floor


def _served_words(key: str) -> list[str]:
    """The authored text of ``key`` in every supported locale."""
    texts = [lookup_translation(key, locale=locale) for locale in SUPPORTED_OUTPUT_LANGUAGES]
    served = [text for text in texts if text is not None]
    assert len(served) == len(texts)
    return served


@pytest.mark.parametrize("offset", [0, 1], ids=["source-outside-envelope", "source-inside-envelope"])
def test_an_absent_source_names_the_statement_whether_inside_or_outside_the_envelope(
    tmp_path: Path, offset: int
) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="130", filing_year=_floor() + offset, period_code="1T") as work,
    ):
        findings = _unclean(work)

    assert [finding.message_locale_key for finding in findings] == [_ATTESTABLE_KEY]
    assert all(_COMMAND in text for text in _served_words(_ATTESTABLE_KEY))


def test_a_held_source_does_not_name_the_statement(tmp_path: Path) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="130", filing_year=_floor() + 1, period_code="1T") as work,
    ):
        _hold_the_source(work)
        findings = _unclean(work, _HELD)

    assert [finding.message_locale_key for finding in findings] == [_PLAIN_KEY]
    assert not any(_COMMAND in text for text in _served_words(_PLAIN_KEY))
