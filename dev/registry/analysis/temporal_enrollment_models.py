"""Canonical records and validated registry-subject identifiers for temporal enrollment audits."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from cadrumo.domain.calculations.registry.ids import ModeloId, RevisionId, SourceRefId
from dev._paths import REPO_ROOT

__all__ = [
    "LiteralEnrollmentAudit",
    "LiteralEnrollmentDeclaration",
    "LiteralEnrollmentFinding",
    "RegistryRevisionSubject",
    "TemporalEnrollmentExclusionPin",
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
    #: Identities the collection names that the registry does not declare at
    #: all, which is how a renamed or retired revision keeps a test green while
    #: the row it pins has stopped existing.
    absent: tuple[RegistryRevisionSubject, ...] = ()

    @property
    def detail(self) -> str:
        """Render every drift category with its exact revision identities."""
        parts = (
            ("missing", self.missing),
            ("extra", self.extra),
            ("absent", self.absent),
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


def _render_subjects(subjects: tuple[RegistryRevisionSubject, ...]) -> str:
    return ",".join(f"{subject.modelo}/{subject.revision}" for subject in subjects)
