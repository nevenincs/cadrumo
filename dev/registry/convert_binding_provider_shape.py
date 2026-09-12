"""Rewrite authored registry binding rows from the legacy pair to the provider shape.

A binding row used to declare an open ``source`` token beside an untyped
``selector`` mapping. :class:`~cadrumo.domain.calculations.registry.schema.BindingDefinition`
now requires a closed ``provider`` member discriminated on ``kind`` and an
explicit ``value`` contract, and refuses the legacy pair outright. The authored
corpus is the last holder of the old shape, so this tool performs that rewrite
in place, one modelo at a time.

Provider construction. ``kind`` is the old ``source`` token and every selector
field is carried across verbatim, with three families whose legacy fields named
an absolute or loose coordinate that the closed temporal union replaces:

* ``previous_filing`` -- the six loose period fields (``filing_year_delta``,
  ``max_year_delta``, ``period``, ``source_periods``,
  ``source_period_offset_from_target``, ``prior_quarter_expanding_span``) fold
  into one ``temporal`` member through
  :func:`~cadrumo.domain.calculations.registry.binding_temporal.temporal_selector_from_previous_modelo_fields`,
  which refuses a combination the union cannot express rather than dropping an
  axis. A row already carrying ``temporal`` passes through untouched.
* ``inventory`` -- ``filing_year = 2025`` was an absolute year standing in for
  "the target's own context"; it becomes ``temporal = { kind =
  "same_target_context" }``. Any other year is refused, never reinterpreted.
* ``m303_regimen_simplificado_annual_summary`` -- ``source_period`` names a
  period the taxpayer has already filed in the target's own year, which is
  exactly ``filed_current_period``.

Value derivation. The ``value`` contract is derived, never invented. Five rules
are tried in order and the one that fired is recorded per row in the report:

1. ``rows`` -- an ``aggregation.op = "rows"`` row carries a row family, so the
   contract is the ``row_set`` channel grouped by
   :data:`~cadrumo.core.aggregation.ROW_SET_GROUPING_FOR_BINDING_SOURCE` for the
   row's kind. A kind with no grouping entry is refused.
2. ``selector_data_type`` -- the selector's own ``data_type`` maps onto the
   binding data type and its one permitted channel.
3. ``typed_enum`` -- a top-level ``typed_enum`` names a closed substrate enum,
   so the contract is the ``enum`` channel bridging it.
4. ``consumer_data_type`` -- the row's declared type is read off a typed
   consumer, in a fixed widening order recorded as a distinct report bucket:
   the consuming casilla in the same revision, then in any revision of the same
   modelo (editions inherit bindings by identifier), then the casilla a
   consuming formula targets, then a consuming export field, then -- for a
   copy-shaped provider naming a source coordinate -- the source casilla the
   value is copied from.
5. otherwise the row is refused: the file it sits in is left untouched and the
   row is listed in the report with its id and the reason. Nothing is guessed.

Every rewritten row is constructed as a ``BindingDefinition`` before anything is
written, and the rewritten file is re-parsed and every row re-validated; a
single failure leaves the whole file untouched.

Rewrite technique. Like ``rename_formula_binding_identifiers``, the rewrite is
textual so that comments, ordering, and hand-authored formatting survive: the
structured parse decides *what* each row becomes, and the edit replaces only the
``source``/``selector``/``typed_enum`` lines of that row's own key region.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_MODELOS_ROOT = REPO_ROOT / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos"

sys.path.insert(0, str(REPO_ROOT / "src"))

from cadrumo.core.aggregation import (  # noqa: E402
    ROW_SET_GROUPING_FOR_BINDING_SOURCE,
    BindingSourceKind,
)
from cadrumo.domain.calculations.registry.binding_temporal import (  # noqa: E402
    temporal_selector_from_previous_modelo_fields,
)
from cadrumo.domain.calculations.registry.binding_value_contract import (  # noqa: E402
    CHANNEL_FOR_BINDING_DATA_TYPE,
    BindingDataType,
)
from cadrumo.domain.calculations.registry.schema import BindingDefinition  # noqa: E402

__all__ = ["ConversionReport", "convert_modelo", "main"]


LEGACY_PREVIOUS_FILING_TEMPORAL_FIELDS: tuple[str, ...] = (
    "filing_year_delta",
    "max_year_delta",
    "period",
    "source_periods",
    "source_period_offset_from_target",
    "prior_quarter_expanding_span",
)
"""The loose previous-filing period fields the closed temporal union replaces."""

INVENTORY_LEGACY_FILING_YEAR = 2025
"""The one absolute ``filing_year`` the inventory selector carried.

