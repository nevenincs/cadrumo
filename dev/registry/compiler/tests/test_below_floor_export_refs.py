"""Teeth for the below-floor downgrade of export binding-reference refusals.

The mechanism is proved on an isolated carrier built in ``tmp_path``: a revision
assembled in memory whose export tree quotes bindings the revision does not
declare, a registry root holding only the supported-filing-years declaration the
validator reads, and a disposition ledger holding one ``below_floor`` row for
it. The REAL export validator produces the refusals and the REAL ledger loader
reads the row, so no committed registry file or shipped ledger decides whether
the mechanism is covered, and no production module is patched. The fixture
declares a floor of its own, distinct from the shipped one, so a validator that
read the shipped declaration instead of the registry it was handed would fail.

The shipped ledger is held to the shipped registry separately: a shipped
``below_floor`` row stays only while its revision's newest filing year lies
below the declared floor and its generated tree is present. The row also
explains why that tree has no law-selectable coordinate, so a tree regenerated
clean of dangling references does not retire it. That check is shown to bite on
the carrier before it is applied to the shipped rows.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest
import rtoml

from cadrumo.core.aggregation import BindingAggregation, BindingAggregationOp
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.domain.calculations.registry.fixed_width_codec import ExportEncoding
from cadrumo.domain.calculations.registry.revision_context import build_revision_validation_context
from cadrumo.domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_base import CasillaDataType, EvidenceTier
from cadrumo.domain.calculations.registry.schema_exports import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
)
from cadrumo.domain.calculations.registry.schema_references import (
    LegalReference,
    PeriodSelector,
    SourceReference,
)

from ...conformance.stamp import bundled_registry_root
from ...pipeline.export_fragment_provenance import export_fragment_provenance_path
from ...pipeline.generated_tree_dispositions import (
    GeneratedTreeBelowSupportedFilingYearsDisposition,
    below_floor_dispositions,
    disposition_ledger_from_path,
)
from ..validate_below_floor_export_refs import (
    below_floor_export_reference_advisories,
    declared_supported_filing_years_floor,
    downgrade_below_floor_export_reference_failures,
)
from ..validate_evidence import EvidenceValidator
from ..validate_exports import validate_export_layout_section

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "999"
_REVISION = "2016-2017"
_REVISION_LAST_YEAR = 2017
#: Distinct from the floor the shipped legal tree declares, on purpose.
_FIXTURE_FLOOR = 2019
_DANGLING_MARKER = "references unknown binding"

_LEGAL_REF = "ley-fixture:art-1"
_SOURCE_REF = "aeat-fixture-design-2016"
_SOURCE_SHA256 = "a" * 64
_DECLARED_BINDING = "declared-binding"
_DANGLING_BINDINGS = ("superseded-spelling-a", "superseded-spelling-b")


@dataclass(frozen=True)
class _Carrier:
    """One isolated below-floor carrier: a revision, its catalogues, a registry root and a ledger."""

    revision: ModeloRevision
    legal_refs: Mapping[str, LegalReference]
    source_refs: Mapping[str, SourceReference]
    registry_root: Path
    ledger_path: Path

    def export_failures(self) -> list[str]:
        """Return the real export-section failures for the revision, undowngraded."""
        return _export_failures(
            _MODELO,
            _REVISION,
            self.revision,
            legal_refs=self.legal_refs,
            source_refs=self.source_refs,
            source_root=None,
        )

    def advisories(self, failures: list[str]) -> tuple[list[str], tuple[str, ...]]:
        """Run the downgrade over ``failures`` against this carrier's own ledger and registry."""
        return below_floor_export_reference_advisories(
            failures,
            modelo_id=_MODELO,
            revision_id=_REVISION,
            ledger_path=self.ledger_path,
            registry_root=self.registry_root,
        )


def _legal_reference() -> LegalReference:
    return LegalReference(
        id=_LEGAL_REF,
        evidence_tier=EvidenceTier.LEGAL_AUTHORITY,
        authority="boe",
        kind="ley",
        corpus_ref="boe/fixture#art-1",
        document_id="BOE-A-2006-20764",
        permalink="https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764",
        effective_from=date(2006, 11, 30),
        review_status="operator_reviewed",
        reviewed_at=date(2026, 7, 1),
        reviewed_by="fixture",
        required_text=("art-1",),
    )


