"""Import-contract guards for registry teardown deletion gates."""

from __future__ import annotations

import ast
import importlib
import importlib.util
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_ROOT = Path(__file__).resolve().parents[2]


def _source(relative: str) -> str:
    return (_ROOT / relative).read_text(encoding="utf-8")


def _function_node(source: str, name: str) -> ast.FunctionDef:
    module = ast.parse(source)
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function {name!r} not found")


def test_declaration_export_no_longer_imports_generated_modules() -> None:
    source = _source("src/aeat/application/filing/_export.py")
    assert "adapters.outbound.aeat.export._formats import modelo_" not in source
    assert "adapters.outbound.aeat.export._formats._serialise" not in source
    assert "adapters.outbound.aeat.export._formats._deserialise" not in source
    assert "produced by :mod:`aeat.adapters.outbound.aeat.export._formats`" not in source


@pytest.mark.parametrize("function_name", ["export_draft", "verify_export"])
def test_declaration_export_functions_fail_before_runtime_work(function_name: str) -> None:
    node = _function_node(_source("src/aeat/application/filing/_export.py"), function_name)
    raises = [stmt for stmt in node.body if isinstance(stmt, ast.Raise)]
    assert raises, f"{function_name} must fail closed until registry snapshots back it"
    first_raise_index = node.body.index(raises[0])
    imported_before_raise = [
        stmt for stmt in node.body[:first_raise_index] if isinstance(stmt, ast.Import | ast.ImportFrom)
    ]
    assert imported_before_raise == []


def test_casilla_catalogue_writers_have_no_filesystem_write_path() -> None:
    casillas_package = importlib.import_module("aeat.domain.casillas")
    assert not hasattr(casillas_package, "save_casillas")
    assert "save_casillas" not in casillas_package.__all__
    package_source = _source("src/aeat/domain/casillas/__init__.py")
    assert "save_casillas" not in package_source
    source = _source("src/aeat/domain/casillas/catalogue.py")
    for function_name in ("save_casillas", "write_extract_draft", "write_translate_draft", "_write_temp_catalogue"):
        node = _function_node(source, function_name)
        write_calls = [
            child
            for child in ast.walk(node)
            if isinstance(child, ast.Call)
            and isinstance(child.func, ast.Attribute)
            and child.func.attr in {"mkdir", "write_text", "write_bytes", "open"}
        ]
        assert write_calls == [], f"{function_name} reintroduced a corpus writer"


def test_public_hydrate_module_cannot_reach_legacy_ruleset_projection() -> None:
    source = _source("src/aeat/domain/casillas/_hydrate/__init__.py")
    assert "from .records import" not in source
    assert "_hydrate_from_rulesets" not in source
    assert "casilla hydrate is disabled" in source
    hydrate_dir = _ROOT / "src/aeat/domain/casillas/_hydrate"
    assert not (hydrate_dir / "records.py").exists()
    assert not (hydrate_dir / "formulas.py").exists()
    assert not (hydrate_dir / "metadata.py").exists()


def test_runtime_schema_provider_cannot_import_model_specific_static_schemas() -> None:
    source = _source("src/aeat/application/filing/runtime.py")
    assert "domain.filing._builders" not in source
    provider = _function_node(source, "build_runtime_schema_provider")
    assert any(isinstance(stmt, ast.Raise) for stmt in provider.body)
    assert "validated registry snapshots" in source


def test_filing_runtime_does_not_derive_supported_modelos_in_python() -> None:
    source = _source("src/aeat/application/filing/runtime.py")
    projector = _function_node(source, "filing_profile_from_autonomo")
    assert "_SUPPORTED_FILING_MODELOS" not in source
    assert "applies_to" not in source
    assert '("130", "303", "390")' not in source
    assert "applicable_modelos=()" in ast.unparse(projector)


