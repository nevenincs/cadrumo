"""Compile raw runtime tables into the registry authority's typed catalogues."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.runtime_catalogues import (
    ApoderamientoScopeRecord,
    CountryVocabularyRecord,
    PublishedIvaPlaceOfSupplyRule,
    PublishedIvaRegulation,
    PublishedRecargoBand,
    RuntimeRegistryCatalogues,
    SpanishPostalTerritory,
    TerritoryCarveOut,
)


def compile_runtime_catalogues(registry_root: Path) -> RuntimeRegistryCatalogues:
    root = registry_root.resolve()
    iva_root = root / "iva"
    countries = _records(_read(iva_root / "country_names.toml"), "country", CountryVocabularyRecord, "code")
    territories = _territories(_read(iva_root / "territories.toml"))
    carve_outs = _records(_read(iva_root / "territory_carve_outs.toml"), "carve_out", TerritoryCarveOut, "code")
    apoderamientos = _read(root / "apoderamientos" / "scopes.toml")
    scopes = _records(apoderamientos, "scopes", ApoderamientoScopeRecord, "code")
    regulations = _regulations(_read(iva_root / "catalogues.toml"))
    place_of_supply = _records(
        _read(iva_root / "place_of_supply.toml"),
        "place_of_supply_rules",
        PublishedIvaPlaceOfSupplyRule,
        "rule_id",
    )
    recargo = _recargo_bands(_read(root / "legal" / "ley-58-2003-recargo-bands.toml"))
    version = apoderamientos.get("catalogue_version")
    if not isinstance(version, str) or not version:
        raise RegistryValidationError("apoderamientos catalogue has no version")
    return RuntimeRegistryCatalogues(
        iva_regulations=regulations,
        iva_place_of_supply=place_of_supply,
        countries=countries,
        spanish_postal_territories=territories,
        territory_carve_outs=carve_outs,
        recargo_bands=recargo,
        apoderamientos_version=version,
        apoderamientos_scopes=scopes,
    )


def _read(path: Path) -> Mapping[str, object]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise RegistryValidationError(f"cannot compile runtime catalogue {path}: {exc}") from exc


def _records(document: Mapping[str, object], member: str, model: type[Any], identity: str) -> dict[str, Any]:
    rows = document.get(member)
    if not isinstance(rows, list) or not rows:
        raise RegistryValidationError(f"runtime catalogue member {member!r} must be a non-empty array")
    compiled: dict[str, Any] = {}
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise RegistryValidationError(f"runtime catalogue member {member!r} contains a non-table row")
        record = model.model_validate(_immutable_toml(raw))
        key = str(getattr(record, identity))
        if key in compiled:
            raise RegistryValidationError(f"runtime catalogue member {member!r} repeats key {key!r}")
        compiled[key] = record
    return compiled


def _territories(document: Mapping[str, object]) -> dict[str, SpanishPostalTerritory]:
    rows = document.get("territory")
    if not isinstance(rows, list) or not rows:
        raise RegistryValidationError("runtime territory catalogue must be a non-empty array")
    compiled: dict[str, SpanishPostalTerritory] = {}
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise RegistryValidationError("runtime territory catalogue contains a non-table row")
        record = SpanishPostalTerritory.model_validate(_immutable_toml(raw))
        for prefix in record.postal_prefixes:
            if prefix in compiled:
                raise RegistryValidationError(f"runtime territory catalogue repeats postal prefix {prefix!r}")
            compiled[prefix] = record
    return compiled


def _regulations(document: Mapping[str, object]) -> dict[str, PublishedIvaRegulation]:
    rows = document.get("regulations")
    if not isinstance(rows, list) or not rows:
        raise RegistryValidationError("runtime IVA catalogue must contain regulations")
    compiled: dict[str, PublishedIvaRegulation] = {}
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise RegistryValidationError("runtime IVA catalogue contains a non-table regulation")
        citations = raw.get("citations", [])
        if not isinstance(citations, list):
            raise RegistryValidationError("runtime IVA regulation citations must be an array")
        record = PublishedIvaRegulation.model_validate(
            _immutable_toml(
                {
                    **raw,
                    "citations": [
                        {**citation, "grounding": citation.get("grounding", "verified")}
                        if isinstance(citation, Mapping)
                        else citation
                        for citation in citations
                    ],
                }
            )
        )
        if record.category in compiled:
            raise RegistryValidationError(f"runtime IVA catalogue repeats category {record.category!r}")
        compiled[record.category] = record
    return compiled


def _recargo_bands(document: Mapping[str, object]) -> dict[str, PublishedRecargoBand]:
    rows = document.get("band")
    if not isinstance(rows, list) or not rows:
        raise RegistryValidationError("runtime recargo catalogue must contain bands")
    compiled: dict[str, PublishedRecargoBand] = {}
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise RegistryValidationError("runtime recargo catalogue contains a non-table band")
        try:
            surcharge = Decimal(str(raw.get("surcharge_pct")))
        except (InvalidOperation, ValueError) as exc:
            raise RegistryValidationError("runtime recargo band has an invalid surcharge") from exc
        record = PublishedRecargoBand.model_validate({**raw, "surcharge_pct": surcharge})
        if record.id in compiled:
            raise RegistryValidationError(f"runtime recargo catalogue repeats band {record.id!r}")
        compiled[record.id] = record
    return compiled


def _immutable_toml(value: object) -> object:
    """Freeze TOML arrays before strict registry-model validation."""
    if isinstance(value, Mapping):
        return {str(key): _immutable_toml(item) for key, item in value.items()}
    if isinstance(value, list):
        return tuple(_immutable_toml(item) for item in value)
    return value
