"""Modelo 210 IRNR treaty-rate resolution helpers.

The registry formula runtime computes the filing values and emits typed
unresolved outcomes when a Modelo 210 rate cannot be applied directly. This
application helper replays the same single tipo-de-gravamen resolution path over a
:class:`~cadrumo.domain.calculations.registry.RegistrySnapshot`: it reads the
``m210-tipo-gravamen-2025`` baseline table, consults the cross-cutting
:class:`~cadrumo.domain.calculations.registry.ConvenioAuthority` treaty projection for
the profile's ``country_of_fiscal_residence``, and returns either a scalar IRNR
rate or blocking :class:`~ModeloVerificationFinding` records for
deferred baseline coverage or missing treaty rows.

Base-dependent branches — the ``allocation_domestic_tariff`` pension delegation and
the pension ``ceiling`` — return ``(None, [])`` because the live base-aware tariff
path in the registry runtime remains the calculation authority; the sweep keeps the
runtime-computed effective rate for those.

See Also:
    :mod:`cadrumo.domain.calculations.registry.formula_runtime`
        Formula-runtime implementation of ``irnr_resolve_tipo_gravamen`` and the
        typed M210 unresolved outcomes this application layer converts into findings.
    :func:`cadrumo.application.modelo.verification_actions.verify_modelo_revision`
        Verification path that replays this resolver for Modelo 210 observations.
    :mod:`cadrumo.application.calculations.tests.test_modelo_210_irnr_continuity`
        Cross-renta enrollment coverage for the registry-backed M210 engine.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.decimal.constants import ZERO
from ...core.irnr import ConvenioOverrideKind, TipoRentaIrnr
from ...domain.calculations.registry.convenio import ConvenioOverride
from ...domain.calculations.registry.ids import (
    LegalRefId,
    SourceRefId,
)
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.deadlines.models import TaxpayerProfile
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)

if TYPE_CHECKING:
    from ...core.casilla_id import CasillaId
    from ...domain.calculations.registry.schema_formula import ParameterDefinition


def _m210_blocking_finding(
    *,
    casilla_id: CasillaId | None,
    reason_code: str,
    message_facts: dict[str, str | int],
    legal_refs: tuple[LegalRefId, ...],
    source_refs: tuple[SourceRefId, ...],
) -> ModeloVerificationFinding:
    """Build a BLOCKING_RULE M210 rate finding with the shared severity/kind.

    The returned :class:`~ModeloVerificationFinding` is the
    application-facing companion to the formula-runtime unresolved outcome:
    callers surface it to the operator instead of letting an unavailable M210
    rate silently produce filing output.
    """
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        casilla_id=casilla_id,
        message_locale_key="application.modelo.findings.m210_rate_unavailable",
        message_facts={"reason_code": reason_code, **message_facts},
        legal_refs=legal_refs,
        source_refs=source_refs,
    )


def _resolve_baseline_rate(
    baseline_param: ParameterDefinition,
    tipo_renta: str,
    year: int,
) -> tuple[Decimal | None, bool]:
    """Find the baseline rate for ``(tipo_renta, year)``.

    Returns ``(rate, ok)``: ``ok`` is False only when a matching bracket was
    found but its value failed to parse as a :class:`~decimal.Decimal` (the
    caller then short-circuits to ``(None, [])``). A simply-absent bracket
    returns ``(None, True)``.
    """
    for entry in baseline_param.keyed_brackets:
        if (
            entry.key == tipo_renta
            and entry.valid_from.year <= year
            and (entry.valid_to is None or entry.valid_to.year >= year)
        ):
            try:
                return Decimal(entry.value), True
            except (ArithmeticError, ValueError):
                return None, False
    return None, True


def _resolve_convenio_override(
    snapshot: RegistrySnapshot,
    baseline_param: ParameterDefinition,
    *,
    country_code: str,
    tipo_renta: str,
    year: int,
    baseline_rate: Decimal | None,
    casilla_id: CasillaId | None,
) -> tuple[Decimal | None, list[ModeloVerificationFinding]]:
    """Resolve the treaty override rate for a treaty-country profile.

    Reads the cross-cutting :class:`~cadrumo.domain.calculations.registry.ConvenioAuthority`
    projected onto the snapshot and branches on the typed
    :class:`~cadrumo.core.ConvenioOverrideKind`. Emits the
    ``m210-convenio-rate-missing`` BLOCKING finding when the treaty carries no
    row for the filed income type. Base-dependent kinds
    (``allocation_domestic_tariff``, pension ``ceiling``) return ``(None, [])`` so
    the base-aware tariff branch in the registry runtime remains the calculation
    authority.
    """
    override: ConvenioOverride | None = None
    try:
        tipo_enum = TipoRentaIrnr(tipo_renta)
    except ValueError:
        tipo_enum = None
    if tipo_enum is not None:
        override = snapshot.convenio.resolve(country_code, tipo_enum, year)

    legal_refs: tuple[LegalRefId, ...] = tuple(baseline_param.legal_refs)
    source_refs: tuple[SourceRefId, ...] = tuple(baseline_param.source_refs)

    if override is None:
        finding = _m210_blocking_finding(
            casilla_id=casilla_id,
            reason_code="convenio_rate_missing",
            message_facts={
                "country_code": country_code,
                "tipo_renta_code": tipo_renta,
                "filing_year": year,
            },
            legal_refs=legal_refs,
            source_refs=source_refs,
        )
        return None, [finding]

    if override.kind is ConvenioOverrideKind.EXEMPT:
        return ZERO, []
    if override.kind is ConvenioOverrideKind.FLAT and override.rate is not None:
        return override.rate, []
    if override.kind is ConvenioOverrideKind.CEILING and override.rate is not None:
        if baseline_rate is None:
            return None, []
        return min(baseline_rate, override.rate), []
    # ALLOCATION_DOMESTIC_TARIFF: base-aware; the runtime tariff branch is authority.
    return None, []


def _has_live_pension_tariff(snapshot: RegistrySnapshot, year: int) -> bool:
    """Return whether the snapshot contains an applicable M210 pension tariff table."""
    for parameter in snapshot.revision.parameters:
        if parameter.id != "m210-pension-tarifa-2025" or parameter.data_type != "bracket_table":
            continue
        return any(
            bracket.valid_from.year <= year and (bracket.valid_to is None or bracket.valid_to.year >= year)
            for bracket in parameter.brackets
        )
    return False


def resolve_m210_rate(
    profile: TaxpayerProfile,
    tipo_renta: str,
    year: int,
    snapshot: RegistrySnapshot,
    *,
    casilla_id: CasillaId | None = None,
) -> tuple[Decimal | None, list[ModeloVerificationFinding]]:
    """Resolve the M210 rate for (profile, tipo_renta, year).

    The :class:`~cadrumo.domain.calculations.registry.RegistrySnapshot` supplies the
    ``m210-tipo-gravamen-2025`` baseline table and the cross-cutting
    :class:`~cadrumo.domain.calculations.registry.ConvenioAuthority`; the
    :class:`~cadrumo.domain.deadlines.TaxpayerProfile` supplies
    ``country_of_fiscal_residence`` for treaty lookup. Returns ``(rate,
    findings)`` where ``findings`` contains blocking
    :class:`~ModeloVerificationFinding` records when a
    required rate is deferred or unavailable.

    A profile with no treaty country uses the baseline table. A profile with a
    treaty country must match a treaty override for ``(country, tipo_renta)``
    unless the override delegates back to the domestic tariff. The resolver
    returns no scalar rate for base-dependent branches because those depend on
    the actual base amount and are computed by the formula runtime.

    See Also:
        :func:`cadrumo.domain.calculations.registry.formula_runtime_irnr.evaluate_irnr_resolve_tipo_gravamen`
        :class:`cadrumo.domain.calculations.registry.ConvenioAuthority`
        :class:`cadrumo.domain.deadlines.TaxpayerProfile`
    """
    baseline_param = None
    for parameter in snapshot.revision.parameters:
        if parameter.id == "m210-tipo-gravamen-2025":
            baseline_param = parameter
            break

    if baseline_param is None:
        return None, []

    baseline_rate, baseline_ok = _resolve_baseline_rate(baseline_param, tipo_renta, year)
    if not baseline_ok:
        return None, []

    treaty_country = profile.country_of_fiscal_residence
    if treaty_country is None:
        if baseline_rate is None:
            if tipo_renta == TipoRentaIrnr.PENSION.value and _has_live_pension_tariff(snapshot, year):
                return None, []
            finding = _m210_blocking_finding(
                casilla_id=casilla_id,
                reason_code="baseline_rate_unavailable",
                message_facts={
                    "tipo_renta_code": tipo_renta,
                    "filing_year": year,
                },
                legal_refs=tuple(baseline_param.legal_refs),
                source_refs=tuple(baseline_param.source_refs),
            )
            return None, [finding]
        return baseline_rate, []

    return _resolve_convenio_override(
        snapshot,
        baseline_param,
        country_code=treaty_country.upper(),
        tipo_renta=tipo_renta,
        year=year,
        baseline_rate=baseline_rate,
        casilla_id=casilla_id,
    )