def test_application_build_draft_cannot_dispatch_legacy_builders() -> None:
    source = _source("src/aeat/application/filing/__init__.py")
    filing_package = importlib.import_module("aeat.application.filing")
    assert "get_builder" not in source
    assert "Modelo130Builder" not in source
    assert "Modelo303Builder" not in source
    assert "Modelo390Builder" not in source
    assert "QUARTERLY_303_INPUT_KEY" not in source
    assert not hasattr(filing_package, "FilingBuilder")
    assert "FilingBuilder" not in filing_package.__all__
    assert not hasattr(filing_package, "QUARTERLY_303_INPUT_KEY")
    builder = _function_node(source, "build_draft")
    assert any(isinstance(stmt, ast.Raise) for stmt in builder.body)
    assert "legacy Python filing builders are disabled" in source


def test_domain_filing_package_does_not_export_legacy_builders() -> None:
    source = _source("src/aeat/domain/filing/__init__.py")
    filing_package = importlib.import_module("aeat.domain.filing")
    legacy_builder_dir = _ROOT / "src/aeat/domain/filing/_builders"
    legacy_builder_abc = _ROOT / "src/aeat/domain/filing/_builder.py"
    assert not legacy_builder_dir.exists()
    assert not legacy_builder_abc.exists()
    assert "from ._builders import" not in source
    assert "from ._builder import" not in source
    assert "get_builder" not in source
    assert "Modelo130Builder" not in source
    assert "Modelo303Builder" not in source
    assert "Modelo390Builder" not in source
    for name in (
        "get_builder",
        "Modelo130Builder",
        "Modelo303Builder",
        "Modelo390Builder",
        "QUARTERLY_303_INPUT_KEY",
        "FilingBuilder",
    ):
        assert not hasattr(filing_package, name)
        assert name not in filing_package.__all__


def test_application_testing_helpers_do_not_import_builder_static_schemas() -> None:
    source = _source("src/aeat/application/filing/testing.py")
    filing_testing = importlib.import_module("aeat.application.filing.testing")
    assert not (_ROOT / "src/aeat/application/filing/_testing_static_schema.py").exists()
    assert importlib.util.find_spec("aeat.application.filing._testing_static_schema") is None
    assert "domain.filing._builders" not in source
    assert "_modelo_130_schema" not in source
    assert "_modelo_303_schema" not in source
    assert "_modelo_390_schema" not in source
    for name in (
        "MODELO_130_SCHEMA",
        "MODELO_303_SCHEMA",
        "MODELO_390_SCHEMA",
        "StaticCasillaCollection",
        "StaticCasillaSchema",
        "StaticCasillaSchemaProvider",
        "default_schema_provider",
    ):
        assert not hasattr(filing_testing, name)
        assert name not in filing_testing.__all__


def test_filing_validator_does_not_own_model_specific_calculation_truth() -> None:
    source = _source("src/aeat/domain/filing/_validator.py")
    assert "quarterly_303_drafts" not in source
    assert "_validate_quarterly_reconciliation" not in source
    assert "_MODELO_390_QUARTERLY_MAP" not in source
    assert "_MODELO_303_RATE_TRIPLES" not in source
    assert "filing-390-303-mismatch" not in source
    assert "filing-303-internal-mismatch" not in source


def test_complementaria_builder_does_not_own_legacy_amendment_truth() -> None:
    source = _source("src/aeat/application/filing/_complementaria.py")
    builder = _function_node(source, "build_complementaria")
    assert any(isinstance(stmt, ast.Raise) for stmt in builder.body)
    assert "legacy Python amendment anchors are disabled" in source
    assert "_liability_anchor" not in source
    assert "_period_uses_rectificativa" not in source
    assert "_validate_complementaria_liability" not in source
    assert 'modelo == "130"' not in source
    assert 'modelo == "303"' not in source
    assert 'modelo == "390"' not in source


def test_application_verification_cannot_import_legacy_formula_engine() -> None:
    source = _source("src/aeat/application/verification/_verify.py")
    assert "domain.formulas" not in source
    verifier = _function_node(source, "verify_declaracion")
    assert any(isinstance(stmt, ast.Raise) for stmt in verifier.body)
    assert "validated registry snapshot" in source


