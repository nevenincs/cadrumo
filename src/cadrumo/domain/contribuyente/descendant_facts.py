"""Helpers for persisting and reloading DescendantInfo as profile facts.

DescendantInfo records are stored as individual profile facts under the
``renta_family.descendiente.{n}.{field}`` key hierarchy. One aggregate — the
row count — is stored alongside them so the registry binding resolver can look
it up by a simple ``profile_key`` selector. Aggregates the ENGINE derives are
not stored here; see the note below the fact table.

Stored fact paths per descendant (n = 0-based index)::

  renta_family.descendiente.{n}.birth_date              ISO-8601 date string
  renta_family.descendiente.{n}.relacion                DescendantRelacion token (absent means ordinary)
  renta_family.descendiente.{n}.inscripcion_registro_civil
                                                        ISO-8601 date string or absent
  renta_family.descendiente.{n}.acogimiento_resolucion  ISO-8601 date string or absent
  renta_family.descendiente.{n}.fallecimiento          ISO-8601 date string or absent (absent means the
                                                        descendant did not die)
  renta_family.descendiente.{n}.discapacidad            "0" / "33" / "65" or absent
  renta_family.descendiente.{n}.convivencia             "true" / "false"
  renta_family.descendiente.{n}.dependencia_economica   "true" / "false" or absent (absent means unset)
  renta_family.descendiente.{n}.custodia_compartida     "true" / "false" (absent means False)
  renta_family.descendiente.{n}.rentas_anuales          decimal euros or absent (absent means undeclared)
  renta_family.descendiente.{n}.declaracion_propia      "true" / "false" (absent means False)
  renta_family.descendiente.{n}.prorrata_minimo         "true" / "false" or absent (absent means unanswered)
  renta_family.descendiente.{n}.meses_madre_trabajo     "MM;MM..." ascending, zero-padded
                                                        (absent means no qualifying months)
  renta_family.descendiente.{n}.alta_posterior_nacimiento_mes
                                                        "1".."12" or absent (absent means no post-birth
                                                        alta increment declared)
  renta_family.descendiente.{n}.gastos_guarderia        non-negative integer euros (absent means 0)
  renta_family.descendiente.{n}.gastos_guarderia_mensuales
                                                        canonical MM:AMOUNT[;MM:AMOUNT...] map or absent
  renta_family.descendiente.{n}.nif                     NIF string or absent

Aggregate facts stored::

  renta_family.descendientes_count               int count

The Art. 81.2 guardería sum (``renta_family.gastos_guarderia_reales_{year}``)
is deliberately NOT stored here, and must not be re-added. It is a DERIVED path:
the calculate-time injector recomputes it from the per-child spend above —
through the canonical record, so the annual figure and the monthly map are
weighed by the same Art. 81.2 month rules — and overwrites whatever the index
holds, precisely so an operator's number can never be substituted for the law's. The
profile write door refuses that path outright, so projecting it from here would
refuse the whole batch rather than persist a second, divergent copy.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Literal, TypedDict

from ...core.descendant_relacion import DescendantRelacion
from ...core.decimal import try_parse_canonical_decimal
from ...core.errors.hierarchy import ProfileAnswerTypeError
from ...core.identity import tax_id_identity_token
from ...core.parsing import parse_bool, parse_iso8601_date
from ...core.text_bounds import is_calendar_month
from .descendant import DescendantInfo
from .family_types import GuarderiaMonthSpend
from .guarderia_mensual import (
    is_plain_whole_number,
    parse_guarderia_mensual,
    serialise_guarderia_mensual,
)
from .meses_trabajo import parse_meses_trabajo, serialise_meses_trabajo

#: Localised refusal for a rentas figure outside the canonical euro grammar.
#:
#: Reuses the key the wizard already raises for the SAME refusal on the same
#: field, rather than minting a second one: it is present and translated in all
#: four catalogues and its copy is exactly the accepted form ("enter euros with
#: a dot for decimals"). Two keys for one refusal would drift, and the operator
#: would meet different words depending on which door they came through.
_RENTAS_GRAMMAR_LOCALE_KEY = "application.wizard.errors.descendant_rentas_not_a_valid_amount"

_DESCENDANT_FACT_PREFIX = "renta_family.descendiente"
_COUNT_PATH = "renta_family.descendientes_count"

_DESCENDIENTE_FLAG_KEYS = frozenset(
    {
        "NACIMIENTO",
        "RELACION",
        "INSCRIPCION",
        "ACOGIMIENTO",
        "FALLECIMIENTO",
        "DISCAPACIDAD",
        "CONVIVENCIA",
        "DEPENDENCIA",
        "CUSTODIA",
        "RENTAS",
        "DECLARACION_PROPIA",
        "PRORRATA",
        "MESES_TRABAJO",
        "ALTA_POSTERIOR_MES",
        "GASTOS_GUARDERIA",
        "GASTOS_GUARDERIA_MENSUAL",
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

    The caller converts these to :class:`domain.user_profile.values.UserProfileFact`
    records; this function only computes the canonical key-value pairs.
    """
    facts: list[tuple[str, str]] = []
    for idx, descendant in enumerate(descendientes):
        prefix = f"{_DESCENDANT_FACT_PREFIX}.{idx}"
        facts.append((f"{prefix}.birth_date", descendant.birth_date.isoformat()))
        _append_present_facts(facts, prefix, _identity_fact_values(descendant))
        _append_present_facts(facts, prefix, _family_fact_values(descendant))
        _append_present_facts(facts, prefix, _maternity_fact_values(descendant))
    facts.append((_COUNT_PATH, str(len(descendientes))))
    return facts


