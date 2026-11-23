"""The two contributions to a Modelo 303 modification box are kept apart at verification.

Casillas 14, 15 and 26 each print one figure made of two contributions: the one
the period's facturas rectificativas make, which a binding reads, and the one
the person states for a modification the catalogue holds no document for. Three
refusals keep them apart, and each is checked here against the real published
revision rather than a stand-in casilla set.

Figures are worked by hand. A 100.00 base at 21 % is a 21.00 cuota, and a
minoración states both negative, so the carrier reads -100.00 and -21.00.

Real-behaviour: the real registry revision and the real finding builder. No
mocks, stubs, skips or xfail.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.modelos.verification_report import ModeloVerificationFindingSeverity
from ..verification_modification_contributions import modification_contribution_findings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon
_PERIOD = Period.from_year_and_code(_YEAR, "2T")
_BASE = Decimal("-100.00")
_CUOTA = Decimal("-21.00")
_RECARGO = Decimal("-5.20")
_TYPED = "-40.00"


@pytest.fixture(autouse=True)
def _authority_operation() -> Iterator[None]:
    """Read the revision under the generation-pinned authority production uses."""
    with bundled_indexed_authority().operation():
        yield


def _revision() -> ModeloRevision:
    return published_snapshot("303", filing_year=_YEAR, period=_PERIOD.registry_token).revision


def _findings(
    *,
    casilla_values: dict[str, Decimal],
    input_values: dict[str, str],
) -> dict[str, ModeloVerificationFindingSeverity]:
    found = modification_contribution_findings(
        revision=_revision(),
        casilla_values=casilla_values,
        input_values_by_casilla_id=input_values,
    )
    return {finding.message_locale_key: finding.severity for finding in found}


def test_a_period_whose_boxes_hold_only_the_invoice_sourced_half_is_not_refused() -> None:
    """The ordinary case: the rectificativas state the modification and the person adds nothing."""
    found = _findings(
        casilla_values={"iva.modificacion-bases-cuotas.base": _BASE, "iva.modificacion-bases-cuotas": _CUOTA},
        input_values={},
    )

    assert found == {}


def test_a_typed_contribution_beside_an_invoice_sourced_one_blocks_naming_both_figures() -> None:
    """The record carries no scope for the typed figure, so the box may be stating one document twice."""
    found = modification_contribution_findings(
        revision=_revision(),
        casilla_values={"iva.modificacion-bases-cuotas": _CUOTA},
        input_values_by_casilla_id={"iva.modificacion-bases-cuotas.operador": _TYPED},
    )

    (finding,) = found
    assert finding.message_locale_key == "application.modelo.findings.modification_typed_beside_invoice_sourced"
    assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert finding.message_facts["casilla_id"] == "15"
    assert finding.message_facts["invoice_sourced_value"] == _CUOTA
    assert finding.message_facts["typed_value"] == Decimal(_TYPED)
    assert finding.message_facts["contribution_casilla_id"] == "iva.modificacion-bases-cuotas.operador"


def test_a_value_stored_against_the_now_computed_box_blocks_and_names_where_to_re_enter_it() -> None:
    """The stored figure is neither dropped nor read as the contribution, which is the ruling."""
    found = modification_contribution_findings(
        revision=_revision(),
        casilla_values={},
        input_values_by_casilla_id={"15": _TYPED},
    )

    (finding,) = found
    assert finding.message_locale_key == "application.modelo.findings.modification_value_stored_on_computed_box"
    assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert finding.message_facts["casilla_id"] == "15"
    assert finding.message_facts["stored_value"] == Decimal(_TYPED)
    assert finding.message_facts["contribution_casilla_id"] == "iva.modificacion-bases-cuotas.operador"


def test_a_recargo_modification_without_its_base_blocks_naming_casilla_25() -> None:
    """Casilla 26 reads the recargo the rectificativas moved; its base stays the person's."""
    found = modification_contribution_findings(
        revision=_revision(),
        casilla_values={
            "iva.modificacion-recargo": _RECARGO,
            "iva.modificacion-bases-cuotas.base": _BASE,
        },
        input_values_by_casilla_id={},
    )

    (finding,) = found
    assert finding.message_locale_key == "application.modelo.findings.modification_recargo_base_missing"
    assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert finding.message_facts["casilla_id"] == "25"
    assert finding.message_facts["recargo_value"] == _RECARGO
    assert finding.message_facts["modification_base_value"] == _BASE


def test_the_recargo_base_the_person_states_closes_that_refusal() -> None:
    """Casilla 25 is the operator's, exactly as the ordinary recargo bases are."""
    found = _findings(
        casilla_values={"iva.modificacion-recargo": _RECARGO},
        input_values={"25": str(_BASE)},
    )

    assert found == {}
