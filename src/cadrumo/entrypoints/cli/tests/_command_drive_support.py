"""Drive a live command through the real CLI with synthetic arguments and observe it.

The command-graph probes share one way of reaching a command: its operator path
comes from the graph's parent chain, each required parameter gets a synthetic
value derived from its declared type, and a seeded natural-person profile gives
profile-bound commands something to open. ``sys.monitoring`` then watches the
command's own behavior target, so a probe can prove its command actually ran.
"""

from __future__ import annotations

import inspect
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from types import CodeType
from typing import Final
from uuid import UUID

from pydantic import SecretStr

from cadrumo.application.operator_surface.command_ports import CommandNodeKind

from ....adapters.persistence.profile.tests.profile_registration import register_cli_profile
from ....adapters.persistence.storage.operator_scope import build_operator_scope_ports
from ....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ....application.auth.operator import configure_operator_auth
from ....application.user_profile.automation_custody_port import AutomationSecretStore
from ....core.config import override_settings
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ....domain.user_profile.values import UserProfileFact
from ....tests.certificates import CERTIFICATE_BUNDLE_INPUT, build_pkcs12_bundle
from .._command_target import resolve_deferred_target
from ..command_graph import CommandSpecGraph
from ..command_parameter_contracts import ArgumentSpec, OptionSpec
from ..command_shared_contracts import DefaultKind, DeferredTarget
from ..command_spec import CommandSpec
from .portable_human_cli_runtime import PortableHumanCliRuntime, portable_human_cli_runtime, portable_password_custody

PROBE_PROFILE_LABEL: Final = "Governed fact declaration probe"
PROBE_PROFILE_TAX_ID: Final = "12345678Z"


def is_runnable(spec: CommandSpec) -> bool:
    """Report whether a spec has terminal behavior an operator can run."""
    return spec.kind == CommandNodeKind.LEAF or (
        spec.kind == CommandNodeKind.GROUP and spec.invocation.terminal_behavior == "executable"
    )


def command_path(graph: CommandSpecGraph, spec: CommandSpec) -> tuple[str, ...]:
    """Return the operator tokens that select ``spec`` below the root."""
    tokens: list[str] = []
    current = spec
    while current.parent_key is not None:
        tokens.append(current.token)
        current = graph.spec(current.parent_key)
    return tuple(reversed(tokens))


def _synthetic_value(spec: CommandSpec, parameter: ArgumentSpec | OptionSpec, workdir: Path) -> str:
    if parameter.value.choices:
        return parameter.value.choices[0]
    annotation = resolve_deferred_target(parameter.value.annotation)
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        member = next(iter(annotation))
        return str(member.value)
    if annotation is int:
        minimum = parameter.constraint.minimum
        return str(int(minimum) if minimum is not None else 1)
    if annotation is UUID:
        return "00000000-0000-4000-8000-000000000001"
    if parameter.name == "review_digest":
        return "0" * 64
    if isinstance(annotation, type) and issubclass(annotation, Path):
        location = workdir / f"{spec.key}-{parameter.name}.bin"
        if parameter.name != "output":
            location.write_bytes(b"synthetic probe input\n")
        return str(location)
    if parameter.name in {"name", "label"}:
        return PROBE_PROFILE_LABEL
    return f"probe-{parameter.name.replace('_', '-')}"


def synthetic_argv(
    graph: CommandSpecGraph,
    spec: CommandSpec,
    workdir: Path,
    *,
    also: tuple[str, ...] = (),
    values: Mapping[str, str] | None = None,
) -> list[str]:
    """Build the command path plus a synthetic value for every required parameter.

    ``also`` names optional parameters to supply as well, and ``values`` gives
    named parameters a domain-valid value in place of the synthetic one.
    """
    supplied = values or {}
    positional: list[str] = []
    named: list[str] = []
    for parameter in spec.parameters:
        wanted = parameter.name in also or parameter.name in supplied
        if parameter.default.kind is not DefaultKind.REQUIRED and not wanted:
            continue
        value = supplied.get(parameter.name) or _synthetic_value(spec, parameter, workdir)
        if isinstance(parameter, OptionSpec):
            named.extend((parameter.declarations[0], value))
        else:
            positional.append(value)
    return [*command_path(graph, spec), *positional, *named]


