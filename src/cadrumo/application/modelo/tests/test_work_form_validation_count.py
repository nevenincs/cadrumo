"""Building a declaration's form checks each field it builds once.

A field is a frozen, validated model. Placing it on its line, its section or
its page must not run its own checks again: on a Modelo 100 of some 2,000
boxes every repeated pass costs the form read a measurable share of its time.
The count is read from the profiler's record of the field's own validator, so
the builder under test runs unchanged, and compared with the number of fields
the returned form holds: a count, not a wall time, so it does not depend on
the machine.
"""

from __future__ import annotations

import cProfile

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import newest_authored_edition
from ..work_form_models import ModeloFormField, ModeloWorkForm
from .work_form_fixture import built_form

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_MODELO = "100"
_PERIOD = "0A"


def _field_check_runs(profile: cProfile.Profile) -> int:
    """How many times :class:`ModeloFormField`'s own derivation check ran while ``profile`` recorded."""
    check = ModeloFormField._derived_from_the_field_itself
    code = getattr(check, "__wrapped__", check).__code__
    return sum(entry.callcount for entry in profile.getstats() if entry.code is code)


def test_each_built_field_is_checked_once(authority_operation: PinnedAuthorityOperation) -> None:
    year = newest_authored_edition(_MODELO)
    built_form(authority_operation, _MODELO, year, _PERIOD)  # loads the registry and the catalogues first
    profile = cProfile.Profile()
    profile.enable()
    form: ModeloWorkForm = built_form(authority_operation, _MODELO, year, _PERIOD)
    profile.disable()
    fields = len(form.fields())
    rechecked = _field_check_runs(profile) - fields
    assert fields > 0
    # Only a repeated box shown read-only and a field replaced by a revised copy are checked beyond the
    # fields the form holds; checking every field again on its line would recheck all of them.
    assert 0 <= rechecked < fields // 2, (fields, rechecked)
