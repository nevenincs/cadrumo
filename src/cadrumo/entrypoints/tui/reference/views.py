"""Lay one reference result out as the facts, tables and onward reads the screen shows.

Column heads are the tokens the command line prints above the same rows, so a
person moving between the two reads one vocabulary. A row that names something
another read describes carries that read, with the scope this one was asked in.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from pydantic import BaseModel

from ....application.auth.output import AuthProvidersResult
from ....application.reference_catalogue_contracts import (
    ApoderadoScopesListResult,
    FormulasResult,
    LedgerCategoriesResult,
    ModeloCasillaResult,
    ModeloCasillasResult,
    ModeloDescribeResult,
    ModeloListResult,
    ModeloSupportMatrixResult,
    PortalsListResult,
    PortalsViewResult,
)
from ....core.i18n.render import tr
from ....domain.calculations.registry.query_reports import ModeloBindingsReport
from .reads import ReferenceQuery, ReferenceRead


@dataclass(frozen=True, slots=True)
class ReferenceTable:
    """Rows of one result, each with the read that describes what the row names."""

    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    opens: tuple[ReferenceQuery | None, ...]
    heading: str | None = None


@dataclass(frozen=True, slots=True)
class ReferenceLink:
    """Another read about the same subject, asked in the same scope."""

    read: ReferenceRead
    query: ReferenceQuery


@dataclass(frozen=True, slots=True)
class ReferenceView:
    """One result as the screen shows it."""

    facts: tuple[tuple[str, str], ...] = ()
    tables: tuple[ReferenceTable, ...] = ()
    links: tuple[ReferenceLink, ...] = ()

    @property
    def row_count(self) -> int:
        """How many rows the result's tables hold between them."""
        return sum(len(table.rows) for table in self.tables)


def _mark(value: bool) -> str:
    return "Y" if value else "-"


def _flag(value: bool) -> str:
    return str(value).lower()


def _joined(values: tuple[str, ...] | list[str]) -> str:
    return ", ".join(values)


def _text(value: object) -> str:
    return "-" if value is None or value == "" else str(value)


def _scoped(query: ReferenceQuery, read: ReferenceRead, *, casilla: str | None = None) -> ReferenceQuery:
    """Ask another read about the same modelo in the scope this one was asked in."""
    return ReferenceQuery(
        read=read, modelo=query.modelo, year=query.year, period=query.period, as_of=query.as_of, casilla=casilla
    )


def _modelos(result: ModeloListResult) -> ReferenceView:
    return ReferenceView(
        tables=(
            ReferenceTable(
                columns=("code", "title", "cadence", "domain", "revisions", "local_work", "local_work_guidance"),
                rows=tuple(
                    (
                        row.code,
                        row.title,
                        row.cadence,
                        row.tax_domain,
                        str(row.revision_count),
                        row.local_work_status,
                        _text(row.local_work_guidance),
                    )
                    for row in result.modelos
                ),
                opens=tuple(ReferenceQuery(ReferenceRead.DESCRIBE, modelo=row.code) for row in result.modelos),
            ),
        )
    )


def _support_matrix(result: ModeloSupportMatrixResult) -> ReferenceView:
    return ReferenceView(
        tables=(
            ReferenceTable(
                columns=("modelo", "revs", "latest", "calc", "manifest", "boe", "xml", "extractor", "renames", "title"),
                rows=tuple(
                    (
                        entry.modelo_id,
                        str(entry.revision_count),
                        entry.latest_revision_id,
                        _mark(entry.calc_grade),
                        _mark(entry.has_completeness_manifest),
                        _mark(entry.has_fixed_width_export),
                        _mark(entry.has_xml_dictionary_export),
                        _mark(entry.has_extractor),
                        str(len(entry.renames)),
                        entry.title,
                    )
                    for entry in result.entries
                ),
                opens=tuple(ReferenceQuery(ReferenceRead.DESCRIBE, modelo=entry.modelo_id) for entry in result.entries),
            ),
        )
    )