def test_filing_review_cannot_resolve_legacy_ruleset_registry() -> None:
    source = _source("src/aeat/application/filing/_review.py")
    assert "domain.formulas" not in source
    assert "get_registry" not in source
    resolver = _function_node(source, "_resolve_ruleset_id")
    assert any(isinstance(stmt, ast.Raise) for stmt in resolver.body)
    assert "validated registry snapshot" in source


def test_filing_cli_cannot_resolve_legacy_formula_rulesets() -> None:
    source = _source("src/aeat/entrypoints/cli/filing/__init__.py")
    assert "domain.formulas" not in source
    assert "get_registry" not in source
    resolver = _function_node(source, "_resolve_ruleset_for_filing")
    resolver_source = ast.get_source_segment(source, resolver)
    assert resolver_source is not None
    assert "_ = (filing_modelo, filing_period, filing_ejercicio)" in resolver_source


def test_audit_cli_cannot_reach_legacy_rulesets() -> None:
    source = _source("src/aeat/entrypoints/cli/audit/__init__.py")
    helper_source = _source("src/aeat/entrypoints/cli/audit/_helpers.py")
    assert "ALL_RULESETS" not in source
    assert "domain.formulas" not in source
    assert "Ruleset" not in helper_source
    validator = _function_node(helper_source, "validate_citation_coverage")
    assert any(isinstance(stmt, ast.Raise) for stmt in validator.body)


def test_aggregation_models_do_not_import_legacy_formula_codes() -> None:
    source = _source("src/aeat/application/aggregation/_models.py")
    assert "domain.formulas" not in source
    assert "class Quarter" in source


@pytest.mark.parametrize(
    "relative",
    [
        "src/aeat/entrypoints/cli/data/ledgers/assets.py",
        "src/aeat/entrypoints/cli/data/ledgers/anexo_d.py",
    ],
)
def test_data_ledger_cli_modules_require_registry_snapshots(relative: str) -> None:
    source = _source(relative)
    assert "domain.formulas" not in source
    assert "_rulesets" not in source
    assert "validated registry snapshot" in source


@pytest.mark.parametrize(
    "relative",
    [
        "src/aeat/domain/profile/__init__.py",
        "src/aeat/domain/profile/inventory/__init__.py",
        "src/aeat/domain/profile/assets/__init__.py",
    ],
)
def test_profile_support_modules_do_not_import_legacy_formula_package(relative: str) -> None:
    source = _source(relative)
    assert "domain.formulas" not in source
    assert "from ...formulas" not in source
    assert "from ..formulas" not in source


def test_legacy_formula_package_is_deleted() -> None:
    formula_dir = _ROOT / "src/aeat/domain/formulas"
    formula_import_contract_dir = _ROOT / "tests/import_contract/domain/formulas"
    assert not formula_dir.exists()
    assert not formula_import_contract_dir.exists()
    assert importlib.util.find_spec("aeat.domain.formulas") is None


def test_generated_export_modules_are_deleted() -> None:
    formats_dir = _ROOT / "src/aeat/adapters/outbound/aeat/export/_formats"
    allowed_runtime_files = {
        "__init__.py",
        "_deserialise.py",
        "_ingest.py",
        "_record_spec.py",
        "_serialise.py",
    }
    runtime_files = {path.name for path in formats_dir.glob("*.py") if not path.name.startswith("test_")}
    assert runtime_files == allowed_runtime_files

    forbidden = (
        "_generate.py",
        "_test_fixtures.py",
        "modelo_130_2024.py",
        "modelo_130_2025.py",
        "modelo_303_2024.py",
        "modelo_303_2024_preview.py",
        "modelo_303_2025.py",
    )
    for filename in forbidden:
        assert not (formats_dir / filename).exists()

    remaining_sources = {
        path.relative_to(_ROOT).as_posix(): path.read_text(encoding="utf-8")
        for path in formats_dir.glob("*.py")
        if not path.name.startswith("test_")
    }
    for relative, source in remaining_sources.items():
        assert "Generated by aeat.adapters.outbound.aeat.export._formats._generate" not in source, relative
        assert "DO NOT hand-edit" not in source, relative
        assert "_generate" not in source, relative


