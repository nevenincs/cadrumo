"""Regression tests for Modelo 151 unsupported local-work refusal.

David round-10 show-stopper: ``aeat app modelo work create --modelo 151``
must return a legally-grounded refusal payload rather than a silent error
or an unroutable work unit.

Modelo 151 is the declaración for the régimen especial de impatriados
("Ley Beckham") under Ley 35/2006 Art. 93 LIRPF, developed by
RD 439/2007 Arts. 113-120 (RIRPF), and submitted via Orden EHA/2887/2008
(BOE-A-2008-16237).  The full casilla inventory and calculation engine
have not yet been authored; the guard surfaces this unsupported surface with the
governing legal authority rather than a generic crash.

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


def test_work_create_151_refuses_with_legal_authority_message(
    _isolated_cli_backend: Path,
) -> None:
    """work create --modelo 151 is refused with a legally-grounded message
    citing Ley 35/2006 Art. 93 and Orden EHA/2887/2008.

    The CLI must NOT return a generic crash, a silent empty result, or
    ``Modelo desconocido 151``.  The refusal message must name the gap,
    cite the legal authority, and redirect to AEAT Sede Electrónica.
    """

    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "create",
            "--modelo", "151",
            "--year", "2024",
            "--period", "0A",
            "--revision", "2024-y-siguientes",
        ],
    )  # fmt: skip

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    # Must name the primary legal authority for the 151 obligation.
    assert "93" in result.output
    # Must cite the form-approval order.
    assert "EHA/2887/2008" in result.output or "2887" in result.output
    # Must redirect to AEAT Sede, not imply local-CLI filing support.
    assert _SEDE_HOST in result.output or "Sede" in result.output
    # Generic crash / unrouted error messages are forbidden.
    assert "could not evaluate" not in result.output
    assert "Modelo desconocido" not in result.output


def test_work_create_151_has_no_placeholder_registry_definition(
    _isolated_cli_backend: Path,
) -> None:
    """M151 registry presence must be legally grounded.

    The registry carries a manual-casilla definition, but the
    calculation engine and form-flow remain unsupported. The
    work-create refusal still fires (sibling test
    test_work_create_151_refuses_with_legal_authority_message proves
    that). The contract this test defends: when M151 IS in the registry, it MUST be
    grounded by the binding legal authority (Ley 35/2006 Art. 93 LIRPF
    Beckham + the form-approval order corpus).
    """

    from ....core.resources import bundled_path
    from ....domain.calculations.registry import load_registry_tree

    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    assert "151" in {modelo.id for modelo in modelos}
    assert "ley-35-2006:art-93" in catalogues.legal
    assert "boe-modelo-151-form" in catalogues.sources


def test_work_create_151_refusal_fires_before_profile_check(
    _isolated_cli_backend: Path,
) -> None:
    """The unsupported-model guard fires before the active-profile requirement.

    An operator without an active profile still gets the M151 refusal
    message (not a ``no active profile`` error), proving the guard
    runs on registry state alone.
    """

    # No profile created — no active session.
    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "create",
            "--modelo", "151",
            "--year", "2024",
            "--period", "0A",
            "--revision", "2024-y-siguientes",
        ],
    )  # fmt: skip

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    # Refusal message fires before profile check: must contain the
    # legal authority reference, not a generic profile-missing message.
    assert "EHA/2887/2008" in result.output or "93" in result.output