def _describe(query: ReferenceQuery, result: ModeloDescribeResult) -> ReferenceView:
    return ReferenceView(
        facts=(
            (tr("cli.app.modelo.describe.label_modelo"), result.code),
            (tr("cli.app.modelo.describe.label_title"), result.title),
            (tr("cli.app.modelo.describe.label_official_name"), result.official_name),
            (tr("cli.app.modelo.describe.label_tax_domain"), result.tax_domain),
            (tr("cli.app.modelo.describe.label_cadence"), result.cadence),
            (tr("cli.app.modelo.describe.label_revision"), result.revision),
            (tr("cli.app.modelo.describe.label_revision_ids"), _joined(result.revision_ids)),
            (tr("cli.app.modelo.describe.label_periods"), _joined(result.periods)),
            (tr("cli.app.modelo.describe.label_casillas"), str(result.casilla_count)),
            (tr("cli.app.modelo.describe.label_bindings"), str(result.binding_count)),
            (tr("cli.app.modelo.describe.label_formulas"), str(result.formula_count)),
            ("jurisdiction", result.jurisdiction),
            ("authority_grade", _text(result.authority_grade)),
            ("filing_year", _text(result.filing_year)),
            ("period", _text(result.period)),
            ("valid_from", result.valid_from.isoformat()),
            ("valid_to", _text(result.valid_to)),
            ("manual_casilla_count", str(result.manual_casilla_count)),
            ("bound_casilla_count", str(result.bound_casilla_count)),
            ("computed_casilla_count", str(result.computed_casilla_count)),
            ("legal_refs", _joined(result.legal_refs)),
            ("source_refs", _joined(result.source_refs)),
        ),
        links=tuple(
            ReferenceLink(read, _scoped(query, read))
            for read in (ReferenceRead.CASILLAS, ReferenceRead.FORMULAS, ReferenceRead.BINDINGS)
        ),
    )


def _revision_facts(
    result: ModeloCasillasResult | FormulasResult | ModeloBindingsReport,
) -> tuple[tuple[str, str], ...]:
    return (
        ("modelo", result.code),
        ("revision", result.revision),
        ("filing_year", _text(result.filing_year)),
        ("period", _text(result.period)),
    )


def _casillas(query: ReferenceQuery, result: ModeloCasillasResult) -> ReferenceView:
    return ReferenceView(
        facts=(*_revision_facts(result), ("casilla_count", str(result.casilla_count))),
        tables=(
            ReferenceTable(
                columns=("casilla_id", "number", "input", "required", "label"),
                rows=tuple(
                    (row.casilla_id, row.number, row.input_kind, _flag(row.required), row.label) for row in result.rows
                ),
                opens=tuple(_scoped(query, ReferenceRead.CASILLA, casilla=row.casilla_id) for row in result.rows),
            ),
        ),
    )


def _casilla(result: ModeloCasillaResult) -> ReferenceView:
    facts: list[tuple[str, str]] = [
        ("modelo", result.modelo),
        ("revision", result.revision),
        ("casilla_id", result.casilla_id),
        ("number", result.number),
        ("input_kind", result.input_kind),
        ("required", _flag(result.required)),
        ("data_type", result.data_type),
        ("label", result.label),
        ("section", " > ".join(result.section)),
        ("legal_refs", _joined(result.legal_refs)),
        ("source_refs", _joined(result.source_refs)),
        ("binding", _text(result.binding)),
        ("formula_id", _text(result.formula_id)),
    ]
    if result.help_text is not None and result.help_text:
        facts.append(("help", result.help_text))
    if result.formula_expression is not None:
        facts.append(("formula_expression", str(result.formula_expression)))
    return ReferenceView(facts=tuple(facts))


def _formulas(query: ReferenceQuery, result: FormulasResult) -> ReferenceView:
    return ReferenceView(
        facts=(*_revision_facts(result), ("formula_count", str(result.formula_count))),
        tables=(
            ReferenceTable(
                columns=("formula_id", "target_casilla_id", "inputs", "legal_refs", "source_refs"),
                rows=tuple(
                    (
                        row.formula_id,
                        row.target_casilla_id,
                        _joined((*row.input_casilla_ids, *row.input_bindings, *row.input_parameters)),
                        _joined(row.legal_refs),
                        _joined(row.source_refs),
                    )
                    for row in result.rows
                ),
                opens=tuple(
                    _scoped(query, ReferenceRead.CASILLA, casilla=row.target_casilla_id) for row in result.rows
                ),
            ),
        ),
    )


