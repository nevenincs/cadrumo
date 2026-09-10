"""Development compilation of mutable Convenio treaty declarations."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.revision_review import RevisionReviewStatus
from cadrumo.core.toml import freeze_toml, read_toml
from cadrumo.domain.calculations.registry.convenio import CONVENIO_OVERRIDE_FACT_ID, ConvenioAuthority, ConvenioTreaty
from cadrumo.domain.calculations.registry.errors import RegistryLoadError, RegistryValidationError
from cadrumo.domain.calculations.registry.facts.schema import (
    FactOwnership,
    FactSelector,
    GovernedFact,
    GovernedFactFamily,
    GovernedFactVariant,
    OverrideFactPayload,
)
from .loader_cache import toml_file_fingerprint
from cadrumo.domain.calculations.registry.schema_base import DateAxis, SourceCitation

__all__ = [
    "collect_convenio_fingerprints",
    "compile_convenio_facts",
    "load_convenio_authority",
    "validate_convenio_legal_refs",
]


def load_convenio_authority(treaties_dir: Path) -> ConvenioAuthority:
    """Compile the mutable ``treaties/`` TOML tree into runtime treaty types."""
    resolved = treaties_dir.resolve()
    if not resolved.is_dir():
        return ConvenioAuthority.empty()
    treaties: dict[str, ConvenioTreaty] = {}
    for path in scan_directory(resolved, pattern="*.toml"):
        raw = freeze_toml(read_toml(path, error_factory=RegistryLoadError))
        table = raw.get("treaty")
        if not isinstance(table, Mapping):
            raise RegistryLoadError(f"{path}: treaty file must declare a [treaty] table")
        try:
            treaty = ConvenioTreaty.model_validate(table)
        except RegistryValidationError as exc:
            raise RegistryLoadError(f"{path}: invalid treaty: {exc}") from exc
        if treaty.country_code in treaties:
            raise RegistryLoadError(
                f"{path}: treaty country {treaty.country_code!r} already declared in another treaties/*.toml file",
            )
        treaties[treaty.country_code] = treaty
    return ConvenioAuthority(treaties=treaties)


def collect_convenio_fingerprints(root: Path) -> tuple[tuple[str, int, int, str], ...]:
    """Fingerprint every mutable treaty declaration used by the compiler."""
    treaties_dir = root.resolve() / "treaties"
    return tuple(toml_file_fingerprint(path.resolve()) for path in scan_directory(treaties_dir, pattern="*.toml"))


def compile_convenio_facts(registry_root: Path) -> tuple[GovernedFact, ...]:
    """Project treaty rows into the governed-fact artifact payload."""
    authority = load_convenio_authority(registry_root.resolve() / "treaties")
    variants: list[GovernedFactVariant] = []
    for country_code, treaty in sorted(authority.treaties.items()):
        for row in treaty.overrides:
            source_ref = f"boe-{row.legal_ref_anchor.replace(':', '-')}"
            variants.append(
                GovernedFactVariant(
                    variant_id=(
                        f"{CONVENIO_OVERRIDE_FACT_ID}.{country_code.lower()}."
                        f"{row.tipo_renta.value}.{row.valid_from.isoformat()}"
                    ),
                    selectors=(
                        FactSelector(name="country_code", value=country_code),
                        FactSelector(name="tipo_renta", value=row.tipo_renta.value),
                    ),
                    date_axis=DateAxis.DEVENGO_DATE,
                    valid_from=row.valid_from,
                    valid_to=row.valid_to,
                    payload=OverrideFactPayload(
                        override_code=row.kind.value,
                        value=row.rate_decimal,
                        unit="ratio" if row.rate_decimal is not None else None,
                    ),
                    legal_refs=row.legal_refs,
                    source_refs=(source_ref,),
                    source_citations=(
                        SourceCitation(
                            source_ref=source_ref,
                            required_text=("Art", f"{row.legal_ref_anchor.rsplit('-', 1)[-1]}"),
                        ),
                    ),
                    review_status=RevisionReviewStatus.AGENT_REVIEWED,
                    ownership=FactOwnership.GENERATED,
                ),
            )
    return (
        (
            GovernedFact(
                fact_id=CONVENIO_OVERRIDE_FACT_ID,
                family=GovernedFactFamily.OVERRIDE,
                variants=tuple(variants),
            ),
        )
        if variants
        else ()
    )


def validate_convenio_legal_refs(authority: ConvenioAuthority, legal_ref_ids: frozenset[str]) -> None:
    """Refuse a treaty override whose legal provenance is absent from its candidate."""
    missing: list[str] = []
    for country_code, treaty in sorted(authority.treaties.items()):
        for row in treaty.overrides:
            for ref in row.legal_refs:
                if ref not in legal_ref_ids:
                    missing.append(f"treaty {country_code} tipo_renta {row.tipo_renta.value}: legal_ref {ref!r}")
    if missing:
        raise RegistryValidationError(
            "convenio treaty legal_refs missing from the legal catalogue:\n"
            + "\n".join(f" - {entry}" for entry in missing),
        )