def _append_present_facts(
    facts: list[tuple[str, str]],
    prefix: str,
    values: tuple[tuple[str, str | None], ...],
) -> None:
    facts.extend((f"{prefix}.{field}", value) for field, value in values if value is not None)


def _identity_fact_values(descendant: DescendantInfo) -> tuple[tuple[str, str | None], ...]:
    """Serialise relationship evidence, omitting the ordinary default relation."""
    return (
        (
            "relacion",
            None if descendant.relacion is DescendantRelacion.DESCENDIENTE else descendant.relacion.value,
        ),
        (
            "inscripcion_registro_civil",
            None
            if descendant.inscripcion_registro_civil_date is None
            else descendant.inscripcion_registro_civil_date.isoformat(),
        ),
        (
            "acogimiento_resolucion",
            None
            if descendant.acogimiento_resolucion_date is None
            else descendant.acogimiento_resolucion_date.isoformat(),
        ),
        ("fallecimiento", None if descendant.death_date is None else descendant.death_date.isoformat()),
        ("discapacidad", None if descendant.discapacidad_grado is None else str(descendant.discapacidad_grado)),
    )


def _family_fact_values(descendant: DescendantInfo) -> tuple[tuple[str, str | None], ...]:
    """Serialise eligibility facts while retaining the unset-versus-false axes."""
    return (
        ("convivencia", "true" if descendant.convive_con_contribuyente else "false"),
        (
            "dependencia_economica",
            None if descendant.dependencia_economica is None else str(descendant.dependencia_economica).lower(),
        ),
        ("custodia_compartida", "true" if descendant.custodia_compartida else None),
        ("rentas_anuales", None if descendant.rentas_anuales_euros is None else str(descendant.rentas_anuales_euros)),
        ("declaracion_propia", "true" if descendant.presenta_declaracion_propia else None),
        (
            "prorrata_minimo",
            None if descendant.prorrata_minimo is None else str(descendant.prorrata_minimo).lower(),
        ),
    )


def _maternity_fact_values(descendant: DescendantInfo) -> tuple[tuple[str, str | None], ...]:
    """Serialise Art. 81 facts, preserving their canonical month representations."""
    return (
        (
            "meses_madre_trabajo",
            None if not descendant.meses_madre_trabajo else serialise_meses_trabajo(descendant.meses_madre_trabajo),
        ),
        (
            "alta_posterior_nacimiento_mes",
            None if descendant.alta_posterior_nacimiento_mes is None else str(descendant.alta_posterior_nacimiento_mes),
        ),
        (
            "segundo_ciclo_infantil_inicio_mes",
            None
            if descendant.segundo_ciclo_infantil_inicio_mes is None
            else str(descendant.segundo_ciclo_infantil_inicio_mes),
        ),
        (
            "gastos_guarderia",
            None if descendant.gastos_guarderia_euros <= 0 else str(descendant.gastos_guarderia_euros),
        ),
        (
            "gastos_guarderia_mensuales",
            None
            if not descendant.gastos_guarderia_mensuales
            else serialise_guarderia_mensual(descendant.gastos_guarderia_mensuales),
        ),
        ("nif", descendant.nif),
    )


