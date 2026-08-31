"""Ownership construction for the closed filing-producer vocabulary."""

from __future__ import annotations

from ...core.filing_producer_key import FilingProducerKey
from ...domain.filing.errors import FilingExportValidationError

_MODELO_PRODUCER_NAMESPACE_OWNERS = {
    "amendment_evidence": "modelo_specific_amendment",
    "contact_person": "modelo_specific_contact",
    "entidad_desarrolladora": "product_software_identity",
    "irnr": "modelo_210",
    "m111": "modelo_111",
    "m200": "modelo_200",
    "m202": "modelo_202",
    "m222": "modelo_222",
    "m296": "modelo_296",
    "m303": "modelo_303",
    "m353": "modelo_353",
    "m360": "modelo_360",
    "m840": "modelo_840",
    "presenter": "modelo_specific_presenter",
    "filing": "modelo_specific_filing",
    "prior_domiciliation": "modelo_specific_domiciliation",
    "selected_account": "modelo_specific_account",
    "taxpayer": "modelo_specific_taxpayer",
}


def filing_producer_ownership(
    *,
    shared_snapshot_keys: frozenset[FilingProducerKey],
) -> dict[FilingProducerKey, str]:
    """Return the exhaustive owner dispatch for the closed producer vocabulary."""
    owners = {key: "shared_snapshot" for key in shared_snapshot_keys}
    for key in FilingProducerKey:
        if key in owners:
            continue
        namespace = key.value.partition(".")[0]
        owner = _MODELO_PRODUCER_NAMESPACE_OWNERS.get(namespace)
        if owner is None:
            raise FilingExportValidationError(f"filing producer key {key.value!r} has no declared owner")
        owners[key] = owner
    return owners


__all__ = ["filing_producer_ownership"]
