"""A credential-shaped field must say so in its classification.

Masking is decided by a field's declared :class:`SensitivityClass` and
nothing else. That is the right runtime rule -- authored prose must not
override an explicit declaration -- but it leaves one hole: a field that
IS a credential and is declared ``identity`` by mistake renders in the
clear, and no runtime check would notice.

This gate is that check, moved to build time where it belongs. A
heuristic that guesses at runtime can only silently override a
declaration, which is what the previous masking policy did. A heuristic
that runs here can only refuse, and it refuses loudly, naming the field.
It also reads every declared field on every run, where the runtime arm
only ever saw fields something happened to render.

Three layers cover the space between them, and it is worth being
explicit about which covers what, because none of them covers all of it:

* The known credential set is pinned by name in the auth schema shape
  tests -- an explicit list, stronger than any heuristic.
* A field NAMED or DESCRIBED like a credential but not classified as one
  is refused here, before it can ship.
* A fact arriving at a surface under a path no schema field declares has
  no declaration to consult, so the runtime keyword arm still covers it.

The honest limit of this gate: its predicate has no purchase on the
three Cl@ve credentials it would most want to protect. Nothing about
``auth.numero_soporte`` reads like a credential to a keyword matcher, so
downgrading it would pass here. That is exactly why the pinned-by-name
tests exist and why this gate does not replace them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import pytest

from ....core.classification import SensitivityClass
from ....domain.user_profile import (
    ProfileFieldDefinition,
    ProfileFieldType,
    ProfileRemovePolicy,
    ProfileSchemaDefinition,
    ProfileSectionDefinition,
    ProfileSnapshotPolicy,
    load_user_profile_schema,
)
from .._overview import _MASK_KEYWORDS

if TYPE_CHECKING:
    from collections.abc import Mapping

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_EXEMPT: Final[Mapping[str, str]] = {
    "censo.divergencia": (
        "Matches on 'provenance token'. That is this project's own term for the source "
        "marker on a divergence row (PROVENANCE_SOURCE_CENSO_ARTEFACT), not a bearer "
        "token: the row holds a diverging fact's schema path, the certificate value the "
        "operator did not adopt, and that marker. Fiscal profile content, rendered in "
        "the clear beside contact.fiscal_address, and not authentication material. Its "
        "former mask was decorative in any case and must not be restored as a fix: the "
        "row the schema declares is the unindexed path, which never carries a value, "
        "while the indexed censo.divergencia.{n}.* subpaths that do carry the content "
        "resolve to no schema field and render unmasked."
    ),
}
"""Fields whose credential-shaped wording is a false positive.

Each entry states why the field is not authentication material. An entry
whose field has stopped matching is removed, not left standing -- the
staleness gate below refuses one, so the list cannot outlive its cause
and quietly pre-approve a future field at the same path.
"""


def _credential_shaped(schema: ProfileSchemaDefinition) -> dict[str, list[str]]:
    """Return every field reading like a credential, with the keywords it matched.

    Args:
        schema: The schema to walk.

    Returns:
        Mapping of dotted field path to the sorted keywords its path or
        description contains.
    """
    matched: dict[str, list[str]] = {}
    for section in schema.sections:
        for field in section.fields:
            path = f"{section.key}.{field.key}"
            haystack = f"{path} {field.description}".casefold()
            if hits := sorted(keyword for keyword in _MASK_KEYWORDS if keyword in haystack):
                matched[path] = hits
    return matched


def _misdeclared(schema: ProfileSchemaDefinition) -> dict[str, list[str]]:
    """Return credential-shaped fields that neither declare ``secret`` nor are exempt."""
    return {
        path: hits
        for path, hits in _credential_shaped(schema).items()
        if path not in _EXEMPT and schema.field(path).sensitivity is not SensitivityClass.SECRET
    }


def _schema_with(field: ProfileFieldDefinition) -> ProfileSchemaDefinition:
    """Wrap one field in the smallest valid schema, for the control cases."""
    return ProfileSchemaDefinition(
        id="test.credential_gate",
        version=1,
        title="Credential gate control schema",
        snapshot_policy=ProfileSnapshotPolicy.IMMUTABLE_SECURE_SNAPSHOT_HASH,
        remove_policy=ProfileRemovePolicy.LIVE_PROFILE_TOMBSTONE_RETAIN_SNAPSHOTS,
        sections=(
            ProfileSectionDefinition(
                key="auth",
                title="Authentication",
                sensitivity=SensitivityClass.IDENTITY,
                fields=(field,),
            ),
        ),
    )


def test_the_shipped_schema_declares_every_credential_shaped_field_secret() -> None:
    """No shipped field may read like a credential and be classed as anything else.

    DISCRIMINATING, but honest about its reach: today the shipped schema
    gives it exactly one live subject, and that one is exempt. Its value
    is prospective -- it refuses the NEXT ``auth.password`` added at
    ``identity`` -- so the control below proves it can fail at all,
    rather than leaving a gate that has never been seen to bite.
    """
    misdeclared = _misdeclared(load_user_profile_schema())
    assert not misdeclared, (
        "these fields read like credentials but are not declared secret; "
        f"classify them or record why they are not: {misdeclared}"
    )


def test_the_gate_refuses_a_credential_named_field_declared_identity() -> None:
    """The positive control: the gate bites on the case it exists for.

    Without this, the assertion above would pass just as happily against
    a predicate that matched nothing at all -- and against the shipped
    schema it very nearly does. This builds the misdeclaration the gate
    is for and requires it to be reported, so a future refactor that
    empties the keyword set or breaks the walk fails here instead of
    going quietly green.
    """
    misdeclared = _misdeclared(
        _schema_with(
            ProfileFieldDefinition(
                key="password",
                type=ProfileFieldType.STRING,
                sensitivity=SensitivityClass.IDENTITY,
                description="Cl@ve Permanente login password.",
            ),
        ),
    )
    assert misdeclared == {"auth.password": ["password"]}


def test_the_gate_accepts_the_same_field_declared_secret() -> None:
    """The negative half of the control: classifying it correctly clears it.

    A gate that refused either way would satisfy the control above while
    making the declaration meaningless.
    """
    assert not _misdeclared(
        _schema_with(
            ProfileFieldDefinition(
                key="password",
                type=ProfileFieldType.STRING,
                sensitivity=SensitivityClass.SECRET,
                description="Cl@ve Permanente login password.",
            ),
        ),
    )


def test_no_exemption_outlives_the_wording_that_caused_it() -> None:
    """An exemption must name a field that still exists and still matches.

    An allowlist nobody prunes is how a gate rots: a stale entry sits
    there pre-approving whatever later occupies that path, and it reads
    to the next author as a decision rather than as residue. An entry
    survives only while the field it names is still flagged.
    """
    schema = load_user_profile_schema()
    flagged = _credential_shaped(schema)
    stale = sorted(path for path in _EXEMPT if path not in flagged)
    assert not stale, f"these exemptions no longer describe a flagged field and must be removed: {stale}"
