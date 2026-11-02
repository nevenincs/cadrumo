"""Refuse a tax value written into the code that handles tax.

The operator's rule is that a tax number, limit, threshold, period or form code lives in
the registry. Calendar facts, arithmetic, technical limits and registry ids may stay in code.
The sweep follows scalar types, lexical producers and canonical technical owners.
Unknown collection bounds remain findings; a lexical width does not select a fiscal value:

- a ``Decimal`` other than an arithmetic identity or a rounding quantum;
- a numeric bound or comparison other than arithmetic, a calendar range or a machine capacity;
- a collection bound or repeated-record count, which can hide a form's row limit;
- complete fixed code alternatives in a regex, rather than its character widths;
- a year in a branch, a ``date`` with a fixed year or day, a ``timedelta`` of days, a month tuple;
- a code-shaped string, ``Literal`` member, ``match`` case or dict key outside a modelo or period address;
- a comparison with a modelo id, or two or more modelo ids held together, which is a routing rule;
- a one or two letter string compared with, or stored under, a name that means a clave;
- a number as an operand, a clamp, a default, an argument, a result or a member, or held by a class or a local;
- a year in a set of years or a ``range``, a ``datetime`` with a fixed date, an ISO date as text;
- a single capital letter compared with anything, keying a dict or spelled in a ``Literal``.

A literal leaves the findings only through a rule below. There is no record of accepted
literals: what the rules do not cover fails and stays listed until it moves or a rule states
why it may stay. The modelo ids come from the registry tree and the period codes from their
enum, so neither is listed.

A number given a name at module scope stays in reach. A tax word in the name decides first, whatever
else the name says and whichever module holds it: ``DEDUCTION_VERSION = 21`` and ``INCOME_PREVIEW_LIMIT
= 12450`` are findings. Otherwise it is a finding unless the same value rules admit it or what it is
says it cannot be a tax value: its name states a machine unit, its module owns machine or presentation
mechanics, one whole word of its name counts a mechanic of the product itself (a page, a retry, a
sample, a freshness window), a calendar number stands under the unit it counts, or every read of it in
its module only cuts a sequence short and it counts no part of a form. A limit word alone speaks for
no capacity, and the units ``S``, ``POINTS`` and ``VERSION`` do not speak for a limit word. A capacity
is a power of two, or a round thousand whose every read is the ``max_length`` of a text, or a round ten
thousand on a collection. A name can lie, so review keeps reading what a new name holds.

A modelo or period code is an address only when the literal itself stands under such a name, read on
its own side and by the name's last word: ``period.casilla == '0208'`` and ``box_token = '0208'`` are
findings. A form code bound to a name at module scope, or compared through a name, is a finding: a
role read from the registry says which form it is. A workbook module holds numbers of its own only
under a name that says it measures the sheet.

A module that hands values to a form may not write a width at all: a fixed digit or code regex, a
length bound below machine capacity, a text length compared with a number, a slice bound, a padding
call or a constraint helper given a number each restate the record design, which the registry owns.

What this sweep cannot see, because catching it would drown the findings in positions and counts:

- a bare integer below thirteen under a name that says nothing, as in ``i - 5`` or ``rows[3]``: only
  a word such as ``LIMIT`` or ``RATE`` in its name, or the ``/ 100`` of a percentage, brings it in;
- a single-letter code held in a variable or returned, and the letter ``X``, which is also the
  record designs' flag mark: a name meaning clave still brings it in;
- a single-letter code as the value of an enum member, as in ``CASTELLANO = "E"``: these are typed vocabularies
  held in records, and they stay in code until the registry declares them and the records can follow;
- a width in a module that hands nothing to a form, which is lexical grammar there;
- a fact spelled in the words of a mechanic, as a name can lie;
- a day or month count under its calendar unit, as in ``_RECTIFICATION_WINDOW_MONTHS = 12``,
  ``if elapsed_days > 30`` or ``if months >= 12``: a plazo and a calendar's own length read alike;
- a number the arithmetic rules admit, as a result or a member with no name around it: ``return 10``,
  ``100 if c else 10`` or ``GENERAL = 10`` in an enum;
- a one percent rate written as a cent with no tax word by it, as in ``x * Decimal('0.01')``;
- two capital letters compared with an unnamed field, as in ``kind == 'AB'``: country codes read alike;
- a single letter as a plain result, as in ``'A' if x else 'B'``;
- a length of text whose characters are tested, as in ``value.isdigit() and len(value) == 18``, in a
  module that hands nothing to a form;
- a number or a letter in the TUI or another owner that only lays values out, unless a tax word names it.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

import pytest

from ._tax_literal_sweep_visitor import (
    _current,
    sweep_source,
    sweep_tree,
)
from ._tax_literal_sweep_vocabulary import (
    _SRC,
    _modelo_ids,
    _period_codes,
    _reader_name,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FAKE_MODELOS: Final = frozenset({"303", "111", "100"})

_FAKE_PERIODS: Final = frozenset({"0A", "1T", "01"})


@pytest.mark.parametrize(
    ("line", "kind"),
    [
        ("cap = Decimal('300.51')\n", "decimal"),
        ("clave: int = Field(ge=1, le=6)\n", "field_bound"),
        ("rows: tuple[int, ...] = Field(min_length=18, max_length=18)\n", "field_length"),
        ("rows: tuple[int, ...] = Field(max_length=12)\n", "field_length"),
        ("ok = len(row) == 3\n", "len_compare"),
        ("BOX = '0208'\n", "code"),
        ("descendant_count: int = Field(ge=0, le=10)\n", "field_bound"),
        ("if revision_id == '2022':\n    pass\n", "code"),
        ("box = '303'\n", "code"),
        ("ROUTED = frozenset({Modelo('111').value, Modelo('303').value})\n", "modelo_set"),
        ("ok = modelo in {'111', '303'}\n", "modelo_set"),
        ("if clave == 'A':\n    pass\n", "letter_clave"),
        ("subclave = 'B'\n", "letter_clave"),
        ("M349_CLAVES: frozenset[str] = frozenset({'A', 'E'})\n", "letter_clave"),
        ("_CLAVES = tuple(('A', 'E'))\n", "letter_clave"),
        ("tipo_renta_code: str = 'XY'\n", "letter_clave"),
        ("first_year: int = Field(ge=2012)\n", "field_bound"),
        ("month: int = Field(le=13)\n", "field_bound"),
        ("minimum_days: int = Field(le=180)\n", "field_bound"),
        ("slot: int = Field(ge=1, le=5)\n", "field_bound"),
        ("deduction_limit: int = Field(le=300)\n", "field_bound"),
        ("rate = Decimal('0.19')\n", "decimal"),
        ("cap = Decimal('1000')\n", "decimal"),
        ("MAX = Decimal('999999.99')\n", "decimal"),
        ("limit: int = Field(max_length=99)\n", "field_length"),
        ("if income > 12450:\n    pass\n", "threshold"),
        ("if width > 77:\n    pass\n", "threshold"),
        ("slot_width: int = Field(ge=2, le=9)\n", "field_bound"),
        ("if ejercicio == 2022:\n    pass\n", "year_branch"),
        ("QUARTERS = (1, 4, 7, 10)\n", "month_tuple"),
        ("QUARTERS = {10, 1, 7, 4}\n", "month_tuple"),
        ("if code == 127:\n    pass\n", "threshold"),
        ("start = date(2023, 1, 1)\n", "date_literal"),
        ("end = date(year, 7, 30)\n", "date_literal"),
        ("due = today + timedelta(days=20)\n", "timedelta"),
        ("modelo: Literal['100']\n", "literal_type"),
        ("if modelo == '303':\n    pass\n", "modelo_compare"),
        ("if context.modelo == Modelo('100').value:\n    pass\n", "modelo_compare"),
        ("match code:\n    case '0208':\n        pass\n", "match_case"),
        ("ROWS = {'0208': 1}\n", "dict_key"),
        ("ok = len(code) in {3, 4}\n", "len_in"),
        ("class OtherCodes(StrEnum):\n    JAN = '01'\n", "code"),
        ("class StandardPeriodCode(StrEnum):\n    def f(self):\n        box = '01'\n", "code"),
        ("PATH = ('ledger', '100', 'import')\n", "code"),
    ],
)
def test_the_sweep_rejects_a_representative_tax_literal(line: str, kind: str) -> None:
    findings = sweep_source(line, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS)
    assert any(finding.startswith(f"{kind}:") for finding in findings), findings


@pytest.mark.parametrize(
    "line",
    [
        "code: Annotated[str, StringConstraints(min_length=2, max_length=2)]\n",
        "code: str = Field(pattern=r'^\\d{3}$')\n",
        "CODE = re.compile(r'^[A-Z]{2}\\d{3}$')\n",
        "code: str = Field(min_length=16, max_length=16)\n",
        "BOX = re.compile(r'^(?P<box>\\d{4})$')\n",
        "x = Decimal('0.01')\n",
        "rate = value / Decimal('100')\n",
        "name: str = Field(max_length=128)\n",
        "name: str = Field(max_length=4096)\n",
        "count: int = Field(ge=0)\n",
        "directory = operation.modelo_directory('303')\n",
        "def f():\n    selected = Modelo('303')\n    return load(selected)\n",
        "work = load(modelo='303', period='1T')\n",
        '"""A docstring may cite casilla 0208 and clave A."""\n',
        "label = 'A'\n",
        "end = date(year, 12, 31)\n",
        "start = date(year, 1, 1)\n",
        "EPOCH = date(1899, 12, 30)\n",
        "later = now + timedelta(hours=18)\n",
        "next_day = day + timedelta(days=1)\n",
        "year: int = Field(ge=1900, le=9999)\n",
        "month: Annotated[int, Field(ge=1, le=12)]\n",
        "calendar_days: int = Field(ge=365, le=366)\n",
        "digest: str = Field(pattern=r'^[0-9a-f]{64}$', min_length=64, max_length=64)\n",
        "run: str = Field(pattern=r'^[0-9a-f]{16}$', min_length=16, max_length=16)\n",
        "ISO = re.compile(r'\\d{4}-\\d{2}-\\d{2}')\n",
        "GAP = re.compile(r'Ejercicio.{0,80}?x')\n",
        "_SPAIN_COUNTRY_CODE = 'ES'\n",
        "NAMES = {'01': 'finding.month_01'}\n",
        "REVISION_ID = '2022'\n",
        "def _validate_yyyymmdd(raw):\n    return len(raw) != 8\n",
        "def _territory_definition(code):\n    return len(code) != 5\n",
        "def _impatriado_jurisdictions_are_canonical(values):\n    return all(len(value) == 2 for value in values)\n",
        "class ModeloCode(str):\n    def __new__(cls, raw):\n        return len(raw) != 3\n",
        "def _require_selector_address(target):\n    return len(target) == 16\n",
        "ok = len(target_period) == 2\n",
        "class StandardPeriodCode(StrEnum):\n    JAN = '01'\n",
        "PATH = ('app', 'live', 'borrador', '100', 'import')\n",
        "DISPLAY = re.compile(r'^(?P<year>\\d{4})\\s+x$')\n",
        "ok = ord(character) == 127\n",
        "ok = 0xD800 <= ord(character) <= 0xDFFF\n",
        "unset = Decimal('NaN')\n",
        "widths = (3, 12, 12, 7)\n",
        "parts = {(4, 2, 2)}\n",
        "parts = {(1, 8, 2)}\n",
    ],
)
def test_the_sweep_admits_what_stands_where_no_tax_fact_can(line: str) -> None:
    assert sweep_source(line, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS) == []


@pytest.mark.parametrize(
    ("source", "kind"),
    [
        ("CODE = re.compile(r'^(?:0208|0209)$')", "regex_values"),
        ("MODELS = re.compile(r'^(?:111|303)$')", "modelo_set"),
        ("MODELS = re.compile(r'^(?:111|303)-\\d{4}$')", "modelo_set"),
        ("CUTOFF = re.compile(r'^2024-\\d{2}-\\d{2}$')", "regex_year"),
        ("clave: str = Field(pattern=r'^(?:A|B)$')", "letter_clave"),
        ("ROWS = re.compile(r'^(?:row;){18}$')", "regex_width"),
        ("rows: tuple[int, ...] = Field(min_length=2, max_length=2)", "field_length"),
        ("qualifying_children: tuple[int, ...] = Field(min_length=2)", "field_length"),
        ("clave: int = Field(ge=1, le=4)", "field_bound"),
        ("deduction: int = Field(ge=0, le=366)", "field_bound"),
        ("tax_years: int = Field(ge=1, le=50)", "field_bound"),
        ("rows = 'text'\ndef f(rows):\n    return len(rows) > 12", "len_compare"),
        ("def f(rows):\n    def nested():\n        rows = 'text'\n    return len(rows) > 12", "len_compare"),
        (
            "def f(raw: str, rows: list[int]):\n    value = rows\n"
            "    if rows:\n        value = raw\n    return len(value) > 12",
            "len_compare",
        ),
        ("def f(rows):\n    return 12 < len(rows)", "len_compare"),
        ("def f(rows):\n    a, b, c = rows\n    return len(rows) == 3", "len_compare"),
    ],
)
def test_grammar_classification_preserves_fiscal_members_and_unknown_collections(source: str, kind: str) -> None:
    assert any(
        item.startswith(kind + ":") for item in sweep_source(source, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS)
    )


@pytest.mark.parametrize(
    "source",
    [
        "def parse(raw: str):\n    parts = raw.split('-')\n    return len(parts) == 3",
        "def parse(raw: str):\n    whole, fraction = raw.rsplit(',', 1)\n    return len(fraction) in {1, 2}",
        "from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression\n"
        "def evaluate(expression: FormulaExpression):\n    return len(expression.args) == 12",
        "from urllib.parse import SplitResult\n"
        "def parse(value: SplitResult):\n    return len(value.path.split('/')) == 4",
        "COUNTRY = re.compile(r'^(?:ES|FR)$')",
    ],
)
def test_scalar_and_record_grammar_is_proven_by_its_producer(source: str) -> None:
    assert sweep_source(source, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS) == []


@pytest.mark.parametrize(
    ("owner", "source"),
    [
        ("application/connectivity_probe.py", "http_status: int = Field(ge=100, le=599)"),
        ("core/external_constants.py", "class AeatNotificationsQuery:\n    lookback_years: int = Field(ge=1, le=50)"),
        (
            "core/config_runtime_fields.py",
            "cadrumo_bucket_default_session_absolute_minutes: int = Field(ge=60, le=720)",
        ),
        (
            "application/workflow/resume_contracts.py",
            "candidates: tuple[WorkflowResumeCandidateSnapshot, ...] = Field(min_length=2)",
        ),
    ],
)
def test_canonical_technical_roles_admit_only_their_own_constraints(owner: str, source: str) -> None:
    assert sweep_source(source, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, owner=owner) == []
    defects = "\ncap = Decimal('300.51')\nclave: int = Field(ge=1, le=4)\nrows: tuple[int, ...] = Field(max_length=12)"
    findings = sweep_source(source + defects, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, owner=owner)
    assert {finding.split(":", 1)[0] for finding in findings} >= {"decimal", "field_bound", "field_length"}


def test_collection_names_cannot_borrow_a_technical_owner_exemption() -> None:
    source = "qualifying_children: tuple[Child, ...] = Field(min_length=2)"
    for owner in (
        "application/ledger/merge_operation.py",
        "application/inventory/registered_requests.py",
        "application/workflow/resume_contracts.py",
    ):
        assert any(
            f.startswith("field_length:")
            for f in sweep_source(source, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, owner=owner)
        )


def test_inventory_plurality_requires_its_canonical_evidence_type() -> None:
    field = "evidence: tuple[PhysicalClosingEvidence, ...] = Field(min_length=2)"
    owner = "application/inventory/registered_requests.py"
    canonical = "from cadrumo.domain.contribuyente.inventory.closing_foundations import PhysicalClosingEvidence\n"
    assert sweep_source(canonical + field, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, owner=owner) == []
    counterfeit = "from unrelated import PhysicalClosingEvidence\n"
    assert any(
        f.startswith("field_length:")
        for f in sweep_source(counterfeit + field, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, owner=owner)
    )


@pytest.mark.parametrize(
    ("field", "owner", "admitted"),
    [
        pytest.param(
            "sources: tuple[SourceDisagreementEntry, ...] = Field(min_length=2)",
            "domain/modelos/source_disagreement.py",
            True,
            id="two-sources-define-a-disagreement",
        ),
        pytest.param(
            "sources: tuple[SourceDisagreementEntry, ...] = Field(min_length=3)",
            "domain/modelos/source_disagreement.py",
            False,
            id="another-minimum",
        ),
        pytest.param(
            "rows: tuple[SourceDisagreementEntry, ...] = Field(min_length=2)",
            "domain/modelos/source_disagreement.py",
            False,
            id="another-field",
        ),
        pytest.param(
            "sources: tuple[int, ...] = Field(min_length=2)",
            "domain/modelos/source_disagreement.py",
            False,
            id="another-element-type",
        ),
        pytest.param(
            "sources: tuple[SourceDisagreementEntry, ...] = Field(min_length=2)",
            "application/example.py",
            False,
            id="another-owner",
        ),
    ],
)
def test_a_source_disagreement_alone_may_require_two_sources(field: str, owner: str, admitted: bool) -> None:
    findings = sweep_source(field, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, owner=owner)
    assert any(f.startswith("field_length:") for f in findings) is not admitted


def test_nested_import_cannot_authorize_a_module_field_annotation() -> None:
    canonical = "from cadrumo.core.i18n.translatable import Translatable as Token\n"
    field = "value: Token = Field(max_length=12)\n"
    assert sweep_source(canonical + field, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS) == []
    source = f"from unrelated import Token\ndef nested():\n    {canonical}{field}"
    assert any(
        f.startswith("field_length:")
        for f in sweep_source(source, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, owner="application/example.py")
    )


def test_calendar_day_wire_bound_requires_unchanged_domain_transfer() -> None:
    source = (
        "from cadrumo.domain.modelos.row_models import Modelo184MemberRow\n"
        "class Wire:\n    dias_miembro: int = Field(ge=0, le=366)\n"
        "    def to_row(self):\n        return Modelo184MemberRow(dias_miembro=self.dias_miembro)"
    )
    owner = "application/modelo/edit_apply_row_contracts.py"
    assert sweep_source(source, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, owner=owner) == []
    assert any(
        f.startswith("field_bound:")
        for f in sweep_source(
            source.replace("dias_miembro=self.dias_miembro", "dias_miembro=0"),
            modelos=_FAKE_MODELOS,
            periods=_FAKE_PERIODS,
            owner=owner,
        )
    )


@pytest.mark.parametrize(
    "source",
    [
        "_STATEMENT_WINDOW = 35\n",
        "_FILING_CAP: Final = 300\n",
        "_SEASONAL_MAX_DAYS: int = 180\n",
        "_FORM_ROWS = 18\n",
        "RATE_PERCENT = 19\n",
        "THRESHOLD = 12450.5\n",
        "_LIMIT = 3 * 13\n",
        "_LOOK = 5\nkept = rows[_LOOK:]\n",
        "_LOOK = 5\nkept = rows[:_LOOK]\nif len(rows) > _LOOK:\n    pass\n",
        "FIRST_FILING = 2017\n",
        "_MAX_DEDUCTION = 301\n",
        "_CASILLA_ROWS = 18\n",
        "_ACTIVITY_SLOTS = 6\n",
    ],
)
def test_a_module_level_number_no_rule_admits_is_a_finding(source: str) -> None:
    findings = sweep_source(source, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS)
    assert any(finding.startswith("module_value:") for finding in findings), findings


_REVIEWED_SHAPES = (
    "r = min(i, 12450)\n",
    "r = i - 5550\n",
    "r = i * 0.19\n",
    "r = i * 19 / 100\n",
    "def f(i, limit=12450):\n    pass\n",
    "class R:\n    LIMIT = 12450\n",
    "def f(i):\n    limit = 12450\n    return i > limit\n",
    "r = f(i, cap=12450)\n",
    "BRACKETS = (12450, 20200, 35200)\n",
    "RATES = {'general': 21}\n",
    "ok = year in (2023, 2024)\n",
    "years = range(2021, 2026)\n",
    "start = datetime(2023, 1, 1)\n",
    "later = day + timedelta(weeks=3)\n",
    "D = '2023-01-30'\n",
    "ok = kind == 'A'\n",
    "M = {'A': 1}\n",
    "kind: Literal['A', 'B']\n",
    "if turnover > 1000000:\n    pass\n",
    "ok = rent >= 50000\n",
    "amount: int = Field(le=4000)\n",
    "OTROS_GASTOS_REDUCCION = 2000\n",
    "rate = Decimal('0.1')\n",
    "SOLIDARITY_SURCHARGE_THRESHOLD = 5\n",
    "RESEARCH_DEDUCTION_RATE = 19\n",
    "REPORTED_INCOME_LIMIT = 300\n",
    "M303_TOLERANCE = 5\n",
    "ANNUAL_WORK_HOURS = 1826\n",
    "FILING_MODE = 3\n",
    "BOX_LIMIT = 30\n",
    "CUOTA_MINIMA = 365\n",
    "EJERCICIO_BASE = 2000\n",
    "PAYMENT_AMOUNT = 2000\n",
    "def f(i):\n    return 12450\n",
    "r = 300 if c else 0\n",
    "r = f(i, 12450)\n",
    "r = i + 12450.5\n",
    "r = max(i, 300)\n",
    "end = date(2023, 6, 30)\n",
    "end = datetime(year, 6, 30)\n",
    "later = day + timedelta(days=20)\n",
    "later = day + timedelta(20)\n",
    "RATES = {'reduced': 0.1}\n",
    "RATES = [0.19, 0.21]\n",
    "async def f(i, cap=300):\n    pass\n",
    "def f(i, *, cap=300):\n    pass\n",
    "class R:\n    def f(self):\n        self.limit = 12450\n",
    "ok = kind in ('A', 'B')\n",
    "ok = year == 2024\n",
    "ok = 'A' == kind\n",
    "kind: Literal['C']\n",
)


@pytest.mark.parametrize("source", _REVIEWED_SHAPES)
def test_a_reviewed_shape_is_a_finding(source: str) -> None:
    assert sweep_source(source, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS), source


_REVIEWED_WIDTHS = (
    "short = text[:40]\n",
    "wide = text.ljust(40)\n",
    "wide = text.rjust(13)\n",
    "wide = text.zfill(9)\n",
    "_Name = Annotated[str, StringConstraints(max_length=40)]\n",
)


@pytest.mark.parametrize("owner", ["domain/modelos/row_models.py", "application/filing/draft_construction.py"])
@pytest.mark.parametrize("source", _REVIEWED_WIDTHS)
def test_a_width_where_a_value_goes_to_a_form_is_a_finding(source: str, owner: str) -> None:
    findings = sweep_source(source, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, owner=owner)
    assert any(finding.startswith("form_width:") for finding in findings), findings


@pytest.mark.parametrize(
    "source",
    [
        "ms = timeout_ms / 1000\n",
        "whole = amount / 100\n",
        "double = amount * 2\n",
        "lead = rows[:3]\n",
        "chunk = recv(min(4096, left))\n",
        "await sleep(0.5)\n",
        "path.mkdir(mode=0o700)\n",
        "_FILE_MODE = 0o600\n",
        "ok = status in (401, 403)\n",
        "ok = 'A' <= char\n",
        "score = value.quantize(Decimal('0.1'))\n",
        "note: str = Field(max_length=2000)\n",
        "_NOTE = 2000\nnote: str = Field(max_length=_NOTE)\n",
        "days = 366 if calendar.isleap(year) else 365\n",
        "_DAYS_OF_A_YEAR = 365\n",
        "MONTHS_PER_YEAR = 12\n",
        "ok = token == 'X'\n",
        "flag: Literal['S', 'N']\n",
        "ok = 1000 <= int(raw) <= 9999\n",
        "timeout_ms: int = Field(ge=1000, le=131072)\n",
        "later = monotonic() + 60\n",
    ],
)
def test_a_number_that_only_does_mechanics_stays_admitted(source: str) -> None:
    assert sweep_source(source, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS) == []


@pytest.mark.parametrize(
    ("source", "owner"),
    [
        ("score = value.quantize(Decimal('3.5'))\n", ""),
        ("_NOTE = 2000\nok = amount > _NOTE\n", ""),
        ("ok = amount > 12\n", ""),
        ("clave = 'X'\n", ""),
        ("ok = kind != 'A'\n", "domain/calculations/registry/rates.py"),
        ("ok = raw in {' ', 'C'}\n", "domain/calculations/registry/export_parse.py"),
    ],
)
def test_the_narrow_rules_do_not_reach_past_what_they_describe(source: str, owner: str) -> None:
    assert sweep_source(source, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, owner=owner), source


@pytest.mark.parametrize(
    "source",
    [
        "r = i - 5\n",
        "x = rows[3]\n",
        "LETTER = 'A'\n",
        "class Kind(StrEnum):\n    ENTREGA = 'E'\n",
        "_RECTIFICATION_WINDOW_MONTHS = 12\n",
        "if elapsed_days > 30:\n    pass\n",
        "if months >= 12:\n    pass\n",
        "def f():\n    return 10\n",
        "r = 100 if c else 10\n",
        "class T(IntEnum):\n    GENERAL = 10\n",
        "r = x * Decimal('0.01')\n",
        "ok = kind == 'AB'\n",
        "r = 'A' if x else 'B'\n",
        "def f(value):\n    return value.isdigit() and len(value) == 18\n",
    ],
)
def test_the_stated_limit_of_the_sweep_holds(source: str) -> None:
    """Pins what the module docstring says the sweep cannot see, so the statement stays true."""
    assert sweep_source(source, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS) == []


@pytest.mark.parametrize(
    "source",
    [
        "r = i * 0.19\n",
        "r = min(i, 12450)\n",
        "_LIMIT = 12450\n",
        "kind: Literal['A']\n",
        "ok = kind == 'A'\n",
    ],
)
def test_the_stated_limit_of_a_layout_owner_holds(source: str) -> None:
    owner = "entrypoints/tui/ledger/x.py"
    assert sweep_source(source, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, owner=owner) == []


@pytest.mark.parametrize(
    "source",
    [
        "MAX_AMORTIZATION_YEARS = 30\n",
        "_PLAZO_DIAS = 30\n",
        "_RETENTION_YEAR = 12\n",
        "INCOME_PREVIEW_LIMIT = 12450\n",
        "DEDUCTION_STATUS = 2000\n",
        "REDUCCION_GAP = 2000\n",
        "RATE_SUMMARY = 21\n",
        "TIPO_DISPLAY = 21\n",
        "LIMIT_S = 12450\n",
        "CAP_POINTS = 2000\n",
        "DEDUCTION_VERSION = 21\n",
        "TIPO = 16\n",
        "_MINIMUM = 64\n",
        "RENTA_LINES = 18\n",
        "MODELO_ID_LIMIT = 300\n",
        "amount_s: int = Field(le=300)\n",
    ],
)
def test_a_fact_word_outranks_a_unit_or_a_mechanic(source: str) -> None:
    assert sweep_source(source, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS), source


@pytest.mark.parametrize(
    "source", ["RATE_SUMMARY = 21\n", "def f(deduction=300):\n    pass\n", "RATES = {'tipo': 21}\n"]
)
def test_a_tax_word_is_read_in_an_owner_that_only_lays_values_out(source: str) -> None:
    owner = "entrypoints/tui/ledger/x.py"
    assert sweep_source(source, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, owner=owner), source


@pytest.mark.parametrize(
    "source",
    [
        "if period.casilla == '0208':\n    pass\n",
        "if work.modelo_box == '0208':\n    pass\n",
        "box_token = '0208'\n",
        "PERIOD_BOX = '0208'\n",
        "revision_id_box = '0208'\n",
        "ok = modelo in ('303',)\n",
        "ok = modelo in ['303']\n",
        "_IVA_MODELO = '303'\n",
        "_IVA = Modelo('303')\n",
        "def f(x):\n    iva = Modelo('303')\n    return x == iva\n",
    ],
)
def test_an_address_is_read_on_the_literals_own_side(source: str) -> None:
    assert sweep_source(source, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS), source


@pytest.mark.parametrize(
    "source",
    [
        "i -= 5550\n",
        "i *= 0.19\n",
        "total += 300\n",
        "r = i or 12450\n",
        "(cap := 12450)\n",
        "f = lambda i, cap=12450: i\n",
        "def g():\n    yield 12450\n",
        "def g():\n    for i in range(18):\n        pass\n",
        "r = rows[18]\n",
        "r = sum(rows[:18])\n",
        "year: Literal[2023, 2024]\n",
        "rate: Literal[21, 10, 4]\n",
        "TABLE = {2023: 300, 2024: 400}\n",
        "threshold: int = Field(default=12450)\n",
        "threshold: int = Field(12450)\n",
        "amount: Decimal = Field(default_factory=lambda: 12450)\n",
        "r = f(i, base=12450)\n",
        "r = f(i, default=12450)\n",
        "r = f(i, count=18)\n",
        "r = f(i, start=12450)\n",
        "r = getattr(x, 'cap', 12450)\n",
        "r = int(12450)\n",
        "r = int('12450')\n",
        "CAP = float('300.51')\n",
        "LIMIT = '300.51'\n",
        "RATES = {'general': '0.21'}\n",
        "from decimal import Decimal as D\ncap = D('300.51')\n",
        "cap = decimal.Decimal('300.51')\n",
        "cap = Decimal(value='300.51')\n",
        "rate = x * 4 / Decimal(100)\n",
        "rate = x * 4 // 100\n",
        "rate = x / 100 * 4\n",
        "rate = x * (4 / 100)\n",
        "x = Fraction(19, 100)\n",
        "due = date(year=2024, month=6, day=30)\n",
        "due = d.replace(month=6, day=30)\n",
        "due = d.replace(month=7)\n",
        "DEADLINE = '07-30'\n",
        "DEADLINE = '30/06/2024'\n",
        "DEADLINE = '20240630'\n",
        "box = 'casilla_0208'\n",
        "box = 'M303'\n",
        "box = f'casilla_{208}'\n",
        "_BOXES = '0208,0209'.split(',')\n",
        "if income > 1900:\n    pass\n",
        "if rent > 9999:\n    pass\n",
        "if edad < 16:\n    pass\n",
        "if turnover >= 1024:\n    pass\n",
        "edad: int = Field(ge=16)\n",
        "rate: int = Field(ge=1, le=12)\n",
        "tipo: int = Field(ge=1, le=31)\n",
        "clave: int = Field(ge=1, le=7)\n",
        "rate = min(i, 64)\n",
        "_FORM_ROWS = 18\nkept = rows[:_FORM_ROWS]\n",
        "rows: tuple[int, ...] = Field(max_length=2000)\n",
        "_ROWS = 40000\nrows: tuple[int, ...] = Field(max_length=_ROWS)\n",
        "ok = kind in 'AE'\n",
        "match kind:\n    case 'A':\n        pass\n",
        "ok = kind.startswith('A')\n",
        "def _row_modelo_code(rows):\n    return len(rows) == 18\n",
        "def _rows_yyyymmdd(rows):\n    return len(rows) == 18\n",
        "def _modelo_code(raw):\n    return len(raw) != 18\n",
        "r = i % 300\n",
        "_RATE = +21\n",
    ],
)
def test_a_shape_a_value_could_hide_in_is_a_finding(source: str) -> None:
    assert sweep_source(source, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS), source


@pytest.mark.parametrize(
    "source",
    [
        "r = i * 0.19\n",
        "r = min(i, 12450)\n",
        "RATES = {'general': 21}\n",
        "_LIMIT = 12450\n",
        "if income > 12450:\n    pass\n",
        "r = i - 5550\n",
    ],
)
@pytest.mark.parametrize(
    "owner", ["application/storage/calc_sheets/engine.py", "application/modelo/reconciliation_export.py"]
)
def test_a_workbook_module_is_read_as_any_other(source: str, owner: str) -> None:
    assert sweep_source(source, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, owner=owner), source


@pytest.mark.parametrize(
    "source",
    [
        "_EUR_VALUE_COLUMN = 9\n",
        "_VIEW_ROWS = 1000\n",
        "_DATA_WIDTHS = ((1, 30), (2, 52))\n",
        "def _column_width(header):\n    return 60\n",
        "def height(text):\n    return max(44, 20 * (len(text) + 99))\n",
        "protect(start_row=1, end_row=1000)\n",
        "for wrap_col in (12, 15, 16):\n    pass\n",
    ],
)
def test_a_workbook_module_holds_its_measures_under_names_that_say_so(source: str) -> None:
    owner = "application/storage/calc_sheets/engine.py"
    assert sweep_source(source, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, owner=owner) == []


@pytest.mark.parametrize(
    "source",
    [
        "site_rate_limit_retry_after = 3\n",
        "CADRUMO_RUNS_RETENTION_DAYS = 30\n",
        "business_total: str = '0.00'\n",
        "income_total: str = '0.00'\n",
        "moment = d.replace(month=2, day=28)\n",
        "for month in range(1, 13):\n    pass\n",
        "_MAX_LEDGER_IMPORT_ROWS = 4096\n",
        "_FILE_NAME_MAX_LENGTH = 255\n",
        "_SCHEMA_VERSION = 3\n",
        "def f(version: Literal[2]):\n    pass\n",
        "ok = 'ES' in countries\n",
    ],
)
def test_a_word_in_another_sense_is_not_a_finding(source: str) -> None:
    assert sweep_source(source, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS) == []


@pytest.mark.parametrize(
    ("source", "owner"),
    [
        ("_TIMEOUT_SECONDS = 37\n", ""),
        ("_POLL_MS: Final = 37\n", ""),
        ("_MAX_RESULT_BYTES = 61440\n", ""),
        ("_WORK_ATTEMPTS = 3\n", ""),
        ("_SCHEMA_VERSION = 3\n", ""),
        ("_CAPACITY = 1024\n", ""),
        ("_PAYLOAD = 64 * 1024\n", ""),
        ("ZERO = 0\n", ""),
        ("DAYS_IN_A_WEEK = 7\n", ""),
        ("LAST_CALENDAR_YEAR = 2100\n", ""),
        ("_VIEW = 5\nkept = rows[:_VIEW]\n", ""),
        ("_RARELY_CHANGING_FRESHNESS_DAYS = 90\n", ""),
        ("_MAX_CASILLAS_IN_MESSAGE = 8\n", ""),
        ("_GRID_LEAD = 3\n", "entrypoints/tui/modelo/workbench/grid.py"),
        ("_WIN_ERROR = 206\n", "core/windows_job_object.py"),
    ],
)
def test_a_module_level_number_a_rule_admits_is_not_a_finding(source: str, owner: str) -> None:
    assert sweep_source(source, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, owner=owner) == []


def test_a_mechanics_owner_may_not_hold_a_decimal_tax_value() -> None:
    owner = "entrypoints/tui/modelo/workbench/grid.py"
    findings = sweep_source("cap = Decimal('300.51')\n", modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, owner=owner)
    assert findings == ["decimal:'300.51'@1"]


@pytest.mark.parametrize(
    "module", ["producer_snapshot_m360", "producer_snapshot", "withholding_bindings", "_modelo_bindings_invoice_iva"]
)
@pytest.mark.parametrize(
    "source",
    [
        "_Digits = Annotated[str, StringConstraints(pattern=r'^\\d{5}$')]\n",
        "_Digits = Annotated[str, StringConstraints(pattern=r'^\\d{1,9}$')]\n",
        "CODE = re.compile(r'^[A-Z0-9]{4}$')\n",
        "tax_id: str = Field(min_length=9, max_length=9)\n",
        "name: str = Field(max_length=25)\n",
        "_Text = Annotated[str, _text(148)]\n",
        "def check(value: str):\n    return len(value) == 9\n",
        "def check(value: str):\n    return len(value) in (9,) or len(value) > 12\n",
    ],
)
def test_a_width_in_a_module_that_hands_values_to_a_form_is_a_finding(module: str, source: str) -> None:
    findings = sweep_source(source, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, module=module)
    assert any(finding.startswith("form_width:") for finding in findings), findings


@pytest.mark.parametrize(
    "source",
    [
        "_Digits = Annotated[str, StringConstraints(pattern=r'^\\d+$', max_length=16)]\n",
        "name: str = Field(min_length=1, max_length=256)\n",
        "digest: str = Field(pattern=r'^[0-9a-f]{64}$')\n",
        "_FourDigitYear = Annotated[str, StringConstraints(pattern=r'^\\d{4}$')]\n",
        "def parse(raw: str):\n    parts = raw.split('.')\n    return len(parts) == 3\n",
        "rows: tuple[int, ...] = Field(min_length=1)\n",
    ],
)
def test_a_module_that_hands_values_to_a_form_keeps_its_technical_bounds(source: str) -> None:
    findings = sweep_source(source, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, module="producer_snapshot_m360")
    assert not [finding for finding in findings if finding.startswith("form_width:")], findings


def test_the_same_width_is_lexical_in_a_module_no_form_reads_from() -> None:
    source = "_Digits = Annotated[str, StringConstraints(pattern=r'^\\d{5}$')]\n"
    assert sweep_source(source, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, module="document_grammar") == []


def test_a_module_named_for_one_form_may_name_that_form_and_no_other() -> None:
    line = "box = '303'\nother = '111'\n"
    findings = sweep_source(line, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, module="m303_arrivals")
    assert sorted(findings) == ["code:'111'@2", "named_form:'other=111'@2"]


def test_a_machine_owner_may_compare_sizes_but_not_hold_a_tax_value() -> None:
    assert sweep_source("ok = status == 404\n", modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, machine=True) == []
    findings = sweep_source("cap = Decimal('300.51')\n", modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, machine=True)
    assert findings == ["decimal:'300.51'@1"]


def test_a_defect_added_to_a_copied_tree_is_found(tmp_path: Path) -> None:
    source = _SRC / "domain" / "period.py"
    copy = tmp_path / "domain" / "period.py"
    copy.parent.mkdir(parents=True)
    copy.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    modelos, periods = _modelo_ids(), _period_codes()
    clean = sweep_tree(tmp_path, modelos=modelos, periods=periods)

    with copy.open("a", encoding="utf-8") as handle:
        handle.write("\n_INSTALMENT_CAP = Decimal('300.51')\n")

    found = sweep_tree(tmp_path, modelos=modelos, periods=periods)["domain/period.py"]
    assert set(found) - set(clean.get("domain/period.py", ())) == {
        f"decimal:'300.51'@{len(copy.read_text(encoding='utf-8').splitlines())}"
    }


_STRICT_FORM_READERS = frozenset(
    {
        "resolve_form_codes",
        "form_for_role",
        "forms_for_role",
        "periodic_withholding_modelos",
        "invoice_evidence_modelos",
        "ledger_payment_modelos",
    }
)

_VALIDATOR_DECORATORS = frozenset({"field_validator", "model_validator"})


def _strict_reads_in_validators(tree: ast.AST) -> list[tuple[int, str]]:
    """Return strict form-fact reads inside Pydantic validators, which a scope-free client also runs."""
    found: list[tuple[int, str]] = []
    for function in ast.walk(tree):
        if not isinstance(function, ast.FunctionDef):
            continue
        decorators = {_reader_name(n) for d in function.decorator_list for n in ast.walk(d)}
        if decorators & _VALIDATOR_DECORATORS:
            found += [
                (call.lineno, function.name)
                for call in ast.walk(function)
                if isinstance(call, ast.Call) and _reader_name(call.func) in _STRICT_FORM_READERS
            ]
    return found


def test_the_validator_rule_finds_a_strict_read() -> None:
    source = """
class M(BaseModel):
    @model_validator(mode="after")
    def _v(self):
        resolve_form_codes("x")
        return self
"""
    assert _strict_reads_in_validators(ast.parse(source)) == [(5, "_v")]
    assert _strict_reads_in_validators(ast.parse("def f():\n    resolve_form_codes('x')\n")) == []


def test_no_validator_turns_a_valid_client_result_into_an_error() -> None:
    src = Path(__file__).resolve().parents[3] / "src"
    findings = [
        f"{path}:{line} {name}"
        for path in src.rglob("*.py")
        if "tests" not in path.parts
        for line, name in _strict_reads_in_validators(ast.parse(path.read_text(encoding="utf-8")))
    ]
    assert not findings, "\n".join(findings)


def test_the_tax_code_holds_no_tax_literal() -> None:
    found = _current()
    listing = "\n".join(f"{path}: {entry}" for path, entries in sorted(found.items()) for entry in entries)
    assert not found, f"a tax value belongs to the registry:\n{listing}"
