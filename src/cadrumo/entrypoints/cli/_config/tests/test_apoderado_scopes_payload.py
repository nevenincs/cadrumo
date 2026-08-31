"""Strict JSON payload checks for ``aeat config auth apoderado scopes list``.

``ApoderadoScopesListResult`` used to be an untyped ``extra="allow"`` shell.
It now projects :class:`~cadrumo.domain.auth.apoderamientos.ApoderamientosCatalogue`
directly: a non-blank ``catalogue_version`` and typed
:class:`~cadrumo.entrypoints.cli._config_payloads.ApoderadoScopePayload` rows
carrying the same uppercase/alphanumeric ``code`` invariant and bounded
localized names the domain catalogue enforces.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .....core.json_contract import strict_round_trip
from .....domain.auth.apoderamientos.catalogue import load_default_catalogue
from ..._config_payloads import ApoderadoScopePayload, ApoderadoScopesListResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_apoderado_scopes_list_result_projects_real_catalogue() -> None:
    """The real shipped catalogue round-trips through the typed payload."""
    catalogue = load_default_catalogue()

    result = strict_round_trip(ApoderadoScopesListResult, catalogue)

    assert result.catalogue_version == catalogue.catalogue_version
    assert len(result.scopes) == len(catalogue.scopes)
    codes = {scope.code for scope in result.scopes}
    assert {"IVA", "RENT", "CENSO"} <= codes


def test_apoderado_scopes_list_result_refuses_empty_catalogue_version() -> None:
    with pytest.raises(ValidationError):
        ApoderadoScopesListResult.model_validate({"catalogue_version": "", "scopes": []})


@pytest.mark.parametrize(
    "scope_row",
    (
        {"code": "bogus"},
        {"oops": 1},
        {"code": "iva", "name_es": "IVA", "name_en": "VAT"},
    ),
)
def test_apoderado_scopes_list_result_refuses_malformed_scope_row(scope_row: dict[str, object]) -> None:
    """A blank/missing/lowercase scope row is refused, matching ApoderadoScope."""
    with pytest.raises(ValidationError):
        ApoderadoScopesListResult.model_validate({"catalogue_version": "1", "scopes": [scope_row]})


def test_apoderado_scopes_list_result_refuses_unknown_top_level_field() -> None:
    with pytest.raises(ValidationError):
        ApoderadoScopesListResult.model_validate({"catalogue_version": "1", "scopes": [], "extra": 1})


def test_apoderado_scope_payload_round_trips_valid_row() -> None:
    row = ApoderadoScopePayload(code="IVA", name_es="IVA", name_en="VAT", modelo_codes=["303", "390"])

    assert row.code == "IVA"
    assert row.modelo_codes == ["303", "390"]
