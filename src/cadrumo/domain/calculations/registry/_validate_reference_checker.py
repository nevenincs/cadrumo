"""Reference-checker accumulator for snapshot validation.

``IdReferenceChecker`` collects all typed-ID sets from a
:class:`RegistrySnapshot` and accumulates dangling-reference diagnostics
used by the per-section reference walkers.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from ....core.casilla_id import CasillaId
from ._validate_revision_context import _IdentifiedRecord, collect_export_field_ids
from .ids import LegalRefId, SourceRefId
from .schema import ModeloRevision

if TYPE_CHECKING:
    from .schema import RegistrySnapshot


def _record_ids[RecordT: _IdentifiedRecord](records: Iterable[RecordT]) -> set[str]:
    return {record.id for record in records}


def _casilla_data_types(revision: ModeloRevision) -> dict[CasillaId, str]:
    return {casilla.id: casilla.data_type for casilla in revision.casillas}


class IdReferenceChecker:
    """Accumulates dangling typed-ID reference diagnostics for one snapshot.

    Holds the per-kind ID sets and a failures buffer so per-kind
    reference walkers can stay focused on their own field paths instead
    of juggling closure state.

    Deliberately NOT an instance of the ``failures=`` parameter convention
    the rest of the registry's section validators moved away from (see the
    accumulator-convention reconciliation this module was audited under).
    That convention passes a FOREIGN accumulator into an otherwise-
    independent function -- the caller must pre-create the list, the
    signature hides the output, and the function cannot be tested without
    manufacturing one. This class is a COHESIVE COLLABORATOR instead: it
    owns its own state (the id sets AND the failures buffer together),
    is constructed exactly once per referential-integrity sweep, is shared
    by roughly twenty related `_check_*` helpers that all genuinely operate
    over the same index, and is drained in exactly one place
    (`_validate_references._check_all_id_references`). Testing it means
    constructing one, running a check, and reading `.failures` -- which
    already IS isolated testing, not a symptom of leaked mutable state.
    Converting `chk`/`chk_opt`/`chk_tuple`/`chk_legal_source_refs` to return
    their own findings would touch every one of those ~25 call sites for no
    structural gain, on the exact module that raises the referential-
    integrity gate. Leave this class's accumulation as-is; the boundary
    between the two conventions is the point, not an oversight to converge
    away.
    """

    __slots__ = (
        "application_link_ids",
        "binding_ids",
        "casilla_data_types",
        "casilla_ids",
        "construct_ids",
        "cross_reference_ids",
        "deadline_window_ids",
        "dependency_classification_ids",
        "export_field_ids",
        "export_layout_ids",
        "extraction_profile_ids",
        "failures",
        "filing_schedule_ids",
        "formula_ids",
        "legal_evidence_tiers",
        "legal_ids",
        "parameter_ids",
        "prefix",
        "provenance_only_source_ids",
        "relation_ids",
        "source_ids",
        "verification_expectation_ids",
        "workbook_parity_ids",
    )

    def __init__(self, snapshot: RegistrySnapshot) -> None:
        revision = snapshot.revision
        self.prefix = f"snapshot modelo {snapshot.modelo.id} revision {revision.id}"
        self.failures: list[str] = []
        self.casilla_ids = _record_ids(revision.casillas)
        self.casilla_data_types = _casilla_data_types(revision)
        self.formula_ids = _record_ids(revision.formulas)
        self.parameter_ids = _record_ids(revision.parameters)
        self.binding_ids = _record_ids(revision.bindings)
        self.relation_ids = _record_ids(revision.relations)
        self.export_layout_ids = _record_ids(revision.export_layouts)
        self.export_field_ids = collect_export_field_ids(revision)
        self.extraction_profile_ids = _record_ids(revision.extraction_profiles)
        self.cross_reference_ids = _record_ids(revision.live_cross_references)
        self.workbook_parity_ids = _record_ids(revision.workbook_parity_refs)
        self.verification_expectation_ids = _record_ids(revision.verification_expectations)
        self.application_link_ids = _record_ids(revision.application_links)
        self.deadline_window_ids = _record_ids(revision.deadline_windows)
        self.filing_schedule_ids = _record_ids(revision.filing_schedules)
        self.construct_ids = _record_ids(revision.constructs)
        self.dependency_classification_ids = _record_ids(revision.dependency_classifications)
        self.legal_ids = set(snapshot.legal)
        self.legal_evidence_tiers = {ref_id: ref.evidence_tier for ref_id, ref in snapshot.legal.items()}
        self.source_ids = set(snapshot.sources)
        #: Sources the catalogue declares as corpus evidence rather than a
        #: machine-readable authority. An export layout may never write against
        #: one: the design it names is not a layout map, so a layout claiming it
        #: would render against something the parser is required to refuse.
        self.provenance_only_source_ids = {
            source_id
            for source_id, source in snapshot.sources.items()
            if getattr(source, "design_authority", "authoritative") == "provenance_only"
        }

    def chk(self, field_path: str, value: str, id_set: set[str]) -> None:
        if value not in id_set:
            self.failures.append(f"{self.prefix}: {field_path} references unknown id {value!r}")
        elif id_set is self.legal_ids:
            self._chk_legal_authority(field_path, value)

    def chk_opt(self, field_path: str, value: str | None, id_set: set[str]) -> None:
        if value is not None and value not in id_set:
            self.failures.append(f"{self.prefix}: {field_path} references unknown id {value!r}")
        elif value is not None and id_set is self.legal_ids:
            self._chk_legal_authority(field_path, value)

    def chk_tuple(self, field_path: str, values: tuple[str, ...], id_set: set[str]) -> None:
        for value in values:
            if value not in id_set:
                self.failures.append(f"{self.prefix}: {field_path} references unknown id {value!r}")
            elif id_set is self.legal_ids:
                self._chk_legal_authority(field_path, value)

    def chk_legal_source_refs(
        self,
        owner: str,
        legal_refs: tuple[LegalRefId, ...],
        source_refs: tuple[SourceRefId, ...],
    ) -> None:
        """Single-call helper for the (legal_refs, source_refs) pair every record carries."""
        self.chk_tuple(f"{owner}.legal_refs", legal_refs, self.legal_ids)
        self.chk_tuple(f"{owner}.source_refs", source_refs, self.source_ids)

    def _chk_legal_authority(self, field_path: str, value: str) -> None:
        if self.legal_evidence_tiers.get(value) != "legal_authority":
            self.failures.append(f"{self.prefix}: {field_path} legal ref {value!r} is not legal authority")
