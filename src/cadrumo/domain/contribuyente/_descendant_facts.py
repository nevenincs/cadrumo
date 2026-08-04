"""Helpers for persisting and reloading DescendantInfo as profile facts.

DescendantInfo records are stored as individual profile facts under the
``renta_family.descendiente.{n}.{field}`` key hierarchy. One aggregate — the
row count — is stored alongside them so the registry binding resolver can look
it up by a simple ``profile_key`` selector. Aggregates the ENGINE derives are
not stored here; see the note below the fact table.

Stored fact paths per descendant (n = 0-based index):
  renta_family.descendiente.{n}.birth_date              ISO-8601 date string
  renta_family.descendiente.{n}.adoption_date           ISO-8601 date string or absent
  renta_family.descendiente.{n}.discapacidad            "0" / "33" / "65" or absent
  renta_family.descendiente.{n}.convivencia             "true" / "false"
  renta_family.descendiente.{n}.custodia_compartida     "true" / "false" (absent means False)
  renta_family.descendiente.{n}.rentas_anuales          decimal euros or absent (absent means undeclared)
  renta_family.descendiente.{n}.declaracion_propia      "true" / "false" (absent means False)
  renta_family.descendiente.{n}.prorrata_minimo         "true" / "false" or absent (absent means unanswered)
  renta_family.descendiente.{n}.meses_madre_trabajo     "0".."12" (absent means 0)
  renta_family.descendiente.{n}.gastos_guarderia        non-negative integer euros (absent means 0)
  renta_family.descendiente.{n}.nif                     NIF string or absent

Aggregate facts stored:
  renta_family.descendientes_count               int count

The Art. 81 bis guardería sum (``renta_family.gastos_guarderia_reales_{year}``)
is deliberately NOT stored here, and must not be re-added. It is a DERIVED path:
the calculate-time injector recomputes it from the per-child
``gastos_guarderia`` figures above and overwrites whatever the index holds,
precisely so an operator's number can never be substituted for the law's. The
profile write door refuses that path outright, so projecting it from here would
refuse the whole batch rather than persist a second, divergent copy.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Literal

from ...core.errors import ProfileAnswerTypeError
from ...core.parsing import parse_bool, parse_iso8601_date
from .family import DescendantInfo

_DESCENDANT_FACT_PREFIX = "renta_family.descendiente"
_COUNT_PATH = "renta_family.descendientes_count"

_DESCENDIENTE_FLAG_KEYS = frozenset(
    {
        "NACIMIENTO",
        "ADOPCION",
        "DISCAPACIDAD",
        "CONVIVENCIA",
        "CUSTODIA",
        "RENTAS",
        "DECLARACION_PROPIA",
        "PRORRATA",
        "MESES_TRABAJO",
        "GASTOS_GUARDERIA",
        "NIF",
    },
)
"""Every key ``--descendiente`` accepts, so an unrecognised one is refused rather than ignored.

The parser looks each known key UP; without this set a token it does not
recognise would sit unread in the parsed mapping while the field it was meant to
set kept its default. That is a silent drop, and it shipped once: a catalogue
translated the key tokens, the accented forms stopped matching, and an operator
declaring a NON-cohabiting descendant got one recorded as cohabiting -- granting
a minimo they were not entitled to. Help copy alone was under-declaring tax.

The catalogues are fixed and a behavioural gate now drives every advertised token
through this parser. This set closes the other half: a token that was never
advertised at all -- a typo, a stale flag from a script, a future locale edit the
gate's extraction misses -- now fails loudly instead of vanishing. Every other
structured-token surface in this tree already refuses unknown keys, through a
typed enum, a strict model, or an explicit check. This one was the exception.
"""


def _discapacidad_grade(value: int | None) -> Literal[0, 33, 65] | None:
    match value:
        case 0:
            return 0
        case 33:
            return 33
        case 65:
            return 65
        case _:
            return None


def descendant_facts_from_list(
    descendientes: Sequence[DescendantInfo],
) -> list[tuple[str, str]]:
    """Return a list of (path, canonical-value-string) tuples for all DescendantInfo entries.

    The caller converts these to :class:`domain.user_profile.UserProfileFact`
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
        if d.rentas_anuales_euros is not None:
            facts.append((f"{prefix}.rentas_anuales", str(d.rentas_anuales_euros)))
        if d.presenta_declaracion_propia:
            facts.append((f"{prefix}.declaracion_propia", "true"))
        if d.prorrata_minimo is not None:
            facts.append((f"{prefix}.prorrata_minimo", "true" if d.prorrata_minimo else "false"))
        if d.meses_madre_trabajo_2024 > 0:
            facts.append((f"{prefix}.meses_madre_trabajo", str(d.meses_madre_trabajo_2024)))
        if d.gastos_guarderia_euros > 0:
            facts.append((f"{prefix}.gastos_guarderia", str(d.gastos_guarderia_euros)))
        if d.nif is not None:
            facts.append((f"{prefix}.nif", d.nif))
    facts.append((_COUNT_PATH, str(len(descendientes))))
    return facts


