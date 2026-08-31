"""Registry contract for codified result-disposition casilla ids."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....core.result_disposition import (
    ResultDisposition,
    derive_result_disposition,
    modelo_has_codified_disposition,
    result_disposition_casilla_ids,
)
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_codified_result_disposition_specs_resolve_against_bundled_revisions() -> None:
    modelos, _catalogues = _committed_registry_tree()

    checked_revisions: list[str] = []
    offences: list[str] = []
    for modelo in modelos:
        if not modelo_has_codified_disposition(modelo.id):
            continue
        for revision_id, revision in modelo.revisions.items():
            checked_revisions.append(f"{modelo.id}:{revision_id}")
            declared_ids = {casilla.id for casilla in revision.casillas}
            result_ids = result_disposition_casilla_ids(modelo.id)
            assert result_ids is not None
            revision_result_ids = tuple(casilla_id for casilla_id in result_ids if casilla_id in declared_ids)
            if not revision_result_ids:
                offences.append(
                    f"modelo {modelo.id} revision {revision_id}: none of the codified result casilla ids "
                    f"{result_ids!r} are declared by the bundled revision",
                )
                continue
            values = {casilla_id: Decimal("1") for casilla_id in revision_result_ids}
            try:
                disposition = derive_result_disposition(modelo.id, values)
            except Exception as exc:
                offences.append(f"modelo {modelo.id} revision {revision_id}: resolver raised {exc!r}")
                continue
            if disposition is not ResultDisposition.INGRESO:
                offences.append(
                    f"modelo {modelo.id} revision {revision_id}: positive values across all canonical "
                    f"casilla.id keys produced {disposition!r}, expected {ResultDisposition.INGRESO!r}",
                )

    assert checked_revisions, "no bundled revisions exercised a codified result-disposition spec"
    assert not offences, "codified result-disposition casilla ids are not registry-backed:\n  " + "\n  ".join(
     