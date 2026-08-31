"""M349's row resolution is byte-identical after the contraparte_clave extension.

The extension moved the ``_InvoiceSelector.claves`` membership check from a
FIELD validator to a ``model_validator(mode="after")`` (grouping determines
which clave vocabulary applies, and a field validator cannot see a sibling
field), and gave ``_filter_invoice_observations`` a branch on ``grouping``.
Both changes route every M349 selector/observation through code M349 did not
touch before. Unlike ``test_invoice_bindings.py``'s existing coverage (which
overrides selectors via ``_with_selector`` for isolated scenarios), this
module uses the REAL, UNMODIFIED committed modelo 349 bindings and a real
bundled revision, so the row output pinned here is the actual production
wiring's output, not a synthetic stand-in.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.aggregation import BindingSourceKind
from ..errors import RegistryValidationError
from ..invoice_bindings import (
    InvoiceObservation,
    resolve_invoice_binding_row_values,
    validate_invoice_binding_definition,
)
from ..schema import ModeloRevision
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _modelo_349_revision() -> ModeloRevision:
    modelo, _catalogues = _committed_modelo("349")
    return modelo.revisions["2020-y-siguientes"]


def _adquisicion_observation(*, party: str, country: str, name: str, base: str, clave: str) -> InvoiceObservation:
    return InvoiceObservation(
        source_kind=BindingSourceKind.PAYABLE_INVOICE,
        invoice_id=f"inv-{party}-{base}",
        party_tax_id=party,
        country_code=country,
        party_legal_name=name,
        transaction_date=date(2026, 3, 15),
        base_amount=Decimal(base),
        intracommunity_clave=clave,
        is_rectification=False,
    )


def test_the_real_committed_operador_adquisicion_bindings_produce_the_same_rows_unmodified() -> None:
    """Pinned wiring proof: the exact, unmodified 2020-y-siguientes operador bindings.

    This is a schema/wiring pin (which binding gets which row value, at which
    row index), not a tax-law-derived figure -- the same class of proof
    ``test_resolve_invoice_binding_row_values_groups_by_operator_and_clave_
    summing_bases`` already uses for a selector-overridden variant. Here the
    revision and its bindings are used exactly as committed.
    """
    revision = _modelo_349_revision()
    observations = (
        _adquisicion_observation(party="DE111111111", country="DE", name="Deutschland GmbH", base="1000.00", clave="A"),
        _adquisicion_observation(party="DE111111111", country="DE", name="Deutschland GmbH", base="500.00", clave="A"),
        _adquisicion_observation(party="IT12345678901", country="IT", name="Italia SRL", base="200.00", clave="I"),
    )

    resolved = resolve_invoice_binding_row_values(revision, observations)

    # Groups sorted by (country_code, party_tax_id, clave): (DE, DE111111111, A), (IT, IT222222222, I)
    assert resolved["iva-349-operador-row-codigo-pais-adquisicion", 1] == "DE"
    assert resolved["iva-349-operador-row-nif-adquisicion", 1] == "111111111"
    assert resolved["iva-349-operador-row-apellidos-adquisicion", 1] == "Deutschland GmbH"
    assert resolved["iva-349-operador-row-clave-adquisicion", 1] == "A"
    assert resolved["iva-349-operador-row-base-adquisicion", 1] == Decimal("1500.00")
    assert resolved["iva-349-operador-row-codigo-pais-adquisicion", 2] == "IT"
    assert resolved["iva-349-operador-row-nif-adquisicion", 2] == "12345678901"
    assert resolved["iva-349-operador-row-apellidos-adquisicion", 2] == "Italia SRL"
    assert resolved["iva-349-operador-row-clave-adquisicion", 2] == "I"
    assert resolved["iva-349-operador-row-base-adquisicion", 2] == Decimal("200.00")


def test_an_invalid_m349_clave_still_refuses_through_the_relocated_validator() -> None:
    """The exact property the validator relocation moved: pin the refusal, not just its absence.

    ``Q`` is not a real AEAT clave de operacion for either vocabulary, so
    this proves the CLOSED-SET check itself (now a model validator, moved
    off the ``claves`` field validator) still fires for M349's own
    selectors, rather than merely proving the selector still parses.
    Constructor-time validation already proves a genuinely malformed
    selector cannot reach this shape via the normal constructor (mirroring
    ``test_is_m347_declarante_summary_invoice_binding.py``'s bite proof), so
    a REAL, already-validated binding is mutated via ``object.__setattr__``
    to stand in for a drifted selector, and the fixed function's OWN
    validation is what is under test.
    """
    revision = _modelo_349_revision()
    real_binding = next(item for item in revision.bindings if item.id == "iva-349-operador-row-codigo-pais-adquisicion")
    binding = real_binding.model_copy()
    drifted_selector = dict(binding.selector)
    drifted_selector["claves"] = ("A", "I", "T", "Q")
    object.__setattr__(binding, "selector", drifted_selector)

    with pytest.raises(RegistryValidationError, match="has malformed invoice selector"):
        validate_invoice_binding_definition(binding)