_N_RE = re.compile(
    r"^renta_family\.descendiente\.(\d+)\."
    r"(birth_date|adoption_date|discapacidad|convivencia|custodia_compartida|"
    r"rentas_anuales|declaracion_propia|prorrata_minimo|"
    r"meses_madre_trabajo|gastos_guarderia|nif)$",
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
        # parse_iso8601_date returns None only for absent/empty input (it raises
        # on a malformed non-empty string); birth_raw is non-empty here.
        birth_date = parse_iso8601_date(birth_raw)
        assert birth_date is not None
        adoption_raw = row.get("adoption_date")
        adoption_date = parse_iso8601_date(adoption_raw) if adoption_raw else None
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
        rentas_anuales = _stored_rentas_anuales(row.get("rentas_anuales"), index=idx)
        declaracion_raw = row.get("declaracion_propia")
        declaracion_propia = (
            _flag_bool(declaracion_raw, key=f"renta_family.descendiente.{idx}.declaracion_propia")
            if declaracion_raw is not None
            else False
        )
        prorrata_raw = row.get("prorrata_minimo")
        prorrata_minimo = (
            _flag_bool(prorrata_raw, key=f"renta_family.descendiente.{idx}.prorrata_minimo")
            if prorrata_raw is not None
            else None
        )
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
                discapacidad_grado=_discapacidad_grade(disc_val),
                convive_con_contribuyente=convive,
                custodia_compartida=custodia,
                rentas_anuales_euros=rentas_anuales,
                presenta_declaracion_propia=declaracion_propia,
                prorrata_minimo=prorrata_minimo,
                meses_madre_trabajo_2024=meses,
                gastos_guarderia_euros=gastos,
                nif=nif,
            ),
        )
    return tuple(result)


def _stored_rentas_anuales(raw: str | None, *, index: int) -> Decimal | None:
    """Read one descendant's stored Art. 58.1 rentas figure, refusing a bad value.

    Returns ``None`` for an absent fact, which the eligibility predicate reads
    as "no figure declared" and therefore as non-excluding.

    A PRESENT but unparseable value refuses instead of falling back to that
    same ``None``, for the reason :func:`_flag_bool` documents: the silent
    fallback points in the CLAIMING direction. ``None`` means the Art. 58.1
    ceiling and the Art. 61 norma 2ª exclusion are both skipped, so a typo in a
    figure that would have disqualified the descendant would instead restore
    the full mínimo — the exact silent over-claim
    :meth:`~domain.contribuyente.DescendantInfo.exceeds_rentas_cap` exists to
    prevent. A negative figure refuses for the same reason rather than being
    clamped to zero.
    """
    if raw is None:
        return None
    try:
        value = Decimal(raw)
    except (ArithmeticError, ValueError) as exc:
        raise ProfileAnswerTypeError(
            f"renta_family.descendiente.{index}.rentas_anuales must be a decimal number of euros; "
            f"got {raw!r}. It is refused rather than ignored because an ignored figure restores the "
            "full mínimo por descendientes, claiming a deduction the figure may disqualify.",
        ) from exc
    if not value.is_finite() or value < 0:
        raise ProfileAnswerTypeError(
            f"renta_family.descendiente.{index}.rentas_anuales must be a finite non-negative amount; got {raw!r}.",
        )
    return value


def _flag_bool(raw: str, *, key: str) -> bool:
    """Read one yes/no flag value, refusing a word the vocabulary cannot read.

    Both fields this serves gate the mínimo por descendientes, and both used
    to resolve an unreadable word to a bool silently — in the direction that
    CLAIMS. ``CONVIVENCIA`` took ``is not False``, so a typo became ``True``,
    and Art. 58 cohabitation is what qualifies the descendant at all.
    ``CUSTODIA`` took ``is True``, so a typo became ``False``, and
    :meth:`~domain.contribuyente.RentaFamilyProfile.custodia_compartida_prorrata_factor`
    returns the full ``1`` for ``False`` against ``0.5`` for shared custody
    (Art. 61 LIRPF). Opposite booleans, one direction: more deduction than the
    operator asked for.

    That is why this refuses rather than picking a safer default. The safe
    default points opposite ways on the two fields, so any single default is
    wrong on one of them, and both silent readings are wrong anyway — one
    over-claims, the other quietly under-claims. An unreadable answer is not
    an answer, and the operator is at a command line where they can correct
    it, which is the same call
    :func:`~cadrumo.core.parsing.parse_bool` is asked to make everywhere else.

    Absence still means the documented default (``CONVIVENCIA`` true,
    ``CUSTODIA`` false); this governs only a value the operator did supply.
    """
    parsed = parse_bool(raw)
    if parsed is None:
        raise ProfileAnswerTypeError(
            f"{key} must say yes or no; got {raw!r}. Write yes as si, sí, s, true, verdadero, y or 1, "
            "and no as no, n, false, falso or 0. It is refused rather than assumed because both "
            "fields decide part of the mínimo por descendientes, and guessing would claim a "
            "deduction nobody asked for.",
        )
    return parsed


