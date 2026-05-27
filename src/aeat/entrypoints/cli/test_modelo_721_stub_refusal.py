"""Regression tests for Modelo 721 Path-B refusal stub.

S367 show-stopper: ``aeat app modelo work create --modelo 721`` must
return a legally-grounded refusal payload rather than a silent error or
an unroutable work unit.

Modelo 721 (declaración informativa sobre monedas virtuales situadas en
el extranjero) is governed by Ley 11/2021 DA 10ª / Art. 13,
Orden HFP/887/2023 (BOE-A-2023-17455), and RD 1065/2007 Art. 42 quáter.
Taxpayers with aggregate virtual-currency holdings abroad exceeding
€50,000 at 31 December have a statutory obligation, but the CLI has not
yet authored the full casilla inventory required for calculation-engine
support.  The refusal guard surfaces the gap with the governing legal
authority rather than a generic crash.

No mocks: the guard runs against the real registry authority and locale
system.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from aeat.tests.cli_runner import invoke_cached_cli
from aeat.tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _isolated_cli_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


def _create_natural_person() -> None:
    result = invoke_cached_cli(
        [
            "config", "profile", "create", "operator",
            "--quiet", "--accept-defaults",
            "--tax-id", "12345678Z",
            "--name", "Operator",
            "--activity", "design",
            "--entity-type", "natural_person",
            "--irpf-income-categories", "actividad_economica",
            "--irpf-estimation-regime", "directa_normal",
        ]
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def test_work_create_721_refuses_with_legal_authority_message(
    _isolated_cli_backend: Path,
) -> None:
    """S367: ``work create --modelo 721`` is refused with a legally-grounded
    message citing Orden HFP/887/2023.

    The CLI must NOT return a generic crash, a silent empty result, or
    ``Modelo desconocido 721``.  The refusal message must name the gap,
    cite the legal authority, and redirect to AEAT Sede.
    """

    _create_natural_person()
    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "create",
            "--modelo", "721",
            "--year", "2024",
            "--period", "0A",
            "--revision", "2023-y-siguientes",
        ]
    )  # fmt: skip

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    # Must name the legal authority for the 721 obligation.
    assert "HFP/887/2023" in result.output
    # Must name the €50.000 threshold from Orden HFP/887/2023 Art. 3.
    assert "50" in result.output
    # Must redirect to AEAT Sede, not imply local-CLI filing support.
    assert "sede.agenciatributaria.gob.es" in result.output or "Sede" in result.output
    # Generic crash / unrouted error messages are forbidden.
    assert "could not evaluate" not in result.output
    assert "Modelo desconocido" not in result.output


def test_work_create_721_registry_loader_accepts_without_integrity_error(
    _isolated_cli_backend: Path,
) -> None:
    """Roundtrip: the registry loader must accept the M721 stub without
    integrity errors (referential integrity, SHA256, source catalogue).

    This test validates the registry entry itself, independently of the
    CLI refusal guard.
    """

    from aeat.core.resources import bundled_path
    from aeat.domain.calculations.registry import (
        RegistryValidator,
        build_snapshot,
        load_registry_tree,
    )

    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo_721 = next(m for m in modelos if m.id == "721")

    # Validate the definition against its catalogues — no integrity errors.
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo_721)

    # Must resolve revision for year 2024, period 0A.
    snapshot = build_snapshot(
        modelo_721,
        catalogues,
        source_root=bundled_path(),
        filing_year=2024,
        period="0A",
    )
    assert snapshot.revision.id == "2023-y-siguientes"


def test_work_create_721_refusal_fires_before_profile_check(
    _isolated_cli_backend: Path,
) -> None:
    """The stub-model guard fires before the active-profile requirement.

    An operator without an active profile still gets the M721 refusal
    message (not a ``no active profile`` error), proving the guard
    runs on registry state alone.
    """

    # No profile created — no active session.
    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "create",
            "--modelo", "721",
            "--year", "2024",
            "--period", "0A",
            "--revision", "2023-y-siguientes",
        ]
    )  # fmt: skip

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    # Refusal message fires before profile check: must contain the
    # legal authority reference, not a generic profile-missing message.
    assert "HFP/887/2023" in result.output
