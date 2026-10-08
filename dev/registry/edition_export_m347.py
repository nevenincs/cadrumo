"""Populated Modelo 347 export inputs resolved from fictional invoices."""

from datetime import date

from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.calculations.registry.invoice_bindings import (
    resolve_invoice_binding_row_values,
    resolve_invoice_binding_values,
)
from cadrumo.domain.filing.protocols import ModeloInputs, ModeloInputScalar, ModeloInputValue

from .compiler.authority import compiled_bundled_authority
from .workbook_demo_third_parties import third_party_observations


def third_party_export_inputs(period: Period) -> ModeloInputs:
    """Exercise purchases, sales and threshold exclusion, without property records."""
    authority = compiled_bundled_authority()
    snapshot = authority.snapshot("347", filing_year=period.filing_year, period=period.registry_token)
    observations = tuple(
        row for row in third_party_observations(period.filing_year) if not row.arrendamiento_local_negocio
    )
    effective_date = date(period.filing_year, 12, 31)
    with validating_governed_facts(authority):
        inputs: dict[str, ModeloInputValue] = dict(
            resolve_invoice_binding_values(snapshot.revision, observations, effective_date=effective_date)
        )
        rows: dict[str, dict[str, ModeloInputScalar]] = {}
        for (binding, index), value in resolve_invoice_binding_row_values(
            snapshot.revision, observations, effective_date=effective_date
        ).items():
            rows.setdefault(binding, {})[str(index)] = value
    inputs.update(rows)
    inputs["decl.ejercicio"] = period.filing_year
    return inputs
