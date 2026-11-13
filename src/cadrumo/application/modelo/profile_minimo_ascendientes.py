"""Derive the mínimo por ascendientes (casillas 0515 and 0516) from the stored ascendant rows.

The rows live at ``renta_family.ascendiente.{n}.{leaf}``. The injector folds them
into the year-free derived facts ``renta_family.ascendientes_minimos_aggregate``
(parte estatal) and ``renta_family.ascendientes_minimos_aggregate_autonomico``
(parte autonómica), which the registry bindings project onto the casillas, the same
division of labour the mínimo por descendientes uses. It runs only where the
selected revision declares a binding that consumes a fact, so coverage of an
edition is registry work.

Both parts apply the same eligibility, ages, ceilings and sharing (LIRPF arts. 59
and 61). The autonomic part differs only in the art. 59.1 cuantía and the art. 59.2
increment: LIRPF art. 56.3 applies the amounts the comunidad of residence approved,
which the edition declares in keyed tables by comunidad token, and the state ones
where the table lists no amount for that comunidad.

A row whose share turns on a fact it does not state withholds the aggregate. The
fact stays absent, never zero; the consuming binding is reported unresolved, and one
``household_row_fact_unstated`` note per missing leaf names the rows that omit it by
their 0-based position. That note is what stops checking, local filing and export,
sending the filer to the ascendant edit door for the first such row.

Two further facts come from the same rows. The ``PCTMINASDLG`` disability key of
each row is derived from its grade, assistance and judicial incapacity, and written
at ``renta_family.ascendiente.{n}.minimo_discapacidad_clave`` for the bindings that
read it; the code for each circumstance is the design's, from the registry. The
art. 60.2 disability minimum of an ascendant is not computed: a row the art. 59
mínimo reaches whose art. 60.3 grade reaches the disability threshold raises one
``ascendant_disability_minimum_not_computed`` note, which stops checking, local
filing and export rather than leaving that minimum silently out.

:class:`RegistrySnapshot` is the pinned registry snapshot.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Final

from ...core.aggregation import BindingSourceKind
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.parsing.dates import parse_iso8601_date
from ...domain.calculations.registry.form_codes import resolve_form_codes
from ...domain.calculations.registry.formula_runtime_ops import resolve_keyed_bracket, resolve_parameter
from ...domain.calculations.registry.profile_bindings import ProfileProvider
from ...domain.contribuyente.ascendant_minimum import (
    CONVIVENCIA_MITAD_PERIODO_LEAF,
    CONVIVIENTES_LEAF,
    DECLARACION_PROPIA_LEAF,
    DISCAPACIDAD_ASISTENCIA_LEAF,
    DISCAPACIDAD_LEAF,
    INCAPACIDAD_JUDICIAL_LEAF,
    RENTAS_ANUALES_LEAF,
    AscendantInfo,
    AscendantMinimumAmounts,
    AscendantMinimumResult,
    DisabilityGrades,
    ascendant_entitlement_weighted_count,
    disability_minimum_positions,
    minimo_ascendientes,
)
from ...domain.modelos.calculation_revision_sources import CalculationNoteFact, CalculationNoteSentence
from ..aggregation.source_mesh import CalculationSourceDiagnostic
from ..user_profile.ascendant_rows import ASCENDANT_ROW_LEAVES
from .profile_binding_refusal_doors import ascendant_row_value_refused_verdict
from .profile_derived_facts import ProfileBindingResolutionError, snapshot_authored_year
from .profile_read_recording import fact_items_under

if TYPE_CHECKING:
    from ...domain.calculations.registry.schema import RegistrySnapshot
    from ...domain.contribuyente.family_fact_context import FamilyFactResolutionContext
    from ...domain.user_profile.values import UserProfileFactValue

__all__ = [
    "ASCENDANT_DISABILITY_KEY_LEAF",
    "ASCENDANT_DISABILITY_MINIMUM_NOT_COMPUTED_REASON",
    "MINIMO_ASCENDIENTES_AGGREGATE_KEY",
    "MINIMO_ASCENDIENTES_AUTONOMICO_AGGREGATE_KEY",
    "AscendantEntitlementCount",
    "AscendantMinimumDerivation",
    "ascendant_entitlement_count",
    "inject_derived_minimo_ascendientes_facts",
]

MINIMO_ASCENDIENTES_AGGREGATE_KEY: Final = "renta_family.ascendientes_minimos_aggregate"
MINIMO_ASCENDIENTES_AUTONOMICO_AGGREGATE_KEY: Final = "renta_family.ascendientes_minimos_aggregate_autonomico"

ASCENDANT_DISABILITY_KEY_LEAF: Final = "minimo_discapacidad_clave"
"""The derived row leaf that carries the ``PCTMINASDLG`` code; the profile never stores it."""
ASCENDANT_DISABILITY_MINIMUM_NOT_COMPUTED_REASON: Final = "ascendant_disability_minimum_not_computed"

_ASCENDANT_GROUP: Final = "renta_family.ascendiente"
_FORM_ROW_CODES_FACT: Final = "form-row-codes"
_DISABILITY_KEY_CODE_PREFIX: Final = "m100.ascendant_disability_key"
_BIRTH_DATE_LEAF: Final = "birth_date"
_DEATH_DATE_LEAF: Final = "fallecimiento"
_ROW_LEAF: Final = re.compile(rf"^{re.escape(_ASCENDANT_GROUP)}\.(\d+)\.([a-z0-9_]+)$")
_YES_NO: Final = {"true": True, "false": False}

_PARAMETER_IDS: Final = {
    "base": "renta-minimo-ascendientes-mayor-65",
    "increment_over_age": "renta-minimo-ascendientes-mayor-75",
    "fallecimiento": "renta-minimo-ascendientes-fallecimiento",
    "rentas_anuales_limite": "renta-minimo-ascendientes-rentas-anuales-limite",
    "declaracion_propia_rentas_limite": "renta-minimo-ascendientes-declaracion-propia-rentas-limite",
}

# The amounts a comunidad may set under Ley 22/2009 art. 46.1.a), keyed by its token.
# The death cuantía, ages and ceilings are not among them and stay the state figures.
_AUTONOMIC_PARAMETER_IDS: Final = {
    "base": "renta-minimo-ascendientes-mayor-65-autonomico",
    "increment_over_age": "renta-minimo-ascendientes-mayor-75-autonomico",
}

_TAX_RESIDENCE_CCAA_KEY: Final = "tax_residence.ccaa"


@dataclass(frozen=True, slots=True)
class AscendantMinimumDerivation:
    """The derived paths withheld for unstated facts, and the notes that name those facts."""

    withheld_paths: frozenset[str] = frozenset()
    diagnostics: tuple[CalculationSourceDiagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class AscendantEntitlementCount:
    """The weighted count of ascendants a comunidad deducción reaches, or the notes that withhold it."""

    count: Decimal | None
    """``None`` while a row owes a deciding fact or the edition lacks a state figure."""
    diagnostics: tuple[CalculationSourceDiagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class _StoredAscendants:
    ascendants: tuple[AscendantInfo, ...]
    positions: tuple[int, ...]
    """The 0-based stored position of each read ascendant, which is the edit door's index."""
    owed: dict[str, list[int]]
    """The rows that cannot be read at all, by the leaf they omit."""
    recorded: int
    indexes: tuple[int, ...] = ()
    """The stored row number of each read ascendant, which its derived leaves are written under."""


