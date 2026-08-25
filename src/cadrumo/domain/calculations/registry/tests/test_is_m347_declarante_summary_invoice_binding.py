"""``is_m347_declarante_summary_invoice_binding`` reads the typed selector, and refuses drift.

``application/invoices/_source_resolver.py`` used to carry its own copy of the
``"m347_declarante_summary"`` literal and read it via
``selector_as_dict(binding).get("record") == _M347_DECLARANTE_SUMMARY_RECORD``.
:class:`_InvoiceSelector` already validates every invoice-source binding's
selector at registry build time, so in production the raw ``.get()`` default
of ``None`` meant only "this binding's selector does not declare a record" --
a real, correct fact for the many invoice bindings that are not the M347
summary. But the raw read could not distinguish that from a RENAMED
``record`` field: a rename would silently, permanently misclassify the real
M347 declarante-summary binding as a non-summary binding on every call,
narrowing ``_invoice_sources_for_revision`` to the modelo's declared source
set even when the summary construct needs the wider set -- with no error at
all.

The canonical predicate is defined once in
``domain/calculations/registry/_invoice_bindings.py`` (the family module that
already owns ``_M347_DECLARANTE_SUMMARY_RECORD`` and the typed
``_InvoiceSelector``), reads through the typed selector, and is now the
single call site both the registry's own internal invariant checks and
``application/invoices/_source_resolver.py`` use -- no duplicate literal, no
duplicate raw read.
"""

from __future__ import annotations

import pytest

from ..errors import RegistryValidationError
from ..invoice_bindings import is_m347_declarante_summary_invoice_binding
from ..schema import DataBindingDefinition
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _modelo_347_revision():
    modelo, _catalogues = _committed_modelo("347")
    return modelo.revisions["2011-2024"]


_M347_COUNT_BINDING = "modelo-347-declarante-numero-personas-entidades"


def test_the_real_committed_m347_summary_binding_is_recognised() -> None:
    """The real, currently-shipped M347 declarante-summary binding is recognised."""
    revision = _modelo_347_revision()
    bindings = {binding.id: binding for binding in revision.bindings}

    assert is_m347_declarante_summary_invoice_binding(bindings[_M347_COUNT_BINDING]) is True


def test_an_ordinary_invoice_binding_with_no_record_is_not_the_summary() -> None:
    """Anti-tautology companion: not every invoice-source binding is the M347 summary.

    The real committed M347 revision declares exactly two invoice bindings,
    and BOTH are the declarante-summary pair (count and amount share the same
    ``record``) -- so a "non-summary invoice binding" negative case needs a
    binding this revision does not itself carry. Built the same way
    ``test_boolean_binding_encoding.py``'s non-boolean negative case is: a
    plausible, law-grounded ``DataBindingDefinition`` declaring an invoice
    fact with NO ``record`` at all, matching the shape a per-transaction
    (non-summary) invoice binding actually declares. Without this, a
    predicate that returned True unconditionally for any invoice-source
    binding would pass the test above and look correct.
    """
    ordinary = DataBindingDefinition.model_validate(
        {
            "id": "modelo-303-iva-devengada-base-sum",
            "source": "collectible_invoice",
            "selector": {"fact": "base_sum"},
            "aggregation": {"op": "sum"},
            "legal_refs": ("ley-37-1992:art-164",),
            "source_refs": ("aeat-dr-303-2025",),
        },
    )

    assert is_m347_declarante_summary_invoice_binding(ordinary) is False


def test_a_non_invoice_binding_is_never_the_summary() -> None:
    """A binding from a different source family is never this predicate's business."""
    non_invoice = DataBindingDefinition.model_validate(
        {
            "id": "renta-2025-profile-tax-residence-ccaa",
            "source": "profile",
            "selector": {
                "profile_model": "TaxResidenceProfile",
                "field": "ccaa",
                "xsd_attribute": "codigoCADeclaracion",
                "dictionary_field": "ZCCAD",
            },
            "aggregation": {"op": "copy"},
            "typed_enum": "CCAA",
            "legal_refs": ("orden-hac-277-2026:art-3",),
            "source_refs": ("aeat-dr-100-2025-dictionary",),
        },
    )

    assert is_m347_declarante_summary_invoice_binding(non_invoice) is False


def test_a_renamed_record_field_is_refused_not_silently_read_as_non_summary() -> None:
    """The bite proof: a selector shape the model rejects must raise, not silently read False.

    The real M347 summary binding's selector is mutated to rename ``record``
    to ``recrd`` via ``object.__setattr__`` on the FROZEN
    :class:`DataBindingDefinition` -- construction-time validation already
    proved a genuinely malformed selector cannot reach this function via the
    normal constructor, so mutating a REAL, already-validated instance is
    what stands in for a drifted ``_InvoiceSelector`` schema: the fixed
    function's OWN validation (not the constructor's) is what is under test.
    """
    revision = _modelo_347_revision()
    shared = {binding.id: binding for binding in revision.bindings}[_M347_COUNT_BINDING]
    # Mutate a COPY, never the shared instance. `_modelo_347_revision()` is
    # cached, so writing through `object.__setattr__` on the binding it returns
    # left every later test that loads modelo 347 looking at a selector carrying
    # `recrd`: this module passed alone and took five sibling cases down with it
    # whenever it ran first, which reads as a defect in THOSE modules.
    #
    # The argument the mutation stands on is unchanged. `model_copy` does not
    # revalidate, so the drifted shape still cannot come from the constructor,
    # and the copy is a real, already-validated instance.
    binding = shared.model_copy()
    drifted_selector = dict(binding.selector)
    drifted_selector["recrd"] = drifted_selector.pop("record")
    object.__setattr__(binding, "selector", drifted_selector)

    with pytest.raises(RegistryValidationError, match="malformed invoice selector"):
        is_m347_declarante_summary_invoice_binding(binding)
