"""Art. 81 LIRPF deducción maternidad computation helpers.

Pure-domain arithmetic; no entrypoint or CLI dependencies.
:func:`compute_deduccion_maternidad_0611` reads its dated operands from the
governed-facts authority and derives the raised post-birth alta cap from the
ordinary cap plus the applicable increment.
"""

from __future__ import annotations

from collections.abc import Container
from datetime import date

from ..calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority
from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.facts.resolution import (
    MappingFactQuery,
    ResolvedMappingFact,
    ResolvedScalarFact,
    ScalarFactQuery,
)
from ..calculations.registry.schema_base import DateAxis

_MATERNIDAD_FORMULA_SPEC_ID = "lirpf-art-81-maternity-formula-spec"
_REQUIRED_FORMULA_SPEC_KEYS = frozenset(
    {
        "formula.monthly_amount_fact_id",
        "formula.annual_cap_fact_id",
        "formula.increment_fact_id",
        "formula.increment_effective_year_fact_id",
    }
)


def _resolve_maternidad_formula_spec(
    filing_year: int,
) -> tuple[ValidatedRegistryAuthority, date, dict[str, str]]:
    """Resolve and validate the dated mapping that names maternity operands."""
    effective_date = date(filing_year, 12, 31)
    authority = bundled_authority()
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_MATERNIDAD_FORMULA_SPEC_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        )
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("maternity formula specification must resolve as a mapping fact")

    declarations: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if type(entry.key) is not str or type(entry.value) is not str:
            raise RegistryValidationError("maternity formula specification entries must be strings")
        key = entry.key.strip()
        value = entry.value.strip()
        if not key or not value or key != entry.key or value != entry.value:
            raise RegistryValidationError("maternity formula specification contains blank or padded entries")
        if key in declarations:
            raise RegistryValidationError(f"maternity formula specification repeats key {key!r}")
        declarations[key] = value

    missing = _REQUIRED_FORMULA_SPEC_KEYS - declarations.keys()
    if missing:
        raise RegistryValidationError(
            f"maternity formula specification is missing required keys {sorted(missing)!r}"
        )
    return authority, effective_date, declarations


def _resolve_maternidad_scalar(
    authority: ValidatedRegistryAuthority,
    fact_id: str,
    effective_date: date,
) -> int:
    """Resolve one named integer operand at the mapping's exact coordinate."""
    resolved = authority.resolve_governed_fact(
        ScalarFactQuery(
            fact_id=fact_id,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        )
    )
    if not isinstance(resolved, ResolvedScalarFact):
        raise RegistryValidationError(f"maternity operand {fact_id!r} did not resolve as a scalar fact")
    value = resolved.payload.value
    if type(value) is not int:
        raise RegistryValidationError(f"maternity operand {fact_id!r} must resolve as an integer")
    return value


def _resolve_maternidad_figure(filing_year: int, slug: str) -> int:
    """Read one Art. 81.1 figure from the published authority.

    The mapping specification names the typed governed facts. Consume that
    specification and each named scalar at their exact filing coordinate; an
    absent coordinate is a registry validation failure rather than a reason to
    read a parallel parameter copy.

    Returns:
        The integer euro figure the registry declares for ``filing_year``.
    """
    key_by_slug = {
        "mensual": "formula.monthly_amount_fact_id",
        "cap-anual": "formula.annual_cap_fact_id",
        "alta-posterior-incremento": "formula.increment_fact_id",
    }
    try:
        mapping_key = key_by_slug[slug]
    except KeyError as exc:
        raise RegistryValidationError(f"unknown maternity figure {slug!r}") from exc
    authority, effective_date, declarations = _resolve_maternidad_formula_spec(filing_year)
    return _resolve_maternidad_scalar(authority, declarations[mapping_key], effective_date)


def _resolve_alta_posterior_increment(filing_year: int) -> int | None:
    """Return the increment, or ``None`` only when its dated declaration excludes it.

    The effective-year scalar is resolved through the mapping specification.
    Missing or malformed declarations remain registry failures.

    Returns:
        The increment for ``filing_year``, or ``None`` when none applies.
    """
    authority, effective_date, declarations = _resolve_maternidad_formula_spec(filing_year)
    effective_year = _resolve_maternidad_scalar(
        authority,
        declarations["formula.increment_effective_year_fact_id"],
        effective_date,
    )
    if filing_year < effective_year:
        return None
    return _resolve_maternidad_scalar(authority, declarations["formula.increment_fact_id"], effective_date)


def compute_deduccion_maternidad_0611(
    meses_por_hijo: list[tuple[str, int]],
    *,
    filing_year: int,
    alta_posterior_hijos: Container[str] = frozenset(),
) -> int:
    """Compute Art. 81 LIRPF deducción maternidad from per-hijo meses pairs.

    The ordinary formula multiplies each child's eligible months by the dated
    monthly parameter and caps it at the dated annual parameter.

    A ``hijo_id`` named in *alta_posterior_hijos* additionally receives the Art.
    81.1 post-birth alta increment for the one calendar month completing the
    30-day minimum contribution period, ONLY for *filing_year* from
    a revision that declares the increment: its total adds that increment on top of the ordinary
    monthly accrual (the completion month is counted once at the ordinary rate,
    already inside ``meses``, and once again here), and its cap is raised to
    derived annual cap. Every other pair, and
    every pair for an earlier filing year, keeps the ordinary rate and cap
    untouched — the increment can only ever ADD to a hijo's total, never
    substitute for it.

    Returns an integer euros amount.
    """
    mensual = _resolve_maternidad_figure(filing_year, "mensual")
    cap_anual = _resolve_maternidad_figure(filing_year, "cap-anual")
    increment = _resolve_alta_posterior_increment(filing_year)
    total = 0
    for hijo_id, meses in meses_por_hijo:
        importe = meses * mensual
        cap = cap_anual
        if increment is not None and hijo_id in alta_posterior_hijos:
            importe += increment
            # The raised cap is DERIVED from its two inputs rather than stored,
            # so it cannot drift away from them the way an independent literal
            # would.
            cap = cap_anual + increment
        total += min(importe, cap)
    return total
