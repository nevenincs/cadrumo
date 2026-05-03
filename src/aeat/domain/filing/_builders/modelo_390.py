"""Modelo 390 builder — annual IVA ``declaración-resumen``.

Modelo 390 is the annual summary filed once per ejercicio by
Spanish autónomos and businesses in the general IVA regime. It
reconciles every quarterly Modelo 303 filed during the year and
exposes the annual totals in a single declarative form. v1
coverage per :mod:`aeat.domain.filing._builders._modelo_390_schema`
comprises the arithmetic backbone of the régimen general annual
totals plus reconciliation findings against the four quarterly
303 drafts.

The builder reads the four quarterly drafts out of a reserved
``_quarterly_303`` key on the :class:`FilingInputs` mapping — the
``FilingBuilder`` ABC's signature is fixed on ``main`` and this
is the least invasive way to thread the tuple through
:func:`aeat.application.filing.build_draft` without changing public API
shape. See the ADR ``2026-04-12-modelo-303-390-adr`` for the
trade-off discussion.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from ....core.logging import get_logger
from .._builder import FilingBuilder
from .._errors import FilingComputationError
from .._protocols import (
    CasillaSchema,
    CasillaSchemaProvider,
    FilingInputs,
    FilingProfile,
)
from .._schema import (
    FilingDraft,
    FilingDraftStatus,
    FilingScalar,
    FilingValue,
    FilingValueKind,
    compute_draft_id,
)

_logger = get_logger(__name__)

#: Reserved key the caller uses to pass the four quarterly 303
#: drafts into :meth:`Modelo390Builder.build`.
QUARTERLY_303_INPUT_KEY = "_quarterly_303"

#: Mapping of 390 quarterly-sum casilla → 303 source casilla.
_QUARTERLY_SUM_MAP: dict[str, str] = {
    "100": "01",
    "101": "03",
    "104": "04",
    "105": "06",
    "108": "07",
    "109": "09",
    "190": "28",
    "191": "29",
    "192": "30",
    "193": "31",
}


class Modelo390Builder(FilingBuilder):
    """Concrete builder for Modelo 390 (annual IVA summary) drafts.

    Example:
        ```python
        from .. import build_draft
        from ..runtime import (
            FilingOperatorProfile,
            build_runtime_schema_provider,
        )

        profile = FilingOperatorProfile(
            tax_id="12345678Z",
            display_name="Demo",
            applicable_modelos=("303", "390"),
        )
        provider = build_runtime_schema_provider()
        q1 = build_draft(modelo="303", period="2025Q1", ...)
        q2 = build_draft(modelo="303", period="2025Q2", ...)
        q3 = build_draft(modelo="303", period="2025Q3", ...)
        q4 = build_draft(modelo="303", period="2025Q4", ...)
        annual = build_draft(
            modelo="390",
            period="2025",
            profile=profile,
            inputs={"01": 2025, "_quarterly_303": (q1, q2, q3, q4)},
            schema_provider=provider,
        )
        ```
    """

    modelo_id = "390"

    def build(
        self,
        *,
        period: str,
        profile: FilingProfile,
        inputs: FilingInputs,
        schema_provider: CasillaSchemaProvider,
    ) -> FilingDraft:
        """Build a frozen Modelo 390 draft.

        Args:
            period: Annual period identifier (e.g. ``"2025"``).
            profile: Taxpayer profile the draft is built for.
            inputs: Mapping that must include
                ``"01"`` (ejercicio int) and
                ``"_quarterly_303"`` (tuple of four Modelo 303
                :class:`FilingDraft` records).
            schema_provider: Resolves the Modelo 390 casilla
                collection.

        Returns:
            A frozen :class:`FilingDraft` with the annual totals
            computed and an :attr:`FilingValueKind.INHERITED`
            provenance on every quarterly-sum casilla.

        Raises:
            FilingComputationError: When the quarterly drafts are
                missing, have the wrong shape, disagree on the
                ejercicio, or a formula dependency is unresolvable.
        """
        quarterly = _extract_quarterly_drafts(inputs)
        ejercicio = _require_ejercicio(inputs)
        _assert_quarterly_shape(quarterly, ejercicio)

        collection = schema_provider.get_collection(self.modelo_id)
        quarterly_index = _index_quarterly_values(quarterly)

        values: dict[str, FilingValue] = {}
        for casilla in collection.all():
            if casilla.id in _QUARTERLY_SUM_MAP:
                values[casilla.id] = _inherit_from_quarterly(
                    casilla_id=casilla.id,
                    source_casilla=_QUARTERLY_SUM_MAP[casilla.id],
                    quarterly_index=quarterly_index,
                )
                continue
            if casilla.formula_inputs:
                continue
            values[casilla.id] = _materialise_literal(casilla, inputs)

        pending = [c for c in collection.all() if c.formula_inputs]
        for _ in range(len(pending) + 1):
            if not pending:
                break
            still: list[CasillaSchema] = []
            for casilla in pending:
                if not all(dep in values for dep in casilla.formula_inputs):
                    still.append(casilla)
                    continue
                values[casilla.id] = self._compute(casilla, values)
            if len(still) == len(pending):
                missing = [c.id for c in still]
                raise FilingComputationError(
                    f"Cannot resolve formula casillas {missing!r}: dependency cycle or missing inputs"
                )
            pending = still

        ordered = tuple(values[c.id] for c in collection.all())
        now = datetime.now(tz=UTC)
        draft_id = compute_draft_id(
            modelo=self.modelo_id,
            period=period,
            profile_tax_id=profile.tax_id,
            schema_version=collection.schema_version,
            values=ordered,
        )
        _logger.debug(
            "built modelo 390 draft draft_id=%s ejercicio=%d",
            draft_id,
            ejercicio,
        )
        return FilingDraft(
            draft_id=draft_id,
            modelo=self.modelo_id,
            period=period,
            profile_tax_id=profile.tax_id,
            status=FilingDraftStatus.DRAFT,
            values=ordered,
            findings=(),
            created_at=now,
            updated_at=now,
            schema_version=collection.schema_version,
            notes="",
        )

    # ── helpers ──────────────────────────────────────────────────

    def _compute(
        self,
        casilla: CasillaSchema,
        values: dict[str, FilingValue],
    ) -> FilingValue:
        """Evaluate a Modelo 390 in-draft formula casilla.

        Args:
            casilla: The casilla schema for the target.
            values: Previously materialised :class:`FilingValue`
                records, keyed by casilla ID.

        Returns:
            The computed :class:`FilingValue`.

        Raises:
            FilingComputationError: When the casilla id is not
                one of the known Modelo 390 formulas.
        """
        if casilla.id == "84":
            total = _dec(values["101"]) + _dec(values["105"]) + _dec(values["109"])
            return _computed(casilla.id, total, ("101", "105", "109"))
        if casilla.id == "85":
            total = _dec(values["191"]) + _dec(values["193"])
            return _computed(casilla.id, total, ("191", "193"))
        if casilla.id == "86":
            return _computed(
                casilla.id,
                _dec(values["84"]) - _dec(values["85"]),
                ("84", "85"),
            )
        if casilla.id == "95":
            return _computed(casilla.id, _dec(values["86"]), ("86",))
        raise FilingComputationError(f"Unknown formula casilla {casilla.id!r} for Modelo 390")


# ── free helpers ────────────────────────────────────────────────


def _extract_quarterly_drafts(inputs: FilingInputs) -> tuple[FilingDraft, ...]:
    """Return the four quarterly 303 drafts, verifying shape.

    Raises:
        FilingComputationError: When the reserved key is absent
            or its value is not a tuple of four
            :class:`FilingDraft` records.
    """
    raw = inputs.get(QUARTERLY_303_INPUT_KEY)
    if raw is None:
        raise FilingComputationError(
            f"Modelo 390 requires inputs[{QUARTERLY_303_INPUT_KEY!r}] to carry the four quarterly Modelo 303 drafts"
        )
    if not isinstance(raw, tuple):
        raise FilingComputationError(
            f"Modelo 390 inputs[{QUARTERLY_303_INPUT_KEY!r}] must be a tuple, got {type(raw).__name__}"
        )
    if len(raw) != 4:
        raise FilingComputationError(f"Modelo 390 expects exactly 4 quarterly drafts, got {len(raw)}")
    drafts: list[FilingDraft] = []
    for index, entry in enumerate(raw):
        if not isinstance(entry, FilingDraft):
            raise FilingComputationError(
                f"Modelo 390 quarterly entry #{index} is not a FilingDraft (got {type(entry).__name__})"
            )
        drafts.append(entry)
    return tuple(drafts)


def _require_ejercicio(inputs: FilingInputs) -> int:
    """Return the ejercicio year as an int.

    Raises:
        FilingComputationError: When casilla ``01`` is missing or
            not coercible to an int year.
    """
    raw = inputs.get("01")
    if raw is None:
        raise FilingComputationError("Modelo 390 requires inputs['01'] (ejercicio year)")
    if isinstance(raw, bool):
        raise FilingComputationError("Ejercicio must be an int year, not a bool")
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str):
        try:
            return int(raw)
        except ValueError as exc:
            raise FilingComputationError(f"Ejercicio {raw!r} is not a valid year") from exc
    raise FilingComputationError(f"Unsupported ejercicio type {type(raw).__name__}")


def _assert_quarterly_shape(quarterly: tuple[FilingDraft, ...], ejercicio: int) -> None:
    """Verify every quarterly draft is a 303 of the same ejercicio.

    Raises:
        FilingComputationError: When any draft has the wrong
            modelo, when periods disagree on the year, or when
            the four periods do not form ``{Q1, Q2, Q3, Q4}``.
    """
    expected_periods = {f"{ejercicio}Q{q}" for q in (1, 2, 3, 4)}
    observed: set[str] = set()
    for draft in quarterly:
        if draft.modelo != "303":
            raise FilingComputationError(
                f"Quarterly draft {draft.draft_id} has modelo {draft.modelo!r}, expected '303'"
            )
        if draft.period in observed:
            raise FilingComputationError(f"Duplicate quarterly period {draft.period!r}")
        observed.add(draft.period)
    if observed != expected_periods:
        missing = sorted(expected_periods - observed)
        extra = sorted(observed - expected_periods)
        raise FilingComputationError(
            f"Quarterly 303 drafts for ejercicio {ejercicio} must cover "
            f"{sorted(expected_periods)!r}; missing={missing!r} extra={extra!r}"
        )


def _index_quarterly_values(
    quarterly: tuple[FilingDraft, ...],
) -> dict[str, dict[str, FilingValue]]:
    """Return ``{period: {casilla_id: FilingValue}}`` for fast lookup."""
    index: dict[str, dict[str, FilingValue]] = {}
    for draft in quarterly:
        index[draft.period] = {v.casilla_id: v for v in draft.values}
    return index


def _inherit_from_quarterly(
    *,
    casilla_id: str,
    source_casilla: str,
    quarterly_index: dict[str, dict[str, FilingValue]],
) -> FilingValue:
    """Sum one 303 casilla across the four quarterly drafts.

    Args:
        casilla_id: The target 390 casilla ID.
        source_casilla: The 303 casilla ID to sum across quarters.
        quarterly_index: Period → (casilla ID → FilingValue).

    Returns:
        An :class:`FilingValue` with kind
        :attr:`FilingValueKind.INHERITED`.

    Raises:
        FilingComputationError: When a quarterly draft is missing
            the source casilla.
    """
    total = Decimal("0")
    periods = sorted(quarterly_index)
    for period in periods:
        casillas = quarterly_index[period]
        source = casillas.get(source_casilla)
        if source is None:
            raise FilingComputationError(f"Quarterly draft {period!r} is missing source casilla {source_casilla!r}")
        total += _dec(source)
    return FilingValue(
        casilla_id=casilla_id,
        value=total,
        kind=FilingValueKind.INHERITED,
        source=f"sum of 303 casilla {source_casilla} across {','.join(periods)}",
        formula_trace=None,
    )


def _materialise_literal(casilla: CasillaSchema, inputs: FilingInputs) -> FilingValue:
    """Build a literal/default/empty :class:`FilingValue` for 390.

    Raises:
        FilingComputationError: When the input cannot be coerced.
    """
    raw = inputs.get(casilla.id)
    if raw is not None:
        return FilingValue(
            casilla_id=casilla.id,
            value=_coerce(casilla, raw),
            kind=FilingValueKind.LITERAL,
            source="user-supplied",
            formula_trace=None,
        )
    if casilla.default is not None:
        return FilingValue(
            casilla_id=casilla.id,
            value=_coerce(casilla, casilla.default),
            kind=FilingValueKind.DEFAULT,
            source="default per modelo schema",
            formula_trace=None,
        )
    return FilingValue(
        casilla_id=casilla.id,
        value=None,
        kind=FilingValueKind.EMPTY,
        source="no input supplied",
        formula_trace=None,
    )


def _coerce(casilla: CasillaSchema, raw: object) -> FilingScalar:
    """Coerce a raw value to the casilla's declared value type.

    Raises:
        FilingComputationError: When coercion fails.
    """
    try:
        if casilla.value_type == "decimal":
            if isinstance(raw, Decimal):
                return raw
            if isinstance(raw, bool):
                raise TypeError("bool is not a valid decimal input")
            if isinstance(raw, int | str):
                return Decimal(raw)
            raise TypeError(f"unsupported decimal input: {type(raw).__name__}")
        if casilla.value_type == "int":
            if isinstance(raw, bool):
                raise TypeError("bool is not a valid int input")
            if isinstance(raw, int):
                return raw
            if isinstance(raw, str):
                return int(raw)
            raise TypeError(f"unsupported int input: {type(raw).__name__}")
        if casilla.value_type == "str":
            if isinstance(raw, str):
                return raw
            raise TypeError(f"unsupported str input: {type(raw).__name__}")
        raise TypeError(f"unknown value_type {casilla.value_type!r}")
    except (TypeError, ValueError) as exc:
        raise FilingComputationError(f"Cannot coerce input for casilla {casilla.id!r}: {exc}") from exc


def _dec(value: FilingValue) -> Decimal:
    """Return ``value.value`` as a :class:`Decimal`, treating None as zero."""
    raw: FilingScalar = value.value
    if raw is None:
        return Decimal("0")
    if isinstance(raw, Decimal):
        return raw
    if isinstance(raw, bool):
        raise FilingComputationError(f"Boolean value on casilla {value.casilla_id!r} cannot participate in a formula")
    if isinstance(raw, int):
        return Decimal(raw)
    raise FilingComputationError(
        f"Cannot use {type(raw).__name__} value on casilla {value.casilla_id!r} in a Modelo 390 formula"
    )


def _computed(casilla_id: str, value: Decimal, trace: tuple[str, ...]) -> FilingValue:
    """Build a :class:`FilingValue` for a computed Modelo 390 casilla."""
    return FilingValue(
        casilla_id=casilla_id,
        value=value,
        kind=FilingValueKind.COMPUTED,
        source=f"computed from casillas {','.join(trace)}",
        formula_trace=trace,
    )