def _amounts(snapshot: RegistrySnapshot) -> AscendantMinimumAmounts | None:
    """The edition's art. 59/61 figures, or ``None`` when it does not declare all of them."""
    # A projected year reuses the authored edition's dated parameter values.
    date_context = {"filing_period": date(snapshot_authored_year(snapshot), 12, 31)}
    declared = {parameter.id: parameter for parameter in snapshot.revision.parameters}
    resolved: dict[str, Decimal] = {}
    for field, parameter_id in _PARAMETER_IDS.items():
        parameter = declared.get(parameter_id)
        if parameter is None:
            return None
        resolved[field] = resolve_parameter(parameter, date_context)
    return AscendantMinimumAmounts.model_validate(resolved)


def _autonomic_amounts(
    snapshot: RegistrySnapshot, state: AscendantMinimumAmounts, ccaa: str
) -> AscendantMinimumAmounts:
    """The amounts for ``ccaa``: its own where the edition's table lists one, else the state ones."""
    declared = {parameter.id: parameter for parameter in snapshot.revision.parameters}
    # A projected year reuses the authored edition's rows, as the state figures do.
    year = snapshot_authored_year(snapshot)
    own: dict[str, Decimal] = {}
    for field, parameter_id in _AUTONOMIC_PARAMETER_IDS.items():
        value = resolve_keyed_bracket(declared.get(parameter_id), key=ccaa, filing_year=year)
        if value is not None:
            own[field] = value
    return state.model_copy(update=own)


