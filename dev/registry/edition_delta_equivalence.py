"""Prove that staged edition chains preserve member identities and effective bytes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from . import edition_delta_chain_materialisation as _edition_delta_chain_materialisation
from . import edition_delta_errors as _edition_delta_errors
from . import edition_delta_proof_source as _edition_delta_proof_source
from .edition_round_trip import RoundTripFindingKind, RoundTripReport


def _prove_chain(
    *,
    reference_modelo_dir,
    staged_modelo_dir,
    revision_ids: Sequence[str],
    report: RoundTripReport,
) -> RoundTripReport:
    """Require staged storage to materialise to the exact bytes planned from."""
    for revision_id in revision_ids:
        before = _edition_delta_proof_source.read_staged_edition(reference_modelo_dir, revision_id, side="reference")
        after = _edition_delta_proof_source.read_staged_edition(staged_modelo_dir, revision_id, side="staged")
        difference = _member_difference(
            _edition_delta_chain_materialisation.member_identities(before),
            _edition_delta_chain_materialisation.member_identities(after),
        )
        if difference is not None:
            raise _edition_delta_errors.MigrationRefusedError(f"edition {revision_id!r}: {difference}")
        before_bytes = _edition_delta_chain_materialisation.chain_materialisation(before)
        after_bytes = _edition_delta_chain_materialisation.chain_materialisation(after)
        if before_bytes != after_bytes:
            raise _edition_delta_errors.MigrationRefusedError(
                f"edition {revision_id!r}: the staged tree materialises to different bytes than the tree it was "
                "planned from, so the lift is not an identity and cannot be proven",
            )
    return RoundTripReport(
        findings=tuple(
            finding
            for finding in report.findings
            if finding.kind not in {RoundTripFindingKind.REFERENCE_NOT_FULL_COPY, RoundTripFindingKind.ROW_ORDER}
        ),
        byte_compared_revisions=report.byte_compared_revisions,
    )


def _member_difference(
    reference_members: Mapping[str, tuple[str, ...]],
    staged_members: Mapping[str, tuple[str, ...]],
) -> str | None:
    """Describe the first family whose complete materialised membership differs."""
    staged_only = [section for section in staged_members if section not in reference_members]
    for section in [*reference_members, *staged_only]:
        members, staged_section = reference_members.get(section, ()), staged_members.get(section, ())
        if staged_section != members:
            return (
                f"lifting changed the {section} members, which a lift may never do: "
                f"{len(members)} before, {len(staged_section)} after, first difference at "
                f"{_first_difference(members, staged_section)}"
            )
    return None


def _first_difference(before: Sequence[str], after: Sequence[str]) -> str:
    """Describe the first position at which two member-identity sequences diverge."""
    for index, (left, right) in enumerate(zip(before, after, strict=False)):
        if left != right:
            return f"position {index}: {left!r} became {right!r}"
    shared = min(len(before), len(after))
    trailing = list(before[shared:]) or list(after[shared:])
    side = "reference" if len(before) > len(after) else "staged"
    return f"position {shared}: {trailing!r} on the {side} side only"
