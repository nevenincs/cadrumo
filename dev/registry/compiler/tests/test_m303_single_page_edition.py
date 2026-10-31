"""The 2022 single-page edition is tied to its own year, source, revision and record design."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.form_codes import resolve_form_codes
from cadrumo.domain.calculations.registry.m303_orden_constants import M303_2022_ORDEN_SOURCE_REF

from .._m303_orden_projection_compiler import require_single_page_edition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]


def _edition() -> str:
    return next(iter(resolve_form_codes("form-row-codes").codes("m303.dp30302.single_page_epochs")))


def test_the_edition_year_with_its_own_source_revision_and_design_passes() -> None:
    edition = _edition()
    require_single_page_edition(
        ejercicio=int(edition),
        source_ref=M303_2022_ORDEN_SOURCE_REF,
        registry_revision_id=edition,
        record_design_epoch=edition,
    )


@pytest.mark.parametrize(
    ("source", "revision", "design"),
    [
        ("another-source", "edition", "edition"),
        (M303_2022_ORDEN_SOURCE_REF, "another", "edition"),
        (M303_2022_ORDEN_SOURCE_REF, "edition", "another"),
    ],
)
def test_the_edition_year_refuses_anything_of_another_edition(source: str, revision: str, design: str) -> None:
    edition = _edition()
    with pytest.raises(RegistryValidationError):
        require_single_page_edition(
            ejercicio=int(edition),
            source_ref=source,
            registry_revision_id=edition if revision == "edition" else revision,
            record_design_epoch=edition if design == "edition" else design,
        )


def test_another_year_may_not_carry_the_edition_source() -> None:
    with pytest.raises(RegistryValidationError):
        require_single_page_edition(
            ejercicio=int(_edition()) + 1,
            source_ref=M303_2022_ORDEN_SOURCE_REF,
            registry_revision_id="any",
            record_design_epoch="any",
        )
