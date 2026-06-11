"""Regression tests for Modelo 721 unsupported local-work refusal.

contract show-stopper: ``aeat app modelo work create --modelo 721`` must
return a legally-grounded refusal payload rather than a silent error or
an unroutable work unit.

Modelo 721 (declaración informativa sobre monedas virtuales situadas en
el extranjero) is governed by Ley 11/2021 DA 10ª / Art. 13,
Orden HFP/887/2023 (BOE-A-2023-17455), and RD 1065/2007 Art. 42 quáter.
Taxpayers with aggregate virtual-currency holdings abroad exceeding
€50,000 at 31 December have a statutory obligation, but the CLI has not
yet authored the full casilla inventory required for calculation-engine
support.  The refusal guard surfaces the unsupported surface with the governing legal
authority rather than a generic crash.

No mocks: the guard runs against the real registry authority and locale
system.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....tests.aeat_literal_fixtures import aeat_host
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
_SEDE_HOST = aeat_host("sede")


@pytest.fixture(autouse=True)
def _isolated_cli_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


def test_work_create_721_refuses_with_legal_authority_message(
    _isolated_cli_backend: Path,
) -> None:
    """contract: ``work create --modelo 721`` is refused with a legally-grounded
    message citing Orden HFP/887/2023.

    The CLI must NOT return a generic crash, a silent empty result, or
    ``Modelo desconocido 721``.  The refusal message must name the gap,
    cite the legal authority, and redirect to AEAT Sede.
    """

    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "create",
            "--modelo", "721",
            "--year", "2024",
            "--period", "0A",
            "--revision", "2023-y-siguientes",
        ],
    )  # fmt: skip

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    # Must name the legal authority for the 721 obligation.
    assert "HFP/887/2023" in result.output
    # Must name the €50.000 threshold from Orden HFP/887/2023 Art. 3.
    assert "50" in result.output
    # Must redirect to AEAT Sede, not imply local-CLI filing support.
    assert _SEDE_HOST in result.output or "Sede" in result.output
    # Generic crash / unrouted error messages are forbidden.
    assert "could not evaluate" not in result.output
    assert "Modelo desconocido" not in result.output


def test_work_create_721_has_no_placeholder_registry_definition(
    _isolated_cli_backend: Path,
) -> None:
    """M721 registry presence must be legally grounded.

    The registry carries a manual-casilla definition. The work-create
    refusal still fires (sibling test
    test_work_create_721_refuses_with_legal_authority_message proves
    that), because the calculation engine and form-flow remain
    unsupported. The contract this test defends: when M721 IS in the registry, it MUST be
    grounded by the binding legal authority (Ley 11/2021 DA 10ª cripto
    declaration obligation + the form-approval order corpus).
    """

    from ....core.resources import bundled_path
    from ....domain.calculations.registry import load_registry_tree

    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    assert "721" in {modelo.id for modelo in modelos}
    assert "ley-11-2021:da-10" in catalogues.legal
    assert "boe-modelo-721-2023-form" in catalogues.sources


def test_work_create_721_refusal_fires_before_profile_check(
    _isolated_cli_backend: Path,
) -> None:
    """The unsupported-model guard fires before the active-profile requirement.

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
        ],
    )  # fmt: skip

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    # Refusal message fires before profile check: must contain the
    # legal authority reference, not a generic profile-missing message.
    assert "HFP/887/2023" in result.output
