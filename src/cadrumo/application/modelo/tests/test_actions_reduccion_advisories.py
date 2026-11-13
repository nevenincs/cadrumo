"""Real-behavior tests for the Modelo 100 reducción advisories.

contract: each advisory reads its casillas by registry semantic role, emits a
non-blocking finding whose message is routed through ``tr()``, and stays silent
when the roles are absent or there is nothing to surface.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.authority import (
    PinnedAuthorityOperation,
    bundled_indexed_authority,
)

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ..art52_advisory import art52_reduccion_advisory_finding
from ..dt12_advisory import dt12_reduccion_advisory_finding
from ..dt12_antiquity_advisory import dt12_antiquity_advisory_finding
from .action_test_revisions import synthetic_casilla_definition, synthetic_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


_FILING_YEAR = filing_year_envelope().horizon
_FACT_DATE = date(_FILING_YEAR, 12, 31)
_DT12_INGRESO_CASILLA: CasillaId = validated_casilla_id("0003")
_DT12_REDUCCION_CASILLA: CasillaId = validated_casilla_id("0011")
_ART52_REDUCCION_CASILLA: CasillaId = validated_casilla_id("0468")
_ART52_TRABAJADOR_CON_CONTRIBUCION_CASILLA: CasillaId = validated_casilla_id("0426")
_ART52_EMPRESARIAL_CASILLA: CasillaId = validated_casilla_id("0427")
_ART52_AUTONOMOS_EMPRESARIOS_CASILLA: CasillaId = validated_casilla_id("0499")
_DT12_ANTIQUITY_REDUCCION_CASILLA: CasillaId = validated_casilla_id("0011")


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    """Lease one authority generation for the advisory resolvers under test."""
    with bundled_indexed_authority().operation() as operation:
        yield operation


def _dt12_revision() -> ModeloRevision:
    return synthetic_revision(
        casillas=(
            synthetic_casilla_definition(
                _DT12_INGRESO_CASILLA,
                semantic_role="irpf_rendimiento_trabajo_importe_integro_dinerario",
            ),
            synthetic_casilla_definition(
                _DT12_REDUCCION_CASILLA,
                semantic_role="irpf_rendimiento_trabajo_reduccion",
            ),
        ),
    )


def _art52_revision() -> ModeloRevision:
    return synthetic_revision(
        casillas=(
            synthetic_casilla_definition(
                _ART52_REDUCCION_CASILLA,
                semantic_role="irpf_reduccion_prevision_social_total",
            ),
            synthetic_casilla_definition(
                _ART52_TRABAJADOR_CON_CONTRIBUCION_CASILLA,
                semantic_role="irpf_red_prevision_social_aportaciones_trabajador_con_contribucion_empresarial",
            ),
            synthetic_casilla_definition(
                _ART52_EMPRESARIAL_CASILLA,
                semantic_role="irpf_red_prevision_social_contribuciones_empresariales_excepto_scd",
            ),
            synthetic_casilla_definition(
                _ART52_AUTONOMOS_EMPRESARIOS_CASILLA,
                semantic_role="irpf_red_prevision_social_aportaciones_autonomos_empresarios",
            ),
        ),
    )


def _dt12_antiquity_revision() -> ModeloRevision:
    return synthetic_revision(
        casillas=(
            synthetic_casilla_definition(
                _DT12_ANTIQUITY_REDUCCION_CASILLA,
                semantic_role="irpf_rendimiento_trabajo_reduccion",
            ),
        ),
    )


# ---------------------------------------------------------------------------
# contract/contract — DT12 reducción advisory message is localised
# ---------------------------------------------------------------------------


def test_dt12_reduccion_advisory_message_is_localised(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """dt12_reduccion_advisory_finding emits a tr()-rendered message.

    A real revision object carrying two casillas with the correct semantic
    roles triggers the advisory. The finding message must contain ingreso_id,
    ingreso_value, and reduccion_id tokens from the locale template.
    """
    revision = _dt12_revision()
    casilla_values = {_DT12_INGRESO_CASILLA: Decimal("25000"), _DT12_REDUCCION_CASILLA: Decimal("0")}

    finding = dt12_reduccion_advisory_finding(
        revision, casilla_values, operation=authority_operation, effective_date=_FACT_DATE
    )

    assert finding is not None
    assert finding.message_locale_key == "application.modelo.findings.dt12a_reduccion_possible"
    assert dict(finding.message_facts) == {
        "ingreso_id": str(_DT12_INGRESO_CASILLA),
        "ingreso_value": Decimal("25000"),
        "reduccion_id": str(_DT12_REDUCCION_CASILLA),
    }


@pytest.mark.parametrize(
    ("ingreso", "reduccion", "expect_finding"),
    [
        (Decimal("20000"), Decimal("0"), False),
        (Decimal("20000.01"), Decimal("0"), True),
        (Decimal("25000"), Decimal("100"), False),
    ],
)
def test_dt12_reduccion_advisory_threshold_is_the_registry_declared_bound(
    authority_operation: PinnedAuthorityOperation,
    ingreso: Decimal,
    reduccion: Decimal,
    expect_finding: bool,
) -> None:
    """The advisory fires strictly above the mapping fact's threshold and only with a zero reducción."""
    finding = dt12_reduccion_advisory_finding(
        _dt12_revision(),
        {_DT12_INGRESO_CASILLA: ingreso, _DT12_REDUCCION_CASILLA: reduccion},
        operation=authority_operation,
        effective_date=_FACT_DATE,
    )

    assert (finding is not None) is expect_finding


