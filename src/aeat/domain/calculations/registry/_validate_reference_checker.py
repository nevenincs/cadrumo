"""Reference-checker accumulator for snapshot validation.

``IdReferenceChecker`` collects all typed-ID sets from a
:class:`RegistrySnapshot` and accumulates dangling-reference diagnostics
used by the per-section reference walkers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._ids import CasillaId

if TYPE_CHECKING:
    from ._snapshot import RegistrySnapshot


class IdReferenceChecker:
    """Accumulates dangling typed-ID reference diagnostics for one snapshot.

    Holds the per-kind ID sets and a failures buffer so per-kind
    reference walkers can stay focused on their own field paths instead
    of juggling closure state.
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
        "formula_ids",
        "legal_ids",
        "parameter_ids",
        "prefix",
        "relation_ids",
        "source_ids",
        "support_removal_decision_ids",
        "verification_expectation_ids",
        "workbook_parity_ids",
    )

    def __init__(self, snapshot: RegistrySnapshot) -> None:
        revision = snapshot.revision
        self.prefix = f"snapshot modelo {snapshot.modelo.id} revision {revision.id}"
        self.failures: list[str] = []
        self.casilla_ids: set[CasillaId] = {c.id for c in revision.casillas}
        self.casilla_data_types: dict[CasillaId, str] = {c.id: c.data_type for c in revision.casillas}
        self.formula_ids = {f.id for f in revision.formulas}
        self.parameter_ids = {p.id for p in revision.parameters}
        self.binding_ids = {b.id for b in revision.bindings}
        self.relation_ids = {r.id for r in revision.relations}
        self.export_layout_ids = {lay.id for lay in revision.export_layouts}
        self.export_field_ids = {
            field.id for lay in revision.export_layouts for rec in lay.records for field in rec.fields
        }
        self.extraction_profile_ids = {p.id for p in revision.extraction_profiles}
        self.cross_reference_ids = {cr.id for cr in revision.live_cross_references}
        self.workbook_parity_ids = {w.id for w in revision.workbook_parity_refs}
        self.verification_expectation_ids = {e.id for e in revision.verification_expectations}
        self.application_link_ids = {lk.id for lk in revision.application_links}
        self.deadline_window_ids = {dw.id for dw in revision.deadline_windows}
        self.support_removal_decision_ids = {d.id for d in revision.support_removal_decisions}
        self.construct_ids = {c.id for c in revision.constructs}
        self.dependency_classification_ids = {dc.id for dc in revision.dependency_classifications}
        self.legal_ids = set(snapshot.legal)
        self.source_ids = set(snapshot.sources)

    def chk(self, field_path: str, value: str, id_set: set[str]) -> None:
        if value not in id_set:
            self.failures.append(f"{self.prefix}: {field_path} references unknown id {value!r}")

    def chk_opt(self, field_path: str, value: str | None, id_set: set[str]) -> None:
        if value is not None and value not in id_set:
            self.failures.append(f"{self.prefix}: {field_path} references unknown id {value!r}")

    def chk_tuple(self, field_path: str, values: tuple[str, ...], id_set: set[str]) -> None:
        for value in values:
            if value not in id_set:
                self.failures.append(f"{self.prefix}: {field_path} references unknown id {value!r}")

    def chk_legal_source_refs(self, owner: str, legal_refs: tuple[str, ...], source_refs: tuple[str, ...]) -> None:
        """Single-call helper for the (legal_refs, source_refs) pair every record carries."""
        self.chk_tuple(f"{owner}.legal_refs", legal_refs, self.legal_ids)
        self.chk_tuple(f"{owner}.source_refs", source_refs, self.source_ids)
