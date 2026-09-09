"""Governed-fact projections of selected global legal parameters."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .....core.directory_scan import DirectoryEntryKind, scan_directory
from ..errors import RegistryValidationError
from ..loader import load_legal_parameters_only
from ..loader_cache import toml_file_fingerprint
from ..loader_fingerprints import RegistryPathFingerprints
from ..schema_base import DateAxis
from ..schema_references import LegalParameter
from .schema import (
    EntitySetFactPayload,
    FactOwnership,
    GovernedFact,
    GovernedFactFamily,
    GovernedFactVariant,
    ScalarFactPayload,
)

LEGAL_PARAMETER_PROVIDER_ID = "global-legal-parameters"
LEGAL_PARAMETER_PROVIDER_DIRECTORY = "legal"

_ENTITY_SET_PARAMETER_IDS = frozenset(
    {
        "rirpf-art-95:selector-m036-actividades-profesionales",
        "rirpf-art-95:selector-m036-actividades-agricolas-ganaderas",
        "rirpf-art-95:selector-m036-actividades-forestales",
        "rirpf-art-95:selector-m036-actividades-ganaderas-engorde-porcino-avicultura",
    }
)
_SCALAR_PARAMETER_IDS = frozenset(
    {
        "liva-art-161:recargo-rate-general",
        "liva-art-161:recargo-rate-reducido",
        "liva-art-161:recargo-rate-super-reducido",
        "liva-art-161:recargo-rate-tabaco",
        "rirpf-art-95:retencion-actividades-profesionales-general",
        "rirpf-art-95:retencion-actividades-profesionales-inicio",
        "rirpf-art-95:retencion-actividades-agricolas-ganaderas-general",
        "rirpf-art-95:retencion-actividades-ganaderas-engorde-porcino-avicultura",
        "rirpf-art-95:retencion-actividades-forestales",
        "rirpf-art-95:retencion-actividades-estimacion-objetiva",
        "lirpf-art-101:retencion-administrador-general",
        "lirpf-art-101:retencion-administrador-reducida",
        "lirpf-art-101:retencion-administrador-incn-umbral-eur",
        "lirpf-dt-32:eo-exclusion-rendimientos-conjunto-eur",
        "lirpf-dt-32:eo-exclusion-rendimientos-factura-eur",
        "lirpf-art-31:eo-exclusion-rendimientos-agricolas-ganaderos-forestales-eur",
        "lirpf-dt-32:eo-exclusion-compras-eur",
    }
)
LEGAL_PARAMETER_FACT_IDS = _SCALAR_PARAMETER_IDS | _ENTITY_SET_PARAMETER_IDS


def compile_legal_parameter_facts(registry_root: Path) -> tuple[GovernedFact, ...]:
    """Project the selected parameters without moving or copying their authority."""
    parameters = load_legal_parameters_only(registry_root.resolve())
    missing = sorted(LEGAL_PARAMETER_FACT_IDS - parameters.keys())
    if missing:
        raise RegistryValidationError(f"global legal-parameter provider is missing ids {missing!r}")
    return tuple(_parameter_fact(parameters[parameter_id]) for parameter_id in sorted(LEGAL_PARAMETER_FACT_IDS))


def collect_legal_parameter_fact_fingerprints(registry_root: Path) -> RegistryPathFingerprints:
    """Fingerprint the complete legal catalogue parsed by the projection adapter."""
    legal_root = registry_root.resolve() / LEGAL_PARAMETER_PROVIDER_DIRECTORY
    return tuple(
        toml_file_fingerprint(path.resolve())
        for path in scan_directory(legal_root, pattern="*.toml", select=DirectoryEntryKind.FILES)
    )


def reset_legal_parameter_fact_provider() -> None:
    """Reset hook for the uncached legal-only loader."""


def _parameter_fact(parameter: LegalParameter) -> GovernedFact:
    if parameter.id in _ENTITY_SET_PARAMETER_IDS:
        family = GovernedFactFamily.ENTITY_SET
        payload = EntitySetFactPayload(entities=frozenset(item for item in parameter.value.split(",") if item))
    else:
        family = GovernedFactFamily.SCALAR
        try:
            value = Decimal(parameter.value)
        except InvalidOperation as exc:
            raise RegistryValidationError(f"global legal parameter {parameter.id!r} is not a decimal scalar") from exc
        payload = ScalarFactPayload(value=value, unit=parameter.unit)
    return GovernedFact(
        fact_id=parameter.id,
        family=family,
        variants=(
            GovernedFactVariant(
                variant_id=f"{parameter.id}.current",
                date_axis=DateAxis.FILING_PERIOD,
                valid_from=date.min,
                payload=payload,
                legal_refs=parameter.legal_refs,
                review_status=parameter.review_status,
                ownership=FactOwnership.GENERATED,
            ),
        ),
    )


__all__ = [
    "LEGAL_PARAMETER_FACT_IDS",
    "LEGAL_PARAMETER_PROVIDER_DIRECTORY",
    "LEGAL_PARAMETER_PROVIDER_ID",
    "collect_legal_parameter_fact_fingerprints",
    "compile_legal_parameter_facts",
    "reset_legal_parameter_fact_provider",
]