def test_vat_domain_does_not_export_modelo_303_casilla_bridge() -> None:
    vat_package = importlib.import_module("aeat.domain.vat")
    package_source = _source("src/aeat/domain/vat/__init__.py")
    assert not (_ROOT / "src/aeat/domain/vat/_modelo_303_mapping.py").exists()
    assert not (_ROOT / "src/aeat/domain/vat/test_modelo_303_mapping.py").exists()
    assert importlib.util.find_spec("aeat.domain.vat._modelo_303_mapping") is None
    assert "_modelo_303_mapping" not in package_source
    for name in (
        "MODELO_303_CASILLA_MAPPING",
        "Modelo303Contribution",
        "CasillaRole",
        "lookup_modelo_303_contribution",
    ):
        assert not hasattr(vat_package, name)
        assert name not in vat_package.__all__


def test_categories_domain_does_not_export_casilla_mapping_bridge() -> None:
    categories_package = importlib.import_module("aeat.domain.categories")
    profile_source = _source("src/aeat/domain/categories/_profile.py")
    registry_source = _source("src/aeat/domain/categories/_registry.py")
    package_source = _source("src/aeat/domain/categories/__init__.py")
    aggregation_source = _source("src/aeat/application/aggregation/_service.py")
    aggregation_exports = _source("src/aeat/application/aggregation/__init__.py")
    aggregation_errors = _source("src/aeat/application/aggregation/_errors.py")
    categories_cli = _source("src/aeat/entrypoints/cli/categories.py")
    assert not (_ROOT / "src/aeat/domain/categories/_casilla_mapping.py").exists()
    assert importlib.util.find_spec("aeat.domain.categories._casilla_mapping") is None
    assert "_casilla_mapping" not in package_source
    assert "casilla_mappings" not in profile_source
    assert "casilla_mappings" not in registry_source
    assert "casilla_mappings" not in aggregation_source
    assert "profile.casilla_mappings" not in categories_cli
    assert "AggregationCasillaMappingError" not in aggregation_exports
    assert "AggregationCasillaMappingError" not in aggregation_errors
    for name in ("CasillaMapping", "CasillaMappingSign"):
        assert not hasattr(categories_package, name)
        assert name not in categories_package.__all__


def test_declaration_cli_does_not_project_invoice_values_to_modelo_casillas() -> None:
    common_source = _source("src/aeat/entrypoints/cli/_common.py")

    assert 'modelo == "303"' not in common_source
    assert "InvoiceKind" not in common_source
    assert "iva.rate" not in common_source
    for assignment in ('inputs["01"]', 'inputs["04"]', 'inputs["07"]', 'inputs["29"]'):
        assert assignment not in common_source


def test_declaracion_extractor_registry_does_not_import_model_specific_extractors() -> None:
    source = _source("src/aeat/adapters/inbound/declaracion/_extractors/__init__.py")
    detect_source = _source("src/aeat/adapters/inbound/declaracion/_detect.py")
    extractor_package = importlib.import_module("aeat.adapters.inbound.declaracion._extractors")
    extractor_dir = _ROOT / "src/aeat/adapters/inbound/declaracion/_extractors"
    parser_modelo_100_dir = _ROOT / "src/aeat/adapters/inbound/declaracion/_parsers/modelo_100"
    generic_extractor = _ROOT / "src/aeat/adapters/inbound/declaracion/_generic_extractor.py"
    assert "_REGISTERED_CLASSES" not in source
    assert "_REGISTRY" not in source
    assert "from .modelo_" not in source
    assert "from .._parsers.modelo_100" not in source
    assert 'modelo == "100"' not in detect_source
    assert "_modelo_100_revision" not in detect_source
    assert sorted(path.name for path in extractor_dir.glob("modelo_*.py")) == []
    assert not parser_modelo_100_dir.exists()
    assert not generic_extractor.exists()
    assert not hasattr(extractor_package, "_REGISTERED_CLASSES")
    get_extractor = _function_node(source, "get_extractor")
    assert any(isinstance(stmt, ast.Raise) for stmt in get_extractor.body)
    assert "legacy Python extractor registry is disabled" in source
