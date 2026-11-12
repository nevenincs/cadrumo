"""Retencion clave vocabulary projected from the governed withholding catalogue."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Final

from ....core.aggregation import RetencionClave
from .errors import RegistryValidationError
from .governed_fact_scope import GovernedFactSource, require_governed_fact_authority

__all__ = ["resolve_retencion_clave", "retencion_clave_declarations"]

_RETENCION_CLAVE_FACT_ID: Final[str] = "m111-m115-m123-withholding-scheme-catalogue"


def retencion_clave_declarations(
    effective_date: date,
    *,
    authority: GovernedFactSource | None = None,
) -> dict[str, str]:
    """Resolve the complete clave vocabulary and projections from the catalogue."""
    from .facts.resolution import MappingFactQuery, ResolvedMappingFact
    from .schema_base import DateAxis

    selected_authority = require_governed_fact_authority(authority, subject="retencion clave catalogue")
    resolved = selected_authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_RETENCION_CLAVE_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("retencion clave catalogue must resolve as a mapping fact")
    declarations: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("retencion clave catalogue entries must be string mappings")
        if entry.key in declarations:
            raise RegistryValidationError(f"duplicate retencion clave declaration {entry.key!r}")
        declarations[entry.key] = entry.value
    return declarations


def resolve_retencion_clave(
    value: str,
    effective_date: date,
    *,
    modelo: str | None = None,
    authority: GovernedFactSource | None = None,
) -> RetencionClave:
    """Project one raw clave through the selected registry vocabulary.

    Membership, canonical value, and model applicability are all authored in
    the withholding catalogue.  The projection intentionally fails closed when
    any declaration is missing or inconsistent; it never turns an unknown raw
    token into a core value.
    """
    if not isinstance(value, str) or not value:
        raise RegistryValidationError("retencion clave must be a non-empty string")
    if not isinstance(effective_date, date):
        raise RegistryValidationError("retencion clave requires a filing-period date")

    declarations = retencion_clave_declarations(effective_date, authority=authority)
    order = _retencion_clave_order(declarations)
    if value not in order:
        raise RegistryValidationError(f"retencion clave {value!r} is not declared by the selected catalogue")
    applicable_models = _retencion_clave_models_for_order(value, order, declarations)
    if modelo is not None and modelo not in applicable_models:
        raise RegistryValidationError(
            f"retencion clave {value!r} is not applicable to Modelo {modelo!r}",
        )
    return RetencionClave.from_registry(value)


def _retencion_clave_order(declarations: Mapping[str, str]) -> tuple[str, ...]:
    order_text = declarations.get("clave_order")
    if order_text is None:
        raise RegistryValidationError("retencion clave catalogue is missing clave_order")
    order = tuple(token.strip() for token in order_text.split(",") if token.strip())
    if not order or len(order) != len(set(order)):
        raise RegistryValidationError("retencion clave catalogue has an invalid clave_order")
    return order


def _retencion_clave_models_for_order(
    selected_value: str,
    order: tuple[str, ...],
    declarations: Mapping[str, str],
) -> tuple[str, ...]:
    applicable_models: tuple[str, ...] = ()
    for token in order:
        models = _retencion_clave_declared_models(token, declarations)
        if token == selected_value:
            applicable_models = models
    return applicable_models


def _retencion_clave_declared_models(token: str, declarations: Mapping[str, str]) -> tuple[str, ...]:
    declared_value = declarations.get(f"clave.{token}.value")
    if declared_value != token:
        raise RegistryValidationError(f"retencion clave {token!r} has no matching canonical value declaration")
    model_text = declarations.get(f"clave.{token}.modelos")
    models = tuple(item.strip() for item in (model_text or "").split(",") if item.strip())
    if not models or len(models) != len(set(models)):
        raise RegistryValidationError(f"retencion clave {token!r} has invalid model applicability")
    return models
