from __future__ import annotations

from collections.abc import Hashable, Mapping
from decimal import Decimal

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ...workbench_capture_memory import WorkbenchMemoSlot
from ..work_form_service import ModeloWorkFormLoadV1, modelo_work_form_load
from ..workbench_projection import (
    PublicModeloFormField,
    PublicModeloWorkFormLoadV1,
    _mirrored_form,
)
from ..workbench_projection_memory import FormProjectionPair, FormSectionPair, form_identities
from .work_form_fixture import built_form

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

type _Slot = WorkbenchMemoSlot[Hashable, Mapping[Hashable, FormSectionPair]]


def _load(
    operation: PinnedAuthorityOperation,
    modelo: str,
    code: str,
    *,
    held: Mapping[str, Decimal | str] | None = None,
    entered: frozenset[str] | None = None,
) -> ModeloWorkFormLoadV1:
    built = built_form(operation, modelo, filing_year_envelope().horizon, code, held=held, entered=entered)
    load = modelo_work_form_load(built, verified=False, filed=False)
    # The first mirror of a process completes the deferred schemas, which moves the schema identity once.
    _mirror(load, None)
    return load


def _mirror(load: ModeloWorkFormLoadV1, slot: _Slot | None, spent: dict[str, int] | None = None) -> FormProjectionPair:
    identities = form_identities(load, PublicModeloWorkFormLoadV1) if slot is not None else None
    return _mirrored_form(load, slot, identities, spent)[0]


def _section_count(load: ModeloWorkFormLoadV1) -> int:
    return sum(len(page.sections) for page in load.form.pages)


def _public_sections(public: object) -> list[object]:
    assert isinstance(public, PublicModeloWorkFormLoadV1)
    return [section for page in public.form.pages for section in page.sections]


def _with_first_section_heading(load: ModeloWorkFormLoadV1, heading: str) -> ModeloWorkFormLoadV1:
    form = load.form
    page = next(page for page in form.pages if page.sections)
    changed = page.sections[0].model_copy(update={"official_heading": heading})
    pages = tuple(
        each.model_copy(update={"sections": (changed, *each.sections[1:])}) if each is page else each
        for each in form.pages
    )
    return load.model_copy(update={"form": form.model_copy(update={"pages": pages})})


def test_a_form_read_again_after_its_lifecycle_moved_reuses_every_section_and_serves_the_same_mirror(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    load = _load(authority_operation, "100", "0A")
    total = _section_count(load)
    assert total > 1
    slot: _Slot = WorkbenchMemoSlot()

    spent: dict[str, int] = {}
    first = _mirror(load, slot, spent)
    assert spent == {"projection_sections_reused": 0, "projection_sections": total}
    assert first.canonical == load

    # A separately built copy with another lifecycle fact shares no object with the first read.
    moved = load.model_copy(deep=True).model_copy(update={"verified": True})
    spent = {}
    second = _mirror(moved, slot, spent)
    assert spent == {"projection_sections_reused": total, "projection_sections": total}

    independent = _mirror(moved, None)
    assert second.public == independent.public
    assert second.canonical == moved
    assert second.public != first.public
    assert all(
        kept is served
        for kept, served in zip(_public_sections(first.public), _public_sections(second.public), strict=True)
    )


def test_a_changed_section_is_mirrored_again_and_the_rest_are_reused(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    load = _load(authority_operation, "100", "0A")
    total = _section_count(load)
    slot: _Slot = WorkbenchMemoSlot()
    first = _mirror(load, slot)

    changed = _with_first_section_heading(load, "a heading no edition carries")
    spent: dict[str, int] = {}
    second = _mirror(changed, slot, spent)

    assert spent == {"projection_sections_reused": total - 1, "projection_sections": total}
    assert second.public == _mirror(changed, None).public
    assert second.canonical == changed
    kept, served = _public_sections(first.public), _public_sections(second.public)
    assert served[0] is not kept[0]
    assert served[0] != kept[0]
    assert all(before is after for before, after in zip(kept[1:], served[1:], strict=True))

    # The memory now holds the changed form's sections: the first form's own first section is proven again.
    spent = {}
    _mirror(load, slot, spent)
    assert spent["projection_sections_reused"] == total - 1


def test_a_decimal_that_only_changed_its_scale_is_not_served_from_the_kept_section(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    short = _load(authority_operation, "130", "1T", held={"01": Decimal("1200.0")}, entered=frozenset({"01"}))
    long = _load(authority_operation, "130", "1T", held={"01": Decimal("1200.00")}, entered=frozenset({"01"}))
    # Equal by value, so only the exact identity can tell the two forms apart.
    assert short == long
    total = _section_count(short)
    slot: _Slot = WorkbenchMemoSlot()
    _mirror(short, slot)

    spent: dict[str, int] = {}
    served = _mirror(long, slot, spent)

    assert spent["projection_sections_reused"] < total
    independent = _mirror(long, None).public
    assert served.public.model_dump_json() == independent.model_dump_json()
    assert served.public.model_dump_json() != _mirror(short, None).public.model_dump_json()


def test_a_closed_memory_keeps_no_section_and_a_rebuilt_schema_reuses_none(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    load = _load(authority_operation, "130", "1T")
    total = _section_count(load)
    closed: _Slot = WorkbenchMemoSlot()
    closed.close()
    for _ in range(2):
        spent: dict[str, int] = {}
        assert _mirror(load, closed, spent).canonical == load
        assert spent == {"projection_sections_reused": 0, "projection_sections": total}

    slot: _Slot = WorkbenchMemoSlot()
    _mirror(load, slot)
    spent = {}
    _mirror(load, slot, spent)
    assert spent["projection_sections_reused"] == total
    PublicModeloFormField.model_rebuild(force=True)
    spent = {}
    assert _mirror(load, slot, spent).canonical == load
    assert spent["projection_sections_reused"] == 0
