"""A ledger row names a stored lease or property, and the profile keeps a named row from being removed.

Every case drives the real ``aeat`` CLI against an isolated profile through the registered
operations: the doors are ``ledger add``, ``ledger classify`` (one row and the CSV table)
and the profile's property and lease removal.
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import NamedTuple

import pytest

from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.transactions.rental_link import RENTAL_LINK_IRPF_CATEGORY
from .cli_fixture_worlds import invoke_joined_cli
from .profile_world_fixtures import recorded_fx_isolated_backend

__all__ = ["recorded_fx_isolated_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_YEAR = filing_year_envelope().horizon
_PROPERTY_DOOR = "aeat config profile inmueble list"
_LEASE_DOOR = "aeat config profile arrendamiento list"


def _words(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def _profile(*arguments: str):
    return invoke_joined_cli(["--format", "json", "config", "profile", *arguments])


def _add_property() -> int:
    result = _profile(
        "inmueble",
        "add",
        "--value",
        "situacion=1",
        "--value",
        "referencia_catastral=9872023vh5797s0001wx",
        "--value",
        "titularidad_regimen=pleno_dominio",
        "--value",
        "titular=primer_declarante",
        "--value",
        "porcentaje_propiedad=100",
        "--value",
        "importe_adquisicion=150000",
        "--value",
        f"valores_catastrales={_YEAR}:80000:48000",
    )
    assert result.exit_code == 0, result.output
    return int(json.loads(result.output)["result"]["row"])


def _add_lease(inmueble: int) -> int:
    result = _profile(
        "arrendamiento",
        "add",
        "--value",
        f"inmueble={inmueble}",
        "--value",
        f"fecha_contrato={date(_YEAR, 1, 10).isoformat()}",
        "--value",
        f"fecha_inicio={date(_YEAR, 2, 1).isoformat()}",
        "--value",
        "inquilinos=12345678z:otra:no",
    )
    assert result.exit_code == 0, result.output
    return int(json.loads(result.output)["result"]["row"])


def _add_row(direction: str, key: str, *extra: str) -> str:
    result = invoke_joined_cli(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            date(_YEAR, 5, 2).isoformat(),
            "--amount",
            "800.00",
            "--direction",
            direction,
            "--description",
            "RENT OR COMMUNITY FEE",
            "--idempotency-key",
            key,
            *extra,
        ]
    )
    assert result.exit_code == 0, result.output
    transaction_id = json.loads(result.output)["result"]["transaction_id"]
    assert isinstance(transaction_id, str)
    return transaction_id


def _classify(transaction_id: str, *extra: str):
    return invoke_joined_cli(
        [
            "--language",
            "en",
            "--format",
            "json",
            "app",
            "ledger",
            "classify",
            transaction_id,
            "--classification",
            "BUSINESS",
            *extra,
        ]
    )


def _rental(*extra: str) -> list[str]:
    return ["--irpf-category", RENTAL_LINK_IRPF_CATEGORY, *extra]


class _Rows(NamedTuple):
    inmueble: int
    arrendamiento: int

    @property
    def missing(self) -> str:
        """A row key no row of the profile holds."""
        return str(max(self) + 7)


@pytest.fixture
def world(isolated_backend: None) -> _Rows:
    """Hold one property and one lease on it."""
    inmueble = _add_property()
    return _Rows(inmueble, _add_lease(inmueble))


def test_an_income_row_is_linked_to_a_stored_lease_at_classification(world: _Rows) -> None:
    transaction_id = _add_row("INCOMING", "rent-1")

    linked = _classify(transaction_id, *_rental("--arrendamiento", str(world.arrendamiento)))

    assert linked.exit_code == 0, linked.output


def test_an_expense_row_is_linked_to_a_stored_property_with_a_registry_concept(world: _Rows) -> None:
    transaction_id = _add_row("OUTGOING", "fee-1")

    linked = _classify(transaction_id, *_rental("--inmueble", str(world.inmueble), "--gasto-inmobiliario", "comunidad"))

    assert linked.exit_code == 0, linked.output


def test_a_row_is_linked_when_it_is_added(world: _Rows) -> None:
    result = invoke_joined_cli(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            date(_YEAR, 6, 2).isoformat(),
            "--amount",
            "800.00",
            "--direction",
            "INCOMING",
            "--description",
            "RENT",
            "--classification",
            "BUSINESS",
            *_rental("--arrendamiento", str(world.arrendamiento)),
        ]
    )

    assert result.exit_code == 0, result.output


def test_a_lease_the_profile_does_not_hold_is_refused_naming_the_listing_door(world: _Rows) -> None:
    transaction_id = _add_row("INCOMING", "rent-2")

    refused = _classify(transaction_id, *_rental("--arrendamiento", world.missing))

    assert refused.exit_code != 0
    assert _LEASE_DOOR in _words(refused.output)


def test_a_property_the_profile_does_not_hold_is_refused_naming_the_listing_door(world: _Rows) -> None:
    transaction_id = _add_row("OUTGOING", "fee-2")

    refused = _classify(transaction_id, *_rental("--inmueble", world.missing))

    assert refused.exit_code != 0
    assert _PROPERTY_DOOR in _words(refused.output)


def test_a_reference_that_is_no_row_key_is_refused(world: _Rows) -> None:
    transaction_id = _add_row("INCOMING", "rent-3")

    refused = _classify(transaction_id, *_rental("--arrendamiento", "lease-a"))

    assert refused.exit_code != 0
    assert _LEASE_DOOR in _words(refused.output)


def test_a_linked_business_row_under_another_category_is_refused(world: _Rows) -> None:
    transaction_id = _add_row("INCOMING", "rent-4")

    refused = _classify(transaction_id, "--irpf-category", "trabajo", "--arrendamiento", str(world.arrendamiento))

    assert refused.exit_code != 0
    assert RENTAL_LINK_IRPF_CATEGORY in _words(refused.output)


def test_a_linked_business_row_without_a_category_is_refused(world: _Rows) -> None:
    transaction_id = _add_row("INCOMING", "rent-5")

    refused = _classify(transaction_id, "--arrendamiento", str(world.arrendamiento))

    assert refused.exit_code != 0
    assert RENTAL_LINK_IRPF_CATEGORY in _words(refused.output)


def test_a_row_naming_a_lease_and_a_property_is_refused(world: _Rows) -> None:
    transaction_id = _add_row("INCOMING", "rent-6")

    refused = _classify(
        transaction_id, *_rental("--arrendamiento", str(world.arrendamiento), "--inmueble", str(world.inmueble))
    )

    assert refused.exit_code != 0


def test_an_expense_concept_without_a_property_is_refused(world: _Rows) -> None:
    transaction_id = _add_row("OUTGOING", "fee-3")

    refused = _classify(transaction_id, *_rental("--gasto-inmobiliario", "comunidad"))

    assert refused.exit_code != 0


def test_an_expense_concept_the_registry_does_not_declare_is_refused_with_the_declared_ones(world: _Rows) -> None:
    transaction_id = _add_row("OUTGOING", "fee-4")

    refused = _classify(
        transaction_id, *_rental("--inmueble", str(world.inmueble), "--gasto-inmobiliario", "bogus_concepto")
    )

    assert refused.exit_code != 0
    assert "comunidad" in _words(refused.output)


def test_the_csv_table_links_rows_and_refuses_a_row_naming_an_unknown_lease(world: _Rows, tmp_path) -> None:
    good = _add_row("INCOMING", "rent-7")
    bad = _add_row("INCOMING", "rent-8")
    table = tmp_path / "rows.csv"
    table.write_text(
        "transaction_id,classification,irpf_category,arrendamiento_ref\n"
        f"{good},BUSINESS,{RENTAL_LINK_IRPF_CATEGORY},{world.arrendamiento}\n"
        f"{bad},BUSINESS,{RENTAL_LINK_IRPF_CATEGORY},{world.missing}\n",
        encoding="utf-8",
    )

    result = invoke_joined_cli(["--format", "json", "app", "ledger", "classify", "--file", str(table)])

    payload = json.loads(result.output)["result"]
    assert payload["applied"] == 1, result.output
    assert len(payload["failures"]) == 1
    assert _LEASE_DOOR in _words(payload["failures"][0]["reason"])


def test_a_lease_a_ledger_row_names_cannot_be_removed_until_the_link_is_cleared(world: _Rows) -> None:
    transaction_id = _add_row("INCOMING", "rent-9")
    assert _classify(transaction_id, *_rental("--arrendamiento", str(world.arrendamiento))).exit_code == 0

    refused = _profile("arrendamiento", "remove", str(world.arrendamiento))
    assert refused.exit_code != 0
    assert "REFUSED_USER_PROFILE_VALIDATION" in refused.output

    assert _classify(transaction_id, *_rental("--arrendamiento", "")).exit_code == 0
    removed = _profile("arrendamiento", "remove", str(world.arrendamiento))
    assert removed.exit_code == 0, removed.output


def test_a_property_a_ledger_row_names_cannot_be_removed(world: _Rows) -> None:
    assert _profile("arrendamiento", "remove", str(world.arrendamiento)).exit_code == 0
    transaction_id = _add_row("OUTGOING", "fee-5")
    assert (
        _classify(
            transaction_id, *_rental("--inmueble", str(world.inmueble), "--gasto-inmobiliario", "comunidad")
        ).exit_code
        == 0
    )

    refused = _profile("inmueble", "remove", str(world.inmueble))

    assert refused.exit_code != 0
    assert "REFUSED_USER_PROFILE_VALIDATION" in refused.output
