"""Tests for the typed modelo registry query API."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest
from pydantic import ValidationError

from .....core.resources import bundled_path
from .. import CasillaId, validated_casilla_id
from .._authority import ValidatedRegistryAuthority
from .._errors import AmbiguousRevisionSelectionError, RegistryValidationError
from .._queries import BindingSelectorQueryProjection, ModeloFormulaRow, RegistryQueryService
from .._schema import InputKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_INPUT_CASILLA: CasillaId = validated_casilla_id("01", surface="_INPUT_CASILLA")
_TARGET_CASILLA: CasillaId = validated_casilla_id("02", surface="_TARGET_CASILLA")

_MINIMAL_CATALOGUE_TOML = """\
[legal."test-ley-001:art-1"]
evidence_tier = "legal_authority"
authority = "boe"
kind = "ley"
corpus_ref = "corpus/test/test-ley-001.html#a1"
document_id = "BOE-T-001"
article = "1"
permalink = "https://example.com/test"
effective_from = 2025-01-01
review_status = "reviewed"

[sources."test-source-001"]
evidence_tier = "layout_authority"
authority = "aeat"
kind = "record_design"
corpus_path = "corpus/test/test-source-001.pdf"
sha256 = "44f8354494a5ba03ba1792a8d3e9c534c47a9181980fde7a3f44b06ef2ae7c7f"
bytes = 1000
retrieved_at = 2025-01-01
source_url = "https://example.com/test-source"
review_status = "reviewed"
"""

_MINIMAL_MANIFEST_TOML = """\
[modelo]
id = "999"
title = "Query ambiguity test modelo"
official_name = "Query ambiguity test modelo"
tax_domain = "iva"
cadence = "quarterly"
jurisdiction = "ES-AEAT"
legal_refs = ["test-ley-001:art-1"]
source_refs = ["test-source-001"]
"""

_MINIMAL_REVISION_TOML_TEMPLATE = """\
[revisions."{revision_id}"]
label = "{label}"
valid_from = 2025-01-01
period_selector = {{ years = [2025], periods = ["{period}"] }}
legal_refs = ["test-ley-001:art-1"]
source_refs = ["test-source-001"]
orden_aplicabilidad = ["test-ley-001:art-1"]

[[revisions."{revision_id}".application_links]]
id = "test-filing-link"
surface = "filing"
consumer = "cli.app"
requires_snapshot = true
legal_refs = ["test-ley-001:art-1"]
source_refs = ["test-source-001"]

[[revisions."{revision_id}".casillas]]
id = "01"
number = "01"
label = "Test casilla"
section = ["test"]
data_type = "integer"
legal_refs = ["test-ley-001:art-1"]
source_refs = ["test-source-001"]

