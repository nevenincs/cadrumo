"""Every finding the verification can emit reads in words, never in the tokens its facts carry.

The findings are discovered from the live producers: every construction of a
verification finding under the source tree, with its catalogue key, its kind,
its severity and every fact name it supplies. Each is given representative
facts of the shape the producers really store (period tokens such as ``4T`` and
``0A``, ISO dates, dotted registry ids, digests, canonical decimals) and is
rendered through the findings list in all four languages. No sentence may
carry a raw period code, an ISO date, a dotted or snake-case identifier, a hex
digest or an unrendered placeholder, and every fact name a producer supplies
must have one declared way of being written.

A finding about a value of a table's records, such as a Modelo 349 operator's
country code, is checked against the published layout: it is named by the
value's own heading, sits with the missing values, and leads to the table.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Final

import pytest
from textual.color import Color
from textual.widget import Widget
from textual.widgets import OptionList, Static

from ......application.modelo.finding_message_text import FINDING_FACT_KINDS, FindingFactKind
from ......application.modelo.work_form import build_modelo_work_form
from ......application.modelo.work_form_models import (
    ModeloFormAttention,
    ModeloFormCasillaAddressV1,
    ModeloFormIssue,
    ModeloFormOrigin,
    ModeloFormRepeatingBlock,
    ModeloFormSection,
    ModeloWorkForm,
    address_key,
)
from ......application.modelo.work_form_service import modelo_form_snapshot
from ......application.modelo.work_review import ModeloWorkProgress, ModeloWorkReview, build_modelo_work_review_casillas
from ......core.config import override_settings
from ......core.external_constants import SUPPORTED_OUTPUT_LANGUAGES, OutputLanguage
from ......core.i18n.render import tr
from ......core.modelo_work_progress_state import ModeloWorkProgressState
from ......core.period import Period
from ......domain.calculations.registry.authority import PinnedAuthorityOperation
from ......domain.modelos.codes import ModeloCode
from ......domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ....components.host import ScreenHostApp
from ....components.theme import CADRUMO_DARK_THEME_NAME, CADRUMO_LIGHT_THEME_NAME
from ..casilla_list_models import CasillaListHeading
from ..header import missing_count
from ..issue_projection import issue_lines
from ..issue_scale import IssueLevel, IssueLine
from ..issues import WorkbenchIssuesScreen
from ..navigator import NavigatorState, navigator_rows, presented_form
from ..page_items import WorkbenchPage, page_items, workbench_pages
from ..vocabulary import BLOCKS_MARK, CHECK_MARK, DONE_MARK, MISSING_MARK
from .declaration_states import recorded_as_filed
from .form_edits import replace_fields
from .workbench_fixture import synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SOURCE_ROOT: Final[Path] = Path(__file__).resolve().parents[5]
_FINDING_CLASS: Final[str] = "ModeloVerificationFinding"
_LEGAL_REF: Final[str] = "ley-37-1992:art-99"

_REPRESENTATIVE: Final[Mapping[FindingFactKind, tuple[str | int | Decimal, ...]]] = {
    FindingFactKind.PERIOD: ("4T", "0A", "01", "2P", "EXT-3T", "AD-HOC"),
    FindingFactKind.DATE: ("2025-03-01", "unknown"),
    FindingFactKind.BOX: ("op.codigo-pais", "0435", "m100.casilla-rnt"),
    FindingFactKind.BOX_NUMBER: ("76-77", "12"),
    FindingFactKind.MODELO: ("303", "absent"),
    FindingFactKind.YEAR: (2025,),
    FindingFactKind.MONEY: (Decimal("1234.5"), "absent"),
    FindingFactKind.NUMBER: (Decimal("0.75"),),
    FindingFactKind.COUNT: (3,),
    FindingFactKind.OFFICIAL_CODE: ("FR",),
    FindingFactKind.TECHNICAL: ("modelo-303.page_1.sujeto-pasivo", "ab12" * 16),
}
"""Values of the shapes the producers store, several per kind so every way of writing one is rendered."""
_VARIANTS: Final[int] = max(len(values) for values in _REPRESENTATIVE.values())

_TOKENS: Final[Mapping[str, re.Pattern[str]]] = {
    "period code": re.compile(r"(?<![\w.-])(?:[1-4][TP]|0A|EXT-[1-4]T|AD-HOC|EVENT-\d+)(?![\w-])"),
    "ISO date": re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    "dotted identifier": re.compile(r"\b[a-z][a-z0-9_-]*\.[a-z0-9_-]+"),
    "snake-case identifier": re.compile(r"\b[a-z]+_[a-z0-9_]+\b"),
    "hex digest": re.compile(r"\b[0-9a-f]{16,}\b"),
    "placeholder": re.compile(r"%\{|\{[a-z_]+\}"),
}
"""What a raw fact looks like when it reaches a sentence."""


@dataclass(frozen=True, slots=True)
class _Producer:
    locator: str
    locale_key: str
    kind: ModeloVerificationFindingKind
    severity: ModeloVerificationFindingSeverity
    facts: frozenset[str]


class _UnreadableFactsError(Exception):
    """A construction whose fact names cannot be read from the source."""


def _dict_keys(node: ast.expr) -> tuple[set[str], list[str]]:
    if not isinstance(node, ast.Dict):
        raise _UnreadableFactsError("message_facts is not a dict literal")
    keys: set[str] = set()
    splats: list[str] = []
    for key, value in zip(node.keys, node.values, strict=True):
        if key is None and isinstance(value, ast.Name):
            splats.append(value.id)
        elif isinstance(key, ast.Constant) and isinstance(key.value, str):
            keys.add(key.value)
        else:
            raise _UnreadableFactsError("a fact key that is not a literal")
    return keys, splats


def _enclosing(module: ast.Module, target: ast.AST) -> ast.FunctionDef | ast.AsyncFunctionDef:
    functions = [
        node
        for node in ast.walk(module)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and any(child is target for child in ast.walk(node))
    ]
    if not functions:
        raise _UnreadableFactsError("a construction outside any function")
    return min(functions, key=lambda node: sum(1 for _ in ast.walk(node)))


def _returned_dict_keys(module: ast.Module, name: str) -> set[str]:
    """The keys of the dict literal a module function of that name returns."""
    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            for inner in ast.walk(node):
                if isinstance(inner, ast.Return) and inner.value is not None:
                    keys, splats = _dict_keys(inner.value)
                    if splats:
                        raise _UnreadableFactsError(f"{name} returns a splatted dict")
                    return keys
    raise _UnreadableFactsError(f"no function {name} returning a dict literal")


def _local_keys(module: ast.Module, function: ast.AST, name: str) -> set[str]:
    """Every fact key bound to the local ``name``: its dict literal or builder, and each key assigned to it."""
    keys: set[str] = set()
    bound = False
    for node in ast.walk(function):
        if isinstance(node, ast.Assign | ast.AnnAssign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            if value is None:
                continue
            for target in targets:
                if isinstance(target, ast.Name) and target.id == name:
                    if isinstance(value, ast.Dict):
                        literal, splats = _dict_keys(value)
                        if splats:
                            raise _UnreadableFactsError(f"{name} splats {splats}")
                        keys |= literal
                        bound = True
                    elif isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
                        keys |= _returned_dict_keys(module, value.func.id)
                        bound = True
                if (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == name
                    and isinstance(target.slice, ast.Constant)
                    and isinstance(target.slice.value, str)
                ):
                    keys.add(target.slice.value)
                    bound = True
    if not bound:
        raise _UnreadableFactsError(f"nothing bound to {name}")
    return keys


def _call_site_keys(module: ast.Module, function_name: str) -> set[str]:
    keys: set[str] = set()
    for node in ast.walk(module):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == function_name:
            for keyword in node.keywords:
                if keyword.arg == "message_facts":
                    literal, _ = _dict_keys(keyword.value)
                    keys |= literal
    return keys


def _fact_names(module: ast.Module, call: ast.Call, facts: ast.expr) -> set[str]:
    if isinstance(facts, ast.Name):
        return _local_keys(module, _enclosing(module, call), facts.id)
    keys, splats = _dict_keys(facts)
    for _ in splats:
        keys |= _call_site_keys(module, _enclosing(module, call).name)
    return keys


def _enum_member[EnumT: (ModeloVerificationFindingKind, ModeloVerificationFindingSeverity)](
    node: ast.expr | None, enum: type[EnumT], default: EnumT
) -> EnumT:
    if isinstance(node, ast.Attribute) and node.attr in enum.__members__:
        return enum[node.attr]
    return default


def _locale_keys(node: ast.expr | None, locator: str) -> tuple[str, ...]:
    """Read every literal branch; refuse a key that cannot be inspected statically."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return (node.value,)
    if isinstance(node, ast.IfExp):
        return tuple(dict.fromkeys((*_locale_keys(node.body, locator), *_locale_keys(node.orelse, locator))))
    pytest.fail(f"{locator}: a finding built without a literal catalogue key")