_N_RE = re.compile(
    r"^renta_family\.descendiente\.(\d+)\."
    r"(birth_date|relacion|inscripcion_registro_civil|acogimiento_resolucion|fallecimiento|"
    r"discapacidad|convivencia|dependencia_economica|custodia_compartida|"
    r"rentas_anuales|declaracion_propia|prorrata_minimo|"
    # The monthly map precedes the annual figure in the alternation because a
    # regex alternation is ordered: with `gastos_guarderia` first, every
    # `gastos_guarderia_mensuales` path would match the shorter branch, fail the
    # `$` anchor, and be DROPPED from the row -- a declared map silently absent
    # on every reload.
    r"meses_madre_trabajo|alta_posterior_nacimiento_mes|segundo_ciclo_infantil_inicio_mes|"
    r"gastos_guarderia_mensuales|gastos_guarderia|nif)$",
)


class RelacionKwarg(TypedDict, total=False):
    """The single optional constructor keyword :func:`relacion_kwarg` may supply.

    A plain mapping loses which keyword is present, so splatting it into a
    constructor reported every unrelated field as mistyped. Declaring the one
    key it can carry keeps the splat precise.
    """

    relacion: DescendantRelacion


class _CivilFields(TypedDict):
    inscripcion_registro_civil_date: date | None
    acogimiento_resolucion_date: date | None
    death_date: date | None
    discapacidad_grado: Literal[0, 33, 65] | None


class _FamilyFields(TypedDict):
    convive_con_contribuyente: bool
    dependencia_economica: bool | None
    custodia_compartida: bool
    rentas_anuales_euros: Decimal | None
    presenta_declaracion_propia: bool
    prorrata_minimo: bool | None


class _MaternityFields(TypedDict):
    meses_madre_trabajo: tuple[int, ...]
    alta_posterior_nacimiento_mes: int | None
    segundo_ciclo_infantil_inicio_mes: int | None
    gastos_guarderia_euros: int
    gastos_guarderia_mensuales: tuple[GuarderiaMonthSpend, ...]


def relacion_kwarg(relacion: DescendantRelacion | None) -> RelacionKwarg:
    """Render an optional relación as the constructor keyword, OMITTING it when unstated.

    "Unstated" and "ordinary descendant" are different inputs and the record
    treats them differently: an unstated relación carrying a Registro Civil
    inscription is read as an adoption, while an explicitly-ordinary one
    carrying the same date is a contradiction the coherence rule refuses. The
    only way to express "unstated" to a pydantic constructor is to leave the
    keyword out, so every door routes through this rather than inventing a
    sentinel — and the type checker sees a plain
    :class:`~cadrumo.core.DescendantRelacion` at each call site.
    """
    return {} if relacion is None else {"relacion": relacion}


def _stored_relacion(raw: str | None, *, index: int) -> DescendantRelacion | None:
    """Read one descendant's stored relación, refusing a token outside the closed set.

    Returns ``None`` for an absent token — UNSTATED, not "ordinary". The two
    differ: :class:`~domain.contribuyente.DescendantInfo` reads an unstated
    relación carrying an inscription date as an adoption, and defaults it to the
    ordinary descendant otherwise. Resolving absence to the ordinary member here
    would pre-empt that reading and turn the adoption record into a
    contradiction the coherence validator then refuses.

    A PRESENT but unreadable token refuses rather than falling back, for the
    reason every other guard in this module refuses: the fallback points in the
    claiming direction on one side and the excluded direction on the other, and
    neither is a reading of what the operator wrote. A corrupted
    ``acogimiento_temporal`` resolving to the default would additionally strip
    the record of the one distinction keeping the Art. 58.2 increase away from
    it.
    """
    if raw is None:
        return None
    try:
        return DescendantRelacion(raw.strip().lower())
    except ValueError:
        accepted = ", ".join(member.value for member in DescendantRelacion)
        raise ProfileAnswerTypeError(
            f"renta_family.descendiente.{index}.relacion must be one of {accepted}; got {raw!r}.",
        ) from None


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

    return tuple(_descendant_from_stored_row(idx, row) for idx, row in sorted(rows.items()) if row.get("birth_date"))