[[revisions."{revision_id}".workbook_parity_refs]]
id = "test-workbook-001"
workbook_source = "test-source-001"
fixture_id = "test-fixture-001"
formula_coverage = "record_design_layout"
runner_required = false
tolerance = "0.00"
legal_refs = ["test-ley-001:art-1"]
source_refs = ["test-source-001"]
"""


def _service() -> RegistryQueryService:
    authority = ValidatedRegistryAuthority.load(_REGISTRY_ROOT, source_root=bundled_path())
    return RegistryQueryService(authority)


def _write_year_ambiguous_registry(tmp_path) -> Path:
    registry_root = tmp_path / "registry" / "aeat"
    legal_dir = registry_root / "legal"
    modelos_dir = registry_root / "modelos" / "999"
    legal_dir.mkdir(parents=True)
    modelos_dir.mkdir(parents=True)
    corpus_file = tmp_path / "corpus" / "test" / "test-source-001.pdf"
    corpus_file.parent.mkdir(parents=True)
    corpus_file.write_bytes(b"x" * 1000)

    (legal_dir / "catalogue.toml").write_text(_MINIMAL_CATALOGUE_TOML, encoding="utf-8")
    (modelos_dir / "manifest.toml").write_text(_MINIMAL_MANIFEST_TOML, encoding="utf-8")

    for revision_id, label, period in (
        ("2025-1t", "2025 first quarter", "1T"),
        ("2025-2t", "2025 second quarter", "2T"),
    ):
        revision_dir = modelos_dir / "revisions" / revision_id
        revision_dir.mkdir(parents=True)
        (revision_dir / "revision.toml").write_text(
            _MINIMAL_REVISION_TOML_TEMPLATE.format(revision_id=revision_id, label=label, period=period),
            encoding="utf-8",
        )

    return registry_root


@pytest.mark.parametrize("period", ("2026Q1", "2026-Q4", "2026-03", "2026"))
def test_query_service_rejects_combined_period_shapes(period: str) -> None:
    service = _service()

    with pytest.raises(RegistryValidationError, match="bare registry token"):
        service.describe_modelo("303", period=period)


def test_query_service_lists_and_describes_committed_modelo() -> None:
    service = _service()

    listed = service.list_modelos(year=2026)
    described = service.describe_modelo_for_scope("303", filing_year=2026, period="1T")

    assert "303" in {row.code for row in listed.modelos}
    assert described.code == "303"
    assert described.filing_year == 2026
    assert described.period == "1T"
    assert described.tax_domain == "iva"
    assert described.casilla_count > 0
    assert described.binding_count > 0
    assert described.formula_count > 0


def test_describe_lists_every_declared_revision_id() -> None:
    """``describe_modelo`` surfaces all declared revision ids so an
    operator can discover the valid ``--revision`` value for
    ``modelo work create`` without first guessing wrong."""

    service = _service()
    authority = ValidatedRegistryAuthority.load(_REGISTRY_ROOT, source_root=bundled_path())

    described = service.describe_modelo_for_scope("303", filing_year=2026, period="1T")
    expected = {str(item.id) for item in authority.modelo("303").revisions.values()}

    assert set(described.revision_ids) == expected
    # The resolved revision is always one of the listed ids.
    assert described.revision in described.revision_ids
    # The list is non-empty and oldest valid_from first (deterministic).
    assert len(described.revision_ids) == len(expected)


def test_query_service_exposes_casillas_bindings_and_formulas_from_same_revision() -> None:
    service = _service()

    casillas = service.casillas_for_scope("303", filing_year=2026, period="1T", input_kind=InputKind.COMPUTED)
    bindings = service.bindings_for_scope("130", filing_year=2026, period="1T")
    formulas = service.formulas_for_scope("303", filing_year=2026, period="1T")

    assert casillas.code == "303"
    assert casillas.rows
    assert all(row.input_kind == InputKind.COMPUTED for row in casillas.rows)
    assert all(row.formula for row in casillas.rows)
    assert bindings.code == "130"
    assert any(row.binding_id == "irpf.previous_year_economic_activity_net_income" for row in bindings.rows)
    assert "previous_filing" in {row.source for row in bindings.rows}
    assert formulas.code == "303"
    assert formulas.rows
    assert any(row.input_casilla_ids or row.input_bindings or row.input_parameters for row in formulas.rows)


def test_binding_query_rows_expose_typed_selector_projection() -> None:
    service = _service()

    report = service.bindings_for_scope("130", filing_year=2026, period="1T")
    row = next(item for item in report.rows if item.binding_id == "modelo-130-resultados-negativos-anteriores")

    assert isinstance(row.selector, BindingSelectorQueryProjection)
    assert not isinstance(row.selector, Mapping)
    assert row.selector.source == "previous_filing"
    assert row.selector.keys == (
        "max_year_delta",
        "source_casilla_id",
        "source_modelo",
        "source_period_offset_from_target",
    )
    assert {entry.key: entry.value for entry in row.selector.entries} == {
        "max_year_delta": 0,
        "source_casilla_id": "saldo-negativo-fin-periodo",
        "source_modelo": "130",
        "source_period_offset_from_target": -1,
    }


def test_binding_query_rows_dump_selector_as_ordered_entries() -> None:
    service = _service()

    report = service.bindings_for_scope("130", filing_year=2026, period="1T")
    row = next(item for item in report.rows if item.binding_id == "modelo-130-resultados-negativos-anteriores")
    dumped = row.model_dump(mode="json")

    assert dumped["selector"] == {
        "source": "previous_filing",
        "keys": [
            "max_year_delta",
            "source_casilla_id",
            "source_modelo",
            "source_period_offset_from_target",
        ],
        "entries": [
            {"key": "max_year_delta", "value": 0},
            {"key": "source_casilla_id", "value": "saldo-negativo-fin-periodo"},
            {"key": "source_modelo", "value": "130"},
            {"key": "source_period_offset_from_target", "value": -1},
        ],
    }


def test_formula_row_rejects_legacy_input_casillas_key() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ModeloFormulaRow.model_validate(
            {
                "formula_id": "test.formula",
                "target_casilla_id": _TARGET_CASILLA,
                "input_casillas": (_INPUT_CASILLA,),
                "input_bindings": (),
                "input_parameters": (),
                "input_relations": (),
                "expression": {"casilla_id": _INPUT_CASILLA},
                "legal_refs": ("test-ley-001:art-1",),
                "source_refs": ("test-source-001",),
            },
        )

    message = str(exc_info.value)
    assert "input_casilla_ids" in message
    assert "input_casillas" in message


def test_describe_accepts_bare_registry_period_token() -> None:
    """``describe`` resolves a bare registry period token to a declaring revision.

    Modelo 100 declares ``0A`` (annual) as its only period. The
    operator passing ``--period 0A`` must select a 100 revision rather
    than be rejected because the token carries no filing year.
    """

    service = _service()

    described = service.describe_modelo("100", period="0A")

    assert described.code == "100"
    assert described.period == "0A"
    assert "0A" in described.periods
    assert described.filing_year is None


def test_describe_rejects_bare_period_not_declared_by_modelo() -> None:
    """A bare token no revision declares is refused naming the declared set."""

    service = _service()

    with pytest.raises(RegistryValidationError, match="not declared by any revision"):
        service.describe_modelo("303", period="0A")


def test_describe_accepts_censo_event_period_token() -> None:
    """``describe`` resolves a non-date censo period token to a revision.

    Modelo 036 declares ``alta`` / ``modificacion`` / ``baja`` as its
    period tokens. None match the registry time-code pattern, so the
    query must match them verbatim against the revision's declared
    periods rather than refuse them.
    """

    service = _service()

    described = service.describe_modelo("036", period="alta")

    assert described.code == "036"
    assert described.period == "alta"
    assert "alta" in described.periods


def test_describe_for_scope_preserves_declared_censo_period_casing() -> None:
    """Exact scope resolution returns the registry-declared non-date token."""

    service = _service()

    described = service.describe_modelo_for_scope("036", filing_year=2026, period="ALTA")

    assert described.code == "036"
    assert described.period == "alta"
    assert "alta" in described.periods


def test_casillas_accepts_censo_event_period_token() -> None:
    """``casillas`` resolves the same censo period tokens as ``describe``."""

    service = _service()

    report = service.casillas("036", period="modificacion")

    assert report.code == "036"
    assert report.period == "modificacion"
    assert report.rows


def test_bindings_for_year_resolves_the_year_covering_revision() -> None:
    """``bindings_for_year`` selects the revision covering the filing year.

    Modelo 100 carries one revision per renta year. Resolving by year
    must return the 2024 revision's binding ids, not the latest
    revision's.
    """

    service = _service()

    report = service.bindings_for_year("100", filing_year=2024)

    assert report.code == "100"
    assert report.filing_year == 2024
    assert report.rows
    assert all(row.binding_id.startswith("renta-2024-") for row in report.rows)


def test_bindings_for_year_refuses_multiple_year_covering_revisions(tmp_path: Path) -> None:
    """A year-only binding query cannot pick among several period-specific revisions."""

    registry_root = _write_year_ambiguous_registry(tmp_path)
    authority = ValidatedRegistryAuthority.load(registry_root, source_root=tmp_path)
    service = RegistryQueryService(authority)

    with pytest.raises(AmbiguousRevisionSelectionError) as exc_info:
        service.bindings_for_year("999", filing_year=2025)

    assert exc_info.value.modelo_id == "999"
    assert exc_info.value.candidate_ids == ("2025-1t", "2025-2t")


def test_binding_rows_report_decimal_input_channel_for_typed_enum_binding() -> None:
    """A ``typed_enum`` binding consumed as a Decimal operand reports
    ``input_channel = "decimal"``.

    The Modelo 100 estimación-directa modality binding carries a
    ``typed_enum`` annotation yet its formulas compare it against a
    numeric literal, so the operator-facing input channel is decimal.
    """

    service = _service()

    report = service.bindings_for_year("100", filing_year=2024)
    row = next(r for r in report.rows if "estimacion-directa-es-normal" in r.binding_id)

    assert row.typed_enum == "EstimacionDirectaModalidad"
    assert row.input_channel == "decimal"


def test_input_casilla_id_map_exposes_only_canonical_ids() -> None:
    """``input_casilla_id_map`` must not reintroduce printed-number references."""

    from .._runtime_graph import input_casilla_id_map

    service = _service()
    described = service.describe_modelo("303", period="1T")
    authority = service._authority
    definition = authority.validate_modelo("303")
    revision = definition.revisions[described.revision]

    id_map = input_casilla_id_map(revision)

    canonical = "iva.compensacion-pendiente-periodos-anteriores"
    assert id_map[canonical] == canonical
    assert "110" not in id_map
