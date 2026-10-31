"""Check authored registry data against the form geometry the registry declares.

These shapes are authored, so a runtime model cannot read the facts while the tree loads.
The compiled registry answers them here, where a defect stops publication.
"""

from __future__ import annotations

from collections.abc import Iterable

from cadrumo.domain.calculations.registry.form_codes import FormCodes, resolve_form_codes
from cadrumo.domain.calculations.registry.irnr_tipo_renta import resolve_tipo_renta_irnr_catalogue
from cadrumo.domain.calculations.registry.prorrata_register_catalogue import resolve_prorrata_register_catalogue
from cadrumo.domain.calculations.registry.prorrata_register_models import ProrrataRegisterCatalogue
from cadrumo.domain.calculations.registry.schema import ModeloDefinition


def prorrata_catalogue_failures(catalogue: ProrrataRegisterCatalogue, codes: FormCodes) -> list[str]:
    """Return failures for a prorrata register vocabulary whose size differs from the declared scope."""
    failures = []
    if len(catalogue.regimes) < int(codes.code("prorrata.catalogue.regimes_min")):
        failures.append("prorrata register catalogue has fewer regimes than declared")
    for key, values in (
        ("prorrata.catalogue.apportioning_regimes", catalogue.apportioning_regimes),
        ("prorrata.catalogue.transition_kinds", catalogue.transition_kinds),
        ("prorrata.catalogue.provenances", catalogue.provenances),
        ("prorrata.catalogue.sector_letters", catalogue.sector_letters),
    ):
        if len(values) != int(codes.code(key)):
            failures.append(f"prorrata register catalogue does not have the {key} the scope declares")
    return failures


def modelo_geometry_failures(modelos: Iterable[ModeloDefinition], codes: FormCodes) -> list[str]:
    """Return failures for modelo revisions whose authored shape differs from the declared geometry."""
    prefix_fields = int(codes.code("aeat.aux.prefix_fields"))
    tipo_renta_widths = codes.codes("m210.tipo_renta_digits")
    failures: list[str] = []
    for modelo in modelos:
        for revision_id, revision in modelo.revisions.items():
            for layout in revision.export_layouts:
                header = layout.auxiliary_envelope_header
                if header is not None and len(header.prefix_fields) != prefix_fields:
                    failures.append(
                        f"modelo {modelo.id} revision {revision_id} auxiliary header does not declare "
                        f"{prefix_fields} prefix fields",
                    )
            failures.extend(
                f"modelo {modelo.id} revision {revision_id} deadline code {code!r} does not have the declared width"
                for window in revision.deadline_windows
                for code in window.tipo_renta_scope or ()
                if str(len(code)) not in tipo_renta_widths
            )
    return failures


def validate_form_geometry(modelos: Iterable[ModeloDefinition]) -> tuple[str, ...]:
    """Return failures for authored data whose shape differs from the declared form geometry."""
    codes = resolve_form_codes("form-row-codes")
    tipo_renta_widths = codes.codes("m210.tipo_renta_digits")
    failures = prorrata_catalogue_failures(resolve_prorrata_register_catalogue(), codes)
    failures.extend(
        f"official tipo-renta code {code!r} does not have the declared width"
        for code in resolve_tipo_renta_irnr_catalogue().official_codes
        if str(len(code)) not in tipo_renta_widths
    )
    failures.extend(modelo_geometry_failures(modelos, codes))
    return tuple(failures)


__all__ = ["modelo_geometry_failures", "prorrata_catalogue_failures", "validate_form_geometry"]
