"""Declared non-enumerable revision-span coverage evidence."""

from __future__ import annotations

#: Designs whose era IS stated but with an OPEN BOUND, which this module refuses to
#: enumerate for the same reason it refuses ``y siguientes``: turning "everything
#: before 2001" or "from 2018 4T onward" into a year list invents years AEAT did not
#: write. Distinct from :data:`_NON_EJERCICIO_COVERAGE_AXIS`, whose designs are scoped
#: on a different axis entirely -- these two ARE ejercicio-scoped, just unbounded on
#: one side, and conflating the two would misdescribe both.
#:
#: Each reason quotes AEAT's OWN published title, read from the per-modelo corpus
#: manifest rather than inferred from the stored filename.
_OPEN_BOUNDED_ERA_DESIGNS: dict[tuple[str, str], str] = {
    (
        "111",
        "04-111-ejercicios-anteriores-al-2001-65-kb-pdf.pdf",
    ): "AEAT titles it '111 - Ejercicios anteriores al 2001': open below, with no earliest ejercicio stated",
    (
        "763",
        "01-763-desde-2018-4t-y-siguientes-actualizado-en-2023.xlsx",
    ): "AEAT titles it '763 - Desde 2018 4T y siguientes': open above, and period-qualified",
}


#: Designs whose coverage IS stated, on an axis that is not an ejercicio. Each entry
#: names the axis the file itself uses, so the reason is checkable against the
#: filename rather than merely asserted. Keyed by ``(modelo, filename)`` -- never by
#: index or line -- and audited for staleness below.
#:
#: This is NOT a place to park a design whose era is merely unknown. An orden-named
#: design states no coverage at all, and absorbing it here would relabel "nobody
#: knows" as "known on another axis", which is the exact confusion the assertion
#: below exists to prevent.
_NON_EJERCICIO_COVERAGE_AXIS: dict[tuple[str, str], str] = {
    (
        "036",
        "01-036-diseno-de-registro-del-modelo-m036-03-02-2025-y-siguientes-124-kb-xlsx.xlsx",
    ): "censal declaration scoped by the date it comes into force ('03-02-2025-y-siguientes'), not by ejercicio",
    (
        "036",
        "02-036-diseno-de-registro-del-modelo-m036-03-02-2025-y-siguientes-provisional-107-kb-xlsx.xlsx",
    ): "the provisional edition of the same in-force-date scope ('03-02-2025-y-siguientes')",
    (
        "210",
        "01-210-devengos-a-partir-de-2026.xlsx",
    ): "non-resident income scoped by DEVENGO ('devengos-a-partir-de-2026'), an accrual span rather than an ejercicio",
    (
        "210",
        "02-210-devengos-entre-01-06-2022-y-01-01-2026.xls",
    ): "a closed devengo span ('devengos-entre-01-06-2022-y-01-01-2026'), again an accrual axis",
}