def _producers() -> Iterator[_Producer]:
    """Every finding construction under the source tree, read from the source as it stands."""
    for path in sorted(_SOURCE_ROOT.rglob("*.py")):
        if "tests" in path.parts:
            continue
        module = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(module):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == _FINDING_CLASS):
                continue
            keywords = {keyword.arg: keyword.value for keyword in node.keywords}
            locator = f"{path.relative_to(_SOURCE_ROOT).as_posix()}:{node.lineno}"
            locale_keys = _locale_keys(keywords.get("message_locale_key"), locator)
            facts_node = keywords.get("message_facts")
            try:
                facts = set() if facts_node is None else _fact_names(module, node, facts_node)
            except _UnreadableFactsError as error:
                pytest.fail(f"{locator}: its facts cannot be read ({error}); an unread one would pass unchecked")
            for locale_key in locale_keys:
                yield _Producer(
                    locator=locator,
                    locale_key=locale_key,
                    kind=_enum_member(
                        keywords.get("kind"), ModeloVerificationFindingKind, ModeloVerificationFindingKind.ADVISORY
                    ),
                    severity=_enum_member(
                        keywords.get("severity"),
                        ModeloVerificationFindingSeverity,
                        ModeloVerificationFindingSeverity.WARNING,
                    ),
                    facts=frozenset(facts),
                )


