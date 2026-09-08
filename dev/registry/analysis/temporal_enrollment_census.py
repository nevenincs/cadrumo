"""Detect literal registry-revision enrolment collections in test modules.

A filename census cannot see a yearless module that embeds its temporal
subjects in a tuple such as ``_GENERATED_TREES``.  This module inspects the
module-level syntax instead.  It recognises only literal row collections whose
first two fields are a modelo and a revision-like token; imported or computed
collections are deliberately not counted again.

Every detected collection is checked against the law-selectable revision
universe derived from the validated registry.  A missing subject is admissible
only through a declaration pinned to an exact source digest.  Reissuing that
source makes the declaration dormant and exposes the missing subject again.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.ids import ModeloId, RevisionId, SourceRefId

from ..._paths import REPO_ROOT
from ..temporal_coverage import compose_temporal_coverage

__all__ = [
    "ENROLLMENT_EXCLUSION_PINS",
    "LiteralEnrollmentAudit",
    "LiteralEnrollmentDeclaration",
    "LiteralEnrollmentFinding",
    "RegistryRevisionSubject",
    "TemporalEnrollmentExclusionPin",
    "audit_registry_test_enrollment_literals",
    "audit_temporal_enrollment_source",
    "law_selectable_revision_subjects",
]

REGISTRY_TEST_ROOT: Final[Path] = REPO_ROOT / "dev" / "registry" / "tests"
_MODELO_ID_ADAPTER: Final[TypeAdapter[ModeloId]] = TypeAdapter(ModeloId)
_REVISION_ID_ADAPTER: Final[TypeAdapter[RevisionId]] = TypeAdapter(RevisionId)


@dataclass(frozen=True, order=True, slots=True)
class RegistryRevisionSubject:
    """One exact registry revision identity."""

    modelo: ModeloId
    revision: RevisionId


class TemporalEnrollmentExclusionPin(BaseModel):
    """Evidence for excluding one revision from one literal enrolment."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    path: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    modelo: ModeloId
    revision: RevisionId
    source_ref: SourceRefId
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason: str = Field(min_length=1)
    reconsideration_condition: str = Field(min_length=1)

    @property
    def subject(self) -> RegistryRevisionSubject:
        """Return the exact revision identity this declaration excludes."""
        return RegistryRevisionSubject(self.modelo, self.revision)


# No live exclusion is needed.  This tuple is the single declaration home if a
# future law-selectable revision cannot participate in a bounded enrolment.
ENROLLMENT_EXCLUSION_PINS: Final[tuple[TemporalEnrollmentExclusionPin, ...]] = ()


@dataclass(frozen=True, slots=True)
class LiteralEnrollmentDeclaration:
    """One module-level literal collection and the subjects it names."""

    path: str
    symbol: str
    subjects: tuple[RegistryRevisionSubject, ...]


@dataclass(frozen=True, slots=True)
class LiteralEnrollmentFinding:
    """Exact drift found between one literal collection and its denominator."""

    path: str
    symbol: str
    missing: tuple[RegistryRevisionSubject, ...]
    extra: tuple[RegistryRevisionSubject, ...]
    duplicates: tuple[RegistryRevisionSubject, ...]
    duplicate_pins: tuple[RegistryRevisionSubject, ...]
    dormant_pins: tuple[RegistryRevisionSubject, ...]
    unnecessary_pins: tuple[RegistryRevisionSubject, ...]

    @property
    def detail(self) -> str:
        """Render every drift category with its exact revision identities."""
        parts = (
            ("missing", self.missing),
            ("extra", self.extra),
            ("duplicates", self.duplicates),
            ("duplicate_pins", self.duplicate_pins),
            ("dormant_pins", self.dormant_pins),
            ("unnecessary_pins", self.unnecessary_pins),
        )
        rendered = [f"{name}={_render_subjects(subjects)}" for name, subjects in parts if subjects]
        return f"{self.path}:{self.symbol}: " + "; ".join(rendered)


@dataclass(frozen=True, slots=True)
class LiteralEnrollmentAudit:
    """All detected declarations and every non-conforming one."""

    declarations: tuple[LiteralEnrollmentDeclaration, ...]
    findings: tuple[LiteralEnrollmentFinding, ...]

    @property
    def clean(self) -> bool:
        """Return whether every detected declaration accounts for its universe."""
        return not self.findings


def law_selectable_revision_subjects(
    authority: ValidatedRegistryAuthority,
) -> frozenset[RegistryRevisionSubject]:
    """Derive the complete law-selectable registered-revision denominator."""
    report = compose_temporal_coverage(authority=authority)
    return frozenset(RegistryRevisionSubject(summary.modelo, summary.revision) for summary in report.revision_summaries)


def audit_registry_test_enrollment_literals(
    authority: ValidatedRegistryAuthority,
    *,
    root: Path = REGISTRY_TEST_ROOT,
    pins: tuple[TemporalEnrollmentExclusionPin, ...] = ENROLLMENT_EXCLUSION_PINS,
) -> LiteralEnrollmentAudit:
    """Audit every literal temporal enrolment declared under registry tests."""
    expected = law_selectable_revision_subjects(authority)
    declarations: list[LiteralEnrollmentDeclaration] = []
    findings: list[LiteralEnrollmentFinding] = []
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(REPO_ROOT).as_posix() if path.is_relative_to(REPO_ROOT) else path.as_posix()
        audit = audit_temporal_enrollment_source(
            path.read_text(encoding="utf-8"),
            path=relative,
            expected=expected,
            authority=authority,
            pins=pins,
        )
        declarations.extend(audit.declarations)
        findings.extend(audit.findings)
    declaration_keys = {(declaration.path, declaration.symbol) for declaration in declarations}
    for pin in pins:
        if (pin.path, pin.symbol) not in declaration_keys:
            findings.append(
                LiteralEnrollmentFinding(
                    path=pin.path,
                    symbol=pin.symbol,
                    missing=(),
                    extra=(),
                    duplicates=(),
                    duplicate_pins=(),
                    dormant_pins=(),
                    unnecessary_pins=(pin.subject,),
                )
            )
    return LiteralEnrollmentAudit(tuple(declarations), tuple(findings))