def _residence_ccaa(fact_index: Mapping[str, UserProfileFactValue]) -> str | None:
    raw = fact_index.get(_TAX_RESIDENCE_CCAA_KEY)
    if not isinstance(raw, str):
        return None
    token = raw.strip().lower()
    return token or None


def _refuse_stored(index: int, leaf: str) -> ProfileBindingResolutionError:
    return ProfileBindingResolutionError(
        f"{_ASCENDANT_GROUP}.{index}.{leaf} holds a value the ascendant row cannot",
        translated_message="application.modelo.errors.ascendant_stored_value_unreadable",
        context={"row": index + 1},
        precondition_verdict=ascendant_row_value_refused_verdict(index, leaf),
    )


def _stored_date(row: Mapping[str, str], index: int, leaf: str) -> date | None:
    raw = row.get(leaf)
    if raw is None:
        return None
    try:
        parsed = parse_iso8601_date(raw)
    except (TypeError, ValueError) as exc:
        raise _refuse_stored(index, leaf) from exc
    if parsed is None:
        raise _refuse_stored(index, leaf)
    return parsed


def _stored_count(row: Mapping[str, str], index: int, leaf: str) -> int | None:
    raw = row.get(leaf)
    if raw is None:
        return None
    if not (raw.isascii() and raw.isdigit()):
        raise _refuse_stored(index, leaf)
    return int(raw)


def _stored_amount(row: Mapping[str, str], index: int) -> Decimal | None:
    raw = row.get(RENTAS_ANUALES_LEAF)
    if raw is None:
        return None
    value = try_parse_canonical_decimal(raw, max_fraction_digits=2)
    if value is None or value < 0:
        raise _refuse_stored(index, RENTAS_ANUALES_LEAF)
    return value


def _stored_answer(row: Mapping[str, str], index: int, leaf: str) -> bool | None:
    raw = row.get(leaf)
    if raw is None:
        return None
    answer = _YES_NO.get(raw.lower())
    if answer is None:
        raise _refuse_stored(index, leaf)
    return answer


def _stored_rows(fact_index: Mapping[str, UserProfileFactValue]) -> dict[int, dict[str, str]]:
    rows: dict[int, dict[str, str]] = {}
    for path, value in fact_items_under(fact_index, f"{_ASCENDANT_GROUP}.").items():
        match = _ROW_LEAF.match(path)
        # Only the leaves the edit door reads make a row, so a position here is the door's index.
        if match is None or value is None or match.group(2) not in ASCENDANT_ROW_LEAVES:
            continue
        text = value.isoformat() if isinstance(value, date) else str(value).strip()
        if text:
            rows.setdefault(int(match.group(1)), {})[match.group(2)] = text
    return dict(sorted(rows.items()))