def _finding(producer: _Producer, variant: int) -> ModeloVerificationFinding:
    facts = {
        name: _REPRESENTATIVE[kind][variant % len(_REPRESENTATIVE[kind])]
        for name in sorted(producer.facts)
        if (kind := FINDING_FACT_KINDS.get(name)) is not None
    }
    return ModeloVerificationFinding(
        kind=producer.kind,
        severity=producer.severity,
        message_locale_key=producer.locale_key,
        message_facts=facts,
        legal_refs=(_LEGAL_REF,),
    )


def _leaks(text: str) -> list[str]:
    return [f"{name} {match.group(0)!r}" for name, pattern in _TOKENS.items() for match in pattern.finditer(text)]


def _read_parts(line: IssueLine) -> str:
    """Everything the list shows for a finding before the filer asks for technical details."""
    return "\n".join((line.where, line.message, line.action, line.detail))


def test_the_walk_reaches_the_live_producers() -> None:
    producers = list(_producers())

    assert len({producer.locale_key for producer in producers}) > 20
    assert any(producer.facts for producer in producers)
    assert {
        "application.modelo.findings.selected_option_requires_zero",
        "application.modelo.findings.selected_option_requires_nonzero",
    } <= {producer.locale_key for producer in producers}


@pytest.mark.parametrize("expression", ["unknown", "build_key()", "'known' if condition else unknown", "42"])
def test_the_producer_walk_refuses_unreadable_catalogue_keys(expression: str) -> None:
    with pytest.raises(pytest.fail.Exception, match="without a literal catalogue key"):
        _locale_keys(ast.parse(expression, mode="eval").body, "fixture:1")


def test_the_producer_walk_reads_all_nested_literal_branches() -> None:
    expression = "'first' if a else ('second' if b else 'first')"
    assert _locale_keys(ast.parse(expression, mode="eval").body, "fixture:1") == ("first", "second")


def test_every_fact_a_producer_supplies_has_one_declared_way_of_being_written() -> None:
    undeclared = sorted(
        f"{producer.locator} {name}"
        for producer in _producers()
        for name in producer.facts
        if name not in FINDING_FACT_KINDS
    )

    assert not undeclared, "\n".join(undeclared)


def test_the_token_check_catches_raw_facts_in_the_real_catalogue() -> None:
    """Detector teeth: the real sentence with its facts interpolated raw carries the tokens the check rejects."""
    raw = tr(
        "application.modelo.findings.cross_period_first_year_fractional_suppression",
        source_modelo="303",
        source_filing_year=2025,
        source_period="4T",
        activity_start_date="2025-03-01",
    )

    assert {leak.split(" ")[0] for leak in _leaks(raw)} >= {"period", "ISO"}
    assert _leaks("Box [op.codigo-pais] and modelo-303.page_1 and " + "ab12" * 16)