It stood for "the target's own filing context" in a corpus whose only inventory
rows target that year. Any other value is a coordinate this tool cannot read as
intent, so it is refused.
"""

BINDING_DATA_TYPE_FOR_CASILLA_DATA_TYPE: dict[str, BindingDataType] = {
    "money": BindingDataType.MONEY,
    "decimal": BindingDataType.DECIMAL,
    "ratio": BindingDataType.MONEY,
    "integer": BindingDataType.INTEGER,
    "year": BindingDataType.INTEGER,
    "boolean": BindingDataType.BOOLEAN,
    "date": BindingDataType.DATE,
    "text": BindingDataType.TEXT,
    "nif": BindingDataType.TEXT,
    "nif_iva": BindingDataType.TEXT,
    "name": BindingDataType.TEXT,
    "iban": BindingDataType.TEXT,
    "bic": BindingDataType.TEXT,
    "period_code": BindingDataType.TEXT,
    "country_code": BindingDataType.TEXT,
    "ccaa_code": BindingDataType.TEXT,
    "province_code": BindingDataType.TEXT,
    "postal_code": BindingDataType.TEXT,
    "municipality_code": BindingDataType.TEXT,
}
"""Casilla data type to binding data type.

The casilla vocabulary is finer than the binding one on two axes and the
collapse is deliberate, not lossy guessing: every catalogued-string type
(``nif``, ``iban``, ``country_code`` and friends) is carried on the ``text``
channel, and every non-integral number is carried on the ``decimal`` channel.
A casilla ``decimal`` is a non-monetary decimal quantity and maps to the
binding ``decimal`` data type of the same name; ``ratio`` has no binding
counterpart and is carried as ``money``. The narrower legal quantity stays
declared on the casilla, which is the contract that rounds and signs it.
"""

_COPY_SOURCE_CASILLA_KINDS: frozenset[str] = frozenset(
    {
        BindingSourceKind.PREVIOUS_FILING.value,
        BindingSourceKind.RELATION_PREFILL.value,
    },
)
"""Providers whose value is a direct carry of one named source casilla."""

_PROFILE_KEY_DATA_TYPES: dict[str, str] = {
    # These derived family facts are deliberately not declared as casilla
    # consumers.  Their owning profile code documents the scalar they inject
    # into the calculation index, so the migration records that contract
    # explicitly instead of leaving the old rows untyped.
    "renta_family.descendientes_count": "integer",
    "renta_family.descendientes_guarderia_2024": "integer",
    "renta_family.gastos_guarderia_reales_2024": "money",
}
"""Closed profile-key types for profile facts with no typed registry consumer."""

_PROFILE_FIELD_DATA_TYPES: dict[str, str] = {
    # These profile-model fields are calculation inputs rather than casilla
    # consumers.  Their owning declarations describe monetary Decimal facts;
    # keep the list closed so a new field cannot acquire a type by accident.
    "incn_prior_12_months": "money",
    "sal_reserva_especial_dotada": "money",
    "sal_capital_social": "money",
}
"""Closed profile-model field types needed by legacy binding rows."""

_SCALAR_MONEY_SOURCES: frozenset[str] = frozenset(
    {
        "ledger_renta_income_aggregation",
        "ledger_irnr_income_aggregation",
        "ledger_iva_aggregation",
        "bienes_inversion_regularizacion",
        "prorrata_regularizacion",
        "iva_compensation_annual_partition",
        "m303_regimen_simplificado_annual_summary",
    },
)
"""Provider families whose residual authored scalar is always a monetary amount.

The claim is read off each family's owning resolver, not off the rows. A source
resolver returns ``CalculationSourceResolution``, which carries scalars on three
disjoint typed channels: ``binding_values`` (``Mapping[BindingId, Decimal]``),
``enum_binding_values`` (``str``) and ``date_binding_values`` (``date``). A
family whose resolver populates only ``binding_values`` can therefore produce no
scalar but a ``Decimal`` amount, which is exactly the ``money`` binding data
type and its ``decimal`` channel (:data:`CHANNEL_FOR_BINDING_DATA_TYPE`); the
finer legal quantity stays declared on the consuming casilla. Each family below
is listed with the resolver whose sole scalar channel is ``binding_values``:

* ``ledger_renta_income_aggregation`` -- ``LedgerRentaIncomeAggregationSourceResolver``
* ``ledger_irnr_income_aggregation`` -- ``LedgerIrnrIncomeAggregationSourceResolver``
* ``ledger_iva_aggregation`` -- ``LedgerIvaAggregationSourceResolver``
  (all three in ``cadrumo.application.aggregation.modelo_bindings``)
* ``bienes_inversion_regularizacion`` -- ``BienesInversionRegularizacionSourceResolver``
* ``prorrata_regularizacion`` -- ``ProrrataRegularizacionSourceResolver``
* ``iva_compensation_annual_partition`` -- ``IvaCompensationAnnualPartitionSourceResolver``
* ``m303_regimen_simplificado_annual_summary`` -- ``M303RegimenSimplificadoAnnualSummarySourceResolver``
  (each in its like-named ``cadrumo.application.calculations`` module)

