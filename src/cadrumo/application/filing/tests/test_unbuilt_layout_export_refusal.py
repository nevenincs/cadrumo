"""A modelo with no complete export layout refuses before creating an artefact.

Modelo 111's fixed-width fichero-BOE layout has never been built (its record
design still names producer fields with no canonical typed producer
authority). Nothing about this is an AEAT-side withdrawal; the layout simply
does not exist yet, and ``export_draft`` refuses honestly rather than writing
a partial artefact.
"""

from pathlib import Path

import pytest

from ....core import Modelo, PaymentElection, PriorDomiciliationElection, RefundElection, ResultDisposition
from .. import (
    FilingElectionFacts,
    Modelo111ProfileFacts,
    PresenterIdentity,
    TaxpayerIdentityFacts,
    build_filing_producer_snapshot,
    export_draft,
)
from .._export import FilingExportError
from ._export_support import _approved_modelo_111_registry_draft, _schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_a_modelo_with_no_export_layout_refuses_before_writing_output(tmp_path: Path) -> None:
    snapshot = build_filing_producer_snapshot(
        modelo=Modelo.M111,
        taxpayer_tax_id="12345678Z",
        taxpayer_identity=TaxpayerIdentityFacts(
            legal_name=None,
            given_name="Ana",
            surnames="Prueba",
            full_name="Ana Prueba",
        ),
        presenter=PresenterIdentity(tax_id="00000000T", full_name="Gestoría Prueba"),
        model_profile=Modelo111ProfileFacts(colegio_concertado=False),
        elections=FilingElectionFacts(
            result_disposition=ResultDisposition.NEGATIVA,
            payment=PaymentElection.INGRESO,
            refund=RefundElection.COMPENSAR,
            prior_domiciliation=PriorDomiciliationElection.KEEP,
        ),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=None,
    )
    output = tmp_path / "unbuilt-layout-modelo-111.txt"

    with pytest.raises(FilingExportError, match="no complete export_layouts definition"):
        export_draft(
            _approved_modelo_111_registry_draft(),
            output_path=output,
            producer_snapshot=snapshot,
            schema_provider=_schema_provider(modelos=("111",)),
        )

    assert not output.exists()