@pytest.mark.parametrize("language", [str(language) for language in SUPPORTED_OUTPUT_LANGUAGES])
def test_every_finding_reads_in_words_in_every_language(language: str) -> None:
    producers = list(_producers())
    base = synthetic_form(needs_input=False)
    failures: list[str] = []
    with override_settings(cadrumo_output_language=language):
        for variant in range(_VARIANTS):
            issues = tuple(ModeloFormIssue(finding=_finding(producer, variant)) for producer in producers)
            lines = issue_lines(base.model_copy(update={"issues": issues}))
            assert len(lines) == len(producers)
            failures.extend(
                f"[{language}] {line.technical}: {leak}" for line in lines for leak in _leaks(_read_parts(line))
            )

    assert not failures, "\n".join(sorted(set(failures)))


def test_a_period_date_and_amount_read_as_the_filer_writes_them() -> None:
    finding = ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message_locale_key="application.modelo.findings.cross_period_operator_declared_suppression",
        message_facts={
            "source_modelo": "303",
            "source_filing_year": 2025,
            "source_period": "4T",
            "activity_start_date": "2025-03-01",
            "origin_code": "operator_declared",
        },
        legal_refs=(_LEGAL_REF,),
    )
    mismatch = ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.RECONCILIATION_MISMATCH,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message_locale_key="application.modelo.findings.m303_m349_intracom_reconciliation_mismatch",
        message_facts={
            "period_code": "0A",
            "filing_year": 2025,
            "m303_total": Decimal("1234.5"),
            "m349_total": Decimal("1000"),
            "gap": Decimal("234.5"),
        },
        legal_refs=(_LEGAL_REF,),
    )
    form = synthetic_form(needs_input=False).model_copy(
        update={"issues": (ModeloFormIssue(finding=finding), ModeloFormIssue(finding=mismatch))}
    )
    with override_settings(cadrumo_output_language="es"):
        spanish = {line.level: line.message for line in issue_lines(form)}
    with override_settings(cadrumo_output_language="en"):
        english = {line.level: line.message for line in issue_lines(form)}

    assert "periodo 4.º trimestre" in spanish[IssueLevel.INFO]
    assert "01/03/2025" in spanish[IssueLevel.INFO]
    assert "(1.234,50 EUR)" in spanish[IssueLevel.CHECK]
    assert "difieren en 234,50 EUR" in spanish[IssueLevel.CHECK]
    assert "period 4th quarter" in english[IssueLevel.INFO]
    assert "(1,234.50 EUR)" in english[IssueLevel.CHECK]


def test_a_missing_value_already_listed_among_the_missing_boxes_is_not_listed_twice() -> None:
    form = replace_fields(
        synthetic_form(needs_input=False), {"07": {"origin": ModeloFormOrigin.NEEDS_INPUT, "value": None}}
    )
    listed = ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        casilla_id="07",
        message_locale_key="application.modelo.findings.missing_required_casilla",
        message_facts={"casilla_id": "07"},
        legal_refs=(_LEGAL_REF,),
    )
    unlisted = listed.model_copy(update={"casilla_id": "06", "message_facts": {"casilla_id": "06"}})
    form = form.model_copy(update={"issues": (ModeloFormIssue(finding=listed), ModeloFormIssue(finding=unlisted))})
    with override_settings(cadrumo_output_language="en"):
        lines = issue_lines(form)

    assert ModeloFormIssue(finding=listed).attention is ModeloFormAttention.MISSING
    assert [(line.level, line.box, line.message) for line in lines] == [
        (IssueLevel.MISSING, "06", "Required box [06] is empty.")
    ]


