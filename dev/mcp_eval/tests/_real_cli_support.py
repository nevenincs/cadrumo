"""Shared real-CLI support for agent evaluation tests.

The helpers in this module project the live command-schema registry and invoke
the cached production CLI command tree. They delegate command discovery,
work-unit creation, and envelope decoding to canonical codebase authorities so
eval tests do not grow parallel orchestration logic.
"""

from __future__ import annotations

from functools import cache

from typer._click.core import Command
from typer.main import get_command

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    profile_authority_contexts,
    seed_test_profile_record,
)
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from cadrumo.entrypoints.cli.command_specs import COMMAND_GRAPH
from cadrumo.entrypoints.cli.tests.modelo_cli import create_modelo_work_unit_via_cli
from cadrumo_client.commands.compiler import build_command_app
from cadrumo_client.commands.graph import CommandSpecGraph
from cadrumo_client.contracts.command_program import CommandProgram


def command_graph(program: CommandProgram) -> CommandSpecGraph:
    """Read the declarations belonging to the named executable."""
    if program is CommandProgram.AUTHENTICATION:
        from cadrumo_runtime.commands.command_specs import RUNTIME_COMMAND_GRAPH

        return RUNTIME_COMMAND_GRAPH
    return COMMAND_GRAPH


def command_program_path(tokens: tuple[str, ...]) -> tuple[CommandProgram, tuple[str, ...]]:
    """Keep explicit executable ownership; existing rootless citations belong to AEAT."""
    if tokens and tokens[0] in {program.value for program in CommandProgram}:
        return CommandProgram(tokens[0]), tokens[1:]
    return CommandProgram.AEAT, tokens


@cache
def program_root_command(program: CommandProgram) -> Command:
    """Materialize each existing public tree through its defining compiler."""
    if program is CommandProgram.AEAT:
        from cadrumo.entrypoints.cli.main import cli_app

        return get_command(cli_app())
    return get_command(build_command_app(command_graph(program)))


def valid_cli_commands() -> frozenset[str]:
    """Return command keys projected from the live CLI schema registry."""
    return frozenset(COMMAND_GRAPH.by_schema_identity())


def create_m130_work_unit(*, filing_year: int, period: str, revision: str) -> str:
    """Create an M130 work unit through the real cached CLI command tree."""
    return create_modelo_work_unit_via_cli(
        modelo="130",
        filing_year=filing_year,
        period=period,
        revision=revision,
    )


def seed_natural_person_profile(runtime_profile: TestRuntimeProfile, *, name: str, label: str) -> None:
    """Seed a natural-person (IRPF estimacion directa) profile into the active bucket.

    Written directly to bypass ``config profile create``, which would
    re-provision the already-present bucket manifest.
    """
    seed_test_profile_record(
        create_user_profile_record(
            context=profile_authority_contexts()[0],
            profile_id=runtime_profile.bucket_id,
            setup_state=ProfileSetupState.COMPLETE,
            facts=(
                UserProfileFact(path="identity.name", value=name),
                UserProfileFact(path="identity.surnames", value="Golden Eval"),
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path="activities.description", value="economic activity"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="provenance.source", value="manual_cli"),
            ),
        ),
        root=runtime_profile.storage_root,
        label=label,
    )