# ---------------------------------------------------------------------------
# contract/contract — art. 52 LIRPF previsión-social individual sub-limit advisory
# ---------------------------------------------------------------------------


def test_art52_reduccion_advisory_fires_for_purely_individual_over_sublimit(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """art52_reduccion_advisory_finding warns on a purely-individual over-reduction.

    A purely-individual filer (no plan-de-empleo worker contribution, no
    contribución empresarial) whose granted reducción (0468) exceeds the EUR 1.500
    art. 52 individual sub-limit — e.g. a EUR 3.000 aportación fully reducible under
    the combined EUR 10.000/30% cap the engine already enforces — should be flagged:
    the combined ceiling requires employer-linked backing this filer does not have.
    """
    revision = _art52_revision()
    casilla_values = {
        _ART52_REDUCCION_CASILLA: Decimal("3000"),
        _ART52_TRABAJADOR_CON_CONTRIBUCION_CASILLA: Decimal("0"),
        _ART52_EMPRESARIAL_CASILLA: Decimal("0"),
        _ART52_AUTONOMOS_EMPRESARIOS_CASILLA: Decimal("0"),
    }

    finding = art52_reduccion_advisory_finding(
        revision,
        casilla_values,
        operation=authority_operation,
        modelo="100",
        effective_date=_FACT_DATE,
    )

    assert finding is not None
    assert finding.kind == "advisory"
    assert finding.severity == "warning"
    assert finding.casilla_id == _ART52_REDUCCION_CASILLA
    assert finding.legal_refs == ("ley-35-2006:art-52-2022",)
    assert finding.message_locale_key == "application.modelo.findings.art52_reduccion_individual_sublimit_possible"
    assert dict(finding.message_facts) == {
        "reduccion_id": str(_ART52_REDUCCION_CASILLA),
        "reduccion_value": Decimal("3000"),
        "sublimit": Decimal("1500"),
    }
    assert "next_action" not in finding.model_dump(mode="json")


def test_art52_reduccion_advisory_silent_when_employer_backed(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """No false positive when a contribución empresarial (0427) backs the reducción.

    The same over-1.500 reducción as the firing case, but with a positive
    contribución empresarial declared: the combined EUR 10.000 ceiling legitimately
    applies, so the advisory must stay silent.
    """
    revision = _art52_revision()
    casilla_values = {
        _ART52_REDUCCION_CASILLA: Decimal("3000"),
        _ART52_TRABAJADOR_CON_CONTRIBUCION_CASILLA: Decimal("0"),
        _ART52_EMPRESARIAL_CASILLA: Decimal("2500"),
        _ART52_AUTONOMOS_EMPRESARIOS_CASILLA: Decimal("0"),
    }

    assert (
        art52_reduccion_advisory_finding(
            revision,
            casilla_values,
            operation=authority_operation,
            modelo="100",
            effective_date=_FACT_DATE,
        )
        is None
    )


def test_art52_reduccion_advisory_silent_when_plan_de_empleo_backed(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """No false positive when a plan-de-empleo worker contribution (0426) backs it."""
    revision = _art52_revision()
    casilla_values = {
        _ART52_REDUCCION_CASILLA: Decimal("3000"),
        _ART52_TRABAJADOR_CON_CONTRIBUCION_CASILLA: Decimal("2500"),
        _ART52_EMPRESARIAL_CASILLA: Decimal("0"),
        _ART52_AUTONOMOS_EMPRESARIOS_CASILLA: Decimal("0"),
    }

    assert (
        art52_reduccion_advisory_finding(
            revision,
            casilla_values,
            operation=authority_operation,
            modelo="100",
            effective_date=_FACT_DATE,
        )
        is None
    )


def test_art52_reduccion_advisory_silent_when_autonomo_backed(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """No false positive when an autónomo/empresario-individual aportación (0499) backs it.

    Casilla 0499 legitimately unlocks the art. 52.1.2º EUR 4.250 increment (not the
    full art. 52.1.1º EUR 8.500 increment 0426/0427 unlock), so a reducción above
    EUR 1.500 backed solely by 0499 must not be flagged — the advisory only detects
    the no-backing-at-all case and leaves the exact 1º/2º split to the COMPUTED
    formula on revisions where 0468 is not a bare MANUAL input.
    """
    revision = _art52_revision()
    casilla_values = {
        _ART52_REDUCCION_CASILLA: Decimal("3000"),
        _ART52_TRABAJADOR_CON_CONTRIBUCION_CASILLA: Decimal("0"),
        _ART52_EMPRESARIAL_CASILLA: Decimal("0"),
        _ART52_AUTONOMOS_EMPRESARIOS_CASILLA: Decimal("2500"),
    }

    assert (
        art52_reduccion_advisory_finding(
            revision,
            casilla_values,
            operation=authority_operation,
            modelo="100",
            effective_date=_FACT_DATE,
        )
        is None
    )


def test_art52_reduccion_advisory_silent_when_under_sublimit(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """No false positive when the purely-individual reducción is at or below EUR 1.500."""
    revision = _art52_revision()
    casilla_values = {
        _ART52_REDUCCION_CASILLA: Decimal("1500"),
        _ART52_TRABAJADOR_CON_CONTRIBUCION_CASILLA: Decimal("0"),
        _ART52_EMPRESARIAL_CASILLA: Decimal("0"),
        _ART52_AUTONOMOS_EMPRESARIOS_CASILLA: Decimal("0"),
    }

    assert (
        art52_reduccion_advisory_finding(
            revision,
            casilla_values,
            operation=authority_operation,
            modelo="100",
            effective_date=_FACT_DATE,
        )
        is None
    )


def test_art52_reduccion_advisory_silent_when_roles_absent(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    assert (
        art52_reduccion_advisory_finding(
            synthetic_revision(),
            {},
            operation=authority_operation,
            modelo="100",
            effective_date=_FACT_DATE,
        )
        is None
    )


# ---------------------------------------------------------------------------
# contract/contract — DT 12ª LIRPF antiquity-condition advisory
# ---------------------------------------------------------------------------


def test_dt12_antiquity_advisory_fires_when_reduccion_applied(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """dt12_antiquity_advisory_finding warns to confirm antiquity when 40% applies.

    A strictly positive trabajo reducción prompts the operator to confirm the
    pre-2007 TRLIRPF art. 17.2.a) two-year antiquity condition (waived for
    invalidez) DT 12ª LIRPF imports for the transitional régimen.
    """
    revision = _dt12_antiquity_revision()
    casilla_values = {_DT12_ANTIQUITY_REDUCCION_CASILLA: Decimal("4000")}

    finding = dt12_antiquity_advisory_finding(
        revision,
        casilla_values,
        operation=authority_operation,
        modelo="100",
        effective_date=_FACT_DATE,
    )

    assert finding is not None
    assert finding.kind == "advisory"
    assert finding.severity == "warning"
    assert finding.casilla_id == _DT12_ANTIQUITY_REDUCCION_CASILLA
    assert finding.legal_refs == ("ley-35-2006:dt-12",)
    assert finding.message_locale_key == "application.modelo.findings.dt12a_reduccion_antiquity_possible"
    assert dict(finding.message_facts) == {
        "reduccion_id": str(_DT12_ANTIQUITY_REDUCCION_CASILLA),
        "reduccion_value": Decimal("4000"),
    }
    assert "next_action" not in finding.model_dump(mode="json")


def test_dt12_antiquity_advisory_silent_when_reduccion_zero(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """No false positive when no reducción has been applied at all."""
    revision = _dt12_antiquity_revision()
    casilla_values = {_DT12_ANTIQUITY_REDUCCION_CASILLA: Decimal("0")}

    assert (
        dt12_antiquity_advisory_finding(
            revision,
            casilla_values,
            operation=authority_operation,
            modelo="100",
            effective_date=_FACT_DATE,
        )
        is None
    )


def test_dt12_antiquity_advisory_silent_when_roles_absent(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    assert (
        dt12_antiquity_advisory_finding(
            synthetic_revision(),
            {},
            operation=authority_operation,
            modelo="100",
            effective_date=_FACT_DATE,
        )
        is None
    )