A family whose resolver also emits an enum or date scalar does not belong here:
without that single-channel evidence the row must be refused instead.
"""

_INVOICE_SCALAR_DATA_TYPES: dict[str, str] = {
    "operator_count": "integer",
    "base_sum": "money",
    "invoice_total_sum": "money",
    "rectified_base_delta_sum": "money",
}
"""Closed scalar type map for invoice facts without a casilla consumer."""

_REVISION_KEY = r'(?:"(?P<quoted>[^"]+)"|(?P<bare>[A-Za-z0-9_-]+))'
"""A revision table key, which the corpus writes both quoted and bare."""

_BINDINGS_HEADER = re.compile(r"^\[\[revisions\." + _REVISION_KEY + r"\.bindings\]\]\s*$")
_SUBTABLE_HEADER = re.compile(r"^\[\[?revisions\." + _REVISION_KEY + r"\.bindings\.(?P<name>[A-Za-z_][\w.]*)\]\]?\s*$")
_KEY_LINE = re.compile(r"^(?P<key>[A-Za-z_][\w]*)\s*=")


class ConversionRefusalError(Exception):
    """One binding row could not be converted without guessing."""

    def __init__(self, binding_id: str, reason: str) -> None:
        """Record the refused binding id and why it was refused."""
        super().__init__(f"{binding_id}: {reason}")
        self.binding_id = binding_id
        self.reason = reason


@dataclass
class ConversionReport:
    """Per-run counts, per-rule row tallies, and the refused rows."""

    modelos: list[str] = field(default_factory=list)
    files_rewritten: list[str] = field(default_factory=list)
    files_skipped: list[str] = field(default_factory=list)
    rows_converted: int = 0
    value_rule_counts: Counter[str] = field(default_factory=Counter)
    refusals: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """Return the JSON-serialisable form of this report."""
        return {
            "modelos": sorted(self.modelos),
            "rows_converted": self.rows_converted,
            "value_rule_counts": dict(sorted(self.value_rule_counts.items())),
            "files_rewritten": sorted(self.files_rewritten),
            "files_skipped": sorted(self.files_skipped),
            "refusals": self.refusals,
        }


def _toml_value(value: object) -> str:
    """Render one Python value as its TOML literal."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        return _toml_inline_table(value)
    raise TypeError(f"no TOML rendering for {type(value).__name__}")


def _toml_inline_table(table: dict[str, object]) -> str:
    """Render a mapping as a single-line TOML inline table."""
    body = ", ".join(f"{key} = {_toml_value(value)}" for key, value in table.items())
    return "{ " + body + " }"


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _iter_family_rows(revision_dir: Path, family: str) -> list[dict[str, Any]]:
    """Return every declared row of one family directory, across fragment files and revision keys."""
    family_dir = revision_dir / family
    if not family_dir.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for toml_path in sorted(family_dir.glob("*.toml")):
        data = _load_toml(toml_path)
        for revision_table in data.get("revisions", {}).values():
            if not isinstance(revision_table, dict):
                continue
            entries = revision_table.get(family)
            if isinstance(entries, list):
                rows.extend(entry for entry in entries if isinstance(entry, dict))
    return rows


def _walk_bindings(node: object, keys: tuple[str, ...]) -> list[tuple[str, str | None]]:
    """Collect ``(binding id, sibling data_type)`` pairs from a nested declaration."""
    found: list[tuple[str, str | None]] = []
    if isinstance(node, dict):
        data_type = node.get("data_type")
        for key in keys:
            value = node.get(key)
            if isinstance(value, str):
                found.append((value, data_type if isinstance(data_type, str) else None))
        for value in node.values():
            found.extend(_walk_bindings(value, keys))
    elif isinstance(node, list):
        for item in node:
            found.extend(_walk_bindings(item, keys))
    return found


@dataclass(frozen=True)
class CasillaTypeEvidence:
    """Every data type the typed consumers of one binding id state for it.

    Evidence is accumulated, never resolved at collection time. A consumer that
    omits ``data_type`` and two consumers that disagree are both recorded as
    they are authored, because collapsing either one at collection time turns a
    contradiction into a silent choice: the earlier collector defaulted an
    omitted type to money and let the first revision directory win. The refusal
    is raised per row from :meth:`ConsumerIndex.lookup`, so one contradicted
    binding is listed in the report and leaves its file untouched rather than
    aborting the whole modelo.
    """

    declared: frozenset[str] = frozenset()
    omitted_by: frozenset[str] = frozenset()
    casilla_ids: frozenset[str] = frozenset()

    def __bool__(self) -> bool:
        """Return whether any consumer spoke about this binding id at all."""
        return bool(self.declared or self.omitted_by)

    def merged_with(self, other: CasillaTypeEvidence) -> CasillaTypeEvidence:
        """Return the union of this evidence and one further consumer's."""
        return CasillaTypeEvidence(
            declared=self.declared | other.declared,
            omitted_by=self.omitted_by | other.omitted_by,
            casilla_ids=self.casilla_ids | other.casilla_ids,
        )

    def resolve(self, binding_id: str) -> str:
        """Return the one data type every consumer agrees on.

        Raises:
            ConversionRefusalError: A consumer declares no data type, or the
                consumers name more than one. Neither is derivable.
        """
        citation = ", ".join(sorted(self.casilla_ids)) or "?"
        if self.omitted_by:
            omitted = ", ".join(sorted(self.omitted_by))
            raise ConversionRefusalError(binding_id, f"consuming casilla {omitted} declares no data_type")
        if len(self.declared) > 1:
            types = ", ".join(sorted(self.declared))
            raise ConversionRefusalError(
                binding_id,
                f"consuming casillas disagree on data_type ({types}); casillas: {citation}",
            )
        return next(iter(self.declared))


