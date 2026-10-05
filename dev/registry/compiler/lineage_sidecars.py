"""Validate lineage attestations against materialised revision family membership."""

from __future__ import annotations

from collections.abc import Mapping

from cadrumo.domain.calculations.registry.errors import (
    RegistryValidationError,
)
from cadrumo.domain.calculations.registry.keyed_families import (
    INHERITED_FAMILY_SPECS as _CANONICAL_INHERITED_FAMILY_SPECS,
)
from cadrumo.domain.calculations.registry.keyed_families import KeyedFamilySpec
from cadrumo.domain.calculations.registry.keyed_families import (
    family_identity_value as _family_identity_value,
)
from cadrumo.domain.calculations.registry.lineage_attestation import (
    LineageAttestation,
    validate_lineage_attestations,
)
from cadrumo.domain.calculations.registry.schema import (
    ModeloRevision,
)

from .loader_fields import (
    _INHERITED_SECTION,
)


def _with_lineage_claims(revision: ModeloRevision) -> ModeloRevision:
    """Expose target-edge claims to typed consumers, never to the inheritance input.

    Sidecars have already passed membership, uniqueness and exact-edge validation.
    The stored claim has one owner; its typed row view must not suppress a second
    authored owner, even when both spell the same evidence.
    """
    claims = {
        attestation.identity: attestation
        for attestation in revision.lineage_attestations
        if attestation.family == _INHERITED_SECTION
    }
    if not claims:
        return revision
    rows = []
    for casilla in revision.casillas:
        claim = claims.get(str(casilla.continuidad_id))
        if claim is None:
            rows.append(casilla)
            continue
        if casilla.continuidad_origin is not None or casilla.continuidad_evidence is not None:
            raise RegistryValidationError(
                f"revision {revision.id!r} casilla {casilla.id!r} duplicates lineage evidence ownership: "
                "declare the claim on the row or in lineage_attestations, not both",
            )
        rows.append(
            casilla.model_copy(
                update={"continuidad_origin": claim.origin, "continuidad_evidence": claim.evidence},
            ),
        )
    return revision.model_copy(update={"casillas": tuple(rows)})


def _validate_lineage_sidecars(
    revisions: Mapping[str, ModeloRevision],
    *,
    predecessors: Mapping[str, str],
) -> None:
    """Validate authored lineage sidecars against the typed materialised revisions.

    The sidecar is revision-level and therefore must be authored on the
    successor it names.  Family identities come from the same canonical keyed
    family policy the materialiser uses: casillas are keyed by
    ``continuidad_id`` and identifier-keyed families by their declared
    identity.  Building the index from typed revisions means inherited members
    are present while row-local claims remain exactly as authored.
    """
    sidecars, members_by_revision = _lineage_snapshot(revisions)
    validate_lineage_attestations(
        sidecars,
        predecessors=predecessors,
        members_by_revision=members_by_revision,
    )


def _lineage_snapshot(
    revisions: Mapping[str, ModeloRevision],
) -> tuple[list[LineageAttestation], dict[str, dict[str, tuple[str, ...]]]]:
    sidecars: list[LineageAttestation] = []
    members_by_revision: dict[str, dict[str, tuple[str, ...]]] = {}
    for revision_id, revision in revisions.items():
        members_by_revision[revision_id] = _revision_members(revision)
        for attestation in revision.lineage_attestations:
            _require_target_revision(revision_id, attestation)
            sidecars.append(attestation)
    return sidecars, members_by_revision


def _revision_members(revision: ModeloRevision) -> dict[str, tuple[str, ...]]:
    """Index casilla and keyed-family identities from one materialised revision."""
    families = {
        _INHERITED_SECTION: tuple(
            str(member.continuidad_id) for member in revision.casillas if member.continuidad_id is not None
        )
    }
    families.update(
        (family.section, _keyed_family_identities(revision, family)) for family in _CANONICAL_INHERITED_FAMILY_SPECS
    )
    return families


def _keyed_family_identities(revision: ModeloRevision, family: KeyedFamilySpec) -> tuple[str, ...]:
    """Return declared member identities using the canonical family policy."""
    value = getattr(revision, family.section)
    members = (value,) if family.singleton and value is not None else () if family.singleton else value or ()
    return tuple(
        str(identity)
        for member in members
        if family.identity is not None and (identity := _family_identity_value(member, family.identity)) is not None
    )


def _require_target_revision(revision_id: str, attestation: LineageAttestation) -> None:
    if attestation.to_revision != revision_id:
        raise RegistryValidationError(
            f"revision {revision_id!r} authors lineage attestation for target "
            f"revision {attestation.to_revision!r}; sidecars are edge-local and "
            "must be authored on their target revision",
        )
