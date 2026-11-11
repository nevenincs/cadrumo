"""Declared non-enumerable revision-span coverage evidence."""

from __future__ import annotations

import json
from pathlib import PurePosixPath

from cadrumo.core.resources.bundled_data import bundled_path


def _bundled_design_name(modelo: str, publication_url: str) -> str:
    """The stored filename of the design AEAT published at ``publication_url``.

    A declaration names a design by the URL AEAT publishes it under, and the
    per-modelo corpus manifest maps that URL to the file the corpus stores. A URL
    the manifest no longer lists yields a name no stored design carries, so the
    staleness audits report the declaration instead of this module failing to load.
    """
    manifest = bundled_path("corpus", "aeat_official", "disenos_registro", f"modelo_{modelo}", "manifest.json")
    artefacts = json.loads(manifest.read_text(encoding="utf-8"))["artefacts"]
    for artefact in artefacts:
        if artefact["url"] == publication_url:
            return PurePosixPath(artefact["stored_path"]).name
    return f"<not bundled: {publication_url}>"


#: Designs whose era IS stated but with an OPEN BOUND, which this module refuses to
#: enumerate for the same reason it refuses ``y siguientes``: turning "everything
#: before 2001" or "from 2018 4T onward" into a year list invents years AEAT did not
#: write. Distinct from :data:`_NON_EJERCICIO_COVERAGE_AXIS`, whose designs are scoped
#: on a different axis entirely -- these two ARE ejercicio-scoped, just unbounded on
#: one side, and conflating the two would misdescribe both.
#:
#: Each reason quotes AEAT's OWN published title, read from the per-modelo corpus
#: manifest rather than inferred from the stored filename.
OPEN_BOUNDED_ERA_DESIGNS: dict[tuple[str, str], str] = {
    (
        "111",
        _bundled_design_name(
            "111",
            "https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/ant_100_199/archivos/dr111_2000.pdf",
        ),
    ): "AEAT titles it '111 - Ejercicios anteriores al 2001': open below, with no earliest ejercicio stated",
    (
        "763",
        _bundled_design_name(
            "763",
            "https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_Resto_Mod/archivos/DR763e18.xlsx",
        ),
    ): "AEAT titles it '763 - Desde 2018 4T y siguientes': open above, and period-qualified",
}


#: Designs whose coverage IS stated, on an axis that is not an ejercicio. Each entry
#: names the axis the file itself uses, so the reason is checkable against the
#: filename rather than merely asserted. Keyed by ``(modelo, filename)`` -- never by
#: index or line -- and audited for staleness below. Each filename is resolved from
#: the AEAT publication URL through the per-modelo corpus manifest.
#:
#: This is NOT a place to park a design whose era is merely unknown. An orden-named
#: design states no coverage at all, and absorbing it here would relabel "nobody
#: knows" as "known on another axis", which is the exact confusion the assertion
#: below exists to prevent.
NON_EJERCICIO_COVERAGE_AXIS: dict[tuple[str, str], str] = {
    (
        "036",
        _bundled_design_name(
            "036",
            "https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_01_99/archivos/DR036v43.xlsx",
        ),
    ): "censal declaration scoped by the date it comes into force (a day-month-year stamp in the filename), not by ejercicio",
    (
        "036",
        _bundled_design_name(
            "036",
            "https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_01_99/archivos/DR036v42.xlsx",
        ),
    ): "the provisional edition of the same in-force-date scope (the same stamp in the filename)",
    (
        "210",
        _bundled_design_name(
            "210",
            "https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_200_299/archivos_26/dr210_2026.xlsx",
        ),
    ): "non-resident income scoped by DEVENGO ('devengos-a-partir-de-2026'), an accrual span rather than an ejercicio",
    (
        "210",
        _bundled_design_name(
            "210",
            "https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_200_299/archivos_22/dr210e22.xls",
        ),
    ): "a closed devengo span ('devengos-entre-01-06-2022-y-01-01-2026'), again an accrual axis",
}