def _declared_evidence(data_type: str, casilla_id: str) -> CasillaTypeEvidence:
    """Return evidence for one consumer that declares a data type."""
    return CasillaTypeEvidence(declared=frozenset({data_type}), casilla_ids=frozenset({casilla_id}))


@dataclass
class ConsumerIndex:
    """Declared data types reachable from every typed consumer of a binding id."""

    revision_casilla: dict[str, CasillaTypeEvidence] = field(default_factory=dict)
    modelo_casilla: dict[str, CasillaTypeEvidence] = field(default_factory=dict)
    formula_target: dict[str, CasillaTypeEvidence] = field(default_factory=dict)
    export_field: dict[str, CasillaTypeEvidence] = field(default_factory=dict)
    source_casilla: dict[str, CasillaTypeEvidence] = field(default_factory=dict)

    def lookup(self, binding_id: str) -> tuple[str, str] | None:
        """Return ``(rule name, casilla data type)`` from the first consumer that declares one.

        Raises:
            ConversionRefusalError: The first consumer rule carrying evidence for
                this binding id names more than one data type, or names a casilla
                that declares none.
        """
        for rule, table in (
            ("consumer_revision_casilla", self.revision_casilla),
            ("consumer_modelo_casilla", self.modelo_casilla),
            ("consumer_formula_target_casilla", self.formula_target),
            ("consumer_export_field", self.export_field),
            ("consumer_source_casilla", self.source_casilla),
        ):
            evidence = table.get(binding_id)
            if evidence:
                return rule, evidence.resolve(binding_id)
        return None


def _casilla_evidence(casilla: dict[str, Any], fallback_id: str) -> CasillaTypeEvidence:
    """Return one casilla's own data-type evidence, declared or omitted."""
    identifier = casilla.get("id")
    casilla_id = identifier if isinstance(identifier, str) else fallback_id
    data_type = casilla.get("data_type")
    if isinstance(data_type, str):
        return _declared_evidence(data_type, casilla_id)
    return CasillaTypeEvidence(omitted_by=frozenset({casilla_id}), casilla_ids=frozenset({casilla_id}))


def _casilla_data_types(revision_dirs: list[Path]) -> dict[str, CasillaTypeEvidence]:
    """Map each binding id named by a casilla to every data type its casillas declare."""
    table: dict[str, CasillaTypeEvidence] = {}
    for revision_dir in revision_dirs:
        for casilla in _iter_family_rows(revision_dir, "casillas"):
            evidence = _casilla_evidence(casilla, revision_dir.name)
            named: list[str] = []
            primary = casilla.get("binding")
            if isinstance(primary, str):
                named.append(primary)
            named.extend(
                alternate for alternate in casilla.get("alternate_bindings") or () if isinstance(alternate, str)
            )
            for binding_id in named:
                table[binding_id] = table.get(binding_id, CasillaTypeEvidence()).merged_with(evidence)
    return table


def _casilla_ids_to_data_type(revision_dirs: list[Path]) -> dict[str, CasillaTypeEvidence]:
    """Map each declared casilla id to every data type its declarations state."""
    table: dict[str, CasillaTypeEvidence] = {}
    for revision_dir in revision_dirs:
        for casilla in _iter_family_rows(revision_dir, "casillas"):
            identifier = casilla.get("id")
            if not isinstance(identifier, str):
                continue
            evidence = _casilla_evidence(casilla, revision_dir.name)
            table[identifier] = table.get(identifier, CasillaTypeEvidence()).merged_with(evidence)
    return table


def _source_casilla_data_types(
    binding_rows: list[dict[str, Any]],
    casilla_data_type_by_modelo: dict[str, dict[str, CasillaTypeEvidence]],
) -> dict[str, CasillaTypeEvidence]:
    """Map each copy-shaped binding id to the type evidence of the casillas it copies."""
    table: dict[str, CasillaTypeEvidence] = {}
    for row in binding_rows:
        if row.get("source") not in _COPY_SOURCE_CASILLA_KINDS:
            continue
        selector = row.get("selector")
        if not isinstance(selector, dict):
            continue
        source_modelo = selector.get("source_modelo")
        if not isinstance(source_modelo, str):
            continue
        source_ids: list[str] = []
        singular = selector.get("source_casilla_id")
        if isinstance(singular, str):
            source_ids.append(singular)
        for plural in selector.get("source_casilla_ids") or ():
            if isinstance(plural, str):
                source_ids.append(plural)
        by_id = casilla_data_type_by_modelo.get(source_modelo, {})
        merged = CasillaTypeEvidence()
        for source_id in source_ids:
            evidence = by_id.get(source_id)
            if evidence is not None:
                merged = merged.merged_with(evidence)
        identifier = row.get("id")
        # Sources that disagree are a contradiction, not a choice: the merged
        # evidence carries both types and the lookup refuses the row.
        if merged and isinstance(identifier, str):
            table[identifier] = merged
    return table


