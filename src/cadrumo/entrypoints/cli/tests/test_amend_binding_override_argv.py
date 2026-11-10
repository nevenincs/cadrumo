"""The amend command states the box sources a filed baseline never recorded.

An imported return holds casilla values only, and a historical correction never
reads today's profile or ledger, so a correction that reaches a formula reading
an unrecorded binding refuses until the operator states it. ``--binding`` is how
the operator states it: the same ``KEY=VALUE`` grammar and request token as
``work calculate``, with the authority admitting each against the baseline's
pinned revision.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer
import yaml
from pydantic import ValidationError

from cadrumo_client.commands.parameters import OptionSpec

from ....application.modelo.calculation_request_fields import ModeloCalculationOverride
from ....application.modelo.work_amend_contracts import (
    ModeloWorkAmendBaseline,
    ModeloWorkAmendOverride,
    ModeloWorkAmendRequest,
)
from ....domain.modelos.filing_record import FilingDeclarationKind
from ..modelo_commands import resolve_amendment_binding_overrides
from ..modelo_core_command_specs import MODELO_CORE_COMMAND_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_LOCALES = ("en", "es", "ca", "hu")
_LOCALES_ROOT = Path(__file__).resolve().parents[3] / "locales"


def _amend_binding_option() -> OptionSpec:
    spec = next(spec for spec in MODELO_CORE_COMMAND_SPECS if spec.key == "app_modelo_work_amend")
    return next(
        option for option in spec.parameters if isinstance(option, OptionSpec) and "--binding" in option.declarations
    )


def _request(binding_overrides: tuple[ModeloCalculationOverride, ...]) -> ModeloWorkAmendRequest:
    return ModeloWorkAmendRequest(
        baseline=ModeloWorkAmendBaseline(from_filing_record_id="a" * 64),
        amendment_kind=FilingDeclarationKind.COMPLEMENTARIA,
        overrides=(ModeloWorkAmendOverride(casilla_id="01", value="1100.00"),),
        reason="under-reported turnover",
        binding_overrides=binding_overrides,
        actor="operator",
    )


def test_binding_specs_become_the_calculation_override_tokens_in_order() -> None:
    resolved = resolve_amendment_binding_overrides(
        (
            "modelo-130-estimacion-directa-modalidad=directa_normal",
            "irpf.previous_year_economic_activity_net_income=20000.00",
        )
    )

    assert resolved == (
        ModeloCalculationOverride(key="modelo-130-estimacion-directa-modalidad", value="directa_normal"),
        ModeloCalculationOverride(key="irpf.previous_year_economic_activity_net_income", value="20000.00"),
    )


def test_no_binding_spec_states_nothing() -> None:
    assert resolve_amendment_binding_overrides(()) == ()


def test_a_repeated_binding_keeps_its_last_value_as_calculate_does() -> None:
    resolved = resolve_amendment_binding_overrides(
        ("modelo-130-retenciones-agrarias=1", "modelo-130-retenciones-agrarias=0")
    )

    assert resolved == (ModeloCalculationOverride(key="modelo-130-retenciones-agrarias", value="0"),)


@pytest.mark.parametrize("spec", ["modelo-130-retenciones-agrarias", "=0", "not a binding id=0"])
def test_a_malformed_binding_spec_is_refused_at_the_boundary(spec: str) -> None:
    with pytest.raises(typer.BadParameter):
        resolve_amendment_binding_overrides((spec,))


def test_the_request_carries_the_stated_bindings() -> None:
    stated = resolve_amendment_binding_overrides(("modelo-130-retenciones-agrarias=0",))

    assert _request(stated).binding_overrides == stated
    assert _request(()).binding_overrides == ()


def test_the_request_refuses_two_values_for_one_binding() -> None:
    with pytest.raises(ValidationError):
        _request(
            (
                ModeloCalculationOverride(key="modelo-130-retenciones-agrarias", value="0"),
                ModeloCalculationOverride(key="modelo-130-retenciones-agrarias", value="1"),
            )
        )


def test_the_command_declares_a_repeatable_binding_option() -> None:
    option = _amend_binding_option()

    assert option.name == "binding"
    assert option.multiple is True


@pytest.mark.parametrize("locale", _LOCALES)
def test_the_binding_option_is_worded_in_this_locale(locale: str) -> None:
    catalogue = yaml.safe_load((_LOCALES_ROOT / locale / "cli.yml").read_text(encoding="utf-8"))
    wording = str(catalogue["cli"]["app"]["modelo"]["work"].get("amend_binding_help", "")).strip()

    assert wording
    assert "BINDING_ID=VALUE" in wording
