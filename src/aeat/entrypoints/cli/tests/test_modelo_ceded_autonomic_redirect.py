"""Ceded autonomic modelo discovery-redirect coverage.

ITP-AJD (Modelo 600 / 620) and ISD (Modelo 650 / 660) are ceded autonomic
taxes managed by each Comunidad Autónoma, not AEAT modelos present in the
calculation registry. A discovery lookup for one of these codes must refuse
with an instructive autonomic redirect that names the ceded tax, its enabling
law, and the regional Hacienda / CCAA filing route, instead of a generic
not-present-in-registry error.

These tests drive the real CLI, registry, and locale system through
``invoke_cached_cli``; no mocks, patches, or monkeypatches are involved.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from ....tests.cli_runner import invoke_cached_cli
from .._errors import CliRefusedBoundaryError
from .._modelo_discovery_cli import guard_ceded_autonomic_modelo

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@dataclass(frozen=True)
class CededRedirectCase:
    modelo: str
    required_groups: tuple[tuple[str, ...], ...]


# 600/620 are ITP-AJD (Ley 28/1990); 650/660 are ISD (Ley 29/1987). Each is a
# tributo cedido filed with the competent regional Hacienda / CCAA.
_CEDED_CASES = (
    CededRedirectCase(modelo="600", required_groups=(("28/1990", "ITPyAJD"), ("Hacienda", "CCAA"))),
    CededRedirectCase(modelo="620", required_groups=(("28/1990", "ITPyAJD"), ("Hacienda", "CCAA"))),
    CededRedirectCase(modelo="650", required_groups=(("29/1987", "LISyD"), ("Hacienda",))),
    CededRedirectCase(modelo="660", required_groups=(("29/1987", "LISyD"), ("Hacienda",))),
)


def _discovery_args(verb: str, modelo: str) -> list[str]:
    if verb == "casilla":
        return ["app", "modelo", "casilla", modelo, "0596"]
    return ["app", "modelo", verb, modelo]


_DISCOVERY_VERBS = ("describe", "casillas", "casilla", "formulas")


@pytest.mark.parametrize("verb", _DISCOVERY_VERBS)
@pytest.mark.parametrize("case", _CEDED_CASES, ids=[case.modelo for case in _CEDED_CASES])
def test_discovery_lookup_of_ceded_modelo_redirects_to_autonomic_authority(
    verb: str,
    case: CededRedirectCase,
) -> None:
    """Every discovery verb refuses a ceded modelo with the autonomic redirect."""

    result = invoke_cached_cli(_discovery_args(verb, case.modelo))
    output = result.output or ""

    assert result.exit_code != 0, output
    assert "Traceback" not in output
    # The generic registry-lookup error must not leak for a known ceded tax.
    assert "not present in the calculation registry" not in output
    assert "Modelo desconocido" not in output
    for required_group in case.required_groups:
        assert any(token in output for token in required_group), (
            f"{verb} {case.modelo} output did not contain any of {required_group!r}: {output!r}"
        )


def test_guard_raises_typed_refusal_with_modelo_context_for_ceded_family() -> None:
    """The guard raises a typed refusal carrying the requested modelo in context."""

    for modelo in ("600", "620", "650", "660", " 600 "):
        with pytest.raises(CliRefusedBoundaryError) as exc_info:
            guard_ceded_autonomic_modelo(modelo)
        assert exc_info.value.translated_message is not None
        assert exc_info.value.context is not None
        assert exc_info.value.context.get("modelo") == modelo.strip()


def test_guard_is_noop_for_registry_backed_and_unknown_modelos() -> None:
    """The guard must not hijack a real registry modelo or a genuinely unknown code."""

    # 303 is registry-backed; 999 is genuinely unknown; neither is a ceded tax.
    guard_ceded_autonomic_modelo("303")
    guard_ceded_autonomic_modelo("999")