def parse_descendiente_flag(raw: str) -> DescendantInfo:
    """Parse a ``--descendiente NACIMIENTO=YYYY-MM-DD,...`` flag value.

    Accepted keys (case-insensitive):
      NACIMIENTO=YYYY-MM-DD  (required) birth date
      ADOPCION=YYYY-MM-DD    (optional) adoption finalisation date
      DISCAPACIDAD=0|33|65   (optional) discapacidad grade
      CONVIVENCIA=true|false (optional, default true) cohabitation flag
      CUSTODIA=true|false    (optional, default false) custodia compartida (Art. 61 LIRPF)
      RENTAS=N               (optional) annual rentas excluding exempt income — Art. 58.1 ceiling
      DECLARACION_PROPIA=true|false
                             (optional, default false) descendant files their own IRPF return
                             — combines with RENTAS for the Art. 61 norma 2ª exclusion
      PRORRATA=true|false    (optional) explicit Art. 61 norma 1ª answer: is another
                             contribuyente also entitled to this descendant's mínimo?
                             Omit to let the engine derive it from profile signals.
      MESES_TRABAJO=0..12    (optional, default 0) months mother worked — Art. 81 deducción maternidad
      GASTOS_GUARDERIA=N     (optional, default 0) actual guardería euros — Art. 81 bis incremento 0613
      NIF=XXXXXXXXX          (optional) NIF/NIE

    Returns a validated :class:`DescendantInfo`.  Raises ``ValueError``
    on missing required keys or invalid values.
    """
    parts = {k.strip().upper(): v.strip() for k, _, v in (p.partition("=") for p in raw.split(","))}

    unknown = sorted(key for key in parts if key not in _DESCENDIENTE_FLAG_KEYS)
    if unknown:
        raise ProfileAnswerTypeError(
            f"--descendiente does not accept {', '.join(unknown)}; "
            f"accepted keys are {', '.join(sorted(_DESCENDIENTE_FLAG_KEYS))}",
        )

    nacimiento_raw = parts.get("NACIMIENTO")
    if not nacimiento_raw:
        raise ProfileAnswerTypeError(f"--descendiente flag requires NACIMIENTO=YYYY-MM-DD; got: {raw!r}")
    # parse_iso8601_date returns None only for absent/empty input (it raises on a
    # malformed non-empty string); nacimiento_raw is non-empty here.
    birth_date = parse_iso8601_date(nacimiento_raw)
    assert birth_date is not None

    adoption_date: date | None = None
    adopcion_raw = parts.get("ADOPCION")
    if adopcion_raw:
        adoption_date = parse_iso8601_date(adopcion_raw)

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
        convive = _flag_bool(conv_raw, key="CONVIVENCIA")

    custodia = False
    custodia_raw = parts.get("CUSTODIA")
    if custodia_raw is not None:
        custodia = _flag_bool(custodia_raw, key="CUSTODIA")

    rentas_anuales_euros = _stored_rentas_anuales(parts.get("RENTAS") or None, index=0)

    presenta_declaracion_propia = False
    declaracion_raw = parts.get("DECLARACION_PROPIA")
    if declaracion_raw is not None:
        presenta_declaracion_propia = _flag_bool(declaracion_raw, key="DECLARACION_PROPIA")

    prorrata_minimo: bool | None = None
    prorrata_raw = parts.get("PRORRATA")
    if prorrata_raw is not None:
        prorrata_minimo = _flag_bool(prorrata_raw, key="PRORRATA")

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

    return DescendantInfo(
        birth_date=birth_date,
        adoption_date=adoption_date,
        discapacidad_grado=_discapacidad_grade(discapacidad_grado),
        convive_con_contribuyente=convive,
        custodia_compartida=custodia,
        rentas_anuales_euros=rentas_anuales_euros,
        presenta_declaracion_propia=presenta_declaracion_propia,
        prorrata_minimo=prorrata_minimo,
        meses_madre_trabajo_2024=meses_madre_trabajo_2024,
        gastos_guarderia_euros=gastos_guarderia_euros,
        nif=nif,
    )


__all__ = [
    "descendant_facts_from_list",
    "descendant_list_from_facts",
    "parse_descendiente_flag",
]
