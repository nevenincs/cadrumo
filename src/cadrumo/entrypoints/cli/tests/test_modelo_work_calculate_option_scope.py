"""The Modelo 303 filing-evidence options stay on the calculation of the modelo that owns them."""

from __future__ import annotations

import pytest

from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.parameters import OptionSpec

from ....application.modelo.m303_filing_evidence import m303_filing_evidence_modelo
from ....application.modelo.work_calculation_contracts import ModeloWorkCalculateOrdinaryM303EvidenceRequestV2
from ..argument_only_refusals import refuse_filing_evidence_options_for_other_modelo
from ..modelo_work_command_specs import MODELO_WORK_COMMAND_SPECS

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]


def _calculate_option_declarations() -> dict[str, tuple[str, ...]]:
    calculate = next(spec for spec in MODELO_WORK_COMMAND_SPECS if spec.key == "app_modelo_work_calculate")
    return {item.name: item.declarations for item in calculate.parameters if isinstance(item, OptionSpec)}


def test_every_evidence_field_is_a_calculate_option_spelled_as_the_refusal_names_it() -> None:
    """The refusal derives each option's spelling from the evidence field; the command must declare that spelling."""
    declarations = _calculate_option_declarations()
    for name in ModeloWorkCalculateOrdinaryM303EvidenceRequestV2.model_fields:
        assert f"--{name.replace('_', '-')}" in declarations[name]


def test_the_owning_modelo_is_the_one_the_evidence_owner_admits() -> None:
    """The refusal consults the evidence owner's modelo, so the owner's own modelo passes."""
    owner = m303_filing_evidence_modelo()
    refuse_filing_evidence_options_for_other_modelo(owner, {"joint_return_elected": True})
    refuse_filing_evidence_options_for_other_modelo(f" {owner} ", {"joint_return_elected": False})


def test_another_modelo_is_refused_naming_each_supplied_option_and_the_owner() -> None:
    """Every supplied option is named, with the modelo asked and the modelo that owns them."""
    owner = m303_filing_evidence_modelo()
    other = next(code for code in ("100", "115", "111") if code != owner)
    with pytest.raises(CliRefusedBoundaryError) as refusal:
        refuse_filing_evidence_options_for_other_modelo(
            other,
            {
                "joint_return_elected": False,
                "m303_exonerado_390_attachment_id": "a" * 64,
                "m303_exonerado_390_sha256": None,
            },
        )
    assert refusal.value.context == {
        "modelo": other,
        "applies_to": owner,
        "options": "--joint-return-elected, --m303-exonerado-390-attachment-id",
    }


def test_another_modelo_without_any_option_is_not_refused() -> None:
    """A calculation that supplies none of the options is not this refusal's business."""
    refuse_filing_evidence_options_for_other_modelo("100", {"joint_return_elected": None})
    refuse_filing_evidence_options_for_other_modelo("100", {})