def _form_349(operation: PinnedAuthorityOperation, findings: tuple[ModeloVerificationFinding, ...]) -> ModeloWorkForm:
    modelo, year, code = "349", 2026, "1T"
    period = Period.from_year_and_code(year, code)
    revision_id = str(operation.revision_for_context(modelo, filing_year=year, period=code).id)
    snapshot = modelo_form_snapshot(operation, ModeloCode(modelo), year, period, revision_id)
    review = ModeloWorkReview(
        bucket_id="13000000-0000-4000-8000-000000000349",
        modelo=modelo,
        filing_year=year,
        period=period,
        registry_revision_id=snapshot.revision.id,
        work_unit_id="e" * 64,
        calculation_revision_id=None,
        lifecycle_state=None,
        verification_outcome=None,
        progress=ModeloWorkProgress(state=ModeloWorkProgressState.UNDEFINED),
        casillas=build_modelo_work_review_casillas(snapshot=snapshot, revision=None, operation=operation),
        findings=findings,
        blockers=(),
    )
    return build_modelo_work_form(
        review=review,
        snapshot=snapshot,
        layout=operation.form_layout(modelo, snapshot.revision.id),
        revision=None,
        permitted_surface=None,
        entered_casilla_ids=None,
        overridden_binding_ids=None,
        language=OutputLanguage.EN,
    )


def test_a_missing_value_of_the_operator_records_is_named_by_its_heading_and_leads_to_the_table(
    operation: PinnedAuthorityOperation,
) -> None:
    row_fields = ("op.codigo-pais", "op.nif-comunitario", "op.clave-operacion")
    findings = tuple(
        ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            casilla_id=casilla_id,
            message_locale_key="application.modelo.findings.missing_required_casilla",
            message_facts={"casilla_id": casilla_id},
            legal_refs=(_LEGAL_REF,),
        )
        for casilla_id in row_fields
    )
    form = _form_349(operation, findings)
    with override_settings(cadrumo_output_language="en"):
        lines = issue_lines(form)

    assert [line.where for line in lines] == [
        "Country code",
        "EU VAT number",
        "Transaction code",
    ]
    assert {line.level for line in lines} == {IssueLevel.MISSING}
    assert {line.message for line in lines} == {"This table has no records yet, and every record needs this value."}
    assert all(line.in_records and line.box == "·" for line in lines)
    assert [line.key for line in lines] == [
        address_key(ModeloFormCasillaAddressV1(casilla_id=casilla_id)) for casilla_id in row_fields
    ]
    assert not any(_leaks(_read_parts(line)) for line in lines)


def _operator_record_findings() -> tuple[ModeloVerificationFinding, ...]:
    return tuple(
        ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            casilla_id=casilla_id,
            message_locale_key="application.modelo.findings.missing_required_casilla",
            message_facts={"casilla_id": casilla_id},
            legal_refs=(_LEGAL_REF,),
        )
        for casilla_id in ("op.codigo-pais", "op.nif-comunitario")
    )


def _records_section(pages: tuple[WorkbenchPage, ...]) -> tuple[WorkbenchPage, ModeloFormSection]:
    """The page and section holding the 349 operators' table of records."""
    return next(
        (page, section)
        for page in pages
        for section in page.sections
        if any(
            "op.codigo-pais" in block.column_casilla_ids
            for block in section.blocks
            if isinstance(block, ModeloFormRepeatingBlock)
        )
    )


def test_a_value_missing_from_the_records_keeps_its_section_and_page_open_in_both_panes(
    operation: PinnedAuthorityOperation,
) -> None:
    form = _form_349(operation, _operator_record_findings())
    with override_settings(cadrumo_output_language="en"):
        pages = workbench_pages(presented_form(form))
        page, section = _records_section(pages)
        index = pages.index(page)
        heading = next(
            item
            for item in page_items(page, staged={})
            if isinstance(item, CasillaListHeading) and item.level == 0 and section.heading.text in item.text
        )
        rows = navigator_rows(pages, current=0, state=NavigatorState(), checked={}, width=60, show_attention=True)
    page_row = next(row for row in rows if row.option_id == f"page:{index}")
    section_row = next(row for row in rows if row.option_id == f"section:{index}:{section.id}")

    assert missing_count(form) == 2
    assert heading.mark is MISSING_MARK
    assert MISSING_MARK in page_row.marks and DONE_MARK not in page_row.marks
    assert MISSING_MARK in section_row.marks
    assert "2" in section_row.prompt.plain


