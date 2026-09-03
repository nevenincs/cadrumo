"""Literal and resolution contracts for the ledger prorrata command leaves."""

from __future__ import annotations

from typing import Final

import pytest

from .._app_ledger_prorrata_command_specs import LEDGER_PRORRATA_COMMAND_SPECS
from .._command_target import resolve_deferred_target
from ..command_spec import CommandSpec, OptionSpec
from ..command_specs import COMMAND_GRAPH

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_EXPECTED_LEAVES: Final[tuple[tuple[object, ...], ...]] = (
    (
        "app_ledger_prorrata_declare_sector",
        "declare-sector",
        "cli.app.ledger.prorrata.declare_sector_help",
        "profile-bound",
        "prorrata_declare_sector",
        "ProrrataDeclareSectorResult",
        "ledger.prorrata.declare_sector",
        (
            (
                "sector_id",
                ("--sector-id",),
                "builtins:str",
                "REQUIRED",
                None,
                "cli.app.ledger.prorrata.sector_id_help",
                False,
            ),
            (
                "letra",
                ("--letra",),
                "cadrumo.core.prorrata_register:SectorDiferenciadoLetra",
                "REQUIRED",
                None,
                "cli.app.ledger.prorrata.letra_help",
                False,
            ),
            (
                "activity_code",
                ("--activity-code",),
                "builtins:str",
                "LITERAL",
                (),
                "cli.app.ledger.prorrata.activity_code_help",
                True,
            ),
        ),
    ),
    (
        "app_ledger_prorrata_elect_especial",
        "elect-especial",
        "cli.app.ledger.prorrata.elect_especial_help",
        "profile-bound",
        "prorrata_elect_especial",
        "ProrrataElectEspecialResult",
        "ledger.prorrata.elect_especial",
        (
            (
                "ejercicio",
                ("--ejercicio",),
                "builtins:int",
                "REQUIRED",
                None,
                "cli.app.ledger.prorrata.ejercicio_help",
                False,
            ),
            (
                "percentage",
                ("--percentage",),
                "builtins:str",
                "REQUIRED",
                None,
                "cli.app.ledger.prorrata.percentage_help",
                False,
            ),
            (
                "evidence_reference",
                ("--evidence-reference",),
                "builtins:str",
                "LITERAL",
                None,
                "cli.app.ledger.prorrata.optional_evidence_reference_help",
                False,
            ),
            (
                "provenance",
                ("--provenance",),
                "cadrumo.core.prorrata_register:ProrrataProvisionalProvenance",
                "LITERAL",
                "carried_prior_definitiva",
                "cli.app.ledger.prorrata.provenance_help",
                False,
            ),
            (
                "reference",
                ("--reference",),
                "builtins:str",
                "LITERAL",
                None,
                "cli.app.ledger.prorrata.reference_help",
                False,
            ),
            ("sector", ("--sector",), "builtins:str", "LITERAL", None, "cli.app.ledger.prorrata.sector_help", False),
        ),
    ),
    (
        "app_ledger_prorrata_elect_general",
        "elect-general",
        "cli.app.ledger.prorrata.elect_general_help",
        "profile-bound",
        "prorrata_elect_general",
        "ProrrataElectGeneralResult",
        "ledger.prorrata.elect_general",
        (
            (
                "ejercicio",
                ("--ejercicio",),
                "builtins:int",
                "REQUIRED",
                None,
                "cli.app.ledger.prorrata.ejercicio_help",
                False,
            ),
            (
                "percentage",
                ("--percentage",),
                "builtins:str",
                "REQUIRED",
                None,
                "cli.app.ledger.prorrata.general_percentage_help",
                False,
            ),
            (
                "provenance",
                ("--provenance",),
                "cadrumo.core.prorrata_register:ProrrataProvisionalProvenance",
                "LITERAL",
                "carried_prior_definitiva",
                "cli.app.ledger.prorrata.provenance_help",
                False,
            ),
            (
                "reference",
                ("--reference",),
                "builtins:str",
                "LITERAL",
                None,
                "cli.app.ledger.prorrata.reference_help",
                False,
            ),
            ("sector", ("--sector",), "builtins:str", "LITERAL", None, "cli.app.ledger.prorrata.sector_help", False),
        ),
    ),
    (
        "app_ledger_prorrata_list",
        "list",
        "cli.app.ledger.prorrata.list_help",
        "none",
        "prorrata_list",
        "ProrrataListResult",
        "ledger.prorrata.list",
        (),
    ),
    (
        "app_ledger_prorrata_revoke_especial",
        "revoke-especial",
        "cli.app.ledger.prorrata.revoke_especial_help",
        "profile-bound",
        "prorrata_revoke_especial",
        "ProrrataRevokeEspecialResult",
        "ledger.prorrata.revoke_especial",
        (
            (
                "ejercicio",
                ("--ejercicio",),
                "builtins:int",
                "REQUIRED",
                None,
                "cli.app.ledger.prorrata.ejercicio_help",
                False,
            ),
            (
                "evidence_reference",
                ("--evidence-reference",),
                "builtins:str",
                "REQUIRED",
                None,
                "cli.app.ledger.prorrata.evidence_reference_help",
                False,
            ),
            (
                "percentage",
                ("--percentage",),
                "builtins:str",
                "REQUIRED",
                None,
                "cli.app.ledger.prorrata.general_percentage_help",
                False,
            ),
            (
                "provenance",
                ("--provenance",),
                "cadrumo.core.prorrata_register:ProrrataProvisionalProvenance",
                "LITERAL",
                "carried_prior_definitiva",
                "cli.app.ledger.prorrata.provenance_help",
                False,
            ),
            (
                "reference",
                ("--reference",),
                "builtins:str",
                "LITERAL",
                None,
                "cli.app.ledger.prorrata.reference_help",
                False,
            ),
            ("sector", ("--sector",), "builtins:str", "LITERAL", None, "cli.app.ledger.prorrata.sector_help", False),
        ),
    ),
    (
        "app_ledger_prorrata_seed",
        "seed",
        "cli.app.ledger.prorrata.seed_help",
        "profile-bound",
        "prorrata_seed",
        "ProrrataSeedResult",
        "ledger.prorrata.seed",
        (
            (
                "ejercicio",
                ("--ejercicio",),
                "builtins:int",
                "REQUIRED",
                None,
                "cli.app.ledger.prorrata.seed_ejercicio_help",
                False,
            ),
            ("sector", ("--sector",), "builtins:str", "LITERAL", None, "cli.app.ledger.prorrata.sector_help", False),
        ),
    ),
    (
        "app_ledger_prorrata_seed_sector",
        "seed-sector",
        "cli.app.ledger.prorrata.seed_sector_help",
        "profile-bound",
        "prorrata_seed_sector",
        "ProrrataSeedSectorResult",
        "ledger.prorrata.seed_sector",
        (
            (
                "ejercicio",
                ("--ejercicio",),
                "builtins:int",
                "REQUIRED",
                None,
                "cli.app.ledger.prorrata.seed_ejercicio_help",
                False,
            ),
            (
                "sector_id",
                ("--sector-id",),
                "builtins:str",
                "REQUIRED",
                None,
                "cli.app.ledger.prorrata.sector_id_help",
                False,
            ),
        ),
    ),
    (
        "app_ledger_prorrata_settle_sector",
        "settle-sector",
        "cli.app.ledger.prorrata.settle_sector_help",
        "profile-bound",
        "prorrata_settle_sector",
        "ProrrataSettleSectorResult",
        "ledger.prorrata.settle_sector",
        (
            (
                "ejercicio",
                ("--ejercicio",),
                "builtins:int",
                "REQUIRED",
                None,
                "cli.app.ledger.prorrata.seed_ejercicio_help",
                False,
            ),
            (
                "sector_id",
                ("--sector-id",),
                "builtins:str",
                "REQUIRED",
                None,
                "cli.app.ledger.prorrata.sector_id_help",
                False,
            ),
            (
                "con_derecho_volume",
                ("--con-derecho-volume",),
                "builtins:str",
                "REQUIRED",
                None,
                "cli.app.ledger.prorrata.con_derecho_volume_help",
                False,
            ),
            (
                "sin_derecho_volume",
                ("--sin-derecho-volume",),
                "builtins:str",
                "REQUIRED",
                None,
                "cli.app.ledger.prorrata.sin_derecho_volume_help",
                False,
            ),
        ),
    ),
)


