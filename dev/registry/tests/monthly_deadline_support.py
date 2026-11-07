"""Monthly gran-empresa deadlines of the retencion returns (111, 115, 123, 216): (due date, domiciled-payment date).

RIRPF art. 108.1, paragraph two, moves the retenedor in the circumstances of
RIVA art. 71.3 numbers 1 and 2 to "los veinte primeros dias naturales de cada
mes, en relacion con las cantidades retenidas y los ingresos a cuenta que
correspondan por el mes inmediato anterior". Every row below is READ from the
bundled Calendario del Contribuyente of the year it closes in, never derived
from that rule: the published day moves for weekends and holidays. One calendar
entry per month carries the whole population by number -- "<mes> <ejercicio>.
grandes empresas: 111, 115, 117, 123, 124, 126, 128, 216, 230" -- so this census
is one published fact and has one home, as the quarterly sibling does.

The December period of the horizon year closes in a January no bundled calendar
covers and takes the statutory twentieth day with no cutoff.

A modelo that does not author ``payment_cutoff_on`` reads the close alone and
asserts its own absent cutoff; the second column stays the published
domiciliacion day for the modelos that do author it.
"""

from __future__ import annotations

MONTHLY_RETENCION_DEADLINES = {
    2022: (
        ("2022-02-21", "2022-02-16"),
        ("2022-03-21", "2022-03-16"),
        ("2022-04-20", "2022-04-15"),
        ("2022-05-20", "2022-05-15"),
        ("2022-06-20", "2022-06-15"),
        ("2022-07-20", "2022-07-15"),
        ("2022-08-22", "2022-08-17"),
        ("2022-09-20", "2022-09-15"),
        ("2022-10-20", "2022-10-15"),
        ("2022-11-21", "2022-11-16"),
        ("2022-12-20", "2022-12-15"),
        ("2023-01-20", "2023-01-15"),
    ),
    2023: (
        ("2023-02-20", "2023-02-15"),
        ("2023-03-20", "2023-03-15"),
        ("2023-04-20", "2023-04-15"),
        ("2023-05-22", "2023-05-17"),
        ("2023-06-20", "2023-06-15"),
        ("2023-07-20", "2023-07-15"),
        ("2023-08-21", "2023-08-16"),
        ("2023-09-20", "2023-09-15"),
        ("2023-10-20", "2023-10-15"),
        ("2023-11-20", "2023-11-15"),
        ("2023-12-20", "2023-12-15"),
        ("2024-01-22", "2024-01-17"),
    ),
    2024: (
        ("2024-02-20", "2024-02-15"),
        ("2024-03-20", "2024-03-15"),
        ("2024-04-22", "2024-04-17"),
        ("2024-05-20", "2024-05-15"),
        ("2024-06-20", "2024-06-17"),
        ("2024-07-22", "2024-07-17"),
        ("2024-08-20", "2024-08-15"),
        ("2024-09-20", "2024-09-17"),
        ("2024-10-21", "2024-10-16"),
        ("2024-11-20", "2024-11-15"),
        ("2024-12-20", "2024-12-17"),
        ("2025-01-20", "2025-01-15"),
    ),
    2025: (
        ("2025-02-20", "2025-02-17"),
        ("2025-03-20", "2025-03-17"),
        ("2025-04-21", "2025-04-15"),
        ("2025-05-20", "2025-05-15"),
        ("2025-06-20", "2025-06-17"),
        ("2025-07-21", "2025-07-16"),
        ("2025-08-20", "2025-08-15"),
        ("2025-09-22", "2025-09-17"),
        ("2025-10-20", "2025-10-15"),
        ("2025-11-20", "2025-11-17"),
        ("2025-12-22", "2025-12-17"),
        ("2026-01-20", "2026-01-15"),
    ),
    2026: (
        ("2026-02-20", "2026-02-17"),
        ("2026-03-20", "2026-03-16"),
        ("2026-04-20", "2026-04-15"),
        ("2026-05-20", "2026-05-15"),
        ("2026-06-22", "2026-06-17"),
        ("2026-07-20", "2026-07-15"),
        ("2026-08-20", "2026-08-17"),
        ("2026-09-21", "2026-09-16"),
        ("2026-10-20", "2026-10-15"),
        ("2026-11-20", "2026-11-17"),
        ("2026-12-21", "2026-12-16"),
        ("2027-01-20", None),
    ),
}