def _build_consumer_index(
    modelo_dir: Path,
    revision_dir: Path,
    casilla_data_type_by_modelo: dict[str, dict[str, CasillaTypeEvidence]],
) -> ConsumerIndex:
    """Index every typed consumer that can establish a binding's declared data type."""
    modelo_revisions = sorted(p for p in (modelo_dir / "revisions").iterdir() if p.is_dir())
    index = ConsumerIndex(
        revision_casilla=_casilla_data_types([revision_dir]),
        modelo_casilla=_casilla_data_types(modelo_revisions),
    )
    casilla_types = _casilla_ids_to_data_type(modelo_revisions)
    for each_revision in modelo_revisions:
        for formula in _iter_family_rows(each_revision, "formulas"):
            target = formula.get("target_casilla_id")
            evidence = casilla_types.get(target) if isinstance(target, str) else None
            if not evidence:
                continue
            for binding_id, _ in _walk_bindings(formula.get("expression"), ("binding", "date_binding")):
                index.formula_target.setdefault(binding_id, evidence)
        for layout in _iter_family_rows(each_revision, "export_layouts"):
            for binding_id, data_type in _walk_bindings(layout, ("binding",)):
                if data_type:
                    index.export_field.setdefault(binding_id, _declared_evidence(data_type, binding_id))
    binding_rows = _iter_family_rows(revision_dir, "bindings")
    index.source_casilla = _source_casilla_data_types(binding_rows, casilla_data_type_by_modelo)
    return index


def _casilla_data_type_by_modelo() -> dict[str, dict[str, CasillaTypeEvidence]]:
    """Map every modelo number to its declared casilla id to type evidence table."""
    table: dict[str, dict[str, CasillaTypeEvidence]] = {}
    for modelo_dir in sorted(p for p in REGISTRY_MODELOS_ROOT.iterdir() if p.is_dir()):
        revisions = modelo_dir / "revisions"
        if not revisions.is_dir():
            continue
        revision_dirs = sorted(p for p in revisions.iterdir() if p.is_dir())
        table[modelo_dir.name] = _casilla_ids_to_data_type(revision_dirs)
    return table


def build_provider(row: dict[str, Any]) -> dict[str, Any]:
    """Return the provider table for one legacy binding row.

    Raises:
        ConversionRefusalError: If a legacy temporal field carries a coordinate the
            closed temporal union cannot express.
    """
    binding_id = str(row.get("id"))
    source = row.get("source")
    if not isinstance(source, str):
        raise ConversionRefusalError(binding_id, "row declares no source token")
    selector = row.get("selector")
    fields: dict[str, Any] = dict(selector) if isinstance(selector, dict) else {}
    provider: dict[str, Any] = {"kind": source}

    if source == BindingSourceKind.PREVIOUS_FILING.value:
        legacy = {key: fields.pop(key) for key in LEGACY_PREVIOUS_FILING_TEMPORAL_FIELDS if key in fields}
        if legacy:
            if "temporal" in fields:
                raise ConversionRefusalError(binding_id, "row carries both a temporal member and legacy period fields")
            periods = legacy.get("source_periods")
            try:
                member = temporal_selector_from_previous_modelo_fields(
                    filing_year_delta=int(legacy.get("filing_year_delta", 0)),
                    max_year_delta=legacy.get("max_year_delta"),
                    period=legacy.get("period"),
                    source_periods=tuple(periods) if isinstance(periods, list) else (),
                    source_period_offset_from_target=legacy.get("source_period_offset_from_target"),
                    prior_quarter_expanding_span=bool(legacy.get("prior_quarter_expanding_span", False)),
                )
            except Exception as exc:
                raise ConversionRefusalError(binding_id, f"legacy temporal fields are not expressible: {exc}") from exc
            dumped = member.model_dump(mode="json")
            # TOML has no null literal, and every optional temporal field is
            # absent-by-default, so an unset axis is dropped rather than spelled.
            fields["temporal"] = {key: item for key, item in dumped.items() if item is not None}
    elif source == BindingSourceKind.INVENTORY.value and "filing_year" in fields:
        filing_year = fields.pop("filing_year")
        if filing_year != INVENTORY_LEGACY_FILING_YEAR:
            raise ConversionRefusalError(binding_id, f"inventory filing_year {filing_year!r} is not a readable intent")
        fields["temporal"] = {"kind": "same_target_context"}
    elif source == BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY.value and "source_period" in fields:
        fields["temporal"] = {"kind": "filed_current_period", "source_period": fields.pop("source_period")}

    provider.update(fields)
    return provider


