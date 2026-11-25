"""Give one revision filing reach in an in-memory authority copy, for tests of the export writer.

The export writer serves filing-grade snapshots only. A test about the bytes a
revision's export layout writes (its geometry, its codec round trip, which box a
value lands in) needs that writer even when the revision declares a lower grade,
for instance a layout authored but not yet released for filing. Such a test lifts
the grade here, in a copy that lives only for the test, and never in the
registry: the declared grade is neither read as earned nor changed, and every
refusal a real export meets at that grade stays in force outside the copy.
"""

from __future__ import annotations

import dataclasses

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority


def with_filing_reach(
    authority: ValidatedRegistryAuthority, modelo_id: str, revision_id: str
) -> ValidatedRegistryAuthority:
    """Return an in-memory copy of ``authority`` in which one revision reaches filing grade."""
    modelo = authority.modelo(modelo_id)
    revision = modelo.revisions[revision_id]
    if revision.effective_authority_grade is RegistryAuthorityGrade.FILING:
        return authority
    staged = modelo.model_copy(
        update={
            "revisions": {
                **modelo.revisions,
                revision_id: revision.model_copy(update={"authority_grade": RegistryAuthorityGrade.FILING}),
            }
        }
    )
    modelos = tuple(staged if candidate.id == modelo_id else candidate for candidate in authority.modelos)
    return dataclasses.replace(
        authority, modelos=modelos, modelos_by_id={candidate.id: candidate for candidate in modelos}, snapshots={}
    )
