"""Advisory label-artifact diagnostics for registry casillas."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from ._schema import ModeloDefinition

_UNRESOLVED_FORMAT_PLACEHOLDER = re.compile(r"\{[A-Za-z0-9_]+\}")


@dataclass(frozen=True, slots=True)
class LabelArtifactFinding:
    """One suspicious extraction artifact in a casilla label."""

    modelo_id: str
    revision_id: str
    casilla_id: str
    artifact: str
    placeholder_token: str
    label: str


def collect_label_artifact_findings(modelos: Iterable[ModeloDefinition]) -> tuple[LabelArtifactFinding, ...]:
    """Return advisory findings for obvious unresolved label extraction artifacts."""

    findings: list[LabelArtifactFinding] = []
    for modelo in modelos:
        for revision in modelo.revisions.values():
            for casilla in revision.casillas:
                for match in _UNRESOLVED_FORMAT_PLACEHOLDER.finditer(casilla.label):
                    findings.append(
                        LabelArtifactFinding(
                            modelo_id=modelo.id,
                            revision_id=revision.id,
                            casilla_id=casilla.id,
                            artifact="unresolved_format_placeholder",
                            placeholder_token=match.group(0),
                            label=casilla.label,
                        )
                    )
    return tuple(findings)