def _source_reference() -> SourceReference:
    return SourceReference(
        id=_SOURCE_REF,
        evidence_tier="layout_authority",
        authority="aeat",
        kind="record_design",
        corpus_path="registry/aeat/sources/fixture-design.pdf",
        sha256=_SOURCE_SHA256,
        bytes=1024,
        retrieved_at=date(2024, 1, 1),
        source_url="https://sede.agenciatributaria.gob.es/fixture-design.pdf",
        review_status="pending_review",
    )


def _field(field_id: str, offset: int, **kind: object) -> ExportFieldDefinition:
    """Build one four-position export field of the requested kind, with valid evidence."""
    return ExportFieldDefinition.model_validate(
        {
            "id": field_id,
            "offset": offset,
            "length": 4,
            "data_type": CasillaDataType.TEXT,
            "required": False,
            "padding": "right_space",
            "justification": "left",
            "signed": False,
            "legal_refs": (_LEGAL_REF,),
            "source_refs": (_SOURCE_REF,),
            **kind,
        },
    )


def _binding_field(field_id: str, offset: int, binding: str) -> ExportFieldDefinition:
    return _field(field_id, offset, kind="binding", binding=binding)


def _revision(*extra_fields: ExportFieldDefinition, dangling: Iterable[str] = _DANGLING_BINDINGS) -> ModeloRevision:
    """Build the carrier revision: one resolving binding field, then one dangling field per name.

    ``extra_fields`` are appended after them, so a case can add a failure of a
    different kind and still have every field at its own position.
    """
    declared = BindingDefinition(
        id=_DECLARED_BINDING,
        provider={"kind": "manual_input", "casilla_id": "62", "data_type": "money"},
        value={"data_type": "money", "channel": "decimal"},
        aggregation=BindingAggregation(op=BindingAggregationOp.COPY),
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
    )
    fields = [_binding_field("field.declared", 1, _DECLARED_BINDING)]
    fields.extend(_binding_field(f"field.dangling.{name}", 4 * (i + 1) + 1, name) for i, name in enumerate(dangling))
    fields.extend(extra_fields)
    return ModeloRevision(
        id=_REVISION,
        localization_key="test.below_floor.revision.label",
        valid_from=date(2016, 1, 1),
        period_selector=PeriodSelector(years=(2016, _REVISION_LAST_YEAR), periods=("0A",)),
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
        bindings=(declared,),
        export_layouts=(
            ExportLayoutDefinition(
                id="layout.fixture",
                legal_refs=(_LEGAL_REF,),
                source_refs=(_SOURCE_REF,),
                records=(
                    ExportRecordDefinition(
                        id="record.fixture",
                        record_type="fixture",
                        order=1,
                        encoding=ExportEncoding.ISO_8859_1,
                        line_ending="none",
                        fields=tuple(fields),
                    ),
                ),
            ),
        ),
    )


def _export_failures(
    modelo_id: str,
    revision_id: str,
    revision: ModeloRevision,
    *,
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    source_root: Path | None,
) -> list[str]:
    """Return the real export-section failures for one revision, undowngraded."""
    context = build_revision_validation_context(revision)
    return validate_export_layout_section(
        prefix=f"modelo {modelo_id} revision {revision_id}",
        revision=revision,
        casillas=context.casillas,
        bindings=context.bindings,
        casilla_by_id=context.casilla_by_id,
        legal_refs=legal_refs,
        source_refs=source_refs,
        evidence=EvidenceValidator(legal_refs=legal_refs, source_refs=source_refs, source_root=source_root),
        source_root=source_root,
    )


def _row(**changes: object) -> dict[str, object]:
    """Return the carrier's below-floor row, with ``changes`` re-declared."""
    return {
        "kind": "below_floor",
        "modelo": _MODELO,
        "revision": _REVISION,
        "source_ref": _SOURCE_REF,
        "source_sha256": _SOURCE_SHA256,
        "supported_filing_years_floor": _FIXTURE_FLOOR,
        "revision_last_filing_year": _REVISION_LAST_YEAR,
        "reason": "every declared filing year lies below the floor",
        "reconsideration_condition": "the floor is lowered or the revision is retired",
        **changes,
    }


