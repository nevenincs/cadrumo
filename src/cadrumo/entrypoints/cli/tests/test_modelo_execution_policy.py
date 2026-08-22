"""Live-tree execution-policy gates for the complete modelo subtree."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
import typer
from typer.testing import CliRunner

from ....tests import REPO_ROOT
from .. import app
from .._command_policy import CommandExecutionPolicy, command_execution_policy
from .._command_suggestions import CadrumoTyperGroup, walk_live_command_tree
from .._modelo_execution_policies import (
    BROWSER_MODEL_WRITE,
    CALCULATION_READ,
    CALCULATION_WRITE,
    CRYPTO_FACT_FILE_WRITE,
    CRYPTO_PROFILE_WRITE,
    CRYPTO_READ,
    INTERACTIVE_MODEL_WRITE,
    METADATA,
    MODEL_DESTRUCTIVE,
    MODEL_HANDOFF,
    MODEL_READ,
    MODEL_WRITE,
    REGISTRY_MODEL_READ,
    REGISTRY_MODEL_WRITE,
    REGISTRY_READ,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _modelo_nodes():
    return tuple(
        node
        for node in walk_live_command_tree(app)
        if len(node.path) > 2 and node.path[:3] == ("aeat", "app", "modelo")
    )


def _assert_network_profile_write(policy: CommandExecutionPolicy | None) -> None:
    assert policy is not None
    assert {"browser", "network", "registry", "encrypted-facts"} <= policy.classification.expanded_capabilities
    assert policy.classification.side_effects == frozenset({"browser", "network", "local-state"})
    assert policy.write_route == "profile-bound"


def test_every_live_modelo_node_owns_an_execution_policy() -> None:
    nodes = _modelo_nodes()

    assert nodes
    assert len({node.path for node in nodes}) == len(nodes)
    assert all(node.execution_policy is not None for node in nodes)


def test_modelo_policy_gate_bites_for_an_external_unclassified_node() -> None:
    probe = typer.Typer(name="modelo-policy-negative", cls=CadrumoTyperGroup)

    @probe.command("missing")
    def missing() -> None:
        return None

    @probe.command("sibling")
    @command_execution_policy(MODEL_WRITE)
    def sibling() -> None:
        return None

    node = next(item for item in walk_live_command_tree(probe) if item.path == ("modelo-policy-negative", "missing"))
    assert node.execution_policy is None


def test_modelo_risk_authority_and_route_judgments_live_on_callbacks() -> None:
    by_path = {node.path: node for node in _modelo_nodes()}
    expected: dict[CommandExecutionPolicy, set[tuple[str, ...]]] = {
        METADATA: {
            (),
            ("audit",),
            ("bindings",),
            ("filing-record",),
            ("iva-wallet",),
            ("m036",),
            ("m145",),
            ("reconcile",),
            ("review-package",),
            ("verification-report",),
            ("work",),
        },
        REGISTRY_READ: {
            ("casilla",),
            ("casillas",),
            ("describe",),
            ("formulas",),
            ("list",),
            ("support-matrix",),
        },
        REGISTRY_MODEL_READ: {
            ("bindings", "list"),
            ("bindings", "resolve"),
            ("requires",),
        },
        CALCULATION_READ: {
            ("compare",),
            ("project",),
            ("readiness",),
            ("work", "compare-taxation"),
            ("work", "dependencies"),
            ("work", "preview-maritime-exemption"),
        },
        CALCULATION_WRITE: {
            ("aggregate",),
            ("review-package", "build"),
            ("work", "amend"),
            ("work", "calculate"),
            ("work", "verify"),
        },
        MODEL_READ: {
            ("audit", "check"),
            ("audit", "show"),
            ("filing-record", "list"),
            ("filing-record", "view"),
            ("history",),
            ("iva-wallet", "balance"),
            ("m036", "list"),
            ("m036", "view"),
            ("m145", "validate"),
            ("reconcile", "history"),
            ("verification-report", "list"),
            ("verification-report", "view"),
            ("work", "history"),
            ("work", "list"),
            ("work", "observations"),
            ("work", "resume"),
            ("work", "review"),
            ("work", "revision"),
            ("work", "revisions"),
            ("work", "runs"),
            ("work", "status"),
        },
        MODEL_WRITE: {
            ("filing-record", "import"),
            ("filing-record", "observe-local"),
            ("iva-wallet", "correct"),
            ("iva-wallet", "override"),
            ("iva-wallet", "seed"),
            ("m036", "alta"),
            ("m036", "baja"),
            ("m036", "modificacion"),
            ("m145", "create"),
            ("m145", "mark-delivered-to-payer"),
            ("m145", "mark-locally-completed"),
            ("work", "rename"),
        },
        REGISTRY_MODEL_WRITE: {("work", "create")},
        MODEL_DESTRUCTIVE: {("work", "discard")},
        MODEL_HANDOFF: {
            ("audit", "export"),
            ("export",),
            ("m145", "export"),
            ("reconcile", "file"),
            ("work", "file"),
        },
        BROWSER_MODEL_WRITE: {("reconcile", "pull")},
        CRYPTO_READ: {
            ("review-package", "verify"),
            ("review-package", "verify-receipt"),
            ("review-package", "verify-signature"),
        },
        CRYPTO_FACT_FILE_WRITE: {
            ("review-package", "encrypt-feedback"),
            ("review-package", "encrypt-for-recipient"),
        },
        CRYPTO_PROFILE_WRITE: {
            ("review-package", "counter-sign"),
            ("review-package", "decrypt"),
            ("review-package", "import-feedback"),
            ("review-package", "sign"),
        },
        INTERACTIVE_MODEL_WRITE: {("work", "amend-wizard"), ("work", "wizard")},
    }

    actual: dict[CommandExecutionPolicy, set[tuple[str, ...]]] = {}
    for path, node in by_path.items():
        assert node.execution_policy is not None
        actual.setdefault(node.execution_policy, set()).add(path[3:])

    assert actual == expected

    registry_profile_read = by_path[("aeat", "app", "modelo", "bindings", "resolve")].execution_policy
    assert registry_profile_read is not None
    assert {"registry", "encrypted-facts", "profile-custody"} <= (
        registry_profile_read.classification.expanded_capabilities
    )
    assert registry_profile_read.classification.side_effects == frozenset({"none"})

    crypto_file = by_path[("aeat", "app", "modelo", "review-package", "encrypt-for-recipient")].execution_policy
    assert crypto_file is not None
    assert {"crypto", "encrypted-facts", "profile-custody"} <= crypto_file.classification.expanded_capabilities
    assert crypto_file.classification.side_effects == frozenset({"local-state"})
    assert crypto_file.write_route == "none"

    crypto_profile_write = by_path[("aeat", "app", "modelo", "review-package", "decrypt")].execution_policy
    assert crypto_profile_write is not None
    assert {"crypto", "encrypted-facts", "profile-custody"} <= (
        crypto_profile_write.classification.expanded_capabilities
    )
    assert crypto_profile_write.classification.side_effects == frozenset({"local-state"})
    assert crypto_profile_write.write_route == "profile-bound"


def test_network_maximum_gate_bites_for_an_external_downgraded_callback() -> None:
    probe = typer.Typer(name="modelo-network-downgrade", cls=CadrumoTyperGroup)

    @probe.command("downgraded")
    @command_execution_policy(MODEL_WRITE)
    def downgraded() -> None:
        return None

    @probe.command("sibling")
    @command_execution_policy(MODEL_WRITE)
    def sibling() -> None:
        return None

    node = next(
        item for item in walk_live_command_tree(probe) if item.path == ("modelo-network-downgrade", "downgraded")
    )
    with pytest.raises(AssertionError):
        _assert_network_profile_write(node.execution_policy)


def test_crypto_gate_bites_for_an_external_custody_downgrade() -> None:
    probe = typer.Typer(name="modelo-crypto-downgrade", cls=CadrumoTyperGroup)

    @probe.command("downgraded")
    @command_execution_policy(MODEL_READ)
    def downgraded() -> None:
        return None

    @probe.command("sibling")
    @command_execution_policy(MODEL_READ)
    def sibling() -> None:
        return None

    node = next(
        item for item in walk_live_command_tree(probe) if item.path == ("modelo-crypto-downgrade", "downgraded")
    )
    policy = node.execution_policy
    with pytest.raises(AssertionError):
        assert policy is not None and "crypto" in policy.classification.expanded_capabilities


def test_registry_and_crypto_storage_gates_bite_for_external_downgrades() -> None:
    registry_probe = typer.Typer(name="modelo-registry-downgrade", cls=CadrumoTyperGroup)

    @registry_probe.command("downgraded")
    @command_execution_policy(MODEL_READ)
    def registry_downgraded() -> None:
        return None

    @registry_probe.command("sibling")
    @command_execution_policy(MODEL_READ)
    def registry_sibling() -> None:
        return None

    registry_node = next(
        item
        for item in walk_live_command_tree(registry_probe)
        if item.path == ("modelo-registry-downgrade", "downgraded")
    )
    with pytest.raises(AssertionError):
        assert registry_node.execution_policy is not None and "registry" in (
            registry_node.execution_policy.classification.expanded_capabilities
        )

    crypto_probe = typer.Typer(name="modelo-crypto-storage-downgrade", cls=CadrumoTyperGroup)

    @crypto_probe.command("downgraded")
    @command_execution_policy(CRYPTO_READ)
    def crypto_downgraded() -> None:
        return None

    @crypto_probe.command("sibling")
    @command_execution_policy(CRYPTO_READ)
    def crypto_sibling() -> None:
        return None

    crypto_node = next(
        item
        for item in walk_live_command_tree(crypto_probe)
        if item.path == ("modelo-crypto-storage-downgrade", "downgraded")
    )
    policy = crypto_node.execution_policy
    with pytest.raises(AssertionError):
        assert (
            policy is not None
            and {
                "encrypted-facts",
                "profile-custody",
            }
            <= policy.classification.expanded_capabilities
            and policy.write_route == "profile-bound"
        )


def test_modelo_group_callbacks_preserve_help_and_bare_invocation() -> None:
    runner = CliRunner()

    for args in (
        ("app", "modelo", "--help"),
        ("app", "modelo", "audit", "--help"),
        ("app", "modelo", "review-package", "--help"),
        ("app", "modelo", "work", "--help"),
    ):
        result = runner.invoke(app, list(args))
        assert result.exit_code == 0, result.output
        assert "Usage:" in result.output

    for args in (
        ("app", "modelo"),
        ("app", "modelo", "audit"),
        ("app", "modelo", "bindings"),
        ("app", "modelo", "work"),
    ):
        result = runner.invoke(app, list(args))
        assert result.exit_code == 2, result.output
        assert "Usage:" in result.output


def test_modelo_group_help_survives_a_real_process() -> None:
    env = {key: value for key, value in os.environ.items() if not key.startswith("AEAT_")}
    env.update({"CADRUMO_OUTPUT_LANGUAGE": "en", "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
    code = (
        'import sys; sys.argv=["aeat","app","modelo","review-package","--help"]; '
        "from cadrumo.entrypoints.cli import main; main()"
    )

    completed = subprocess.run(  # noqa: S603 - fixed interpreter and in-tree command arguments.
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=120.0,
    )

    output = f"{completed.stdout}\n{completed.stderr}"
    assert completed.returncode == 0, output
    assert "Usage:" in output
    assert "Traceback" not in output
