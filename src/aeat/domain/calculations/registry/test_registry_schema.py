"""Tests for the registry-backed AEAT calculation schema."""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import pytest

from . import RegistryCatalogues, RegistryLoadError, RegistryValidationError, build_snapshot, load_modelo_file
from ._schema import LegalReference, SourceReference
from ._validate import RegistryValidator

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _catalogues() -> RegistryCatalogues:
    source_sha = hashlib.sha256(b"x").hexdigest()
    return RegistryCatalogues(
        legal={
            "ley-37-1992:art-90": LegalReference(
                id="ley-37-1992:art-90",
                authority="boe",
                kind="ley",
                corpus_ref="corpus/normatives/ley-37-1992.json#art-90",
                document_id="BOE-A-1992-28740",
                article="90",
                permalink="https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740#a90",
                effective_from=date(1992, 12, 29),
                review_status="reviewed",
            ),
            "ley-37-1992:art-92": LegalReference(
                id="ley-37-1992:art-92",
                authority="boe",
                kind="ley",
                corpus_ref="corpus/normatives/ley-37-1992.json#art-92",
                document_id="BOE-A-1992-28740",
                article="92",
                permalink="https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740#a92",
                effective_from=date(1992, 12, 29),
                review_status="reviewed",
            ),
        },
        sources={
            "aeat-dr-303-2024-v2": SourceReference(
                id="aeat-dr-303-2024-v2",
                authority="aeat",
                kind="record_design",
                corpus_path="corpus/aeat_official/disenos_registro/modelo_303/example.xlsx",
                sha256=source_sha,
                bytes=1,
                retrieved_at=date(2026, 5, 3),
                source_url="https://sede.agenciatributaria.gob.es/example",
                review_status="reviewed",
            ),
            "manual-iva-2025": SourceReference(
                id="manual-iva-2025",
                authority="aeat",
                kind="manual_pdf",
                corpus_path="corpus/manuals/iva/2025/source.pdf",
                sha256=source_sha,
                bytes=1,
                retrieved_at=date(2026, 5, 3),
                source_url="https://sede.agenciatributaria.gob.es/manual",
                review_status="reviewed",
            ),
        },
    )