def build_value(row: dict[str, Any], consumers: ConsumerIndex) -> tuple[dict[str, Any], str]:
    """Return ``(value contract table, rule name)`` for one legacy binding row.

    Raises:
        ConversionRefusalError: If no rule establishes the row's value contract.
    """
    binding_id = str(row.get("id"))
    source = str(row.get("source"))
    raw_selector = row.get("selector")
    selector: dict[str, Any] = dict(raw_selector) if isinstance(raw_selector, dict) else {}
    raw_aggregation = row.get("aggregation")
    aggregation: dict[str, Any] = dict(raw_aggregation) if isinstance(raw_aggregation, dict) else {}

    # Rule 0. An author who already wrote the contract has stated it with more
    # authority than any derivation: a hand-authored ``value`` wins outright.
    # It is still validated with the rest of the row, so an authored
    # contradiction is refused rather than trusted.
    authored = row.get("value")
    if isinstance(authored, dict):
        contract = dict(authored)
        # A legacy authored contract may still spell the retired ``rows`` data
        # type, which conflated the element type with the transport. Re-derive
        # the element type rather than carry the conflation forward.
        if contract.get("data_type") != "rows":
            return contract, "authored_value"
        element, rule = _scalar_contract(binding_id, source, selector, row, consumers)
        return _row_set_contract(binding_id, source, str(element["data_type"])), f"authored_value_row_set:{rule}"

    if aggregation.get("op") == "rows":
        element, rule = _scalar_contract(binding_id, source, selector, row, consumers)
        return _row_set_contract(binding_id, source, str(element["data_type"])), f"rows_aggregation:{rule}"

    return _scalar_contract(binding_id, source, selector, row, consumers)


def _row_set_contract(binding_id: str, source: str, element_data_type: str) -> dict[str, Any]:
    """Return the row-set value contract for one row-producing binding.

    ``channel = "row_set"`` states that the binding yields a row collection and
    ``data_type`` is then the *per-row element* type. Whether the collection
    also carries a ``row_grouping`` depends on which of the two row channels
    assembles it: a family enrolled in
    :data:`~cadrumo.core.aggregation.ROW_SET_GROUPING_FOR_BINDING_SOURCE` is
    assembled by the grouped row-set assembler and names its grouping axis;
    the remaining row-producing families emit their rows provider-natively and
    declare no grouping, because there is no grouped assembler to name.

    Raises:
        ConversionRefusalError: The source is unknown or yields no derivable
            element type.
    """
    try:
        kind = BindingSourceKind(source)
    except ValueError as exc:
        raise ConversionRefusalError(binding_id, f"unknown binding source {source!r}") from exc
    if element_data_type == "rows":
        raise ConversionRefusalError(binding_id, "row-set element data type is not derivable")
    contract: dict[str, Any] = {"data_type": element_data_type, "channel": "row_set"}
    grouping = ROW_SET_GROUPING_FOR_BINDING_SOURCE.get(kind)
    if grouping is not None:
        contract["row_grouping"] = grouping.value
    return contract


def _scalar_contract(
    binding_id: str,
    source: str,
    selector: dict[str, Any],
    row: dict[str, Any],
    consumers: ConsumerIndex,
) -> tuple[dict[str, Any], str]:
    """Return ``(scalar value contract, rule name)`` for one legacy binding row.

    A row-producing binding reaches here too: its scalar contract is the
    per-row element type its row-set contract is then built from.

    Raises:
        ConversionRefusalError: If no rule establishes the row's element type.
    """
    declared = selector.get("data_type")
    if isinstance(declared, str):
        return _contract_for_casilla_data_type(binding_id, declared), "selector_data_type"

    typed_enum = row.get("typed_enum")
    if isinstance(typed_enum, str):
        return {"data_type": "enum", "channel": "enum", "typed_enum": typed_enum}, "typed_enum"

    profile_key = selector.get("profile_key")
    if isinstance(profile_key, str):
        profile_data_type = _PROFILE_KEY_DATA_TYPES.get(profile_key)
        if profile_data_type is not None:
            return _contract_for_casilla_data_type(binding_id, profile_data_type), "profile_key_data_type"

    profile_field = selector.get("field")
    if source == BindingSourceKind.PROFILE.value and isinstance(profile_field, str):
        profile_data_type = _PROFILE_FIELD_DATA_TYPES.get(profile_field)
        if profile_data_type is not None:
            return _contract_for_casilla_data_type(binding_id, profile_data_type), "profile_field_data_type"

    resolved = consumers.lookup(binding_id)
    if resolved is not None:
        rule, data_type = resolved
        return _contract_for_casilla_data_type(binding_id, data_type), rule

    if source in _SCALAR_MONEY_SOURCES:
        return {"data_type": "money", "channel": "decimal"}, "source_scalar_data_type"

    if source in {"payable_invoice", "collectible_invoice", "m347_third_party_operation"}:
        fact = selector.get("fact")
        invoice_data_type = _INVOICE_SCALAR_DATA_TYPES.get(fact) if isinstance(fact, str) else None
        if invoice_data_type is not None:
            return _contract_for_casilla_data_type(binding_id, invoice_data_type), "invoice_fact_data_type"

    # The M347/M349 row-field vocabulary is closed by InvoiceProvider.  Older
    # rows omit the redundant export type, but the field itself still gives an
    # explicit scalar contract for each emitted row value.
    if source in {"payable_invoice", "collectible_invoice", "m347_third_party_operation"}:
        row_field = selector.get("row_field")
        if isinstance(row_field, str):
            if row_field in {"party_tax_id", "country_code", "party_legal_name", "clave", "rectified_period"}:
                return {"data_type": "text", "channel": "text"}, "invoice_row_field"
            if row_field == "rectified_year":
                return {"data_type": "integer", "channel": "integer"}, "invoice_row_field"
            if row_field in {
                "base_imponible",
                "importe_total",
                "importe_q1",
                "importe_q2",
                "importe_q3",
                "importe_q4",
                "rectified_base_previous",
            }:
                return {"data_type": "money", "channel": "decimal"}, "invoice_row_field"

    raise ConversionRefusalError(binding_id, "no selector data_type, typed_enum, or typed consumer")


