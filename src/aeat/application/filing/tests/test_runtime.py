"""Structural tests for the registry casilla schema projection.

Asserts that legal_refs and source_refs survive the projection from
CasillaDefinition through to RegistryCasillaSchema so that filing-layer
consumers have access to regulatory grounding.

Modelo 130 is used as the reference fixture because it is fully validated
and representative of the registry's legal-grounding requirements.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import time_machine as tm

from ....core.resources import resources
from ....domain.filing import ModeloBuilderError
from ..runtime import RegistryCasillaSchema, _value_type, build_runtime_schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TEST_MODELO = "130"
_TEST_YEAR = 2026
_TEST_PERIOD = "1T"


def _source_casilla_refs() -> dict[str, tuple[str, ...]]:
    """Return {casilla_id: legal_refs} from the authoritative CasillaDefinition."""
    snapshot = resources().modelos.authority.snapshot(_TEST_MODELO, filing_year=_TEST_YEAR, period=_TEST_PERIOD)
    return {casilla.id: casilla.legal_refs for casilla in snapshot.revision.casillas}


def _source_casilla_source_refs() -> dict[str, tuple[str, ...]]:
    """Return {casilla_id: source_refs} from the authoritative CasillaDefinition."""
    snapshot = resources().modelos.authority.snapshot(_TEST_MODELO, filing_year=_TEST_YEAR, period=_TEST_PERIOD)
    return {casilla.id: casilla.source_refs for casilla in snapshot.revision.casillas}


def test_legal_refs_survive_projection() -> None:
    """RegistryCasillaSchema must carry the same legal_refs as the source CasillaDefinition."""
    source = _source_casilla_refs()
    provider = build_runtime_schema_provider(modelos=[_TEST_MODELO], filing_year=_TEST_YEAR, period=_TEST_PERIOD)
    collection = provider.get_collection(_TEST_MODELO)
    schemas = collection.all()

    casillas_with_refs = [s for s in schemas if source.get(s.id)]
    assert casillas_with_refs, f"No casillas with legal_refs found in modelo {_TEST_MODELO} — test would be vacuous"

    for schema in schemas:
        assert isinstance(schema, RegistryCasillaSchema)
        expected = source.get(schema.id, ())
        assert schema.legal_refs == expected, (
            f"legal_refs mismatch for casilla {schema.id}: projected={schema.legal_refs!r}, source={expected!r}"
        )


def test_source_refs_survive_projection() -> None:
    """RegistryCasillaSchema must carry the same source_refs as the source CasillaDefinition."""
    source = _source_casilla_source_refs()
    provider = build_runtime_schema_provider(modelos=[_TEST_MODELO], filing_year=_TEST_YEAR, period=_TEST_PERIOD)
    collection = provider.get_collection(_TEST_MODELO)
    schemas = collection.all()

    casillas_with_refs = [s for s in schemas if source.get(s.id)]
    assert casillas_with_refs, f"No casillas with source_refs found in modelo {_TEST_MODELO} — test would be vacuous"

    for schema in schemas:
        assert isinstance(schema, RegistryCasillaSchema)
        expected = source.get(schema.id, ())
        assert schema.source_refs == expected, (
            f"source_refs mismatch for casilla {schema.id}: projected={schema.source_refs!r}, source={expected!r}"
        )


def test_provider_absent_modelo_error_is_localized() -> None:
    provider = build_runtime_schema_provider(modelos=[_TEST_MODELO], filing_year=_TEST_YEAR, period=_TEST_PERIOD)

    with pytest.raises(ModeloBuilderError) as exc_info:
        provider.get_collection("999")

    assert exc_info.value.translated_message == "application.filing.runtime.errors.modelo_not_in_registry"
    assert exc_info.value.context == {"modelo": "999"}


def test_blank_modelo_selection_error_is_localized() -> None:
    with pytest.raises(ModeloBuilderError) as exc_info:
        build_runtime_schema_provider(modelos=[" "])

    assert exc_info.value.translated_message == "application.filing.runtime.errors.blank_modelo_selection"


def test_missing_requested_modelo_error_is_localized() -> None:
    with pytest.raises(ModeloBuilderError) as exc_info:
        build_runtime_schema_provider(modelos=["999"])

    assert exc_info.value.translated_message == "application.filing.runtime.errors.registry_missing_requested_modelos"
    assert exc_info.value.context == {"modelos": "999"}


def test_empty_registry_error_uses_non_sensitive_context(tmp_path: Path) -> None:
    registry_root = tmp_path / "registry-root"
    (registry_root / "legal").mkdir(parents=True)
    (registry_root / "modelos").mkdir()

    with pytest.raises(ModeloBuilderError) as exc_info:
        build_runtime_schema_provider(registry_root, source_root=registry_root)

    assert exc_info.value.translated_message == "application.filing.runtime.errors.registry_empty"
    assert exc_info.value.context == {"registry_root_name": "registry-root"}


def test_filing_year_period_pair_error_is_localized() -> None:
    with pytest.raises(ModeloBuilderError) as exc_info:
        build_runtime_schema_provider(modelos=[_TEST_MODELO], filing_year=_TEST_YEAR)

    assert exc_info.value.translated_message == "application.filing.runtime.errors.filing_year_period_pair"


def test_unsupported_casilla_data_type_error_is_localized() -> None:
    with pytest.raises(ModeloBuilderError) as exc_info:
        _value_type("blob")

    assert exc_info.value.translated_message == "application.filing.runtime.errors.unsupported_casilla_data_type"
    assert exc_info.value.context == {"data_type": "blob"}


def test_registry_tree_fingerprint_ttl_cache(tmp_path: Path, time_machine: tm.TimeMachineFixture) -> None:  # ty: ignore[possibly-missing-attribute]  # time_machine ships no typed TimeMachineFixture export
    """_registry_tree_fingerprint must cache results with a 1-second TTL and support clearing."""
    import os

    from ..runtime import _registry_tree_fingerprint, clear_runtime_fingerprint_cache

    clear_runtime_fingerprint_cache()
    reg_root = tmp_path / "registry"
    (reg_root / "legal").mkdir(parents=True)
    (reg_root / "modelos").mkdir()

    toml_file = reg_root / "legal" / "test.toml"
    toml_file.write_text("a = 1")

    time_machine.move_to("2026-06-09T12:00:00+00:00")
    fp1 = _registry_tree_fingerprint(reg_root)

    toml_file.write_text("a = 2")
    os.utime(toml_file, (1812542400, 1812542400))  # 2027-06-09 12:00:00

    fp2 = _registry_tree_fingerprint(reg_root)
    assert fp2 == fp1

    clear_runtime_fingerprint_cache()
    fp3 = _registry_tree_fingerprint(reg_root)
    assert fp3 != fp1

    toml_file.write_text("a = 3")
    os.utime(toml_file, (1812542405, 1812542405))

    time_machine.move_to("2026-06-09T12:00:02+00:00")
    fp4 = _registry_tree_fingerprint(reg_root)
    assert fp4 != fp3
