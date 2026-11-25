"""Both counterpart registry readers take a mapping value stripped and refuse an absent or blank one."""

from __future__ import annotations

from datetime import date

import pytest

from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.calculations.registry.tests.authority_lease_support import private_authority_lease
from ...invoices import catalogue_creation
from .. import counterpart
from ..counterpart import counterpart_catalogue_entry, counterpart_operation_catalogue_entries

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_EFFECTIVE = date(_YEAR, 3, 14)


@pytest.mark.parametrize(("declared", "expected"), [("value", "value"), ("  value\t", "value"), (" a, b ", "a, b")])
def test_a_declared_value_is_returned_stripped(declared: str, expected: str) -> None:
    assert counterpart_catalogue_entry({"key": declared}, "key") == expected


@pytest.mark.parametrize("declared", ["", "   ", "\t\n"])
def test_a_blank_value_is_refused_with_its_key(declared: str) -> None:
    with pytest.raises(ValueError, match=r"counterpart registry mapping is missing 'key'"):
        counterpart_catalogue_entry({"key": declared}, "key")


def test_an_absent_key_is_refused_with_its_key() -> None:
    with pytest.raises(ValueError, match=r"counterpart registry mapping is missing 'absent'"):
        counterpart_catalogue_entry({"key": "value"}, "absent")


@pytest.mark.parametrize("module", [counterpart, catalogue_creation], ids=["aggregation", "catalogue-creation"])
def test_a_padded_registry_mapping_reads_as_the_declared_one(module: object, monkeypatch: pytest.MonkeyPatch) -> None:
    with private_authority_lease() as operation:
        declared = counterpart_operation_catalogue_entries(_EFFECTIVE, operation=operation)
        read_catalogue = counterpart.registry_counterpart_catalogue(_EFFECTIVE, operation=operation)
        read_m349 = catalogue_creation.registry_m349_operation_type_requirement(_EFFECTIVE, operation=operation)

        padded = {key: f"  {value}\t" for key, value in declared.items()}
        monkeypatch.setattr(module, "counterpart_operation_catalogue_entries", lambda *_args, **_kwargs: padded)

        if module is counterpart:
            assert counterpart.registry_counterpart_catalogue(_EFFECTIVE, operation=operation) == read_catalogue
        else:
            assert catalogue_creation.registry_m349_operation_type_requirement(_EFFECTIVE, operation=operation) == (
                read_m349
            )


@pytest.mark.parametrize("module", [counterpart, catalogue_creation], ids=["aggregation", "catalogue-creation"])
def test_a_blank_registry_value_is_refused_by_each_reader(module: object, monkeypatch: pytest.MonkeyPatch) -> None:
    with private_authority_lease() as operation:
        declared = counterpart_operation_catalogue_entries(_EFFECTIVE, operation=operation)
        blank_key = (
            "modelo.349.operation_type_candidates"
            if module is catalogue_creation
            else next(key for key in declared if key.endswith(".readiness.groi_country"))
        )
        blanked = {**declared, blank_key: "   "}
        monkeypatch.setattr(module, "counterpart_operation_catalogue_entries", lambda *_args, **_kwargs: blanked)

        with pytest.raises(ValueError, match=f"counterpart registry mapping is missing '{blank_key}'"):
            if module is counterpart:
                counterpart.registry_counterpart_catalogue(_EFFECTIVE, operation=operation)
            else:
                catalogue_creation.registry_m349_operation_type_requirement(_EFFECTIVE, operation=operation)