def _contract_for_casilla_data_type(binding_id: str, casilla_data_type: str) -> dict[str, Any]:
    binding_data_type = BINDING_DATA_TYPE_FOR_CASILLA_DATA_TYPE.get(casilla_data_type)
    if binding_data_type is None:
        raise ConversionRefusalError(binding_id, f"casilla data_type {casilla_data_type!r} has no binding data type")
    return {
        "data_type": binding_data_type.value,
        "channel": CHANNEL_FOR_BINDING_DATA_TYPE[binding_data_type].value,
    }


def _as_tuples(value: object) -> object:
    """Return ``value`` with every list turned into a tuple, recursively.

    Registry models validate under ``strict=True``, so a TOML array (which
    ``tomllib`` yields as a list) has to arrive as a tuple; the production
    loader performs the same coercion before construction.
    """
    if isinstance(value, list):
        return tuple(_as_tuples(item) for item in value)
    if isinstance(value, dict):
        return {key: _as_tuples(item) for key, item in value.items()}
    return value


def _validated_row(row: dict[str, Any], provider: dict[str, Any], value: dict[str, Any]) -> None:
    """Construct the row as a ``BindingDefinition``, raising on any refusal."""
    candidate = {key: item for key, item in row.items() if key not in {"source", "selector", "typed_enum"}}
    candidate["provider"] = provider
    candidate["value"] = value
    candidate = {key: _as_tuples(item) for key, item in candidate.items()}
    try:
        BindingDefinition.model_validate(candidate)
    except Exception as exc:
        raise ConversionRefusalError(str(row.get("id")), f"rewritten row does not validate: {exc}") from exc


@dataclass
class _Block:
    """One ``[[...bindings]]`` array element located in the file text."""

    revision: str
    header_index: int
    key_region_end: int
    subtable_spans: list[tuple[str, int, int]]


def _locate_blocks(lines: list[str]) -> list[_Block]:
    """Return every binding array element in document order with its line spans."""
    blocks: list[_Block] = []
    index = 0
    while index < len(lines):
        header = _BINDINGS_HEADER.match(lines[index])
        if header is None:
            index += 1
            continue
        revision = header.group("quoted") or header.group("bare")
        cursor = index + 1
        while cursor < len(lines) and not lines[cursor].lstrip().startswith("["):
            cursor += 1
        key_region_end = cursor
        subtables: list[tuple[str, int, int]] = []
        while cursor < len(lines):
            sub = _SUBTABLE_HEADER.match(lines[cursor])
            if sub is None:
                break
            start = cursor
            cursor += 1
            while cursor < len(lines) and not lines[cursor].lstrip().startswith("["):
                cursor += 1
            subtables.append((sub.group("name"), start, cursor))
        blocks.append(_Block(revision, index, key_region_end, subtables))
        index = cursor if cursor > index else index + 1
    return blocks


def _rewrite_block(
    lines: list[str],
    block: _Block,
    provider: dict[str, Any],
    value: dict[str, Any],
    line_ending: str,
) -> list[str]:
    """Return ``lines`` with one block's legacy keys replaced by provider and value."""
    provider_line = f"provider = {_toml_inline_table(provider)}{line_ending}"
    value_line = f"value = {_toml_inline_table(value)}{line_ending}"
    rewritten = list(lines)
    dropped_subtables = [span for span in block.subtable_spans if span[0] in {"selector", "typed_enum", "value"}]
    for _, start, end in sorted(dropped_subtables, key=lambda span: span[1], reverse=True):
        del rewritten[start:end]
    region = rewritten[block.header_index + 1 : block.key_region_end]
    new_region: list[str] = []
    inserted = False
    for line in region:
        match = _KEY_LINE.match(line)
        key = match.group("key") if match else None
        if key == "source":
            new_region.extend((provider_line, value_line))
            inserted = True
            continue
        if key in {"selector", "typed_enum", "value"}:
            continue
        new_region.append(line)
    if not inserted:
        new_region = [provider_line, value_line, *new_region]
    rewritten[block.header_index + 1 : block.key_region_end] = new_region
    return rewritten


