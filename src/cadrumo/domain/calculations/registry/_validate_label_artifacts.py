"""Advisory label-artifact diagnostics for registry casillas.

Scans casilla labels across every :class:`ModeloDefinition` to surface
unresolved format-string placeholders left by the extraction pipeline.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from ....core import CasillaId
from ....core.i18n import MissingTranslationError
from .ids import RevisionId
from .schema import ModeloDefinition

_UNRESOLVED_FORMAT_PLACEHOLDER = re.compile(r"\{[A-Za-z0-9_]+\}")

__all__ = (
    "LabelArtifactFinding",
    "collect_label_artifact_findings",
    "validate_no_label_artifacts",
)


@dataclass(frozen=True, slots=True)
class LabelArtifactFinding:
    """One suspicious extraction artifact in a casilla label."""

    modelo_id: str
    revision_id: RevisionId
    casilla_id: CasillaId
    artifact: str
    placeholder_token: str
    label: str


def collect_label_artifact_findings(modelos: Iterable[ModeloDefinition]) -> tuple[LabelArtifactFinding, ...]:
    """Return :class:`LabelArtifactFinding` items for obvious unresolved label extraction artifacts.

    Args:
        modelos: Iterable of :class:`ModeloDefinition` instances whose casilla labels are inspected.
    """
    findings: list[LabelArtifactFinding] = []
    for modelo in modelos:
        for revision in modelo.revisions.values():
            for casilla in revision.casillas:
                try:
                    label = casilla.label
                except MissingTranslationError:
                    # A custom registry root may be validated before its
                    # shared catalogue is available. Missing-key completeness
                    # is reported by catalogue coverage; there is no label
                    # text here from which to derive an artifact finding.
                    continue
                for match in _UNRESOLVED_FORMAT_PLACEHOLDER.finditer(label):
                    findings.append(
                        LabelArtifactFinding(
                            modelo_id=modelo.id,
                            revision_id=revision.id,
                            casilla_id=casilla.id,
                            artifact="unresolved_format_placeholder",
                            placeholder_token=match.group(0),
                            label=label,
                        ),
                    )
    return tuple(findings)


def validate_no_label_artifacts(modelos: Iterable[ModeloDefinition]) -> tuple[str, ...]:
    """Return failures for unresolved casilla label formatting placeholders.

    Args:
        modelos: Iterable of :class:`ModeloDefinition` entries to scan.
    """
    return tuple(
        f"modelo {finding.modelo_id} revision {finding.revision_id} casilla {finding.casilla_id}: "
        f"label contains unresolved {finding.artifact} {finding.placeholder_token!r}: {finding.label!r}"
        for finding in collect_label_artifact_findings(modelos)
    )