def _write_ledger(directory: Path, rows: list[dict[str, object]]) -> Path:
    path = directory / "generated_tree_dispositions.toml"
    path.write_text(rtoml.dumps({"schema_version": 4, "dispositions": rows}, pretty=True), encoding="utf-8")
    return path


def _write_registry_root(directory: Path, *, floor: int = _FIXTURE_FLOOR) -> Path:
    """Write the one file the validator reads from a registry root: the floor declaration."""
    root = directory / "registry"
    declaration = root / "legal" / "supported-filing-years.toml"
    declaration.parent.mkdir(parents=True)
    declaration.write_text(
        rtoml.dumps({"supported_filing_years": {"floor": floor, "horizon": floor + 5}}),
        encoding="utf-8",
    )
    return root


def _carrier(
    tmp_path: Path,
    revision: ModeloRevision | None = None,
    *,
    rows: list[dict[str, object]] | None = None,
) -> _Carrier:
    """Assemble a carrier in ``tmp_path`` with the honouring row, or with ``rows`` instead."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    return _Carrier(
        revision=_revision() if revision is None else revision,
        legal_refs={_LEGAL_REF: _legal_reference()},
        source_refs={_SOURCE_REF: _source_reference()},
        registry_root=_write_registry_root(tmp_path),
        ledger_path=_write_ledger(tmp_path, [_row()] if rows is None else rows),
    )


def _dangling(failures: Iterable[str]) -> list[str]:
    return [line for line in failures if _DANGLING_MARKER in line]


def _row_disagreements(
    rows: Iterable[GeneratedTreeBelowSupportedFilingYearsDisposition],
    *,
    registry_root: Path,
) -> list[str]:
    """Return how each below-floor row disagrees with the registry it is read against.

    A row explains why a generated tree has no law-selectable coordinate, so it
    must still describe the live registry: its newest filing year lies below the
    floor the legal tree declares, and the tree it explains is present.
    """
    floor = declared_supported_filing_years_floor(registry_root=registry_root)
    disagreements: list[str] = []
    for row in rows:
        if row.revision_last_filing_year >= floor:
            disagreements.append(
                f"{row.subject}: newest filing year {row.revision_last_filing_year} "
                f"is not below the declared floor {floor}",
            )
        export_root = registry_root / "modelos" / row.modelo / "revisions" / row.revision / "export"
        if not export_fragment_provenance_path(export_root).is_file():
            disagreements.append(f"{row.subject}: no generated export tree at {export_root}")
    return disagreements


def test_the_carrier_has_exactly_the_dangling_references_it_was_built_with(tmp_path: Path) -> None:
    """The fixture is only evidence if its refusals are the planted ones and nothing else."""
    failures = _carrier(tmp_path).export_failures()

    dangling = _dangling(failures)
    assert len(dangling) == len(_DANGLING_BINDINGS)
    for name in _DANGLING_BINDINGS:
        assert sum(f"'{name}'" in line for line in dangling) == 1
    assert not any(_DECLARED_BINDING in line for line in failures)
    assert failures == dangling


def test_the_row_downgrades_every_dangling_export_reference_and_counts_it(tmp_path: Path) -> None:
    """The honoured row must move the refusals onto one advisory that states how many."""
    carrier = _carrier(tmp_path)
    failures = carrier.export_failures()
    dangling = _dangling(failures)
    assert len(dangling) == 2

    kept, advisories = carrier.advisories(failures)

    assert _dangling(kept) == []
    assert kept == []
    assert len(advisories) == 1
    assert f"export tree of {_MODELO}/{_REVISION} is below the supported-filing-years floor" in advisories[0]
    assert f"({_FIXTURE_FLOOR})" in advisories[0]
    assert f"{len(dangling)} references to superseded binding spellings are not a refusal" in advisories[0]


def test_the_floor_is_read_from_the_registry_the_validator_is_handed(tmp_path: Path) -> None:
    """The recorded floor is checked against the declaration of the given root, not the shipped one."""
    carrier = _carrier(tmp_path)

    assert declared_supported_filing_years_floor(registry_root=carrier.registry_root) == _FIXTURE_FLOOR
    assert declared_supported_filing_years_floor(registry_root=carrier.registry_root) != (
        declared_supported_filing_years_floor()
    )


def test_without_the_row_the_same_revision_still_refuses(tmp_path: Path) -> None:
    """The downgrade must come from the declaration, not from the revision being old."""
    carrier = _carrier(tmp_path, rows=[])
    failures = carrier.export_failures()

    kept, advisories = carrier.advisories(failures)

    assert advisories == ()
    assert kept == failures
    assert len(_dangling(kept)) == len(_DANGLING_BINDINGS)


def test_a_row_for_another_revision_does_not_cover_this_one(tmp_path: Path) -> None:
    """A row is keyed by modelo and revision, so a neighbour's declaration explains nothing here."""
    carrier = _carrier(tmp_path, rows=[_row(revision="2014-2015")])
    failures = carrier.export_failures()

    kept, advisories = carrier.advisories(failures)

    assert advisories == ()
    assert kept == failures