@contextmanager
def seeded_probe_runtime(
    tmp_path: Path,
    *,
    extra_facts: tuple[UserProfileFact, ...] = (),
    certificate_path: Path | None = None,
    client_native_store: AutomationSecretStore | None = None,
) -> Iterator[PortableHumanCliRuntime]:
    """Register real password custody and own admitted, observable CLI execution.

    Registration's governed-fact lease ends before the joined runtime captures
    its context. No fixture-level governed-fact scope is lent to a handler.
    """
    with portable_password_custody(), isolated_profile_storage_root(tmp_path=tmp_path) as root:
        profile_id = register_cli_profile(
            label=PROBE_PROFILE_LABEL,
            facts={
                "identity.name": "Ana",
                "identity.surnames": "Perez",
                "identity.tax_id": PROBE_PROFILE_TAX_ID,
                "taxpayer_type.entity_type": "natural_person",
                "provenance.source": "manual_cli",
                **{fact.path: str(fact.value) for fact in extra_facts},
            },
            log_in=False,
        )
        if certificate_path is not None:
            with bundled_indexed_authority().operation() as operation, validating_governed_facts(operation):
                configure_operator_auth(
                    "certificate",
                    certificate_path=certificate_path,
                    operator_scope_ports=build_operator_scope_ports(),
                    operation=operation,
                )
        with portable_human_cli_runtime(
            storage_root=root,
            profile_id=UUID(profile_id),
            label=PROBE_PROFILE_LABEL,
            client_native_store=client_native_store,
        ) as runtime:
            yield runtime


@contextmanager
def synthetic_aeat_credentials(workdir: Path) -> Iterator[Path]:
    """Configure a real, self-signed certificate naming the seeded profile's taxpayer.

    A session-gated AEAT flow refuses at credential loading when nothing is
    configured, before it ever builds a Sede session. With this certificate the
    flow loads its credentials and reaches the Sede client, where a sealed run
    stops at the browser launch. The bundle is synthetic and never leaves the
    test's directory.
    """
    now = datetime.now(UTC)
    bundle = build_pkcs12_bundle(
        workdir,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=365),
        name="probe-certificate",
        subject_cn=f"PROBE HOLDER - {PROBE_PROFILE_TAX_ID}",
    )
    with override_settings(
        cadrumo_certificate_path=bundle,
        cadrumo_certificate_password_secret=SecretStr(CERTIFICATE_BUNDLE_INPUT),
    ):
        yield bundle


def free_monitoring_tool() -> int:
    """Return a ``sys.monitoring`` tool id no other tool holds."""
    for tool_id in (3, 4):
        if sys.monitoring.get_tool(tool_id) is None:
            return tool_id
    raise AssertionError("no free sys.monitoring tool id for a command probe")


def handler_code(target: DeferredTarget) -> CodeType:
    """Return the code object of a command's declared behavior target."""
    behavior = resolve_deferred_target(target)
    if callable(behavior):
        behavior = inspect.unwrap(behavior)
    code = getattr(behavior, "__code__", None)
    if not isinstance(code, CodeType):
        raise AssertionError(f"behavior target {target.identity!r} has no Python code to observe")
    return code


__all__ = [
    "PROBE_PROFILE_LABEL",
    "PROBE_PROFILE_TAX_ID",
    "command_path",
    "free_monitoring_tool",
    "handler_code",
    "is_runnable",
    "seeded_probe_runtime",
    "synthetic_aeat_credentials",
    "synthetic_argv",
]
