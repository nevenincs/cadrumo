""":class:`Modelo`-keyed supplementary Orden compilation.

AEAT republishes some modelos' regulatory content as its own annual Orden rather
than in the modelo's authoring tree. Each such modelo registers a compiler and a
fingerprint collector here, and generic authority construction folds every
registered result onto the shared catalogues without naming a modelo. A second
such modelo is a table entry, never a branch.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Protocol

from ....core import Modelo
from .ids import LegalRefId, SourceRefId
from .m303_orden_manifest import (
    collect_m303_annual_orden_fingerprints,
    load_m303_annual_orden_authority,
)
from .m303_orden_projection_models import (
    M303AnnualOrdenAuthority,
    M303AnnualOrdenCompilation,
)
from .schema import LegalReference, ModeloDefinition, RegistryModel, SourceReference


class SupplementaryOrdenCompiler(Protocol):
    """Compile one modelo's annually published Orden into registry material."""

    def __call__(
        self,
        root: Path,
        *,
        source_root: Path,
        modelos: Sequence[ModeloDefinition],
        sources: Mapping[SourceRefId, SourceReference],
        supported_filing_years: tuple[int, ...],
    ) -> M303AnnualOrdenCompilation: ...


_ORDEN_COMPILERS: Mapping[Modelo, SupplementaryOrdenCompiler] = {
    Modelo.M303: load_m303_annual_orden_authority,
}

_ORDEN_FINGERPRINT_COLLECTORS: Mapping[Modelo, Callable[[Path], tuple[tuple[str, int, int, str], ...]]] = {
    Modelo.M303: collect_m303_annual_orden_fingerprints,
}


class SupplementaryOrdenCompilation(RegistryModel):
    """Every registered modelo's compiled Orden authority and its legal provisions."""

    authorities: Mapping[Modelo, M303AnnualOrdenAuthority]
    legal: Mapping[LegalRefId, LegalReference]


def compile_supplementary_ordenes(
    root: Path,
    *,
    source_root: Path,
    modelos: Sequence[ModeloDefinition],
    sources: Mapping[SourceRefId, SourceReference],
    supported_filing_years: tuple[int, ...],
) -> SupplementaryOrdenCompilation:
    """Compile every registered modelo whose :class:`ModeloDefinition` declares a revision.

    Returns:
        The compiled authorities keyed by modelo, and the legal provisions they contribute.
    """
    present = {modelo.id for modelo in modelos if modelo.revisions}
    authorities: dict[Modelo, M303AnnualOrdenAuthority] = {}
    legal: dict[LegalRefId, LegalReference] = {}
    for modelo_id, compiler in _ORDEN_COMPILERS.items():
        if modelo_id not in present:
            continue
        compilation = compiler(
            root,
            source_root=source_root,
            modelos=modelos,
            sources=sources,
            supported_filing_years=supported_filing_years,
        )
        authorities[modelo_id] = compilation.authority
        legal.update(compilation.legal)
    return SupplementaryOrdenCompilation(authorities=authorities, legal=legal)


def collect_supplementary_orden_fingerprints(root: Path) -> tuple[tuple[str, int, int, str], ...]:
    """Fingerprint every registered modelo's generated Orden manifest."""
    collected: tuple[tuple[str, int, int, str], ...] = ()
    for collector in _ORDEN_FINGERPRINT_COLLECTORS.values():
        collected += collector(root)
    return collected


def supplementary_orden_authority(
    ordenes: Mapping[Modelo, M303AnnualOrdenAuthority],
    modelo: Modelo,
) -> M303AnnualOrdenAuthority:
    """Read one modelo's compiled Orden authority, empty when the modelo declares none."""
    return ordenes.get(modelo, M303AnnualOrdenAuthority.empty())
