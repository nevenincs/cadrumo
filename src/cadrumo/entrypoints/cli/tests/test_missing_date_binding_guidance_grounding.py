"""Date-binding calculate guidance names the profile fact, not the binding id.

The guidance tells the operator to set something on their profile, so it must
name a profile fact. A registry binding id names the registry's internal
consumer of that fact and appears nowhere in the profile editor.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....application.modelo._data_inventory import profile_requirements_for_binding
from ....application.user_profile.preflight import build_profile_preflight_requirement
from ....core import Period, PeriodError
from ....core.resources import resources
from ....domain.calculations.registry import (
    DataBindingDefinition,
    RegistrySnapshotError,
    RegistryValidationError,
    RevisionId,
    binding_profile_keys,
)
from ....domain.modelos import WorkUnit, derive_work_unit_id
from ....domain.user_profile.loader import load_user_profile_schema
from .._modelo_behavior_support import _date_binding_profile_requirements

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


_WORK_UNIT_BUCKET_ID = "00000000-0000-4000-8000-000000000042"
_WORK_UNIT_NAME = "missing-date-binding-guidance"
_WORK_UNIT_TIMESTAMP = datetime(2026, 1, 1, tzinfo=UTC)


def _work_unit(modelo: str, filing_year: int, period: Period, revision_id: RevisionId) -> WorkUnit:
    """Build a real deterministic work unit for the address under test."""
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_WORK_UNIT_BUCKET_ID,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_WORK_UNIT_BUCKET_ID,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=_WORK_UNIT_NAME,
        created_at=_WORK_UNIT_TIMESTAMP,
        updated_at=_WORK_UNIT_TIMESTAMP,
    )


def _an_addressable_profile_binding() -> tuple[WorkUnit, DataBindingDefinition]:
    """Return ``(unit, binding)`` for a real committed profile binding.

    Searched rather than hand-picked, and validated through the SAME
    resolution the production lookup performs. Two things make a binding
    unreachable here and neither is visible from the binding itself: some
    revisions declare lifecycle period tokens the canonical period grammar
    does not accept, and a revision's declared year is not always a year the
    authority resolves for that period. Requiring the snapshot to resolve, and
    to actually contain the binding, is what makes the returned pair genuinely
    addressable rather than merely plausible.
    """
    authority = resources().modelos.authority
    for model in authority.modelos:
        for revision in model.revisions.values():
            candidates = [b for b in revision.bindings if binding_profile_keys(b)]
            if not candidates:
                continue
            selector = revision.period_selector
            for filing_year in (selector.year_from or 2026, (selector.year_from or 2026) + 1):
                for token in selector.periods or ("0A",):
                    try:
                        period = Period.from_year_and_code(filing_year, token)
                        snapshot = authority.snapshot(
                            str(model.id),
                            filing_year=filing_year,
                            period=period.registry_token,
                        )
                        resolved = {str(b.id) for b in snapshot.revision.bindings}
                    except (PeriodError, RegistrySnapshotError, RegistryValidationError):
                        # This helper is a SEARCH: an unaddressable or
                        # currently-invalid combination is a candidate to skip,
                        # not a failure. An empty search fails loudly below.
                        continue
                    for binding in candidates:
                        if str(binding.id) in resolved:
                            return _work_unit(str(model.id), filing_year, period, snapshot.revision.id), binding
    pytest.fail("no committed profile binding sits under a resolvable revision")


def test_an_unresolvable_work_unit_degrades_to_the_binding_id() -> None:
    """The documented fallback: better a raw id than no guidance at all."""
    assert _date_binding_profile_requirements(None, "some.binding.id") == "some.binding.id"


def test_a_binding_id_matching_no_row_degrades_to_the_binding_id() -> None:
    unit = _work_unit("303", 2026, Period.from_year_and_code(2026, "1T"), "test-revision")

    assert _date_binding_profile_requirements(unit, "no-such-binding") == "no-such-binding"


def test_a_real_profile_binding_resolves_to_its_profile_facts() -> None:
    """The positive case, over a real committed binding and the real schema.

    Asserts the rendered text carries the field's operator LABEL, not merely
    that it differs from the binding id. Checking only the latter would pass
    against a lookup that resolved the binding to its profile keys and then
    printed those keys raw, which is the same defect one layer along - and is
    exactly what happened while these keys were routed through the selector
    lookup instead of the path lookup.
    """
    unit, binding = _an_addressable_profile_binding()
    schema = load_user_profile_schema()
    # Binding keys are schema PATHS, so the label is resolved by path.
    labelled = [build_profile_preflight_requirement(key, schema=schema).label for key in binding_profile_keys(binding)]

    rendered = _date_binding_profile_requirements(unit, str(binding.id))

    assert str(binding.id) not in rendered
    assert any(label in rendered for label in labelled), rendered


def test_the_application_helper_resolves_the_same_facts_the_transport_renders() -> None:
    """The resolution lives in the application layer; the CLI only addresses it.

    Pins that split: the helper called directly, with the same addressing the
    transport would build, produces the text the transport returns. If the
    resolution ever migrates back into the CLI root it will still pass, but the
    architecture budget gate on that module will not.
    """
    unit, binding = _an_addressable_profile_binding()

    from_app = profile_requirements_for_binding(
        modelo=unit.modelo,
        filing_year=unit.filing_year,
        period=unit.period,
        binding_id=str(binding.id),
    )
    from_transport = _date_binding_profile_requirements(unit, str(binding.id))

    assert from_app, "the application helper resolved nothing for an addressable binding"
    assert from_transport == from_app