def _descendant_from_stored_row(index: int, row: dict[str, str]) -> DescendantInfo:
    """Hydrate one complete descendant record from its canonical fact row."""
    birth_raw = row["birth_date"]
    birth_date = parse_iso8601_date(birth_raw)
    # The row filter rejects absent/empty values; the parser raises on a
    # malformed non-empty value, so a surviving row always has a date.
    assert birth_date is not None
    relacion = _stored_relacion(row.get("relacion"), index=index)
    return DescendantInfo(
        birth_date=birth_date,
        **relacion_kwarg(relacion),
        **_stored_civil_fields(row),
        **_stored_family_fields(row, index=index),
        **_stored_maternity_fields(row, index=index),
        nif=row.get("nif"),
    )


def _stored_civil_fields(row: dict[str, str]) -> _CivilFields:
    inscripcion_raw = row.get("inscripcion_registro_civil")
    acogimiento_raw = row.get("acogimiento_resolucion")
    fallecimiento_raw = row.get("fallecimiento")
    discapacidad_raw = row.get("discapacidad")
    disc_val = int(discapacidad_raw) if discapacidad_raw is not None else None
    if disc_val is not None and disc_val not in (0, 33, 65):
        disc_val = 0
    return {
        "inscripcion_registro_civil_date": parse_iso8601_date(inscripcion_raw) if inscripcion_raw else None,
        "acogimiento_resolucion_date": parse_iso8601_date(acogimiento_raw) if acogimiento_raw else None,
        "death_date": parse_iso8601_date(fallecimiento_raw) if fallecimiento_raw else None,
        "discapacidad_grado": _discapacidad_grade(disc_val),
    }


def _stored_family_fields(row: dict[str, str], *, index: int) -> _FamilyFields:
    dependencia_raw = row.get("dependencia_economica")
    declaracion_raw = row.get("declaracion_propia")
    prorrata_raw = row.get("prorrata_minimo")
    return {
        "convive_con_contribuyente": row.get("convivencia", "true").lower() not in ("false", "0"),
        "dependencia_economica": (
            _flag_bool(dependencia_raw, key=f"renta_family.descendiente.{index}.dependencia_economica")
            if dependencia_raw is not None
            else None
        ),
        "custodia_compartida": row.get("custodia_compartida", "false").lower() not in ("false", "0"),
        "rentas_anuales_euros": _stored_rentas_anuales(row.get("rentas_anuales"), index=index),
        "presenta_declaracion_propia": (
            _flag_bool(declaracion_raw, key=f"renta_family.descendiente.{index}.declaracion_propia")
            if declaracion_raw is not None
            else False
        ),
        "prorrata_minimo": (
            _flag_bool(prorrata_raw, key=f"renta_family.descendiente.{index}.prorrata_minimo")
            if prorrata_raw is not None
            else None
        ),
    }


def _stored_maternity_fields(row: dict[str, str], *, index: int) -> _MaternityFields:
    meses_raw = row.get("meses_madre_trabajo")
    return {
        "meses_madre_trabajo": (
            parse_meses_trabajo(meses_raw, field=f"renta_family.descendiente.{index}.meses_madre_trabajo")
            if meses_raw is not None
            else ()
        ),
        "alta_posterior_nacimiento_mes": _stored_alta_posterior_mes(
            row.get("alta_posterior_nacimiento_mes"),
            index=index,
        ),
        "segundo_ciclo_infantil_inicio_mes": _stored_alta_posterior_mes(
            row.get("segundo_ciclo_infantil_inicio_mes"),
            index=index,
        ),
        "gastos_guarderia_euros": _stored_gastos_guarderia(row.get("gastos_guarderia"), index=index),
        "gastos_guarderia_mensuales": parse_guarderia_mensual(
            row.get("gastos_guarderia_mensuales") or "",
            field=f"renta_family.descendiente.{index}.gastos_guarderia_mensuales",
        ),
    }