def _write_sources(root: Path) -> None:
    for relative in (
        "corpus/aeat_official/disenos_registro/modelo_303/example.xlsx",
        "corpus/manuals/iva/2025/source.pdf",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")


def _write_modelo(path: Path, extra: str = "") -> None:
    path.write_text(
        f"""
[modelo]
id = "303"
title = "IVA autoliquidacion"
official_name = "Impuesto sobre el Valor Anadido. Autoliquidacion"
tax_domain = "iva"
cadence = "quarterly"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-37-1992:art-90"]
source_refs = ["aeat-dr-303-2024-v2"]

[revisions."2024-from-09-3t"]
valid_from = 2024-09-01
valid_to = 2024-12-31
period_selector = {{ years = [2024], periods = ["3T", "4T"] }}
legal_refs = ["ley-37-1992:art-90"]
source_refs = ["aeat-dr-303-2024-v2"]

[[revisions."2024-from-09-3t".parameters]]
id = "iva.general.rate"
data_type = "ratio"
unit = "ratio"
legal_refs = ["ley-37-1992:art-90"]
source_refs = ["manual-iva-2025"]

[[revisions."2024-from-09-3t".parameters.values]]
value = "0.21"
date_axis = "transaction_date"
valid_from = 2024-09-01
valid_to = 2024-12-31

[[revisions."2024-from-09-3t".bindings]]
id = "vat.output.general.quota"
source = "vat"
selector = {{ fact = "output_quota", regime = "general" }}
aggregation = {{ op = "sum", date_axis = "transaction_date" }}
legal_refs = ["ley-37-1992:art-90"]
source_refs = ["manual-iva-2025"]

[[revisions."2024-from-09-3t".casillas]]
id = "03"
number = "03"
label = "IVA devengado por operaciones interiores"
section = ["iva_devengado", "regimen_general"]
data_type = "money"
required = true
input_kind = "bound"
binding = "vat.output.general.quota"
legal_refs = ["ley-37-1992:art-90"]
source_refs = ["aeat-dr-303-2024-v2"]
export_refs = ["dp30304.casilla-03"]

[[revisions."2024-from-09-3t".casillas]]
id = "46"
number = "46"
label = "Resultado regimen general"
section = ["resultado"]
data_type = "money"
required = true
input_kind = "computed"
formula = "resultado-regimen-general"
legal_refs = ["ley-37-1992:art-92"]
source_refs = ["aeat-dr-303-2024-v2"]

[[revisions."2024-from-09-3t".formulas]]
id = "resultado-regimen-general"
target = "46"
op = "copy"
args = [{{ casilla = "03" }}]
rounding = "money-2"
legal_refs = ["ley-37-1992:art-92"]
source_refs = ["aeat-dr-303-2024-v2"]
{extra}
""",
        encoding="utf-8",
    )


def test_modelo_file_loads_and_snapshot_selects_revision(tmp_path: Path) -> None:
    path = tmp_path / "303.toml"
    _write_modelo(path)
    _write_sources(tmp_path)

    modelo = load_modelo_file(path)
    RegistryValidator(_catalogues(), source_root=tmp_path).validate_modelo(modelo)
    snapshot = build_snapshot(modelo, _catalogues(), source_root=tmp_path, filing_year=2024, period="3T")

    assert snapshot.modelo.id == "303"
    assert snapshot.revision.id == "2024-from-09-3t"
    assert "ley-37-1992:art-90" in snapshot.legal
    assert "aeat-dr-303-2024-v2" in snapshot.sources


def test_modelo_file_rejects_local_source_catalogue(tmp_path: Path) -> None:
    path = tmp_path / "303.toml"
    _write_modelo(path, extra='[source."local"]\nkind = "record_design"\n')

    with pytest.raises(RegistryLoadError, match="must not define local legal/source"):
        load_modelo_file(path)


def test_modelo_file_rejects_empty_filing_grade_evidence(tmp_path: Path) -> None:
    path = tmp_path / "303.toml"
    _write_modelo(path)
    text = path.read_text(encoding="utf-8").replace(
        'legal_refs = ["ley-37-1992:art-92"]',
        "legal_refs = []",
        1,
    )
    path.write_text(text, encoding="utf-8")

    with pytest.raises(RegistryLoadError, match="too_short"):
        load_modelo_file(path)


def test_snapshot_requires_source_integrity(tmp_path: Path) -> None:
    path = tmp_path / "303.toml"
    _write_modelo(path)
    modelo = load_modelo_file(path)

    with pytest.raises(RegistryValidationError, match="missing corpus file"):
        build_snapshot(modelo, _catalogues(), source_root=tmp_path, filing_year=2024, period="3T")


def test_validator_rejects_unresolved_algorithm_provider(tmp_path: Path) -> None:
    path = tmp_path / "303.toml"
    _write_modelo(
        path,
        extra="""
[[revisions."2024-from-09-3t".algorithm_bindings]]
id = "renta-complex"
provider = "missing-provider"
target = "46"
inputs = { quota = "03" }
outputs = { result = "46" }
legal_refs = ["ley-37-1992:art-92"]
source_refs = ["aeat-dr-303-2024-v2"]
""",
    )
    _write_sources(tmp_path)
    modelo = load_modelo_file(path)

    with pytest.raises(RegistryValidationError, match="unknown provider"):
        RegistryValidator(_catalogues(), source_root=tmp_path).validate_modelo(modelo)


def test_validator_rejects_unresolved_algorithm_io(tmp_path: Path) -> None:
    path = tmp_path / "303.toml"
    _write_modelo(
        path,
        extra="""
[[revisions."2024-from-09-3t".algorithm_providers]]
id = "provider"
import_path = "aeat.domain.example"
callable_name = "calculate"
deterministic = true
side_effect_free = true
allowed_input_schema = { quota = "money" }
output_schema = { result = "money" }
trace_contract = "trace"
legal_refs = ["ley-37-1992:art-92"]
source_refs = ["aeat-dr-303-2024-v2"]

[[revisions."2024-from-09-3t".algorithm_bindings]]
id = "bad-binding"
provider = "provider"
target = "missing-target"
inputs = { quota = "missing-input" }
outputs = { result = "missing-output" }
legal_refs = ["ley-37-1992:art-92"]
source_refs = ["aeat-dr-303-2024-v2"]
""",
    )
    _write_sources(tmp_path)
    modelo = load_modelo_file(path)

    with pytest.raises(RegistryValidationError, match=r"unknown casilla|unknown value"):
        RegistryValidator(_catalogues(), source_root=tmp_path).validate_modelo(modelo)


def test_validator_rejects_duplicate_formula_targets(tmp_path: Path) -> None:
    path = tmp_path / "303.toml"
    _write_modelo(
        path,
        extra="""
[[revisions."2024-from-09-3t".formulas]]
id = "duplicate-target"
target = "46"
op = "copy"
args = [{ casilla = "03" }]
rounding = "money-2"
legal_refs = ["ley-37-1992:art-92"]
source_refs = ["aeat-dr-303-2024-v2"]
""",
    )
    _write_sources(tmp_path)
    modelo = load_modelo_file(path)

    with pytest.raises(RegistryValidationError, match="duplicate formula target"):
        RegistryValidator(_catalogues(), source_root=tmp_path).validate_modelo(modelo)


def test_validator_rejects_formula_id_shadowing_casilla_id(tmp_path: Path) -> None:
    path = tmp_path / "303.toml"
    _write_modelo(path)
    text = path.read_text(encoding="utf-8").replace('id = "resultado-regimen-general"', 'id = "46"', 1)
    text = text.replace('formula = "resultado-regimen-general"', 'formula = "46"', 1)
    path.write_text(text, encoding="utf-8")
    _write_sources(tmp_path)
    modelo = load_modelo_file(path)

    with pytest.raises(RegistryValidationError, match="shadowed registry id '46'"):
        RegistryValidator(_catalogues(), source_root=tmp_path).validate_modelo(modelo)


def test_validator_rejects_formula_target_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "303.toml"
    _write_modelo(path)
    text = path.read_text(encoding="utf-8").replace('target = "46"', 'target = "03"', 1)
    path.write_text(text, encoding="utf-8")
    _write_sources(tmp_path)
    modelo = load_modelo_file(path)

    with pytest.raises(RegistryValidationError, match="targeting '03'"):
        RegistryValidator(_catalogues(), source_root=tmp_path).validate_modelo(modelo)


def test_validator_rejects_missing_legal_reference(tmp_path: Path) -> None:
    path = tmp_path / "303.toml"
    _write_modelo(path)
    _write_sources(tmp_path)
    modelo = load_modelo_file(path)
    catalogues = _catalogues().model_copy(update={"legal": {}})

    with pytest.raises(RegistryValidationError, match="unknown legal id"):
        RegistryValidator(catalogues, source_root=tmp_path).validate_modelo(modelo)
