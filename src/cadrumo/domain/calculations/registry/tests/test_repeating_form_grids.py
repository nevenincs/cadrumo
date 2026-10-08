"""Member grids refer to one declared row, never to unrelated scalar inputs."""

import pytest
from pydantic import ValidationError

from ..schema_form_layouts import FormRepeatingGroupBlock

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _payload():
    return {
        "id": "members",
        "row_source": "export_record",
        "export_record_id": "members",
        "columns": [
            {"key": key, "heading_key": f"modelo.form.{key}.heading", "casilla_id": key}
            for key in ("name", "january-status", "january-amount")
        ],
        "grids": [
            {
                "id": "calendar",
                "columns": [{"key": key, "heading_key": f"modelo.form.{key}.heading"} for key in ("status", "amount")],
                "rows": [
                    {
                        "key": "january",
                        "heading_key": "modelo.form.january.heading",
                        "cells": [
                            {"kind": "casilla", "casilla_id": key} for key in ("january-status", "january-amount")
                        ],
                    }
                ],
            }
        ],
    }


def test_grid_is_a_presentation_of_declared_member_columns():
    group = FormRepeatingGroupBlock.model_validate(_payload(), strict=False)
    assert len(group.columns) == 3 and len(group.grids[0].rows[0].cells) == 2
    assert FormRepeatingGroupBlock.model_validate_json(group.model_dump_json()) == group


@pytest.mark.parametrize("defect", ["foreign", "duplicate", "constant", "binding", "row_source", "unaddressed"])
def test_grid_refuses_ambiguous_or_foreign_value_owners(defect):
    payload = _payload()
    cells = payload["grids"][0]["rows"][0]["cells"]
    if defect == "foreign":
        cells[0]["casilla_id"] = "other-record"
    elif defect == "duplicate":
        cells[1]["casilla_id"] = cells[0]["casilla_id"]
    elif defect == "constant":
        cells[0] = {"kind": "design_constant", "literal": "0"}
    elif defect == "binding":
        cells[0] = {"kind": "binding_input", "binding_id": "unrelated-input"}
    elif defect == "row_source":
        payload["row_source"] = "row_set_binding"
        payload["binding_id"] = "members"
        del payload["export_record_id"]
    else:
        del payload["columns"][0]["casilla_id"]
    with pytest.raises(ValidationError):
        FormRepeatingGroupBlock.model_validate(payload, strict=False)