def _stored_alta_posterior_mes(raw: str | None, *, index: int) -> int | None:
    """Read one descendant's stored Art. 81.1 alta-posterior completion month.

    Absent means ``None`` — no post-birth alta increment declared for this
    child, the ordinary case.

    A PRESENT but unreadable value REFUSES rather than resolving to ``None``,
    for the reason every other guard in this module refuses: ``None`` here
    means the increment does not apply, and silently reading a corrupted month
    as "not declared" would withhold an entitlement the operator believes they
    recorded, with nothing said. A month outside 1-12 refuses for the same
    reason a whole-number test is used elsewhere rather than a bare ``int()``:
    a bare parse raises an untranslated ``ValueError`` naming neither the row
    nor the accepted range.
    """
    if raw is None:
        return None
    text = raw.strip()
    if not is_plain_whole_number(text):
        raise ProfileAnswerTypeError(
            f"renta_family.descendiente.{index}.alta_posterior_nacimiento_mes must be a month 1-12; got {raw!r}.",
        )
    month = int(text)
    if not is_calendar_month(month):
        raise ProfileAnswerTypeError(
            f"renta_family.descendiente.{index}.alta_posterior_nacimiento_mes must be a month 1-12; got {raw!r}.",
        )
    return month


def _stored_gastos_guarderia(raw: str | None, *, index: int) -> int:
    """Read one descendant's stored ANNUAL guardería figure, refusing a bad value.

    Absent means zero — no annual spend declared for this child.

    A present but unreadable value refuses INSTRUCTIVELY and by index, where a
    bare ``int()`` raised an untranslated ``ValueError`` naming neither the row
    nor the accepted form. That mattered once this became the canonical reader
    for the calculate path: the derived-facts injector used to carry its own
    tolerant coercion and its own named refusal, and folding it onto this reader
    would otherwise have traded a diagnostic naming the row for a raw traceback.

    A negative figure refuses rather than clamping to zero, for this module's
    standing reason: a clamp is a value the operator never wrote, and silently
    substituting one is how a figure stops meaning what was typed.

    The sign is read rather than stripped. An earlier form of this guard used
    ``lstrip("-")``, which removes EVERY leading dash, so ``"--5"`` satisfied the
    digit test and fell through to ``int``, which rejects a double sign with the
    exact bare ``ValueError`` the paragraph above says this function exists to
    replace. That is the shape where an almost-right guard is worse than none,
    because the test proving it works passes. ``removeprefix`` takes one dash
    and no more, so a second one is left in the text and fails the shape test.
    """
    if raw is None:
        return 0
    text = raw.strip()
    negative = text.startswith("-")
    digits = text.removeprefix("-")
    if not is_plain_whole_number(digits):
        raise ProfileAnswerTypeError(
            f"renta_family.descendiente.{index}.gastos_guarderia must be a whole number of euros; got {raw!r}.",
        )
    if negative:
        # Reached for a signed zero too, deliberately. ``"-0"`` is numerically
        # the default and harmless, but accepting it while refusing ``"-5"``
        # would make the sign sometimes readable and sometimes not, and a reader
        # cannot tell which from the code. One rule: a sign here is refused.
        raise ProfileAnswerTypeError(
            f"renta_family.descendiente.{index}.gastos_guarderia must be zero or more; got {raw!r}.",
        )
    return int(digits)


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
    # The canonical grammar, not a bare ``Decimal()``. A bare constructor reads
    # the Spanish thousands shape ``12.500`` as twelve euros fifty -- three
    # orders of magnitude below what the taxpayer typed, silently, and in the
    # CLAIMING direction: the real figure would breach the Art. 58.1 ceiling
    # and disqualify the descendant, while the misread figure sits far below it
    # and restores the full mínimo.
    #
    # ``max_fraction_digits=2`` is what makes the thousands shape refuse, since
    # a Spanish grouping is always exactly three digits. That protection is
    # therefore incidental rather than separator recognition, and it declines a
    # literal ``8.000`` meaning eight euros exactly. That cost is accepted
    # knowingly: a parser that GUESSES which convention the
    # operator meant is the silent-corruption surface, and a loud refusal
    # naming the accepted form is the safe direction.
    value = try_parse_canonical_decimal(raw, max_fraction_digits=2)
    if value is None:
        raise ProfileAnswerTypeError(
            f"renta_family.descendiente.{index}.rentas_anuales must be euros with a dot decimal "
            f"separator and no thousands grouping (for example 12500 or 12500.75); got {raw!r}. "
            "The Spanish thousands shape is refused rather than read, because reading '12.500' as "
            "twelve euros fifty would restore a mínimo por descendientes that the real figure "
            "disqualifies.",
            translated_message=_RENTAS_GRAMMAR_LOCALE_KEY,
        )
    if value < 0:
        raise ProfileAnswerTypeError(
            f"renta_family.descendiente.{index}.rentas_anuales must be a non-negative amount; got {raw!r}.",
            translated_message=_RENTAS_GRAMMAR_LOCALE_KEY,
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

    Accepted keys (case-insensitive)::

      NACIMIENTO=YYYY-MM-DD  (required) birth date
      RELACION=descendiente|adoptado|acogimiento_preadoptivo_o_permanente|
               acogimiento_temporal|tutela|guarda_y_custodia_judicial
                             (optional, default descendiente) Art. 58.1 / 58.2
                             relationship. A temporal acogimiento takes the
                             tranches and NOT the under-three increase. A
                             judicial guarda y custodia takes the tranches and
                             neither the increase nor the Art. 81.1 deducción
                             por maternidad, which excludes it by name.
      INSCRIPCION=YYYY-MM-DD (optional) Registro Civil inscription of the
                             adoption, or the resolución judicial o
                             administrativa where inscription is not required
                             — the Art. 58.2 anchor for RELACION=adoptado.
                             Supplying it without RELACION reads as adoptado.
      ACOGIMIENTO=YYYY-MM-DD (optional) first ENTITLING acogimiento resolución
                             — the Art. 58.2 anchor for a preadoptivo or
                             permanente placement, and retained on an adoptado
                             record so a fostered-then-adopted child's window
                             is capped at three periods rather than restarted.
      DISCAPACIDAD=0|33|65   (optional) discapacidad grade
      CONVIVENCIA=true|false (optional, default true) cohabitation flag
      DEPENDENCIA=true|false (optional) the taxpayer contributes to this
                             descendant's upkeep without cohabiting. Omit to
                             leave UNSET, which never assimilates; only an
                             explicit true does, and only when no anualidades
                             are declared.
      CUSTODIA=true|false    (optional, default false) custodia compartida (Art. 61 LIRPF)
      RENTAS=N               (optional) annual rentas excluding exempt income — Art. 58.1 ceiling
      DECLARACION_PROPIA=true|false
                             (optional, default false) descendant files their own IRPF return
                             — combines with RENTAS for the Art. 61 norma 2ª exclusion
      PRORRATA=true|false    (optional) explicit Art. 61 norma 1ª answer: is another
                             contribuyente also entitled to this descendant's mínimo?
                             Omit to let the engine derive it from profile signals.
      MESES_TRABAJO=0..12    (optional, default 0) months mother worked — Art. 81 deducción maternidad
      ALTA_POSTERIOR_MES=1..12
                             (optional) calendar month in which a mother not registered with the
                             Seguridad Social or a mutualidad at the birth completed the 30-day
                             minimum contribution period Art. 81.1 requires for the post-birth alta
                             route. Adds the 150 euro completion-month increment (raising this
                             child's cap to 1.350 euros) for filing years from 2023 only. Omit for
                             the ordinary case.
      GASTOS_GUARDERIA=N     (optional, default 0) actual guardería euros — Art. 81.2 incremento 0613,
                             as an ANNUAL total. Sufficient only while the
                             child is under three for the whole period.
      GASTOS_GUARDERIA_MENSUAL=MM:N[;MM-MM:N...]
                             (optional) the same spend month by month, sparse.
                             Entries are separated by ';' rather than ',' because
                             ',' already separates this flag's own keys, and a
                             month specification may be a range (9-12:210) for
                             the ordinary case of a constant fee across an
                             enrolment span. Required for the period in which the
                             child turns three, whose post-birthday months an
                             annual total cannot be apportioned across. Mutually
                             exclusive with GASTOS_GUARDERIA for one child.
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

    # RELACION is read through the same stored-token authority the fact-index
    # path uses, so the flag door and the profile-read door refuse an unknown
    # value identically rather than each inventing a tolerance.
    relacion_raw = parts.get("RELACION")
    relacion = _stored_relacion(relacion_raw.strip() or None if relacion_raw else None, index=0)

    civil_fields = _flag_civil_fields(parts)
    family_fields = _flag_family_fields(parts)
    maternity_fields = _flag_maternity_fields(parts)
    nif_raw = parts.get("NIF")

    return DescendantInfo(
        birth_date=birth_date,
        **relacion_kwarg(relacion),
        **civil_fields,
        **family_fields,
        **maternity_fields,
        nif=tax_id_identity_token(nif_raw) if nif_raw else None,
    )


def _flag_civil_fields(parts: dict[str, str]) -> _CivilFields:
    inscripcion_raw = parts.get("INSCRIPCION")
    acogimiento_raw = parts.get("ACOGIMIENTO")
    fallecimiento_raw = parts.get("FALLECIMIENTO")
    disc_raw = parts.get("DISCAPACIDAD")
    discapacidad_grado: int | None = int(disc_raw) if disc_raw is not None else None
    if discapacidad_grado not in (None, 0, 33, 65):
        raise ProfileAnswerTypeError(f"DISCAPACIDAD must be 0, 33, or 65; got {discapacidad_grado!r}")
    return {
        "inscripcion_registro_civil_date": parse_iso8601_date(inscripcion_raw) if inscripcion_raw else None,
        "acogimiento_resolucion_date": parse_iso8601_date(acogimiento_raw) if acogimiento_raw else None,
        "death_date": parse_iso8601_date(fallecimiento_raw) if fallecimiento_raw else None,
        "discapacidad_grado": _discapacidad_grade(discapacidad_grado),
    }


def _flag_family_fields(parts: dict[str, str]) -> _FamilyFields:
    conv_raw = parts.get("CONVIVENCIA")
    dependencia_raw = parts.get("DEPENDENCIA")
    custodia_raw = parts.get("CUSTODIA")
    declaracion_raw = parts.get("DECLARACION_PROPIA")
    prorrata_raw = parts.get("PRORRATA")
    return {
        "convive_con_contribuyente": _flag_bool(conv_raw, key="CONVIVENCIA") if conv_raw is not None else True,
        "dependencia_economica": (
            _flag_bool(dependencia_raw, key="DEPENDENCIA") if dependencia_raw is not None else None
        ),
        "custodia_compartida": _flag_bool(custodia_raw, key="CUSTODIA") if custodia_raw is not None else False,
        "rentas_anuales_euros": _stored_rentas_anuales(parts.get("RENTAS") or None, index=0),
        "presenta_declaracion_propia": (
            _flag_bool(declaracion_raw, key="DECLARACION_PROPIA") if declaracion_raw is not None else False
        ),
        "prorrata_minimo": _flag_bool(prorrata_raw, key="PRORRATA") if prorrata_raw is not None else None,
    }


def _flag_maternity_fields(parts: dict[str, str]) -> _MaternityFields:
    meses_raw = parts.get("MESES_TRABAJO")
    alta_posterior_raw = parts.get("ALTA_POSTERIOR_MES")
    alta_posterior_nacimiento_mes = int(alta_posterior_raw) if alta_posterior_raw is not None else None
    if alta_posterior_nacimiento_mes is not None and not is_calendar_month(alta_posterior_nacimiento_mes):
        raise ProfileAnswerTypeError(f"ALTA_POSTERIOR_MES must be 1-12; got {alta_posterior_nacimiento_mes!r}")
    gastos_raw = parts.get("GASTOS_GUARDERIA")
    gastos_guarderia_euros = int(gastos_raw) if gastos_raw is not None else 0
    if gastos_guarderia_euros < 0:
        raise ProfileAnswerTypeError(f"GASTOS_GUARDERIA must be ≥ 0; got {gastos_guarderia_euros!r}")
    gastos_guarderia_mensuales = parse_guarderia_mensual(
        parts.get("GASTOS_GUARDERIA_MENSUAL") or "",
        field="GASTOS_GUARDERIA_MENSUAL",
    )
    if gastos_guarderia_mensuales and gastos_guarderia_euros > 0:
        raise ProfileAnswerTypeError(
            "--descendiente accepts GASTOS_GUARDERIA or GASTOS_GUARDERIA_MENSUAL for one "
            "descendant, not both. The monthly breakdown is the authority where it exists, "
            "so drop GASTOS_GUARDERIA rather than stating the same spend twice.",
        )
    return {
        "meses_madre_trabajo": parse_meses_trabajo(meses_raw, field="MESES_TRABAJO") if meses_raw is not None else (),
        "alta_posterior_nacimiento_mes": alta_posterior_nacimiento_mes,
        "segundo_ciclo_infantil_inicio_mes": None,
        "gastos_guarderia_euros": gastos_guarderia_euros,
        "gastos_guarderia_mensuales": gastos_guarderia_mensuales,
    }


__all__ = [
    "descendant_facts_from_list",
    "descendant_list_from_facts",
    "parse_descendiente_flag",
    "relacion_kwarg",
]