def _literal_contract(command: CommandSpec) -> tuple[object, ...]:
    """Project a leaf into every public prorrata fact this refactor must preserve."""
    assert command.handler is not None and command.handler.target is not None
    assert command.result_schema.target is not None
    parameters: list[tuple[object, ...]] = []
    for parameter in command.parameters:
        assert isinstance(parameter, OptionSpec)
        assert parameter.help_key is not None
        parameters.append(
            (
                parameter.name,
                parameter.declarations,
                parameter.value.annotation.identity,
                parameter.default.kind.name,
                parameter.default.literal,
                parameter.help_key.value,
                parameter.multiple,
            )
        )
    return (
        command.key,
        command.token,
        command.help_key.value,
        command.policy.write_route,
        command.handler.target.qualname,
        command.result_schema.target.qualname,
        command.result_schema.identity,
        tuple(parameters),
    )


def test_ledger_prorrata_leaves_keep_their_literal_contracts() -> None:
    """Every command keeps its distinct help, default, ordering, policy, and target facts."""
    assert tuple(_literal_contract(spec) for spec in LEDGER_PRORRATA_COMMAND_SPECS) == _EXPECTED_LEAVES
    assert all(
        spec.kind.value == "leaf"
        and spec.parent_key == "app_ledger_prorrata"
        and spec.short_help_key is None
        and not spec.invocation.invoke_without_command
        and not spec.invocation.no_args_is_help
        and spec.invocation.context_parameter == "ctx"
        for spec in LEDGER_PRORRATA_COMMAND_SPECS
    )


def test_ledger_prorrata_leaves_resolve_through_the_live_command_graph() -> None:
    """The installed graph reaches each authored leaf and both deferred public targets."""
    for spec in LEDGER_PRORRATA_COMMAND_SPECS:
        resolved = COMMAND_GRAPH.resolve_path(("aeat", "app", "ledger", "prorrata", spec.token))
        assert resolved is spec
        assert spec.handler is not None and spec.handler.target is not None
        assert callable(resolve_deferred_target(spec.handler.target))
        assert spec.result_schema.target is not None
        assert resolve_deferred_target(spec.result_schema.target) is not None
