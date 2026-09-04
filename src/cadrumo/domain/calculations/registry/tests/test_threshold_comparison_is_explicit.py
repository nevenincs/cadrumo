"""Gate the declarations whose COMPARISON DIRECTION is load-bearing.

``DatedValue.comparison`` defaults to ``EXCLUSIVE``. That default is right for
the many values never used as a threshold, but it makes a threshold parameter
dangerous in one specific way: deleting the ``comparison`` line from its TOML is
not a validation error, it is a silent semantic flip.

LIVA art. 103.Dos.2 is the case in point. The redaction in force reads "exceda en
un 10 por ciento o más", and the "o más" is what makes a deduction landing
exactly on the margin already compulsory. Drop the declared ``comparison`` and
the same taxpayer files under prorrata general where the law compels especial --
with registry validation, type checking and every other test still passing.

These tests therefore assert that the key is EXPLICITLY DECLARED in the source,
not what its value is. That distinction is deliberate: what the law says belongs
to the registry declaration, and a test asserting it here would just move the
legal claim back into Python. What a test can honestly own is that the
declaration is not silently relying on a default.

The compiled half of each check goes through the validated authority; the
explicitness half must read the TOML source, because a default is by definition
invisible once compiled.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from ..authority import ValidatedRegistryAuthority, bundled_authority

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

#: Parameters whose comparison direction changes the arithmetic, by modelo.
_THRESHOLD_PARAMETER_IDS = (
    "m303-prorrata-especial-obligatoria-margen-porcentaje",
    "m303-bien-inversion-regularizacion-umbral-puntos",
)

_M303_REVISIONS = (
    "2022",
    "2023",
    "2024-hasta-08-y-2t",
    "2024-desde-09-y-3t",
    "2025",
    "2026-y-siguientes",
)

_M303_REVISIONS_ROOT = Path(__file__).resolve().parents[4] / "_data/registry/aeat/modelos/303/revisions"


@pytest.fixture(scope="session")
def registry_authority() -> ValidatedRegistryAuthority:
    """The bundled validated authority."""
    return bundled_authority()


def _declared_values_in_source(revision_id: str, parameter_id: str) -> list[dict[str, object]]:
    """Return the raw declared values for one parameter, read from the TOML source.

    Source is read here rather than the compiled revision precisely because the
    question is whether a key was WRITTEN. Once compiled, a defaulted field and
    a declared one are indistinguishable.
    """
    found: list[dict[str, object]] = []
    for path in sorted((_M303_REVISIONS_ROOT / revision_id / "parameters").glob("*.toml")):
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        for revision in raw.get("revisions", {}).values():
            for parameter in revision.get("parameters", []):
                if parameter.get("id") == parameter_id:
                    found.extend(parameter.get("values", []))
    return found


@pytest.mark.parametrize("parameter_id", _THRESHOLD_PARAMETER_IDS)
@pytest.mark.parametrize("revision_id", _M303_REVISIONS)
def test_every_revision_declares_the_threshold_parameter(
    registry_authority: ValidatedRegistryAuthority,
    revision_id: str,
    parameter_id: str,
) -> None:
    """A revision missing one of these has no grounded threshold to compare against."""
    revision = registry_authority.modelo("303").revisions[revision_id]
    assert any(parameter.id == parameter_id for parameter in revision.parameters), (
        f"modelo 303 revision {revision_id} does not declare {parameter_id}"
    )


@pytest.mark.parametrize("parameter_id", _THRESHOLD_PARAMETER_IDS)
@pytest.mark.parametrize("revision_id", _M303_REVISIONS)
def test_the_comparison_direction_is_explicitly_declared(
    revision_id: str,
    parameter_id: str,
) -> None:
    """TEETH: deleting the comparison line is a silent semantic flip, not an error.

    The assertion is about the KEY being written, never about which direction it
    names -- that is the registry's claim to make, not this file's.
    """
    values = _declared_values_in_source(revision_id, parameter_id)
    assert values, f"{parameter_id} not found in modelo 303 revision {revision_id} source"
    for value in values:
        assert "comparison" in value, (
            f"{parameter_id} in modelo 303 revision {revision_id} declares a dated value with no "
            "explicit 'comparison'. DatedValue.comparison defaults to EXCLUSIVE, so an omitted key "
            "here silently changes whether a value landing exactly on the threshold qualifies. "
            "Declare the direction the governing redaction states."
        )


@pytest.mark.parametrize("parameter_id", _THRESHOLD_PARAMETER_IDS)
def test_the_threshold_agrees_across_every_revision(
    registry_authority: ValidatedRegistryAuthority,
    parameter_id: str,
) -> None:
    """A divergence means one revision was updated and the others were not.

    Compares revisions against EACH OTHER rather than against a literal, so this
    holds no legal value of its own and survives a lawful change that moves
    every revision at once.
    """
    seen: dict[str, tuple[object, object]] = {}
    for revision_id in _M303_REVISIONS:
        revision = registry_authority.modelo("303").revisions[revision_id]
        parameter = next(p for p in revision.parameters if p.id == parameter_id)
        assert len(parameter.values) == 1, (
            f"{parameter_id} in revision {revision_id} declares {len(parameter.values)} dated "
            "values; a threshold read per filing context carries exactly one per revision"
        )
        value = parameter.values[0]
        assert value.date_axis == "filing_period"
        assert value.valid_from == revision.valid_from
        assert value.valid_to == revision.valid_to
        seen[revision_id] = (value.value, value.comparison)

    first, *rest = _M303_REVISIONS
    for revision_id in rest:
        assert seen[revision_id] == seen[first], (
            f"revision {revision_id} declares a different {parameter_id} than {first}: "
            f"{seen[revision_id]} vs {seen[first]}"
        )
