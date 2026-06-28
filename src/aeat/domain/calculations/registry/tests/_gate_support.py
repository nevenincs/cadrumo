"""Shared helpers for registry gate tests."""

from __future__ import annotations

from .._schema import RegistryCatalogues

_M130_LEGAL_REF_IDS = frozenset(
    {
        "ley-35-2006:art-27",
        "ley-35-2006:art-28",
        "ley-35-2006:art-30",
        "ley-35-2006:art-99",
        "orden-eha-672-2007:art-1",
        "rd-439-2007:art-95",
        "rd-439-2007:art-110",
        "rd-439-2007:art-110-3-b",
    },
)
_M130_SOURCE_REF_IDS = frozenset({"aeat-dr-130-2019-v12", "aeat-modelo-130-instructions"})


def catalogues_for_m130_gate_tests(catalogues: RegistryCatalogues) -> RegistryCatalogues:
    return catalogues.model_copy(
        update={
            "legal": {ref_id: catalogues.legal[ref_id] for ref_id in _M130_LEGAL_REF_IDS},
            "sources": {ref_id: catalogues.sources[ref_id] for ref_id in _M130_SOURCE_REF_IDS},
        },
    )
