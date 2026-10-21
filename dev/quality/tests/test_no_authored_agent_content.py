"""Cadrumo carries no authored agent content, and its MCP service serves none.

cadrumo-agent owns every persona, operating rule and workflow skill, their
metadata and their delivery. Cadrumo keeps the deterministic MCP service: the
protocol contract, the operation projection, the authority and corpus queries
and the runtime admission around them. Two kinds of regression would move that
boundary back without anyone noticing.

The first is authored prose returning to the shipped tree: a reviewed
``_data/agent`` subtree, a ``SKILL.md`` document, or a directory of persona,
rule or skill markdown under a shipped package. The second is a serving
channel for it: the retired ``harness_load`` tool, or the ``cadrumo://skill``
and ``cadrumo://rule`` resource families the server no longer advertises.

Both gates walk the filesystem under the shipped source roots. Neither asks
Git what it tracks: an untracked file in a working tree is as shipped as a
committed one once a wheel is built from it, and this repository's tooling
reads the filesystem and its inclusion policy rather than a checkout's
history.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pytest

from dev._paths import REPO_ROOT, UTF_8
from dev.first_party_source import MCP_PACKAGE, PRODUCT_SOURCE_ROOTS, SERVICE_PACKAGE

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SHIPPED_ROOTS: Final[tuple[Path, ...]] = tuple(
    REPO_ROOT / root for root in (*PRODUCT_SOURCE_ROOTS, MCP_PACKAGE, SERVICE_PACKAGE)
)
"""Every package a Cadrumo wheel ships, each read from the filesystem as it stands."""

_SKILL_DOCUMENT: Final = "SKILL.md"
"""The file name a workflow skill is authored under; cadrumo-agent owns every one."""

_AUTHORED_DIRECTORIES: Final = frozenset({"agent", "personas", "rules", "skills"})
"""Directory names that hold authored agent prose wherever cadrumo-agent keeps it."""

_SERVING_TOKENS: Final = ("harness_load", "cadrumo://skill", "cadrumo://rule")
"""The retired floor tool and the two resource families that served skills and rules."""

_PRUNED_DIRECTORIES: Final = frozenset({"__pycache__"})

_PYTHON_SUFFIX: Final = ".py"


@dataclass(frozen=True, slots=True)
class AgentContentFinding:
    """One shipped path that carries authored agent content, or serves it."""

    path: str
    """The path relative to the scanned root, in POSIX form."""
    reason: str


def _walk(root: Path) -> Iterator[tuple[Path, list[str], list[str]]]:
    """Yield every directory below ``root``, skipping compiled-bytecode caches."""
    for parent, directories, files in os.walk(root):
        directories[:] = sorted(name for name in directories if name not in _PRUNED_DIRECTORIES)
        yield Path(parent), directories, sorted(files)


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def authored_agent_content_findings(root: Path) -> tuple[AgentContentFinding, ...]:
    """Report every authored-agent-content path below ``root``.

    A directory named for personas, operating rules, workflow skills or the
    harness's own ``agent`` subtree is a finding on its own, so the documents
    inside it are not listed again. A ``SKILL.md`` anywhere is a finding
    wherever it sits.
    """
    findings: list[AgentContentFinding] = []
    for parent, directories, files in _walk(root):
        for name in directories:
            if name in _AUTHORED_DIRECTORIES:
                findings.append(
                    AgentContentFinding(
                        path=_relative(parent / name, root),
                        reason=f"authored agent content directory {name!r}; cadrumo-agent owns it",
                    )
                )
        for name in files:
            if name == _SKILL_DOCUMENT:
                findings.append(
                    AgentContentFinding(
                        path=_relative(parent / name, root),
                        reason="authored workflow skill document; cadrumo-agent owns it",
                    )
                )
    return tuple(findings)


def skill_serving_findings(root: Path) -> tuple[AgentContentFinding, ...]:
    """Report every Python module below ``root`` that names a retired skill or rule channel."""
    findings: list[AgentContentFinding] = []
    for parent, _directories, files in _walk(root):
        for name in files:
            if not name.endswith(_PYTHON_SUFFIX):
                continue
            path = parent / name
            source = path.read_text(encoding=UTF_8)
            for token in _SERVING_TOKENS:
                if token in source:
                    findings.append(
                        AgentContentFinding(
                            path=_relative(path, root),
                            reason=f"serves authored agent content through {token!r}",
                        )
                    )
    return tuple(findings)


def _modules_read(root: Path) -> int:
    return sum(1 for _parent, _directories, files in _walk(root) for name in files if name.endswith(_PYTHON_SUFFIX))


def _reported(findings: tuple[AgentContentFinding, ...]) -> str:
    return "\n".join(f"{finding.path}: {finding.reason}" for finding in findings)


@pytest.mark.parametrize("root", _SHIPPED_ROOTS, ids=lambda root: root.name)
def test_no_shipped_package_carries_authored_agent_content(root: Path) -> None:
    assert root.is_dir(), f"{root} is a shipped package the gate must read"
    findings = authored_agent_content_findings(root)

    assert not findings, f"authored agent content under {root.name}:\n{_reported(findings)}"


@pytest.mark.parametrize("root", _SHIPPED_ROOTS, ids=lambda root: root.name)
def test_no_shipped_module_serves_a_skill_or_a_rule(root: Path) -> None:
    # The scan reads real modules, so a renamed or emptied package cannot pass by holding none.
    assert _modules_read(root) > 0, f"{root} holds the modules the gate reads"
    findings = skill_serving_findings(root)

    assert not findings, f"skill or rule serving under {root.name}:\n{_reported(findings)}"


def test_the_content_gate_reports_an_authored_tree_planted_in_a_fixture(tmp_path: Path) -> None:
    package = tmp_path / "cadrumo_mcp"
    skill = package / "_data" / "agent" / "skills" / "cadrumo-preparar-modelo-130"
    skill.mkdir(parents=True)
    (skill / _SKILL_DOCUMENT).write_text("---\nname: synthetic\n---\n\nPrepare it.\n", encoding=UTF_8)
    rules = package / "_data" / "agent" / "rules"
    rules.mkdir()
    (rules / "cadrumo-operator-grounding.md").write_text("# Ground every figure\n", encoding=UTF_8)
    ordinary = package / "mcp"
    ordinary.mkdir()
    (ordinary / "protocol_contract.py").write_text('TOOLS = ("status",)\n', encoding=UTF_8)

    findings = authored_agent_content_findings(package)

    assert {finding.path for finding in findings} == {
        "_data/agent",
        "_data/agent/rules",
        "_data/agent/skills",
        "_data/agent/skills/cadrumo-preparar-modelo-130/SKILL.md",
    }
    # The ordinary module beside them is not a finding, so the gate is not simply always red.
    assert authored_agent_content_findings(ordinary) == ()


@pytest.mark.parametrize(
    ("served", "token"),
    [
        ('def harness_load(args):\n    return {"outcome": "loaded"}\n', "harness_load"),
        ('_SKILL_URI_PREFIX = "cadrumo://skill/"\n', "cadrumo://skill"),
        ('_RULE_URI_PREFIX = "cadrumo://rule/"\n', "cadrumo://rule"),
    ],
)
def test_the_serving_gate_reports_a_channel_planted_in_a_fixture(tmp_path: Path, served: str, token: str) -> None:
    package = tmp_path / "cadrumo_mcp" / "mcp"
    package.mkdir(parents=True)
    (package / "operating_layer.py").write_text(served, encoding=UTF_8)
    (package / "server.py").write_text("def build_server(adapter):\n    return adapter\n", encoding=UTF_8)
    (package / "notes.md").write_text(f"The retired channel was {token}.\n", encoding=UTF_8)

    findings = skill_serving_findings(package)

    assert [(finding.path, finding.reason) for finding in findings] == [
        ("operating_layer.py", f"serves authored agent content through {token!r}")
    ]
