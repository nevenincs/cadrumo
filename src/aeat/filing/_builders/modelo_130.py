"""Modelo 130 builder — proof of concept for :mod:`aeat.filing`.

Modelo 130 is the quarterly *pago fraccionado IRPF* form filed
by Spanish autónomos in régimen de estimación directa. Its
casilla shape is small enough to exercise every
:class:`aeat.filing._schema.FilingValueKind` while remaining
hand-verifiable in unit tests.

The casilla schema is loaded from the synthetic provider in
:mod:`aeat.filing._builders._modelo_130_schema` and will be
swapped for the real casilla DB once #23 lands.
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

#: 20% advance payment rate, locked into the synthetic Modelo 130 PoC.
_PAGO_FRACCIONADO_RATE = Decimal("0.20")


class Modelo130Builder(FilingBuilder):
    """Concrete builder for Modelo 130 drafts."""

    modelo_id = "130"

    def build(
        self,
        *,
        period: str,
        profile: FilingProfile,
        inputs: FilingInputs,
        schema_provider: CasillaSchemaProvider,
    ) -> FilingDraft:
        """Build a frozen Modelo 130 draft.

        Args:
            period: Period identifier (e.g. ``"2026Q1"``).
            profile: Taxpayer profile the draft is built for.
            inputs: Mapping casilla ID → raw input value (the
                builder coerces decimals from ``int`` / ``str`` /
                :class:`Decimal`).
            schema_provider: Resolves the Modelo 130 casilla
                collection.

        Returns:
            A frozen :class:`FilingDraft` in
            :attr:`FilingDraftStatus.DRAFT` state with computed
            casillas populated. Findings are empty — the
            validator runs separately.

        Raises:
            FilingComputationError: When a required casilla is
                missing, when an input cannot be coerced, or when
                a formula's dependency is not satisfied.
        """
        collection = schema_provider.get_collection(self.modelo_id)

        values: dict[str, FilingValue] = {}
        # First pass: literal / default / empty values from inputs.
        for casilla in collection.all():
            if casilla.formula_inputs:
                continue
            values[casilla.id] = self._materialise_literal(casilla, inputs)

        # Second pass: computed casillas in dependency order. The
        # synthetic Modelo 130 schema is small and acyclic so a
        # bounded fixed-point loop is enough; production builders
        # will use the formula AST from #9.
        pending = [c for c in collection.all() if c.formula_inputs]
        max_passes = len(pending) + 1
        for _ in range(max_passes):
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

        ordered_values = tuple(values[casilla.id] for casilla in collection.all())
        now = datetime.now(tz=UTC)
        draft_id = compute_draft_id(
            modelo=self.modelo_id,
            period=period,
            profile_tax_id=profile.tax_id,
            schema_version=collection.schema_version,
            values=ordered_values,
        )
        _logger.debug(
            "Built Modelo 130 draft %s for profile %s period %s",
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

    def _materialise_literal(
        self,
        casilla: CasillaSchema,
        inputs: FilingInputs,
    ) -> FilingValue:
        """Build a literal/default/empty :class:`FilingValue`."""
        raw = inputs.get(casilla.id)
        if raw is not None:
            value = self._coerce(casilla, raw)
            return FilingValue(
                casilla_id=casilla.id,
                value=value,
                kind=FilingValueKind.LITERAL,
                source="user-supplied",
                formula_trace=None,
            )
        if casilla.default is not None:
            value = self._coerce(casilla, casilla.default)
            return FilingValue(
                casilla_id=casilla.id,
                value=value,
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

    def _coerce(self, casilla: CasillaSchema, raw: object) -> FilingScalar:
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
            if casilla.value_type == "bool":
                if isinstance(raw, bool):
                    return raw
                raise TypeError(f"unsupported bool input: {type(raw).__name__}")
            raise TypeError(f"unknown value_type {casilla.value_type!r}")
        except (TypeError, ValueError) as exc:
            raise FilingComputationError(f"Cannot coerce input for casilla {casilla.id!r}: {exc}") from exc

    def _compute(
        self,
        casilla: CasillaSchema,
        values: dict[str, FilingValue],
    ) -> FilingValue:
        """Compute one Modelo 130 formula casilla."""
        if casilla.id == "03":
            ingresos = _as_decimal(values["01"].value)
            gastos = _as_decimal(values["02"].value)
            return _computed_value(casilla.id, ingresos - gastos, ("01", "02"))
        if casilla.id == "04":
            rendimiento = _as_decimal(values["03"].value)
            return _computed_value(casilla.id, rendimiento * _PAGO_FRACCIONADO_RATE, ("03",))
        if casilla.id == "07":
            bruto = _as_decimal(values["04"].value)
            retenciones = _as_decimal(values["05"].value)
            anteriores = _as_decimal(values["06"].value)
            resultado = bruto - retenciones - anteriores
            if resultado < 0:
                resultado = Decimal("0")
            return _computed_value(casilla.id, resultado, ("04", "05", "06"))
        raise FilingComputationError(f"Unknown formula casilla {casilla.id!r} for Modelo 130")


def _as_decimal(value: FilingScalar) -> Decimal:
    """Return ``value`` as a :class:`Decimal`, treating None as zero.

    Raises:
        FilingComputationError: When the value is not a numeric
            type the builder knows how to coerce.
    """
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise FilingComputationError("Boolean values cannot participate in formulas")
    if isinstance(value, int):
        return Decimal(value)
    raise FilingComputationError(f"Cannot use {type(value).__name__} value in a Modelo 130 formula")


def _computed_value(casilla_id: str, value: Decimal, trace: tuple[str, ...]) -> FilingValue:
    """Helper that builds a computed :class:`FilingValue`."""
    return FilingValue(
        casilla_id=casilla_id,
        value=value,
        kind=FilingValueKind.COMPUTED,
        source=f"computed from casillas {','.join(trace)}",
        formula_trace=trace,
    )