def test_a_row_pinned_to_a_floor_the_registry_no_longer_declares_is_not_honoured(tmp_path: Path) -> None:
    """A stale floor describes a registry that no longer exists, so the refusals return.

    The recorded floor is lowered to 2018, which the ledger loader still accepts
    because 2017 stays below it. What retires the row here is the live
    declaration: the legal tree says 2019, and a row written against a different
    floor no longer explains this registry.
    """
    carrier = _carrier(tmp_path, rows=[_row(supported_filing_years_floor=2018)])
    assert disposition_ledger_from_path(carrier.ledger_path)
    failures = carrier.export_failures()

    kept, advisories = carrier.advisories(failures)

    assert advisories == ()
    assert kept == failures


def test_a_row_is_not_honoured_once_the_registry_floor_moves_away_from_it(tmp_path: Path) -> None:
    """The same row stops covering the tree when the declaration it was written against changes."""
    carrier = _carrier(tmp_path)
    failures = carrier.export_failures()
    assert carrier.advisories(failures)[1]

    moved = tmp_path / "moved"
    moved.mkdir()
    moved_root = _write_registry_root(moved, floor=_FIXTURE_FLOOR + 1)
    kept, advisories = below_floor_export_reference_advisories(
        failures,
        modelo_id=_MODELO,
        revision_id=_REVISION,
        ledger_path=carrier.ledger_path,
        registry_root=moved_root,
    )

    assert advisories == ()
    assert kept == failures


def test_a_row_whose_revision_the_floor_no_longer_excludes_is_refused_by_the_ledger(tmp_path: Path) -> None:
    """Lowering the floor under the revision retires the row at the loader itself."""
    ledger_path = _write_ledger(tmp_path, [_row(supported_filing_years_floor=_REVISION_LAST_YEAR)])

    with pytest.raises(ValueError, match="must be retired rather than kept"):
        disposition_ledger_from_path(ledger_path)


def test_the_downgrade_leaves_unrelated_export_failures_standing(tmp_path: Path) -> None:
    """Only the binding-reference lines are covered; anything else still refuses.

    The unrelated failures are real ones the export validator raises over the
    same tree: a literal wider than its slot and a field naming a casilla the
    revision does not declare. A synthetic line that merely resembles an export
    field failure is added too, because the coverage must come from the
    ``references unknown binding`` wording and not from the ``export field``
    prefix every field failure shares.
    """
    wide_literal = _field("field.literal", 13, kind="literal", literal="abcdef", length=2)
    unknown_casilla = _field(
        "field.casilla",
        15,
        kind="casilla",
        casilla_id=validated_casilla_id("98", surface="below-floor fixture"),
    )
    carrier = _carrier(tmp_path, _revision(wide_literal, unknown_casilla))
    failures = carrier.export_failures()
    unrelated_real = [line for line in failures if _DANGLING_MARKER not in line]
    assert any("literal length 6 exceeds declared length 2" in line for line in unrelated_real)
    assert any("references unknown casilla '98'" in line for line in unrelated_real)
    synthetic = f"modelo {_MODELO} revision {_REVISION}: export field 'x' has an unreadable declaration"

    kept, advisories = carrier.advisories([*failures, synthetic])

    assert len(advisories) == 1
    assert f"{len(_DANGLING_BINDINGS)} references to superseded binding spellings" in advisories[0]
    assert kept == [*unrelated_real, synthetic]


