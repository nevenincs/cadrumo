"""Modelo 303 builder — quarterly IVA autoliquidación (general regime).

Modelo 303 is the quarterly IVA form filed by Spanish autónomos
and businesses in the general IVA regime. This builder covers v1
scope per :mod:`aeat.filing._builders._modelo_303_schema`:
operaciones interiores régimen general (casillas 01-09), IVA
deducible (28-45), and resultado de la liquidación (64-71).

The formula set is hand-curated against the *Manual práctico IVA
2025* (AEAT) and will be re-sourced from the casilla DB (#23)
once that subpackage lands on ``main``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from ...logging import get_logger
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

#: Reduced rate for food / cultural goods in 2025.
_RATE_4 = Decimal("0.04")
#: Reduced rate for hospitality / passenger transport in 2025.
_RATE_10 = Decimal("0.10")
#: General IVA rate for 2025.
_RATE_21 = Decimal("0.21")


class Modelo303Builder(FilingBuilder):
    """Concrete builder for Modelo 303 (quarterly IVA) drafts.

    Example:
        ```python
        from decimal import Decimal

        from .. import build_draft
        from ..testing import (
            SyntheticProfile,
            default_schema_provider,
        )

        profile = SyntheticProfile(
            tax_id="12345678Z",
            display_name="Demo S.L.",
            applicable_modelos=("303",),
        )
        draft = build_draft(
            modelo="303",
            period="2025Q1",
            profile=profile,
            inputs={
                "07": Decimal("10000.00"),  # base gravada al 21%
                "29": Decimal("200.00"),    # cuota deducible
            },
            schema_provider=default_schema_provider(),
        )
        ```
    """

    modelo_id = "303"

    def build(
        self,
        *,
        period: str,
        profile: FilingProfile,
        inputs: FilingInputs,
        schema_provider: CasillaSchemaProvider,
    ) -> FilingDraft:
        """Build a frozen Modelo 303 draft.

        Args:
            period: Period identifier — must match
                ``r"^\\d{4}Q[1-4]$"`` (e.g. ``"2025Q1"``). The
                builder does not enforce the regex; the validator
                will flag shape issues.
            profile: Taxpayer profile the draft is built for.
            inputs: Mapping casilla ID → raw input value. The
                builder coerces decimals from
                ``int`` / ``str`` / :class:`Decimal`.
            schema_provider: Resolves the Modelo 303 casilla
                collection.

        Returns:
            A frozen :class:`FilingDraft` with every casilla
            populated, in :attr:`FilingDraftStatus.DRAFT` state.

        Raises:
            FilingComputationError: When an input cannot be
                coerced or a formula dependency is unresolvable.
        """
        collection = schema_provider.get_collection(self.modelo_id)
        values: dict[str, FilingValue] = {}

        for casilla in collection.all():
            if casilla.formula_inputs:
                continue
            values[casilla.id] = _materialise_literal(casilla, inputs)

        pending = [c for c in collection.all() if c.formula_inputs]
        for _ in range(len(pending) + 1):
            if not pending:
                break
            still_pending: list[CasillaSchema] = []
            for casilla in pending:
                if not all(dep in values for dep in casilla.formula_inputs):
                    still_pending.append(casilla)
                    continue
                values[casilla.id] = self._compute(casilla, values)
            if len(still_pending) == len(pending):
                missing = [c.id for c in still_pending]
                raise FilingComputationError(
                    f"Cannot resolve formula casillas {missing!r}: dependency cycle or missing inputs"
                )
            pending = still_pending

        ordered_values = tuple(values[c.id] for c in collection.all())
        now = datetime.now(tz=UTC)
        draft_id = compute_draft_id(
            modelo=self.modelo_id,
            period=period,
            profile_tax_id=profile.tax_id,
            schema_version=collection.schema_version,
            values=ordered_values,
        )
        _logger.debug(
            "Built Modelo 303 draft %s for profile %s period %s",
            draft_id,
            profile.tax_id,
            period,
        )
        return FilingDraft(
            draft_id=draft_id,
            modelo=self.modelo_id,
            period=period,
            profile_tax_id=profile.tax_id,
            status=FilingDraftStatus.DRAFT,
            values=ordered_values,
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
        """Evaluate a Modelo 303 formula casilla.

        Args:
            casilla: The casilla schema for the target.
            values: Previously materialised :class:`FilingValue`
                records, keyed by casilla ID.

        Returns:
            The computed :class:`FilingValue`.

        Raises:
            FilingComputationError: When the casilla id is not
                one of the known Modelo 303 formulas.
        """
        if casilla.id == "03":
            return _computed(casilla.id, _dec(values["01"]) * _RATE_4, ("01",))
        if casilla.id == "06":
            return _computed(casilla.id, _dec(values["04"]) * _RATE_10, ("04",))
        if casilla.id == "09":
            return _computed(casilla.id, _dec(values["07"]) * _RATE_21, ("07",))
        if casilla.id == "44":
            trace = ("29", "31", "33", "35", "37", "39", "40", "41", "42", "43")
            total = sum((_dec(values[k]) for k in trace), Decimal("0"))
            return _computed(casilla.id, total, trace)
        if casilla.id == "45":
            cuotas = _dec(values["03"]) + _dec(values["06"]) + _dec(values["09"])
            return _computed(casilla.id, cuotas - _dec(values["44"]), ("03", "06", "09", "44"))
        if casilla.id == "64":
            return _computed(casilla.id, _dec(values["45"]), ("45",))
        if casilla.id == "66":
            base = _dec(values["64"])
            pct = _dec(values["65"])
            return _computed(casilla.id, base * pct / Decimal("100"), ("64", "65"))
        if casilla.id == "69":
            return _computed(
                casilla.id,
                _dec(values["66"]) - _dec(values["67"]),
                ("66", "67"),
            )
        if casilla.id == "71":
            return _computed(casilla.id, _dec(values["69"]), ("69",))
        raise FilingComputationError(f"Unknown formula casilla {casilla.id!r} for Modelo 303")


def _materialise_literal(casilla: CasillaSchema, inputs: FilingInputs) -> FilingValue:
    """Build a literal/default/empty :class:`FilingValue`.

    Args:
        casilla: The casilla schema for the target.
        inputs: Raw input mapping supplied by the caller.

    Returns:
        A :class:`FilingValue` carrying the user input, the schema
        default, or an EMPTY marker.

    Raises:
        FilingComputationError: When a user-supplied value cannot
            be coerced to the casilla's declared value type.
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
    """Coerce a raw value to the casilla's declared value type."""
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
        f"Cannot use {type(raw).__name__} value on casilla {value.casilla_id!r} in a Modelo 303 formula"
    )


def _computed(casilla_id: str, value: Decimal, trace: tuple[str, ...]) -> FilingValue:
    """Build a :class:`FilingValue` for a computed Modelo 303 casilla."""
    return FilingValue(
        casilla_id=casilla_id,
        value=value,
        kind=FilingValueKind.COMPUTED,
        source=f"computed from casillas {','.join(trace)}",
        formula_trace=trace,
    )