def test_a_filed_declaration_marks_no_section_done_in_either_pane(operation: PinnedAuthorityOperation) -> None:
    form = recorded_as_filed(_form_349(operation, ()))
    with override_settings(cadrumo_output_language="en"):
        pages = workbench_pages(presented_form(form, recorded=True))
        headings = [
            item
            for page in pages
            for item in page_items(page, staged={})
            if isinstance(item, CasillaListHeading) and item.row is None and item.level == 0
        ]
        rows = navigator_rows(pages, current=0, state=NavigatorState(), checked={}, width=60, show_attention=False)

    assert headings, "the filed form still shows its sections"
    assert all(item.mark is not DONE_MARK and not item.text.startswith(DONE_MARK.glyph) for item in headings)
    assert not any(DONE_MARK in row.marks for row in rows)


def _glyph_colours(widget: Widget, glyph: str) -> list[Color]:
    colours: list[Color] = []
    for y in range(widget.region.height):
        for segment in widget.render_line(y):
            if glyph in segment.text and segment.style is not None and segment.style.color is not None:
                colours.append(Color.from_rich_color(segment.style.color))
    return colours


@pytest.mark.asyncio
@pytest.mark.parametrize("theme", [CADRUMO_DARK_THEME_NAME, CADRUMO_LIGHT_THEME_NAME])
async def test_every_blocking_mark_in_the_findings_list_is_drawn_in_the_error_colour(theme: str) -> None:
    blocking = ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key="application.modelo.findings.oss_evidence_missing",
        legal_refs=(_LEGAL_REF,),
    )
    warning = blocking.model_copy(
        update={"kind": ModeloVerificationFindingKind.ADVISORY, "severity": ModeloVerificationFindingSeverity.WARNING}
    )
    form = synthetic_form(needs_input=False).model_copy(
        update={"issues": (ModeloFormIssue(finding=blocking), ModeloFormIssue(finding=warning))}
    )
    with override_settings(cadrumo_output_language="en"):
        screen = WorkbenchIssuesScreen(form)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(100, 40)) as pilot:
            app.theme = theme
            for _ in range(4):
                await pilot.pause()
            error = Color.parse(app.theme_variables["error"])
            title = _glyph_colours(screen.query_one("#issues-title", Static), BLOCKS_MARK.glyph)
            heading = _glyph_colours(screen.query_one("#issues-list", OptionList), BLOCKS_MARK.glyph)
            check = _glyph_colours(screen.query_one("#issues-list", OptionList), CHECK_MARK.glyph)
            app.exit(None)

    assert title and heading, "the title and the blocking level's heading each draw the mark"
    assert all(colour == error for colour in (*title, *heading))
    assert check and all(colour != error for colour in check)


@pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
def test_reconciliation_wire_findings_reach_tui_issue_lines(locale):
    from ......application.modelo.verification_projection import ModeloFindingSnapshot
    from .....tests.reconciliation_finding_fixtures import reconciliation_findings

    original = reconciliation_findings()
    restored = tuple(
        ModeloFindingSnapshot.model_validate_json(
            ModeloFindingSnapshot.from_finding(finding).model_dump_json()
        ).to_finding()
        for finding in original
    )
    assert restored == original
    form = synthetic_form().model_copy(
        update={"issues": tuple(ModeloFormIssue(finding=finding) for finding in restored)}
    )
    with override_settings(cadrumo_output_language=locale):
        lines = issue_lines(form)
    matched = [line for line in lines if "test-reconciliation-evidence" in line.technical]
    assert len(matched) == 3
    assert all(line.level is IssueLevel.CHECK for line in matched)
    assert all("application.modelo" not in line.message and "%{" not in line.message for line in matched)
    by_key = {
        finding.message_locale_key: next(line for line in matched if finding.message_locale_key in line.technical)
        for finding in original
    }
    incomplete = by_key["application.modelo.findings.cross_model_reconciliation_incomplete"]
    assert "303" in incomplete.message and "349" in incomplete.message
    assert "2" in incomplete.message and "1" in incomplete.message
    working = by_key["application.modelo.findings.pulled_filing_casilla_mismatch"]
    cross_model = by_key["application.modelo.findings.m303_m349_intracom_reconciliation_mismatch"]
    if locale == "en":
        assert "6,000.25" in working.message and "7,250.50" in working.message
        assert "10,000.25" in cross_model.message and "8,000.50" in cross_model.message
    elif locale == "es":
        assert "6.000,25" in working.message and "7.250,50" in working.message
        assert "10.000,25" in cross_model.message and "8.000,50" in cross_model.message