def convert_file(
    path: Path,
    consumers: ConsumerIndex,
    report: ConversionReport,
    *,
    apply: bool,
) -> None:
    """Convert every legacy row in one bindings fragment, or leave the file untouched."""
    original = path.read_text(encoding="utf-8", newline="")
    line_ending = "\r\n" if "\r\n" in original else "\n"
    data = tomllib.loads(original)
    rows_by_revision: dict[str, list[dict[str, Any]]] = {}
    for revision, revision_table in data.get("revisions", {}).items():
        if isinstance(revision_table, dict) and isinstance(revision_table.get("bindings"), list):
            rows_by_revision[revision] = [row for row in revision_table["bindings"] if isinstance(row, dict)]
    if not rows_by_revision:
        return

    lines = original.splitlines(keepends=True)
    blocks = _locate_blocks(lines)
    seen: Counter[str] = Counter()
    planned: list[tuple[_Block, dict[str, Any], dict[str, Any]]] = []
    rule_counts: Counter[str] = Counter()
    refusals: list[dict[str, str]] = []

    for block in blocks:
        ordinal = seen[block.revision]
        seen[block.revision] += 1
        rows = rows_by_revision.get(block.revision, [])
        if ordinal >= len(rows):
            refusals.append({"file": str(path), "binding_id": "?", "reason": "text and parsed row order disagree"})
            break
        row = rows[ordinal]
        if "source" not in row and "selector" not in row:
            continue
        try:
            provider = build_provider(row)
            value, rule = build_value(row, consumers)
            _validated_row(row, provider, value)
        except ConversionRefusalError as refusal:
            refusals.append({"file": str(path), "binding_id": refusal.binding_id, "reason": refusal.reason})
            continue
        rule_counts[rule] += 1
        planned.append((block, provider, value))

    if refusals:
        report.refusals.extend(refusals)
        report.files_skipped.append(str(path))
        return
    if not planned:
        return

    rewritten = lines
    for block, provider, value in sorted(planned, key=lambda item: item[0].header_index, reverse=True):
        rewritten = _rewrite_block(rewritten, block, provider, value, line_ending)
    new_text = "".join(rewritten)

    try:
        reparsed = tomllib.loads(new_text)
    except tomllib.TOMLDecodeError as exc:
        report.refusals.append({"file": str(path), "binding_id": "*", "reason": f"rewritten file is not TOML: {exc}"})
        report.files_skipped.append(str(path))
        return
    try:
        for revision_table in reparsed.get("revisions", {}).values():
            for row in revision_table.get("bindings", []) or []:
                BindingDefinition.model_validate(_as_tuples(row))
    except Exception as exc:
        report.refusals.append({"file": str(path), "binding_id": "*", "reason": f"rewritten file rejected: {exc}"})
        report.files_skipped.append(str(path))
        return

    report.value_rule_counts.update(rule_counts)
    report.rows_converted += len(planned)
    report.files_rewritten.append(str(path))
    if apply:
        path.write_text(new_text, encoding="utf-8", newline="")


def convert_modelo(
    modelo: str,
    report: ConversionReport,
    casilla_data_type_by_modelo: dict[str, dict[str, CasillaTypeEvidence]],
    *,
    apply: bool,
    modelos_root: Path = REGISTRY_MODELOS_ROOT,
) -> None:
    """Convert every bindings fragment of one modelo."""
    modelo_dir = modelos_root / modelo
    revisions = modelo_dir / "revisions"
    if not revisions.is_dir():
        report.refusals.append({"file": str(modelo_dir), "binding_id": "*", "reason": "modelo has no revisions"})
        return
    report.modelos.append(modelo)
    for revision_dir in sorted(p for p in revisions.iterdir() if p.is_dir()):
        bindings_dir = revision_dir / "bindings"
        if not bindings_dir.is_dir():
            continue
        consumers = _build_consumer_index(modelo_dir, revision_dir, casilla_data_type_by_modelo)
        for toml_path in sorted(bindings_dir.glob("*.toml")):
            convert_file(toml_path, consumers, report, apply=apply)


def _all_modelos(modelos_root: Path) -> list[str]:
    return sorted(p.name for p in modelos_root.iterdir() if p.is_dir() and (p / "revisions").is_dir())


def main(argv: list[str] | None = None) -> int:
    """Run the conversion and return the process exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelo", action="append", default=[], help="Modelo to convert; repeatable.")
    parser.add_argument("--all", action="store_true", help="Convert every modelo carrying a revisions tree.")
    parser.add_argument("--dry-run", action="store_true", help="Report the rewrite without writing any file.")
    parser.add_argument("--report", type=Path, default=None, help="Write the JSON summary to this path.")
    args = parser.parse_args(argv)

    if not args.modelo and not args.all:
        parser.error("pass --modelo <id> at least once, or --all")
    modelos = _all_modelos(REGISTRY_MODELOS_ROOT) if args.all else list(dict.fromkeys(args.modelo))

    casilla_types = _casilla_data_type_by_modelo()
    report = ConversionReport()
    for modelo in modelos:
        convert_modelo(modelo, report, casilla_types, apply=not args.dry_run)

    summary = report.as_dict()
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    mode = "dry-run" if args.dry_run else "applied"
    print(f"Modelos: {', '.join(summary['modelos']) or '(none)'} [{mode}]")
    print(f"Rows converted: {summary['rows_converted']} across {len(summary['files_rewritten'])} files")
    for rule, count in summary["value_rule_counts"].items():
        print(f"  value rule {rule}: {count}")
    if summary["refusals"]:
        print(f"Refused rows ({len(summary['refusals'])}); their files were left untouched:")
        by_reason: dict[str, list[str]] = defaultdict(list)
        for refusal in summary["refusals"]:
            by_reason[refusal["reason"]].append(refusal["binding_id"])
        for reason, ids in sorted(by_reason.items()):
            print(f"  {reason}: {', '.join(sorted(set(ids))[:8])}{' ...' if len(set(ids)) > 8 else ''}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