def test_a_row_with_no_dangling_reference_to_cover_reports_no_advisory(tmp_path: Path) -> None:
    """A clean tree under a row yields nothing to downgrade, so no advisory claims a covered refusal."""
    carrier = _carrier(tmp_path, _revision(dangling=()))
    failures = carrier.export_failures()
    assert failures == []

    kept, advisories = carrier.advisories(failures)

    assert (kept, advisories) == ([], ())


def test_the_logging_entry_point_reports_each_honoured_row_and_returns_what_still_stands(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The advisory reaches the log, while the refusals the row does not cover are returned."""
    carrier = _carrier(tmp_path, _revision(_field("field.literal", 13, kind="literal", literal="abcdef", length=2)))
    failures = carrier.export_failures()

    with caplog.at_level(logging.WARNING):
        kept = downgrade_below_floor_export_reference_failures(
            failures,
            modelo_id=_MODELO,
            revision_id=_REVISION,
            ledger_path=carrier.ledger_path,
            registry_root=carrier.registry_root,
        )

    assert kept == [line for line in failures if _DANGLING_MARKER not in line]
    assert len(kept) == 1
    warnings = [record.getMessage() for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert f"{len(_DANGLING_BINDINGS)} references to superseded binding spellings are not a refusal" in warnings[0]


def _carrier_rows(carrier: _Carrier) -> list[GeneratedTreeBelowSupportedFilingYearsDisposition]:
    return [
        row
        for row in disposition_ledger_from_path(carrier.ledger_path)
        if isinstance(row, GeneratedTreeBelowSupportedFilingYearsDisposition)
    ]


def _write_tree(registry_root: Path) -> None:
    """Give the carrier's registry root a provenance-attested export directory for its revision."""
    export_root = registry_root / "modelos" / _MODELO / "revisions" / _REVISION / "export"
    export_root.mkdir(parents=True)
    export_fragment_provenance_path(export_root).write_text("{}", encoding="utf-8")


def test_a_row_that_agrees_with_its_registry_and_its_tree_has_no_disagreement(tmp_path: Path) -> None:
    """The positive path of the shipped agreement check, on the carrier."""
    carrier = _carrier(tmp_path)
    _write_tree(carrier.registry_root)

    assert _row_disagreements(_carrier_rows(carrier), registry_root=carrier.registry_root) == []


def test_a_row_whose_tree_is_absent_is_a_disagreement(tmp_path: Path) -> None:
    """Teeth: a row for a tree the registry does not carry explains nothing."""
    carrier = _carrier(tmp_path)

    disagreements = _row_disagreements(_carrier_rows(carrier), registry_root=carrier.registry_root)

    assert len(disagreements) == 1
    assert f"{_MODELO}/{_REVISION}: no generated export tree" in disagreements[0]


def test_a_row_the_declared_floor_no_longer_excludes_is_a_disagreement(tmp_path: Path) -> None:
    """Teeth: lowering the declared floor to the revision's newest year leaves the row unexplained."""
    carrier = _carrier(tmp_path)
    _write_tree(carrier.registry_root)
    declaration = carrier.registry_root / "legal" / "supported-filing-years.toml"
    declaration.write_text(
        rtoml.dumps({"supported_filing_years": {"floor": _REVISION_LAST_YEAR, "horizon": 2024}}),
        encoding="utf-8",
    )

    disagreements = _row_disagreements(_carrier_rows(carrier), registry_root=carrier.registry_root)

    assert len(disagreements) == 1
    assert (
        f"newest filing year {_REVISION_LAST_YEAR} is not below the declared floor {_REVISION_LAST_YEAR}"
        in (disagreements[0])
    )


def test_every_shipped_below_floor_row_agrees_with_the_declared_floor_and_its_tree() -> None:
    """A shipped row stays only while its revision lies below the floor and its tree is present.

    A below-floor row also explains why a generated tree has no law-selectable
    coordinate, so it is not retired when the tree is regenerated clean. It
    retires when the floor is lowered to admit the revision or the revision is
    retired, which is what this agreement check detects.
    """
    assert _row_disagreements(below_floor_dispositions(), registry_root=bundled_registry_root()) == []
