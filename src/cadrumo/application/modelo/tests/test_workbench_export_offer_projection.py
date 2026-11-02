"""Exact instalment figures cross the public boundary without numeric coercion."""

import json

import pytest

from ...operations.public_mirror import project_public_mirror, restore_public_mirror
from ...operations.registry_schema_validation import strict_model_json_schema
from ..work_form_export_offer import ModeloFormExportOffer
from ..workbench_projection import ModeloWorkbenchFormProjectionV1, PublicModeloFormExportOffer

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_public_export_offer_roundtrip_rejects_noncanonical_amounts() -> None:
    available = {"available": True, "reason": None, "words": None}
    payload = {
        "artefacts": [{"artefact": "calculation_report_pdf", "words": "Report", "availability": available}],
        "record": available,
        "review_package": {"words": "Package", "availability": available},
        "asks_elections": True,
        "elections": [
            {
                "election": "instalment",
                "request_field": "instalment_election",
                "words": "Instalments",
                "choices": [{"value": "split", "words": "Split"}],
                "figures": [
                    {
                        "instalment": "first",
                        "amount": "600.01",
                        "words": "First",
                        "advisory": True,
                        "advisory_words": "Rounding",
                    },
                    {
                        "instalment": "second",
                        "amount": "400.00",
                        "words": "Second",
                        "advisory": True,
                        "advisory_words": "Rounding",
                    },
                ],
            }
        ],
        "file_format": None,
        "file_format_words": None,
    }
    canonical = ModeloFormExportOffer.model_validate_json(json.dumps(payload))
    public = project_public_mirror(canonical, ModeloFormExportOffer, PublicModeloFormExportOffer)
    assert isinstance(public, PublicModeloFormExportOffer)
    assert tuple(figure.amount for figure in public.elections[0].figures) == ("600.01", "400.00")
    restored = restore_public_mirror(
        PublicModeloFormExportOffer.model_validate_json(public.model_dump_json()),
        ModeloFormExportOffer,
        PublicModeloFormExportOffer,
    )
    assert isinstance(restored, ModeloFormExportOffer) and restored == canonical
    assert restored.elections[0].figures[1].amount.as_tuple().exponent == -2
    strict_model_json_schema(ModeloWorkbenchFormProjectionV1)
    for invalid in ("NaN", "01.0", 600.01):
        invalid_payload = public.model_dump(mode="json")
        invalid_payload["elections"][0]["figures"][0]["amount"] = invalid
        with pytest.raises(ValueError):
            PublicModeloFormExportOffer.model_validate_json(json.dumps(invalid_payload))
    invalid_payload = public.model_dump(mode="json")
    invalid_payload["elections"][0]["figures"][0]["advisory_words"] = None
    with pytest.raises(ValueError):
        PublicModeloFormExportOffer.model_validate_json(json.dumps(invalid_payload))
