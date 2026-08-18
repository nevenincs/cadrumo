"""The IRNR party producer keys are measured against the official design.

Modelo 210's export layout binds roughly half its anchors to party identity, and
those anchors have no casilla and no literal to fall back on. This module reads
the party surface out of the hash-pinned official binary through the shipped
parser and requires the closed producer-key enum to match it exactly, so the
family is proven complete by the SOURCE rather than by a count someone typed.
"""

from __future__ import annotations

import re
from collections import Counter

import pytest

from cadrumo.core import FilingProducerKey
from cadrumo.core.resources import bundled_path
from cadrumo.domain.calculations.registry import load_catalogue_file

from ..pipeline._record_design_ir import load_record_design_intermediate

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_MODELO_210_DESIGNS = (
    ("aeat-dr-210-2022", 2025, "2022"),
    ("aeat-dr-210-2026", 2026, "2026"),
)

#: AEAT's own Contenido prefix for each party block, mapped to the producer-key
#: scope that owns it. Keyed on the official text rather than on anchor ordinals
#: so a re-layout that MOVES a block is tolerated while a block that changes
#: MEANING is not.
_PARTY_BLOCK_SCOPES = {
    "Persona que realiza la autoliquidación": "declarante",
    "Contribuyente.": "contribuyente",
    "Representante del contribuyente": "representante",
    "Pagador/Retenedor": "pagador",
    "Situación del inmueble": "inmueble",
}

#: The one anchor inside a party block that is NOT that party's data: AEAT
#: interleaves administration-reserved padding into the representante and
#: inmueble blocks, and those render as filler, never as a producer key.
_RESERVED_PREFIX = "Reservado para la Administración"


def _party_anchor_counts(source_ref: str, filing_year: int, design_epoch: str) -> Counter[str]:
    """Count official party anchors per scope, straight from the bundled binary."""
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "irnr.toml"))
    intermediate = load_record_design_intermediate(
        bundled_path(),
        catalogues.sources,
        source_ref=source_ref,
        filing_year=filing_year,
        design_epoch=design_epoch,
    )
    counts: Counter[str] = Counter()
    for sheet in intermediate.sheets:
        for field in sheet.fields:
            description = field.normalized_description
            if description.startswith(_RESERVED_PREFIX):
                continue
            for prefix, scope in _PARTY_BLOCK_SCOPES.items():
                if description.startswith(prefix):
                    counts[scope] += 1
                    break
    return counts


def _declared_scope_counts() -> Counter[str]:
    """Count declared IRNR producer keys per PARTY scope.

    Scoped to the party scopes deliberately. The IRNR family also carries
    form-level, ganancia and ingreso/devolución scopes that answer to different
    parts of the design, and counting those here would compare them against a
    party-block census they were never meant to match.
    """
    party_scopes = set(_PARTY_BLOCK_SCOPES.values())
    counts: Counter[str] = Counter()
    for member in FilingProducerKey:
        parts = member.value.split(".")
        if parts[0] == "irnr" and parts[1] in party_scopes:
            counts[parts[1]] += 1
    return counts


@pytest.mark.parametrize(("source_ref", "filing_year", "design_epoch"), _MODELO_210_DESIGNS)
def test_declared_irnr_party_keys_match_the_official_design_anchor_count(
    source_ref: str,
    filing_year: int,
    design_epoch: str,
) -> None:
    """Every party anchor AEAT declares has exactly one producer key, and no key is spare.

    An inequality in either direction is a real defect. Fewer keys than anchors
    means the semantic map will have an anchor it cannot bind, which is the
    blank-slot failure the export completeness gate exists to catch. More keys
    than anchors means a member nothing renders -- dead vocabulary that invites a
    later author to bind the wrong one.
    """
    official = _party_anchor_counts(source_ref, filing_year, design_epoch)
    declared = _declared_scope_counts()

    assert set(official) == set(_PARTY_BLOCK_SCOPES.values()), (
        f"{source_ref}: the official design no longer declares every expected party block; found {sorted(official)}"
    )
    assert declared == official, (
        f"{source_ref}: declared IRNR producer keys per party scope do not match the official "
        f"design's anchor counts.\n  declared: {dict(sorted(declared.items()))}\n  "
        f"official: {dict(sorted(official.items()))}"
    )


def test_irnr_party_keys_are_flat_scoped_and_unique() -> None:
    """The family keeps the enum's flat dotted shape and collides with nothing."""
    values = [member.value for member in FilingProducerKey]
    assert len(values) == len(set(values)), "FilingProducerKey values must be unique"

    irnr = [value for value in values if value.startswith("irnr.")]
    assert irnr, "the IRNR family must be declared"
    malformed = sorted(value for value in irnr if not re.fullmatch(r"irnr(?:\.[a-z0-9_]+){2,4}", value))
    assert malformed == [], (
        "IRNR producer key(s) do not follow the flat dotted scope grammar "
        "'irnr.<party>.<component>[.<sub>]':\n  " + "\n  ".join(malformed)
    )


def test_the_two_address_vocabularies_stay_structurally_separate() -> None:
    """The Spanish-coded and foreign address shapes must not converge on shared members.

    The Spanish-coded vocabulary carries an INE municipal code, a two-digit
    province code and a five-digit postal code; the contribuyente's foreign
    residence carries none of those. Merging them would make rendering a foreign
    region name into a numeric province slot a well-typed operation, so the
    separation is asserted rather than left to authoring discipline.
    """
    spanish_only = {"codigo_ine_municipio", "codigo_provincia"}
    foreign_only = {"region", "country_code"}

    def leaves(infix: str) -> set[str]:
        return {member.value.rsplit(".", 1)[-1] for member in FilingProducerKey if f".{infix}." in member.value}

    representante = leaves("domicilio")
    inmueble = leaves("situacion")
    foreign = leaves("foreign_address")

    assert spanish_only <= representante, "the representante domicilio must keep its Spanish-coded components"
    assert spanish_only <= inmueble, "the inmueble situacion must keep its Spanish-coded components"
    assert foreign_only <= foreign, "the contribuyente foreign address must keep its free-form components"
    assert not (spanish_only & foreign), "the foreign address must not adopt Spanish-coded components"
    assert not (foreign_only & representante), "the representante domicilio must not adopt foreign components"
    assert not (foreign_only & inmueble), "the inmueble situacion must not adopt foreign components"