def _ascendant(index: int, row: Mapping[str, str]) -> AscendantInfo | None:
    """One stored row, or ``None`` when it has no birth date, which the door always requires."""
    birth = _stored_date(row, index, _BIRTH_DATE_LEAF)
    if birth is None:
        return None
    return AscendantInfo(
        birth_date=birth,
        death_date=_stored_date(row, index, _DEATH_DATE_LEAF),
        convivientes=_stored_count(row, index, CONVIVIENTES_LEAF),
        convivencia_mitad_periodo=_stored_answer(row, index, CONVIVENCIA_MITAD_PERIODO_LEAF),
        rentas_anuales_euros=_stored_amount(row, index),
        presenta_declaracion_propia=_stored_answer(row, index, DECLARACION_PROPIA_LEAF),
        discapacidad_grado=_stored_count(row, index, DISCAPACIDAD_LEAF),
        discapacidad_asistencia=_stored_answer(row, index, DISCAPACIDAD_ASISTENCIA_LEAF),
        incapacidad_judicial=_stored_answer(row, index, INCAPACIDAD_JUDICIAL_LEAF),
    )


def _unstated_note(leaf: str, rows: tuple[int, ...], recorded: int, *, bucket_id: str) -> CalculationSourceDiagnostic:
    """One note for ``leaf``, naming by 0-based position each row that omits it, as the edit door takes it."""
    omitting = len(rows)
    return CalculationSourceDiagnostic(
        reason="household_row_fact_unstated",
        source_kind=BindingSourceKind.PROFILE.value,
        binding_source=BindingSourceKind.PROFILE,
        message=(
            f"profile object {_ASCENDANT_GROUP!r} records {recorded} rows, {omitting} of them without "
            f"{leaf!r}, which the mínimo por ascendientes needs; the aggregate is withheld"
        ),
        resolver_id="profile",
        source_ref=f"profile:{bucket_id}:rows:{_ASCENDANT_GROUP}.{leaf}",
        fact=CalculationNoteFact.of(
            CalculationNoteSentence.HOUSEHOLD_ROW_FACT_UNSTATED,
            rows=tuple(str(row) for row in rows),
            group=_ASCENDANT_GROUP,
            leaf=leaf,
            omitting=omitting,
            recorded=recorded,
        ),
    )


def _read_stored_ascendants(fact_index: Mapping[str, UserProfileFactValue]) -> _StoredAscendants:
    rows = _stored_rows(fact_index)
    ascendants: list[AscendantInfo] = []
    positions: list[int] = []
    indexes: list[int] = []
    owed: dict[str, list[int]] = {}
    for position, (index, row) in enumerate(rows.items()):
        ascendant = _ascendant(index, row)
        if ascendant is None:
            owed.setdefault(_BIRTH_DATE_LEAF, []).append(position)
        else:
            ascendants.append(ascendant)
            positions.append(position)
            indexes.append(index)
    return _StoredAscendants(tuple(ascendants), tuple(positions), owed, len(rows), tuple(indexes))


def _reads_disability_key(snapshot: RegistrySnapshot) -> bool:
    """Whether a row binding of the edition reads the derived disability key of the ascendant rows."""
    return any(
        isinstance(binding.provider, ProfileProvider)
        and binding.provider.rows is not None
        and binding.provider.rows.object_path == _ASCENDANT_GROUP
        and binding.provider.rows.leaf == ASCENDANT_DISABILITY_KEY_LEAF
        for binding in snapshot.revision.bindings
    )


def _inject_disability_keys(
    fact_index: dict[str, UserProfileFactValue],
    snapshot: RegistrySnapshot,
    stored: _StoredAscendants,
    *,
    context: FamilyFactResolutionContext,
) -> None:
    """Write each row's ``PCTMINASDLG`` code where an edition reads it; a row with none decided gets none.

    The path is derived, so a value already there can only be stale or hand-planted.
    """
    prefix = f"{_ASCENDANT_GROUP}."
    suffix = f".{ASCENDANT_DISABILITY_KEY_LEAF}"
    for path in [path for path in fact_index if path.startswith(prefix) and path.endswith(suffix)]:
        fact_index.pop(path)
    if not _reads_disability_key(snapshot):
        return
    grades = DisabilityGrades.resolve(context)
    codes = resolve_form_codes(_FORM_ROW_CODES_FACT, authority=context.authority)
    for index, ascendant in zip(stored.indexes, stored.ascendants, strict=True):
        key = ascendant.disability_key(grades)
        if key is not None:
            fact_index[f"{_ASCENDANT_GROUP}.{index}{suffix}"] = codes.code(f"{_DISABILITY_KEY_CODE_PREFIX}.{key.value}")


