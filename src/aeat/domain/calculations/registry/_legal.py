"""Legal catalogue helpers."""

from __future__ import annotations

from collections.abc import Mapping

from ...modelos import LegalCitationSource
from ...modelos._citation_registry import find_known_bad
from ._errors import RegistryValidationError
from ._schema import LegalReference

_SOURCE_BY_KIND = {
    "ley": LegalCitationSource.LEY,
    "real_decreto": LegalCitationSource.REGLAMENTO,
    "orden": LegalCitationSource.ORDEN_MINISTERIAL,
    "reglamento": LegalCitationSource.REGLAMENTO,
    "manual": LegalCitationSource.MANUAL_PRACTICO,
    "instruction": LegalCitationSource.BOE,
}


def verify_legal_reference(reference: LegalReference) -> None:
    """Verify one already parsed legal reference is filing-grade."""

    if reference.review_status != "reviewed":
        raise RegistryValidationError(f"legal reference {reference.id!r} is not reviewed")
    if reference.article is None:
        return
    source = _SOURCE_BY_KIND.get(reference.kind)
    if source is None:
        return
    role_text = " ".join(part for part in (reference.section, reference.notes) if part)
    if role_text and (known_bad := find_known_bad(source, reference.article, role_text)):
        raise RegistryValidationError(
            f"legal reference {reference.id!r} matches known-bad citation: {known_bad.reason}"
        )


def verify_legal_catalogue(legal: Mapping[str, LegalReference]) -> None:
    """Verify every legal reference in a shared legal catalogue."""

    failures: list[str] = []
    for ref_id, reference in legal.items():
        if ref_id != reference.id:
            failures.append(f"legal catalogue key {ref_id!r} does not match reference id {reference.id!r}")
        try:
            verify_legal_reference(reference)
        except RegistryValidationError as exc:
            failures.append(str(exc))
    if failures:
        raise RegistryValidationError("legal catalogue validation failed:\n" + "\n".join(f" - {f}" for f in failures))
