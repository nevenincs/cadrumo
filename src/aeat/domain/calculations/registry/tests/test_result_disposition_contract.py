"""Registry contract for codified result-disposition casilla ids."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....core import ResultDisposition, derive_result_disposition, modelo_has_codified_disposition
from .....core.resources import bundled_path
from .. import load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_codified_result_disposition_specs_resolve_against_bundled_revisions() -> None:
    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))

    checked_revisions: list[str] = []
    offences: list[str] = []
    for modelo in modelos:
        if not modelo_has_codified_disposition(modelo.id):
            continue
        for revision_id, revision in modelo.revisions.items():
            checked_revisions.append(f"{modelo.id}:{revision_id}")
            values = {casilla.id: Decimal("1") for casilla in revision.casillas}
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
        offences,
    )
