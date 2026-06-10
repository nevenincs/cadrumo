"""Helpers for persisting and reloading DescendantInfo as profile facts.

DescendantInfo records are stored as individual profile facts under the
``renta_family.descendiente.{n}.{field}`` key hierarchy. Aggregate summary
facts are derived and stored alongside individual facts so that the registry
binding resolver can look them up by a simple ``profile_key`` selector.

Stored fact paths per descendant (n = 0-based index):
  renta_family.descendiente.{n}.birth_date              ISO-8601 date string
  renta_family.descendiente.{n}.adoption_date           ISO-8601 date string or absent
  renta_family.descendiente.{n}.discapacidad            "0" / "33" / "65" or absent
  renta_family.descendiente.{n}.convivencia             "true" / "false"
  renta_family.descendiente.{n}.custodia_compartida     "true" / "false" (absent means False)
  renta_family.descendiente.{n}.meses_madre_trabajo     "0".."12" (absent means 0)
  renta_family.descendiente.{n}.gastos_guarderia        non-negative integer euros (absent means 0)
  renta_family.descendiente.{n}.nif                     NIF string or absent

Aggregate facts stored:
  renta_family.descendientes_count               int count
  renta_family.gastos_guarderia_reales_2024      sum of gastos_guarderia for eligible menores-3 (absent when zero)
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date
from typing import Literal, cast

from ...core.errors import ProfileAnswerTypeError
from ...core.parsing._dates import _parse_iso8601_date
from .family import DescendantInfo

_DESCENDANT_FACT_PREFIX = "renta_family.descendiente"
_COUNT_PATH = "renta_family.descendientes_count"
_GASTOS_REALES_2024_PATH = "renta_family.gastos_guarderia_reales_2024"


def descendant_facts_from_list(
    descendientes: Sequence[DescendantInfo],
) -> list[tuple[str, str]]:
    """Return a list of (path, canonical-value-string) tuples for all DescendantInfo entries.

    The caller converts these to :class:`~aeat.domain.user_profile.UserProfileFact`
    records; this function only computes the canonical key-value pairs.
    """
    facts: list[tuple[str, str]] = []
    for idx, d in enumerate(descendientes):
        prefix = f"{_DESCENDANT_FACT_PREFIX}.{idx}"
        facts.append((f"{prefix}.birth_date", d.birth_date.isoformat()))
        if d.adoption_date is not None:
            facts.append((f"{prefix}.adoption_date", d.adoption_date.isoformat()))
        if d.discapacidad_grado is not None:
            facts.append((f"{prefix}.discapacidad", str(d.discapacidad_grado)))
        facts.append((f"{prefix}.convivencia", "true" if d.convive_con_contribuyente else "false"))
        if d.custodia_compartida:
            facts.append((f"{prefix}.custodia_compartida", "true"))
        if d.meses_madre_trabajo_2024 > 0:
            facts.append((f"{prefix}.meses_madre_trabajo", str(d.meses_madre_trabajo_2024)))
        if d.gastos_guarderia_euros > 0:
            facts.append((f"{prefix}.gastos_guarderia", str(d.gastos_guarderia_euros)))
        if d.nif is not None:
            facts.append((f"{prefix}.nif", d.nif))
    facts.append((_COUNT_PATH, str(len(descendientes))))
    gastos_reales_2024 = sum(d.gastos_guarderia_euros for d in descendientes if d.is_eligible_menor_tres(2024))
    if gastos_reales_2024 > 0:
        facts.append((_GASTOS_REALES_2024_PATH, str(gastos_reales_2024)))
    return facts


_N_RE = re.compile(
    r"^renta_family\.descendiente\.(\d+)\."
    r"(birth_date|adoption_date|discapacidad|convivencia|custodia_compartida|"
    r"meses_madre_trabajo|gastos_guarderia|nif)$"
)


def descendant_list_from_facts(facts: dict[str, str]) -> tuple[DescendantInfo, ...]:
    """Reconstruct a tuple of DescendantInfo from a flat profile-fact dict.

    ``facts`` is a ``{path: canonical-value-string}`` mapping. Only
    ``renta_family.descendiente.*`` paths are consumed; all others are ignored.

    Entries are sorted by index so the reconstructed tuple preserves the
    original insertion order.

    Returns:
        Tuple of :class:`DescendantInfo` reconstructed from the profile facts.
    """
    rows: dict[int, dict[str, str]] = {}
    for path, value in facts.items():
        m = _N_RE.match(path)
        if m is None:
            continue
        idx = int(m.group(1))
        field = m.group(2)
        rows.setdefault(idx, {})[field] = value

    result: list[DescendantInfo] = []
    for idx in sorted(rows):
        row = rows[idx]
        birth_raw = row.get("birth_date")
        if not birth_raw:
            continue
        # _parse_iso8601_date returns None only for absent/empty input (it raises
        # on a malformed non-empty string); birth_raw is non-empty here.
        birth_date = _parse_iso8601_date(birth_raw)
        assert birth_date is not None
        adoption_raw = row.get("adoption_date")
        adoption_date = _parse_iso8601_date(adoption_raw) if adoption_raw else None
        discapacidad_raw = row.get("discapacidad")
        if discapacidad_raw is not None:
            disc_val = int(discapacidad_raw)
            if disc_val not in (0, 33, 65):
                disc_val = 0
        else:
            disc_val = None
        convivencia_raw = row.get("convivencia", "true")
        convive = convivencia_raw.lower() not in ("false", "0")
        custodia_raw = row.get("custodia_compartida", "false")
        custodia = custodia_raw.lower() not in ("false", "0")
        meses_raw = row.get("meses_madre_trabajo")
        meses = int(meses_raw) if meses_raw is not None else 0
        if not (0 <= meses <= 12):
            meses = 0
        gastos_raw = row.get("gastos_guarderia")
        gastos = int(gastos_raw) if gastos_raw is not None else 0
        if gastos < 0:
            gastos = 0
        nif = row.get("nif")
        result.append(
            DescendantInfo(
                birth_date=birth_date,
                adoption_date=adoption_date,
                discapacidad_grado=cast(  # CAST-RATIONALE-DISCAPACIDAD-GRADO-LITERAL-NARROW
                    "Literal[0, 33, 65] | None",
                    disc_val,
                ),
                convive_con_contribuyente=convive,
                custodia_compartida=custodia,
                meses_madre_trabajo_2024=meses,
                gastos_guarderia_euros=gastos,
                nif=nif,
            )
        )
    return tuple(result)


def parse_descendiente_flag(raw: str) -> DescendantInfo:
    """Parse a ``--descendiente NACIMIENTO=YYYY-MM-DD,...`` flag value.

    Accepted keys (case-insensitive):
      NACIMIENTO=YYYY-MM-DD  (required) birth date
      ADOPCION=YYYY-MM-DD    (optional) adoption finalisation date
      DISCAPACIDAD=0|33|65   (optional) discapacidad grade
      CONVIVENCIA=true|false (optional, default true) cohabitation flag
      CUSTODIA=true|false    (optional, default false) custodia compartida (Art. 59 LIRPF)
      MESES_TRABAJO=0..12    (optional, default 0) months mother worked — Art. 81 deducción maternidad
      GASTOS_GUARDERIA=N     (optional, default 0) actual guardería euros — Art. 81 bis incremento 0613
      NIF=XXXXXXXXX          (optional) NIF/NIE

    Returns a validated :class:`DescendantInfo`.  Raises ``ValueError``
    on missing required keys or invalid values.
    """
    parts = {k.strip().upper(): v.strip() for k, _, v in (p.partition("=") for p in raw.split(","))}

    nacimiento_raw = parts.get("NACIMIENTO")
    if not nacimiento_raw:
        raise ProfileAnswerTypeError(f"--descendiente flag requires NACIMIENTO=YYYY-MM-DD; got: {raw!r}")
    # _parse_iso8601_date returns None only for absent/empty input (it raises on a
    # malformed non-empty string); nacimiento_raw is non-empty here.
    birth_date = _parse_iso8601_date(nacimiento_raw)
    assert birth_date is not None

    adoption_date: date | None = None
    adopcion_raw = parts.get("ADOPCION")
    if adopcion_raw:
        adoption_date = _parse_iso8601_date(adopcion_raw)

    discapacidad_grado = None
    disc_raw = parts.get("DISCAPACIDAD")
    if disc_raw is not None:
        val = int(disc_raw)
        if val not in (0, 33, 65):
            raise ProfileAnswerTypeError(f"DISCAPACIDAD must be 0, 33, or 65; got {val!r}")
        discapacidad_grado = val

    convive = True
    conv_raw = parts.get("CONVIVENCIA")
    if conv_raw is not None:
        convive = conv_raw.lower() not in ("false", "0", "no")

    custodia = False
    custodia_raw = parts.get("CUSTODIA")
    if custodia_raw is not None:
        custodia = custodia_raw.lower() in ("true", "1", "si", "sí", "yes")

    meses_madre_trabajo_2024 = 0
    meses_raw = parts.get("MESES_TRABAJO")
    if meses_raw is not None:
        meses_val = int(meses_raw)
        if not (0 <= meses_val <= 12):
            raise ProfileAnswerTypeError(f"MESES_TRABAJO must be 0-12; got {meses_val!r}")
        meses_madre_trabajo_2024 = meses_val

    gastos_guarderia_euros = 0
    gastos_raw = parts.get("GASTOS_GUARDERIA")
    if gastos_raw is not None:
        gastos_val = int(gastos_raw)
        if gastos_val < 0:
            raise ProfileAnswerTypeError(f"GASTOS_GUARDERIA must be ≥ 0; got {gastos_val!r}")
        gastos_guarderia_euros = gastos_val

    nif: str | None = None
    nif_raw = parts.get("NIF")
    if nif_raw:
        nif = nif_raw.strip().upper()

    # CAST-RATIONALE-DISCAPACIDAD-LITERAL:
    # val validated against (0, 33, 65) above; int|None cannot be narrowed to
    # Literal[0,33,65]|None by mypy without cast.
    return DescendantInfo(
        birth_date=birth_date,
        adoption_date=adoption_date,
        discapacidad_grado=cast(  # CAST-RATIONALE-DISCAPACIDAD-GRADO-LITERAL-NARROW
            "Literal[0, 33, 65] | None",
            discapacidad_grado,
        ),
        convive_con_contribuyente=convive,
        custodia_compartida=custodia,
        meses_madre_trabajo_2024=meses_madre_trabajo_2024,
        gastos_guarderia_euros=gastos_guarderia_euros,
        nif=nif,
    )


__all__ = [
    "descendant_facts_from_list",
    "descendant_list_from_facts",
    "parse_descendiente_flag",
]