def audit_temporal_enrollment_source(
    source: str,
    *,
    path: str,
    expected: frozenset[RegistryRevisionSubject],
    authority: ValidatedRegistryAuthority,
    pins: tuple[TemporalEnrollmentExclusionPin, ...] = (),
) -> LiteralEnrollmentAudit:
    """Audit module-level literal revision collections in one Python source."""
    declarations = _literal_enrollment_declarations(source, path=path)
    findings = tuple(
        finding
        for declaration in declarations
        if (
            finding := _declaration_finding(
                declaration,
                expected=expected,
                authority=authority,
                pins=pins,
            )
        )
        is not None
    )
    return LiteralEnrollmentAudit(declarations, findings)


def _literal_enrollment_declarations(source: str, *, path: str) -> tuple[LiteralEnrollmentDeclaration, ...]:
    tree = ast.parse(source, filename=path)
    declarations: list[LiteralEnrollmentDeclaration] = []
    for statement in tree.body:
        assignment = _module_assignment(statement)
        if assignment is None:
            continue
        symbol, value = assignment
        subjects = tuple(subject for row in _literal_rows(value) if (subject := _row_subject(row)) is not None)
        if subjects:
            declarations.append(LiteralEnrollmentDeclaration(path, symbol, subjects))
    return tuple(declarations)


def _module_assignment(statement: ast.stmt) -> tuple[str, ast.expr] | None:
    if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
        target = statement.targets[0]
        if isinstance(target, ast.Name):
            return target.id, statement.value
    if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name) and statement.value is not None:
        return statement.target.id, statement.value
    return None


def _literal_rows(value: ast.expr) -> tuple[ast.expr, ...]:
    if isinstance(value, ast.Tuple | ast.List | ast.Set):
        return tuple(value.elts)
    if isinstance(value, ast.Dict):
        return tuple(key for key in value.keys if key is not None)
    return ()


def _row_subject(row: ast.expr) -> RegistryRevisionSubject | None:
    fields: list[ast.expr]
    if isinstance(row, ast.Tuple | ast.List):
        fields = row.elts
    elif isinstance(row, ast.Call):
        fields = row.args
    else:
        return None
    if len(fields) < 2:
        return None
    modelo = _string_literal(fields[0])
    revision = _string_literal(fields[1])
    if modelo is None or revision is None or not revision[:1].isdigit():
        return None
    try:
        return RegistryRevisionSubject(
            _MODELO_ID_ADAPTER.validate_python(modelo),
            _REVISION_ID_ADAPTER.validate_python(revision),
        )
    except ValidationError:
        return None


def _string_literal(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _declaration_finding(
    declaration: LiteralEnrollmentDeclaration,
    *,
    expected: frozenset[RegistryRevisionSubject],
    authority: ValidatedRegistryAuthority,
    pins: tuple[TemporalEnrollmentExclusionPin, ...],
) -> LiteralEnrollmentFinding | None:
    declared = set(declaration.subjects)
    duplicates = tuple(sorted(subject for subject in declared if declaration.subjects.count(subject) > 1))
    matching_pins = tuple(pin for pin in pins if pin.path == declaration.path and pin.symbol == declaration.symbol)
    pinned_subjects = tuple(pin.subject for pin in matching_pins)
    duplicate_pins = tuple(sorted(subject for subject in set(pinned_subjects) if pinned_subjects.count(subject) > 1))
    active_pins = frozenset(pin.subject for pin in matching_pins if _pin_is_current(pin, authority=authority))
    dormant_pins = tuple(sorted(pin.subject for pin in matching_pins if pin.subject not in active_pins))
    unnecessary_pins = tuple(sorted(active_pins - (expected - declared)))
    missing = tuple(sorted(expected - declared - active_pins))
    extra = tuple(sorted(declared - expected))
    if not (missing or extra or duplicates or duplicate_pins or dormant_pins or unnecessary_pins):
        return None
    return LiteralEnrollmentFinding(
        path=declaration.path,
        symbol=declaration.symbol,
        missing=missing,
        extra=extra,
        duplicates=duplicates,
        duplicate_pins=duplicate_pins,
        dormant_pins=dormant_pins,
        unnecessary_pins=unnecessary_pins,
    )


def _pin_is_current(
    pin: TemporalEnrollmentExclusionPin,
    *,
    authority: ValidatedRegistryAuthority,
) -> bool:
    try:
        revision = authority.modelo(pin.modelo).revisions[pin.revision]
    except (KeyError, LookupError):
        return False
    source = authority.catalogues.sources.get(pin.source_ref)
    return pin.source_ref in revision.source_refs and source is not None and source.sha256 == pin.source_sha256


def _render_subjects(subjects: tuple[RegistryRevisionSubject, ...]) -> str:
    return ",".join(f"{subject.modelo}/{subject.revision}" for subject in subjects)
