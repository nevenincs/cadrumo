"""CLI surface tests for ``aeat app live deudas {list, view, latest}``.

Exercises the three read verbs against isolated local storage, never AEAT. The
family deliberately has no ``pull``: fetching the debts consulta needs an
operator-authorised specimen and the adapter guard refuses every landing until
one exists, so these verbs read only what a capture would have persisted.

The verb name is ``view``, not ``show``, matching the live convention.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from click.testing import Result

from ....adapters.outbound.aeat.sede.deudas import Deuda
from ....application.live.deudas import (
    DeudasCapture,
    DeudasService,
)
from ....core import DeudaDireccion, ObjetoTributario, Period
from ....tests.active_profile_isolated_backend_fixture import active_profile_isolated_backend_fixture
from ....tests.cli_runner import invoke_cached_cli

# INTENTIONAL: integration because it exercises the deudas CLI surface against
# isolated local storage without contacting AEAT.
pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET = "00000000-0000-4000-8000-000000000000"

_isolated_backend = active_profile_isolated_backend_fixture(
    bucket_id=_BUCKET,
    settings_overrides=lambda tmp_path: {"cadrumo_live_state_dir": tmp_path / "probe-live-state"},
)


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(["app", "live", "deudas", *args])


def _persist_snapshot() -> str:
    """Persist one deudas snapshot the read verbs can then display."""
    capture = DeudasCapture(
        deudas=(
            Deuda(
                clave_liquidacion="A2860024500012345",
                objeto_tributario=ObjetoTributario.SANCION,
                importe_pendiente=Decimal("1250.75"),
                direccion=DeudaDireccion.DEUDOR,
                periodo=Period.from_year_and_code(2025, "1T"),
                situacion="Pendiente de pago",
            ),
            Deuda(
                clave_liquidacion="A2860024500067890",
                objeto_tributario=ObjetoTributario.INTERES_DEMORA,
                importe_pendiente=Decimal("83.19"),
                direccion=DeudaDireccion.ACREEDOR,
                periodo=None,
                situacion="Devolución acordada",
            ),
        ),
        captured_at=datetime(2026, 3, 14, 10, 45, tzinfo=UTC),
        source_url="deudas:consulta",
        authenticated_identity="99999999R",
    )
    return str(DeudasService().capture(bucket_id=_BUCKET, capture=capture).snapshot_id)


def test_list_is_empty_on_a_fresh_bucket() -> None:
    """An empty register reports empty rather than reaching for AEAT."""
    result = _invoke(["list"])
    assert result.exit_code == 0, result.output
    assert "count\t0" in result.output


def test_latest_reports_no_snapshot_on_a_fresh_bucket() -> None:
    result = _invoke(["latest"])
    assert result.exit_code == 0, result.output
    assert "snapshot_id\t-" in result.output


def test_list_reports_the_persisted_snapshot() -> None:
    snapshot_id = _persist_snapshot()
    result = _invoke(["list"])
    assert result.exit_code == 0, result.output
    assert "count\t1" in result.output
    assert snapshot_id in result.output
    assert "deudas=2" in result.output


def test_view_displays_each_liability_as_aeat_reported_it() -> None:
    """The amount stays a positive magnitude and direction is its own column."""
    snapshot_id = _persist_snapshot()
    result = _invoke(["view", snapshot_id])
    assert result.exit_code == 0, result.output
    assert "deuda_count\t2" in result.output
    assert "A2860024500012345" in result.output
    assert "sancion" in result.output
    assert "1250.75" in result.output
    assert "Pendiente de pago" in result.output
    # The refundable row carries a POSITIVE amount plus the acreedor direction;
    # a sign-encoded reading would show "-83.19" and no direction token.
    assert "83.19" in result.output
    assert "-83.19" not in result.output
    assert "acreedor" in result.output
    assert "deudor" in result.output


def test_view_resolves_an_unambiguous_prefix() -> None:
    snapshot_id = _persist_snapshot()
    result = _invoke(["view", snapshot_id[:12]])
    assert result.exit_code == 0, result.output
    assert "deuda_count\t2" in result.output


def test_view_refuses_an_unknown_snapshot() -> None:
    result = _invoke(["view", "no-such-snapshot"])
    assert result.exit_code != 0


def test_latest_reports_the_persisted_snapshot() -> None:
    snapshot_id = _persist_snapshot()
    result = _invoke(["latest"])
    assert result.exit_code == 0, result.output
    assert snapshot_id in result.output
    assert "deuda_count\t2" in result.output


def test_the_family_exposes_exactly_list_view_and_latest() -> None:
    """No verb here fetches, pays, or requests an aplazamiento.

    Asserted on the registered command names rather than scraped from help
    text, because Typer's own ``--help`` epilogue contains the word "Show" and
    would make a text scan pass or fail for reasons unrelated to this surface.

    This family sits beside AEAT's payment controls, so the verb set is pinned
    rather than merely spot-checked: a later convenience verb cannot slip in
    unnoticed, and ``view`` is asserted as the canonical spelling over ``show``.
    """
    from .._app_live_command_specs import LIVE_COMMAND_SPECS

    names = {spec.token for spec in LIVE_COMMAND_SPECS if spec.parent_key == "app_live_deudas" and spec.kind == "leaf"}
    assert names == {"list", "view", "latest"}
    assert "view" not in names
    assert "pull" not in names
