"""Regression tests for Modelo 714 Path-B refusal stub.

Eva round-10 show-stopper: ``aeat app modelo work create --modelo 714``
must return a legally-grounded refusal payload rather than a silent error
or an unroutable work unit.

Modelo 714 is the declaración for the Impuesto sobre el Patrimonio under
Ley 19/1991 Art. 28, governed by Orden HAC/1023/2021 (BOE-A-2021-7593).
The obligation threshold is net wealth > €700.000 in general (€600.000 in
Comunitat Valenciana).  The full casilla inventory and calculation engine
have not yet been authored; the guard surfaces this gap with the governing
legal authority rather than a generic crash.

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
            "--activity", "designer",
            "--entity-type", "natural_person",
            "--irpf-income-categories", "trabajo",
            "--irpf-estimation-regime", "directa_normal",
        ]
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def test_work_create_714_refuses_with_legal_authority_message(
    _isolated_cli_backend: Path,
) -> None:
    """work create --modelo 714 is refused with a legally-grounded message
    citing Ley 19/1991 Art. 28 and Orden HAC/1023/2021.

    The CLI must NOT return a generic crash, a silent empty result, or
    ``Modelo desconocido 714``.  The refusal message must name the gap,
    cite the legal authority, and redirect to AEAT Sede Electrónica.
    """

    _create_natural_person()
    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "create",
            "--modelo", "714",
            "--year", "2024",
            "--period", "0A",
            "--revision", "2021-y-siguientes",
        ]
    )  # fmt: skip

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    # Must name the primary legal authority for the 714 obligation.
    assert "19/1991" in result.output or "1991" in result.output
    # Must cite the form-approval order.
    assert "HAC/1023/2021" in result.output or "1023" in result.output
    # Must redirect to AEAT Sede, not imply local-CLI filing support.
    assert "sede.agenciatributaria.gob.es" in result.output or "Sede" in result.output
    # Generic crash / unrouted error messages are forbidden.
    assert "could not evaluate" not in result.output
    assert "Modelo desconocido" not in result.output


def test_work_create_714_registry_loader_accepts_without_integrity_error(
    _isolated_cli_backend: Path,
) -> None:
    """Roundtrip: the registry loader must accept the M714 stub without
    integrity errors (referential integrity, source catalogue).

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
    modelo_714 = next(m for m in modelos if m.id == "714")

    # Validate the definition against its catalogues — no integrity errors.
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo_714)

    # Must resolve revision for year 2024, period 0A.
    snapshot = build_snapshot(
        modelo_714,
        catalogues,
        source_root=bundled_path(),
        filing_year=2024,
        period="0A",
    )
    assert snapshot.revision.id == "2021-y-siguientes"


def test_work_create_714_refusal_fires_before_profile_check(
    _isolated_cli_backend: Path,
) -> None:
    """The stub-model guard fires before the active-profile requirement.

    An operator without an active profile still gets the M714 refusal
    message (not a ``no active profile`` error), proving the guard
    runs on registry state alone.
    """

    # No profile created — no active session.
    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "create",
            "--modelo", "714",
            "--year", "2024",
            "--period", "0A",
            "--revision", "2021-y-siguientes",
        ]
    )  # fmt: skip

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    # Refusal message fires before profile check: must contain the
    # legal authority reference, not a generic profile-missing message.
    assert "HAC/1023/2021" in result.output or "1991" in result.output
