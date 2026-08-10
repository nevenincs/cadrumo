"""Registry product payloads preserve their canonical typed reports."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .._registry_payloads import RegistryVerifyFiledStateResult

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_verify_filed_state_refuses_an_empty_comparison() -> None:
    """The comparison is a typed verdict, not an arbitrary mapping."""
    with pytest.raises(ValidationError):
        RegistryVerifyFiledStateResult.model_validate(
            {"observation_path": "obs.json", "comparison": {}},
        )


def test_verify_filed_state_refuses_a_malformed_comparison() -> None:
    """An out-of-set status, blank revision, and duplicate casilla ids are refused."""
    with pytest.raises(ValidationError):
        RegistryVerifyFiledStateResult.model_validate(
            {
                "observation_path": "obs.json",
                "comparison": {
                    "modelo": "303",
                    "revision": "",
                    "filing_year": 1899,
                    "period": "1T",
                    "status": "bogus",
                    "compared_casilla_ids": ["01", "01"],
                },
            },
        )