def _disability_minimum_notes(
    stored: _StoredAscendants,
    snapshot: RegistrySnapshot,
    *,
    amounts: AscendantMinimumAmounts,
    context: FamilyFactResolutionContext,
    bucket_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """The note that the art. 60.2 minimum of the rows it reaches is not computed, or none when it reaches none."""
    positions = disability_minimum_positions(stored.ascendants, snapshot.filing_year, amounts=amounts, context=context)
    if not positions:
        return ()
    rows = tuple(str(stored.positions[position - 1]) for position in positions)
    return (
        CalculationSourceDiagnostic(
            reason=ASCENDANT_DISABILITY_MINIMUM_NOT_COMPUTED_REASON,
            source_kind=BindingSourceKind.PROFILE.value,
            binding_source=BindingSourceKind.PROFILE,
            message=(
                f"profile object {_ASCENDANT_GROUP!r} records {len(rows)} ascendants with a disability for whom the "
                "mínimo por ascendientes applies; their disability minimum is not computed"
            ),
            resolver_id="profile",
            source_ref=f"profile:{bucket_id}:rows:{_ASCENDANT_GROUP}.{DISCAPACIDAD_LEAF}",
            fact=CalculationNoteFact.of(
                CalculationNoteSentence.ASCENDANT_DISABILITY_MINIMUM_NOT_COMPUTED,
                rows=rows,
                group=_ASCENDANT_GROUP,
                count=len(rows),
            ),
        ),
    )


def _owed_notes(
    stored: _StoredAscendants, result: AscendantMinimumResult, *, bucket_id: str
) -> tuple[CalculationSourceDiagnostic, ...]:
    """One note per leaf the stored rows omit, unreadable rows and withholding rows alike."""
    owed = {leaf: list(rows) for leaf, rows in stored.owed.items()}
    for unstated in result.unstated:
        for leaf in unstated.leaves:
            owed.setdefault(leaf, []).append(stored.positions[unstated.position - 1])
    return tuple(
        _unstated_note(leaf, tuple(sorted(omitting)), stored.recorded, bucket_id=bucket_id)
        for leaf, omitting in sorted(owed.items())
    )


def ascendant_entitlement_count(
    fact_index: Mapping[str, UserProfileFactValue],
    snapshot: RegistrySnapshot,
    *,
    qualifying_age: int,
    qualifying_discapacidad_grado: int,
    context: FamilyFactResolutionContext,
    bucket_id: str,
) -> AscendantEntitlementCount:
    """Count the stored ascendants a comunidad deducción resting on the mínimo reaches.

    Reads the rows exactly as the mínimo does, so a row that owes a fact for one owes
    it for the other and the notes coincide. A row a stated fact rules out counts
    zero; a row that owes a deciding fact withholds the count with its notes.
    """
    amounts = _amounts(snapshot)
    if amounts is None:
        return AscendantEntitlementCount(count=None)
    stored = _read_stored_ascendants(fact_index)
    result = ascendant_entitlement_weighted_count(
        stored.ascendants,
        snapshot.filing_year,
        amounts=amounts,
        context=context,
        qualifying_age=qualifying_age,
        qualifying_discapacidad_grado=qualifying_discapacidad_grado,
    )
    notes = _owed_notes(stored, result, bucket_id=bucket_id)
    if notes or result.total is None:
        return AscendantEntitlementCount(count=None, diagnostics=notes)
    return AscendantEntitlementCount(count=result.total)


def inject_derived_minimo_ascendientes_facts(
    fact_index: dict[str, UserProfileFactValue],
    snapshot: RegistrySnapshot,
    declared_selectors: frozenset[str],
    *,
    context: FamilyFactResolutionContext,
    bucket_id: str,
) -> AscendantMinimumDerivation:
    """Write the art. 59 aggregates a binding consumes, or withhold them and say why.

    Computes always where a consumer is declared: the paths are derived, so a stored
    value there can only be stale or hand-planted. Leaves the paths absent without a
    note when the edition lacks one of the state figures, which the derived-binding
    advisory then reports as a structural gap. A row that owes a fact withholds both
    parts. The autonomic part is also withheld when an ascendant is entitled and the
    profile states no comunidad of residence, since its amounts depend on it.

    Also writes each row's derived disability key where the edition reads it, and
    notes the rows whose art. 60.2 disability minimum is not computed.
    """
    stored = _read_stored_ascendants(fact_index)
    _inject_disability_keys(fact_index, snapshot, stored, context=context)
    consumed = tuple(
        key
        for key in (MINIMO_ASCENDIENTES_AGGREGATE_KEY, MINIMO_ASCENDIENTES_AUTONOMICO_AGGREGATE_KEY)
        if key in declared_selectors
    )
    if not consumed:
        return AscendantMinimumDerivation()
    for key in consumed:
        fact_index.pop(key, None)
    amounts = _amounts(snapshot)
    if amounts is None:
        return AscendantMinimumDerivation()
    ascendants = stored.ascendants
    result = minimo_ascendientes(ascendants, snapshot.filing_year, amounts=amounts, context=context)
    unproven = _disability_minimum_notes(stored, snapshot, amounts=amounts, context=context, bucket_id=bucket_id)
    notes = _owed_notes(stored, result, bucket_id=bucket_id)
    if notes or result.total is None:
        return AscendantMinimumDerivation(withheld_paths=frozenset(consumed), diagnostics=(*notes, *unproven))
    if MINIMO_ASCENDIENTES_AGGREGATE_KEY in consumed:
        fact_index[MINIMO_ASCENDIENTES_AGGREGATE_KEY] = result.total
    if MINIMO_ASCENDIENTES_AUTONOMICO_AGGREGATE_KEY not in consumed:
        return AscendantMinimumDerivation(diagnostics=unproven)
    autonomic = _inject_autonomic_part(
        fact_index, snapshot, ascendants, amounts=amounts, state_total=result.total, context=context
    )
    return AscendantMinimumDerivation(withheld_paths=autonomic.withheld_paths, diagnostics=unproven)


def _inject_autonomic_part(
    fact_index: dict[str, UserProfileFactValue],
    snapshot: RegistrySnapshot,
    ascendants: Sequence[AscendantInfo],
    *,
    amounts: AscendantMinimumAmounts,
    state_total: Decimal,
    context: FamilyFactResolutionContext,
) -> AscendantMinimumDerivation:
    """Write the autonomic aggregate from the comunidad of residence's amounts, or withhold it."""
    if state_total == 0:
        # No ascendant is entitled, so no comunidad's amounts can change the zero.
        fact_index[MINIMO_ASCENDIENTES_AUTONOMICO_AGGREGATE_KEY] = state_total
        return AscendantMinimumDerivation()
    ccaa = _residence_ccaa(fact_index)
    if ccaa is None:
        return AscendantMinimumDerivation(withheld_paths=frozenset({MINIMO_ASCENDIENTES_AUTONOMICO_AGGREGATE_KEY}))
    autonomico = minimo_ascendientes(
        ascendants,
        snapshot.filing_year,
        amounts=_autonomic_amounts(snapshot, amounts, ccaa),
        context=context,
    )
    if autonomico.total is None:
        return AscendantMinimumDerivation(withheld_paths=frozenset({MINIMO_ASCENDIENTES_AUTONOMICO_AGGREGATE_KEY}))
    fact_index[MINIMO_ASCENDIENTES_AUTONOMICO_AGGREGATE_KEY] = autonomico.total
    return AscendantMinimumDerivation()
