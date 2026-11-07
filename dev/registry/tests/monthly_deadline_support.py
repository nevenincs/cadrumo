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

import json
from pathlib import Path

MONTHLY_RETENCION_DEADLINES: dict[int, tuple[tuple[str, str | None], ...]] = {
    int(exercise): tuple((close, cutoff) for close, cutoff in rows)
    for exercise, rows in json.loads(
        Path(__file__).with_name("monthly_retencion_deadlines.json").read_text(encoding="utf-8")
    ).items()
}
"""Each published exercise's twelve (close, domiciled-payment) pairs, read from the census data beside this module."""