def _bindings(result: ModeloBindingsReport) -> ReferenceView:
    return ReferenceView(
        facts=(*_revision_facts(result), ("binding_count", str(len(result.rows)))),
        tables=(
            ReferenceTable(
                columns=("binding_id", "source", "input_channel", "typed_enum", "borrador_capable", "legal_refs"),
                rows=tuple(
                    (
                        row.binding_id,
                        row.provider.kind,
                        row.input_channel,
                        _text(row.typed_enum),
                        _flag(row.borrador_capable),
                        _joined(row.legal_refs),
                    )
                    for row in result.rows
                ),
                opens=tuple(None for _row in result.rows),
            ),
        ),
    )


def _categories(result: LedgerCategoriesResult) -> ReferenceView:
    spending = tuple((category_id, family.family) for family in result.families for category_id in family.category_ids)
    return ReferenceView(
        facts=(("income_requires_category", _flag(result.income_requires_category)),),
        tables=(
            ReferenceTable(
                heading=tr("tui.reference.section.spending_categories"),
                columns=("category_id", "family"),
                rows=spending,
                opens=tuple(None for _row in spending),
            ),
            ReferenceTable(
                heading=tr("tui.reference.section.irpf_categories"),
                columns=("irpf_category_id", "purpose", "directions", "net_paid_invoice", "related_category_ids"),
                rows=tuple(
                    (
                        category.id,
                        category.purpose,
                        _joined(category.directions),
                        _flag(category.net_paid_invoice),
                        _joined(category.related_category_ids),
                    )
                    for category in result.irpf_categories
                ),
                opens=tuple(None for _category in result.irpf_categories),
            ),
        ),
    )


def _portals(result: PortalsListResult) -> ReferenceView:
    return ReferenceView(
        facts=(("count", str(result.count)),),
        tables=(
            ReferenceTable(
                columns=("portal", "category", "url_stability", "label"),
                rows=tuple((row.portal, row.category, row.url_stability, row.label) for row in result.rows),
                opens=tuple(ReferenceQuery(ReferenceRead.PORTAL, portal=row.portal) for row in result.rows),
            ),
        ),
    )


def _portal(result: PortalsViewResult) -> ReferenceView:
    return ReferenceView(
        facts=tuple((key, str(value)) for key, value in result.model_dump(mode="json").items() if value != "")
    )


def _auth_providers(result: AuthProvidersResult) -> ReferenceView:
    return ReferenceView(
        tables=(
            ReferenceTable(
                columns=("id", "label", "description"),
                rows=tuple((provider.id, provider.label, provider.description) for provider in result.providers),
                opens=tuple(None for _provider in result.providers),
            ),
        )
    )


def _apoderado_scopes(result: ApoderadoScopesListResult) -> ReferenceView:
    return ReferenceView(
        facts=(("catalogue_version", result.catalogue_version),),
        tables=(
            ReferenceTable(
                columns=("code", "name_es", "name_en", "modelo_codes"),
                rows=tuple(
                    (scope.code, scope.name_es, scope.name_en, _joined(scope.modelo_codes)) for scope in result.scopes
                ),
                opens=tuple(None for _scope in result.scopes),
            ),
        ),
    )


def view_of(query: ReferenceQuery, result: BaseModel) -> ReferenceView:
    """Lay out the result of one read.

    Raises:
        TypeError: The result is not one a reference read returns.
    """
    if isinstance(result, ModeloListResult):
        return _modelos(result)
    if isinstance(result, ModeloSupportMatrixResult):
        return _support_matrix(result)
    if isinstance(result, ModeloDescribeResult):
        return _describe(replace(query, modelo=result.code), result)
    if isinstance(result, ModeloCasillasResult):
        return _casillas(replace(query, modelo=result.code), result)
    if isinstance(result, ModeloCasillaResult):
        return _casilla(result)
    if isinstance(result, FormulasResult):
        return _formulas(replace(query, modelo=result.code), result)
    if isinstance(result, ModeloBindingsReport):
        return _bindings(result)
    if isinstance(result, LedgerCategoriesResult):
        return _categories(result)
    if isinstance(result, PortalsViewResult):
        return _portal(result)
    if isinstance(result, PortalsListResult):
        return _portals(result)
    if isinstance(result, AuthProvidersResult):
        return _auth_providers(result)
    if isinstance(result, ApoderadoScopesListResult):
        return _apoderado_scopes(result)
    raise TypeError(f"not a reference result: {type(result).__name__}")


__all__ = ["ReferenceLink", "ReferenceTable", "ReferenceView", "view_of"]
