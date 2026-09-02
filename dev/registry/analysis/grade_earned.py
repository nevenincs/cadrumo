"""Screen: a revision's declared ``authority_grade`` against the prerequisites its own tree derives.

The grade is asserted once, in the manifest. What would EARN it is derived
elsewhere, from fragment presence, by
:func:`~cadrumo.domain.calculations.registry.support_matrix.revision_capability_probe`:
a calculation closure, a completeness manifest, a fixed-width or XML export
layout. Nothing ties the assertion to the derivation, so a revision can
declare ``filing`` with no layout to file through, or declare
``applicability`` while carrying a full export layout and completeness
manifest that the grade then hides from every consumer that trusts it.

This screen reads the DERIVED probe, not the raw fragment directories, so it
cannot disagree with the support matrix about what a revision carries. Two
finding kinds:

``under_supported``
    The declared grade needs a prerequisite the probe does not find. Filing
    needs an export layout (fixed-width or XML dictionary) and a completeness
    manifest; calculation needs a completeness manifest.

``under_declared``
    The probe finds prerequisites the declared grade does not claim: an
    applicability-grade revision carrying an export layout or a completeness
    manifest, or a calculation-grade revision carrying an export layout.

A finding is not a verdict. A revision may carry a reasoned family
disposition or be mid-authoring; the screen reports and exits 0.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Literal

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.support_matrix import revision_capability_probe

__all__ = ["GradeFinding", "grade_findings", "screen_authority"]

type GradeFindingKind = Literal["under_supported", "under_declared"]


@dataclass(frozen=True, slots=True)
class GradeFinding:
    """One revision whose declared grade and derived prerequisites disagree."""

    modelo: str
    revision: str
    declared_grade: str
    kind: GradeFindingKind
    prerequisite: str


def grade_findings(revision: ModeloRevision, *, modelo_id: str) -> tuple[GradeFinding, ...]:
    """Compare the declared grade of ``revision`` with its derived capability probe."""
    grade = revision.effective_authority_grade
    probe = revision_capability_probe(revision, modelo_id=modelo_id)
    has_layout = probe.has_fixed_width_export or probe.has_xml_dictionary_export
    findings: list[GradeFinding] = []

    def finding(kind: GradeFindingKind, prerequisite: str) -> GradeFinding:
        return GradeFinding(
            modelo=modelo_id,
            revision=str(revision.id),
            declared_grade=grade.value,
            kind=kind,
            prerequisite=prerequisite,
        )

    if grade is RegistryAuthorityGrade.FILING:
        if not has_layout:
            findings.append(finding("under_supported", "export_layout"))
        if not probe.has_completeness_manifest:
            findings.append(finding("under_supported", "completeness_manifest"))
    elif grade is RegistryAuthorityGrade.CALCULATION:
        if not probe.has_completeness_manifest:
            findings.append(finding("under_supported", "completeness_manifest"))
        if has_layout:
            findings.append(finding("under_declared", "export_layout"))
    else:
        if has_layout:
            findings.append(finding("under_declared", "export_layout"))
        if probe.has_completeness_manifest:
            findings.append(finding("under_declared", "completeness_manifest"))
    return tuple(findings)


def screen_authority(authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]) -> tuple[GradeFinding, ...]:
    """Screen every revision of the named modelos through the validated authority."""
    findings: list[GradeFinding] = []
    for modelo_id in modelo_ids:
        for revision in authority.modelo(modelo_id).revisions.values():
            findings.extend(grade_findings(revision, modelo_id=modelo_id))
    return tuple(findings)


def _bundled_modelo_ids() -> tuple[str, ...]:
    from cadrumo.application.modelo.registry_discovery import registry_modelo_codes

    return tuple(sorted(str(code) for code in registry_modelo_codes()))


def main() -> int:
    """Print one greppable row per finding and a summary; always exit 0."""
    findings = screen_authority(bundled_authority(), _bundled_modelo_ids())
    for f in findings:
        sys.stdout.write(
            f"grade_{f.kind} modelo={f.modelo} revision={f.revision} declared={f.declared_grade} "
            f"prerequisite={f.prerequisite}\n",
        )
    under_supported = sum(1 for f in findings if f.kind == "under_supported")
    sys.stdout.write(
        f"summary surface=derived_probe findings={len(findings)} under_supported={under_supported} "
        f"under_declared={len(findings) - under_supported}\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
