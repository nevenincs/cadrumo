"""The exchange-rate port serves only what a host composed."""

from __future__ import annotations

import threading
from contextvars import copy_context
from datetime import date
from decimal import Decimal

import pytest

from ...core.errors.hierarchy import InternalInvariantError
from ..exchange_rate_provider import bind_exchange_rate_provider_factory, exchange_rate_provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _FixedProvider:
    rate_source_id = "fixed"

    def get_eur_rate(self, currency: str, rate_date: date) -> Decimal | None:
        return Decimal("1") if currency == "EUR" else None


def test_an_unbound_port_refuses() -> None:
    # A bare thread starts from an empty context, where no host has bound anything.
    outcomes: list[object | None] = []
    worker = threading.Thread(target=lambda: outcomes.append(_bound_or_none()))
    worker.start()
    worker.join()

    assert outcomes == [None]


def test_a_bound_factory_is_served_and_unbinds_on_exit() -> None:
    provider = _FixedProvider()
    outer = copy_context().run(_bound_or_none)

    with bind_exchange_rate_provider_factory(lambda: provider):
        assert exchange_rate_provider() is provider

    assert copy_context().run(_bound_or_none) is outer


def _bound_or_none() -> object | None:
    try:
        return exchange_rate_provider()
    except InternalInvariantError:
        return None
