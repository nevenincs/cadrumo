"""The year gate finds each kind of year written into code and admits what is not one.

Each planted defect stands in an isolated source text or a copied tree, so the
proof does not depend on what the repository holds today. A planted edition id
is built from the running year rather than spelled, because this module is
itself read by the gate it proves.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from dev.quality.typescript_text_blanking import blank_text
from dev.quality.year_literal_python import python_findings
from dev.quality.year_literal_typescript import typescript_findings
from dev.quality.year_literals import governed_sources, main, scan

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_YEAR = datetime.now(UTC).year


def _python_rules(source: str) -> list[str]:
    return [finding.rule for finding in python_findings(source, "planted.py")]


@pytest.mark.parametrize(
    ("planted", "rule"),
    [
        ("if year < 2022:\n    raise ValueError\n", "year compared"),
        ("if 2000 <= row.filing_year <= 2099:\n    pass\n", "year compared"),
        ("ok = result.as_of_year == 2028\n", "year compared"),
        ("if value < 1900 or value > 9999:\n    raise ValueError\n", "year compared"),
        ("ok = revision.año == 2025\n", "year compared"),
        ("MIN_YEAR = 2022\n", "year bound"),
        ("LAST_YEAR: int = 2100\n", "year bound"),
        ("_FILING_YEAR = 2025\n", "year bound"),
        ("floor = 2022\n", "year bound"),
        ("filing_year: int = Field(ge=2000)\n", "year bound"),
        ("class Row:\n    tax_year: Annotated[int, Field(le=2099)]\n", "year bound"),
        ("def build(filing_year: int = 2025) -> None:\n    pass\n", "year bound"),
        ("def build(*, ejercicio: int = 2025) -> None:\n    pass\n", "year bound"),
        ("work = create_work(modelo='303', filing_year=2025)\n", "year bound"),
        ("row = {'ejercicio': 2025}\n", "year bound"),
        ("self.year = 2026\n", "year bound"),
        ("period = Period.from_year_and_code(2025, '1T')\n", "year argument"),
        ("window = resolve_filing_window(authority, 2026)\n", "year argument"),
        ("unit = _work(2025, '4T')\n", "year argument"),
        ("cases = [pytest.param(2025, '0A')]\n", "year argument"),
        ("previous = year - 2020\n", "year arithmetic"),
        ("SUPPORTED = (2022, 2023, 2024)\n", "year list"),
        ("for year in range(2022, horizon):\n    pass\n", "year list"),
        ("RATES = {2024: rate_a, 2025: rate_b}\n", "year list"),
        ("start = date(2025, 1, 1)\n", "year date"),
        ("now = datetime(2026, 10, 7, 12, tzinfo=UTC)\n", "year date"),
        ("when = dt.date(year=2025, month=3, day=1)\n", "year date"),
        ("day = date.fromisoformat('2025-03-01')\n", "year date"),
        ("CLOCK = datetime.fromisoformat('2026-04-01T09:00:00+00:00')\n", "year date"),
        ("when = datetime.strptime('01/04/2026', '%d/%m/%Y')\n", "year date"),
        ("when = parser.isoparse('2026-04-01T09:00Z')\n", "year date"),
        ("when = parse_iso_instant(text='2026-04-01T09:00:00Z')\n", "year date"),
        ("FIXTURE_TODAY = '2026-10-06'\n", "date text"),
        ("stamp = '2026-03-02T10:00:00Z'\n", "date text"),
        ("month = '2026-03'\n", "date text"),
        ("day = '02/03/2026'\n", "date text"),
        ("row = build_row(fecha='2026-03-02')\n", "date text"),
        ("def f(today: str = '2026-03-02') -> None:\n    pass\n", "date text"),
        ("cases = [('2026-03-02', 3)]\n", "date text"),
        ("payload = {'issued_on': '2026-03-02'}\n", "date text"),
        ("day = f'2026-03-{day:02d}'\n", "date text"),
        ("PERIOD = '2026-2T'\n", "period text"),
        ("period = Period.from_string('2026 1T')\n", "period text"),
        ("work = create_work(period='2026-0A')\n", "period text"),
        ("rows = {'period': '2026-4P'}\n", "period text"),
        ("quarter = '2026Q1'\n", "period text"),
        ("scheme = '2026-EXT-3T'\n", "period text"),
        ("event = '2026-EVENT-2'\n", "period text"),
        ("month = '2026 03'\n", "period text"),
        ("def f(period: str = '2026:4T') -> None:\n    pass\n", "period text"),
        ("key = f'2026-{code}'\n", "period text"),
        ("label = f'2026 1T {suffix}'\n", "period text"),
        ("ejercicio = '2025'\n", "year text"),
        ("expected = {'year': '2026'}\n", "year text"),
        # Casilla-looking places that hold a year: a casilla helper's revision argument,
        # a time word in the casilla name, a value under a casilla key, a box word.
        ("rows = casilla('2024', '0001', number='1')\n", "year text"),
        ("rows = edition_casilla('2023', '0002')\n", "year text"),
        ("write(manifest, casilla_storage_baseline='2024')\n", "year text"),
        ("rows = casillas_by_revision['2024']\n", "year text"),
        ("casilla_year = '2025'\n", "year text"),
        ("_CASILLA_REVISION = '2025'\n", "year text"),
        ("ok = snapshot.revision.id == '2025'\n", "year text"),
        ("ok = revision.id in {'2022', '2023'}\n", "year text"),
        ("payload = build(input_values_by_casilla_id={_EJERCICIO_CASILLA: '2024'})\n", "year text"),
        ("EXPECTED = {M840_EJERCICIO_CASILLA: '2024'}\n", "year text"),
        ("ejercicio_casilla_id = '2024'\n", "year text"),
        ("disposition = Disposition(box_retired_in='2023')\n", "year text"),
        ("label = expected_labels['2038']\n", "year text"),
        ("ids = {'2022', '2023'}\n", "year text"),
        ("casilla_id = validated_casilla_id(revision_id='2024')\n", "year text"),
        ("ok = casilla.id == number and year == '2025'\n", "year text"),
        (f"revision = '{_YEAR}-y-siguientes'\n", "edition id"),
        (f"revision = '{_YEAR}-{_YEAR + 1}'\n", "edition id"),
        (f"revision = '{_YEAR}-desde-09-y-3t'\n", "edition id"),
        (f"path = 'modelos/303/revisions/{_YEAR}/revision.toml'\n", "edition id"),
        (f"path = f'modelos/{{modelo}}/revisions/{_YEAR}-y-siguientes'\n", "edition id"),
    ],
)
def test_a_planted_python_year_is_found(planted: str, rule: str) -> None:
    assert rule in _python_rules(planted)


@pytest.mark.parametrize(
    "allowed",
    [
        '"""Since 2022 the edition changed; see the 2026 design."""\n',
        'def f() -> None:\n    """The 2025 edition."""\n',
        "# years before 2022 carry no edition\nx = 1\n",
        "citation = 'Ley 58/2003, art. 122.1'\n",
        "order = 'Orden HAC/1417/2023'\n",
        "boe = 'BOE-A-2023-12345'\n",
        "source = 'aeat-dr-190-2024'\n",
        "assert stamp == '2026-03-02T10:00:00Z'\n",
        "assert day in ('2026-03-02', '2026-03-03')\n",
        "assert payload == {'issued_on': '2026-03-02'}\n",
        "match day:\n    case '2026-03-02':\n        pass\n",
        "note = 'filed on 2026-03-02 by the operator'\n",
        "assert str(period) == '2026 1T'\n",
        "assert key in ('2026-1T', '2026-2T')\n",
        "note = 'the 2026 1T return is late'\n",
        "key = f'{year}-{code}'\n",
        "label = f'{period.filing_year} {period.code}'\n",
        "when = datetime.fromisoformat(stamp)\n",
        "when = date(horizon, 4, 1).isoformat()\n",
        'def f() -> None:\n    """Filed on 2026-03-02."""\n',
        "url = 'https://sede.example/2025/form'\n",
        "_MAX_ROWS = 2000\n",
        "if len(rows) < 2048:\n    pass\n",
        "if request.secret_bytes > 2048:\n    pass\n",
        "if len(redirects) - dynamic > 2000:\n    pass\n",
        "if year < support.floor:\n    pass\n",
        "_ARCHIVE_EPOCH = (1980, 1, 1)\n",
        "epoch = datetime(1970, 1, 1, tzinfo=UTC)\n",
        "RANGES = ((0x2027, 0x2035), (0x2045, 0x2045))\n",
        "bases = (Decimal('2000'), Decimal('2500'))\n",
        "_FULL_CONSOLIDATED_SIZE_FLOOR = 5000\n",
        "amount = Money(2025)\n",
        "start = date(year, 3, 1)\n",
        "start = date(support.floor, 1, 1)\n",
        "period = Period.from_year_and_code(newest_authored_edition('303'), '1T')\n",
        "filing_year: FilingYear\n",
    ],
)
def test_what_is_no_python_year_coordinate_is_admitted(allowed: str) -> None:
    assert python_findings(allowed, "allowed.py") == []


@pytest.mark.parametrize(
    "casilla",
    [
        "parent = validated_casilla_id('2003')\n",
        "parent = validated_casilla_id(value='2057', surface='casilla.id')\n",
        "values = validated_casilla_id_map({'2038': amount, '2039': rest})\n",
        "PARENT: CasillaId = '2030'\n",
        "PARENT: Final[CasillaId] = '2030'\n",
        "PENDING: tuple[CasillaId, ...] = ('2022', '2023')\n",
        "VALUES: Mapping[CasillaId, Decimal] = {'2031': Decimal(1)}\n",
        "def f(target: CasillaId = '2032') -> None:\n    pass\n",
        "def f(casilla_id: str = '2032') -> None:\n    pass\n",
        "row = observe(casilla_id='2038', value=amount)\n",
        "row = observe(casilla_ids=('2038', '2039'))\n",
        "query = ReferenceQuery(modelo='100', casilla='2003')\n",
        "draft = build(input_values_by_casilla_id={'2003': amount})\n",
        "_PARENT_CASILLA = '2030'\n",
        "expected_casilla_ids = {'2022', '2023', '2030'}\n",
        "casilla_values = {'2003': Decimal(1), '2004': Decimal(2)}\n",
        "payload = {'casilla_id': '2057'}\n",
        "parent = casillas_by_id['2003']\n",
        "parent = revision.casillas_by_id['2003']\n",
        "ok = row.casilla_id == '2038'\n",
        "ok = '2038' == row.casilla_id\n",
        "found = [casilla for casilla in revision.casillas if casilla.id in {'2003', '2004'}]\n",
        "assert revision.casillas[0].id == '2057'\n",
        "assert set(casillas_by_id) == {'1055', '2038', '2039'}\n",
        "assert sorted(casilla_ids) == ['2038', '2039']\n",
    ],
)
def test_a_casilla_id_the_code_places_as_one_is_no_year(casilla: str) -> None:
    assert python_findings(casilla, "casilla.py") == []


def test_a_casilla_place_admits_only_its_casilla_ids_and_not_the_years_beside_them() -> None:
    source = (
        "row = observe('2025', casilla_id='2038', ejercicio='2025')\n"
        "values = {'casilla_id': '2003', 'ejercicio': '2026'}\n"
        "draft = build(input_values_by_casilla_id={'2003': '2024'})\n"
        "pending = casillas_by_id['2039'], editions['2024']\n"
    )

    assert [(finding.line, finding.text) for finding in python_findings(source, "mixed.py")] == [
        (1, "'2025'"),
        (2, "'2026'"),
        (3, "'2024'"),
        (4, "'2024'"),
    ]


def _typescript_rules(source: str) -> list[str]:
    return [finding.rule for finding in typescript_findings(source, "planted.ts")]


@pytest.mark.parametrize(
    ("planted", "rule"),
    [
        ("if (year < 2022) return null;", "year compared"),
        ("const late = row.tax_year >= 2026;", "year compared"),
        ("if (2099 < year) invalid();", "year compared"),
        ("if (year === 2026) return [];", "year compared"),
        ("const shown = `${year > 2025 ? 'later' : 'now'}`;", "year compared"),
        ("const capped = Math.min(year, 2025);", "year clamped"),
        ("const FIRST_SUPPORTED_YEAR = 2022;", "year constant"),
        ("const [firstYear = 1970] = parts;", "year constant"),
        ("export const YEAR_MAX: number = 2200;", "year constant"),
        ("const Y = 2026;", "year constant"),
        ("const ask = (series: string, year = 2026) => series;", "year constant"),
        ("const row = { tax_year: 2025, code: '1T' };", "year constant"),
        ("const row = { ejercicio: 2025 };", "year constant"),
        ('export const Claim = claiming("furgoneta", 2027, {});', "year argument"),
        ("const boxes = servedHandoffOf(2025)!;", "year argument"),
        ('await choosePeriod(target, 2026, "3T");', "year argument"),
        ("expect(stepYear(2026, 1)).toBe(next);", "year argument"),
        ("expect(row.tax_year).toBe(2022);", "year expected"),
        ("expect(served.default_year).toBe(2026);", "year expected"),
        ("expect(first).not.toEqual(2025);", "year expected"),
        ("expect(row.tax_year).toBeGreaterThanOrEqual(2022);", "year expected"),
        ("const NOW = new Date(2026, 9, 30, 12, 0, 0);", "year date"),
        ("const START = Date.UTC(2026, 2, 2);", "year date"),
        ('const at = Date.parse("2026-01-12T00:00:00Z");', "year date"),
        ('const at = new Date("2026-01-12");', "year date"),
        ('const at = DateTime.fromISO("2026-01-12");', "year date"),
        ('await page.clock.install({ time: new Date("2026-11-02T12:00:00Z") });', "year date"),
        ('export const FIXTURE_TODAY = "2026-10-06";', "date text"),
        ("const BUSY_TODAY = '2027-01-12';", "date text"),
        ('const row = { today: "2026-03-02T10:00:00Z" };', "date text"),
        ('const month = "2026-03";', "date text"),
        ("const day = `2026-03-${pad(day)}`;", "date text"),
        ('seed(store, "2026-03-02");', "date text"),
        ('const PERIOD = "2026-2T";', "period text"),
        ("const row = { period: '2026-0A' };", "period text"),
        ('await choose(target, "2026 4T");', "period text"),
        ("const key = `2026-${code}`;", "period text"),
        ("const key = `2026-1T-${suffix}`;", "period text"),
        ("const edition = { projected: year > horizon };", "edition worked out"),
        ("const edition = { revision_id: String(Math.min(year, last)) };", "edition worked out"),
        ("const behind = row.edition.authored_filing_year < year;", "edition worked out"),
        ("const gap = year - row.edition?.authored_filing_year;", "edition worked out"),
        ("const id = '2025';", "year text"),
        ('const id = "2026";', "year text"),
        (f"const revision = '{_YEAR}-y-siguientes';", "edition id"),
        (f'const path = "modelos/303/revisions/{_YEAR}/revision.toml";', "edition id"),
    ],
)
def test_a_planted_typescript_year_is_found(planted: str, rule: str) -> None:
    source = f"// a planted defect\nexport function sample(year: number) {{\n  {planted}\n}}\n"

    assert rule in _typescript_rules(source)


@pytest.mark.parametrize(
    "clean",
    [
        'const label = "Since 2000, or before 2022";',
        "// years before 2022 carry no edition",
        "/* the 2026 design */",
        "if (servedAdmits(year) && !servedBeyondLastAdmitted(year)) years.push(year);",
        "if ([...words].length <= 2048) keep(words);",
        "const edition = servedEditionOf(year);",
        'expect(row.date).toBe("2026-03-02");',
        'expect(row).toEqual({ day: "2026-03-02", at: "2026-03-02T10:00:00Z" });',
        'if (row.date === "2026-03-02") return;',
        'const late = "2026-03-02" !== row.date;',
        'switch (day) { case "2026-03-02": break; }',
        'const label = "Filed on 2026-03-02 by the operator";',
        'expect(row.period).toBe("2026-2T");',
        'if (key === "2026 1T") return;',
        'const label = "The 2026 1T return is late";',
        "const key = `${year}-${code}`;",
        "const at = Date.parse(served.today);",
        "const when = `${year}-01-01`;",
        "const amount = 2026.5 > total;",
        "const first = Number(range.from_date.slice(0, 4));",
        "export const MAX_ANSWER_CHARS = 2048;",
        'await notes.fill(" ".repeat(2049));',
        "const wide = columnLayout(columns, 16, 2000);",
        "const scenarioYear = Number(TODAY.slice(0, 4));",
        "await choosePeriod(target, scenarioYear - 1, code);",
        "expect(answer.length).toBe(2048);",
        'expect(await list.locator(".record").count()).toBe(2000);',
        "  .toBeGreaterThan(2000);",
        "expect(served.default_year).toBe(scenarioYear);",
        "const day = new Date(1970, 0, 4 + column);",
        "const date = new Date(0);",
        'const citation = "Ley 58/2003";',
    ],
)
def test_served_reads_text_and_counts_are_not_typescript_findings(clean: str) -> None:
    source = f"export function sample(year: number) {{\n  {clean}\n}}\n"

    assert typescript_findings(source, "clean.ts") == []


def test_a_date_inside_a_multiline_expectation_is_compared_and_one_after_it_is_not() -> None:
    source = 'expect(rows).toEqual([\n  { day: "2026-03-02" },\n]);\nconst TODAY = "2026-03-02";\n'

    assert [(finding.line, finding.rule) for finding in typescript_findings(source, "rows.ts")] == [(4, "date text")]


def test_an_unpaired_jsx_apostrophe_hides_no_later_finding_and_keeps_line_numbers() -> None:
    source = "export const Note = () => (\n  <p>Don't file twice</p>\n);\nif (year < 2022) refuse();\n"

    assert blank_text(source).count("\n") == source.count("\n")
    assert [(finding.line, finding.rule) for finding in typescript_findings(source, "planted.tsx")] == [
        (4, "year compared")
    ]


def test_an_unparseable_module_is_a_finding_not_a_pass() -> None:
    assert _python_rules("def broken(:\n") == ["unreadable"]


def _tree(root: Path, files: dict[str, str]) -> None:
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def test_a_defect_planted_in_a_copied_tree_is_found_wherever_it_stands(tmp_path: Path) -> None:
    clean = "def f(year: int) -> int:\n    return year\n"
    _tree(
        tmp_path,
        {
            "src/cadrumo/application/thing.py": clean,
            "src/cadrumo/application/tests/test_thing.py": clean,
            "dev/tool.py": clean,
            "native/desktop/frontend/src/view.ts": "export const view = (year: number) => year;\n",
        },
    )
    assert list(scan(tmp_path)) == []

    _tree(
        tmp_path,
        {
            "src/cadrumo/application/thing.py": clean + "FLOOR_YEAR = 2022\n",
            "src/cadrumo/application/tests/test_thing.py": clean + "start = date(2025, 1, 1)\n",
            "dev/tool.py": clean + "SUPPORTED = (2024, 2025)\n",
            "native/desktop/frontend/src/view.ts": "export const view = (year: number) => year < 2022;\n",
        },
    )
    assert sorted((finding.path, finding.rule) for finding in scan(tmp_path)) == [
        ("dev/tool.py", "year list"),
        ("native/desktop/frontend/src/view.ts", "year compared"),
        ("src/cadrumo/application/tests/test_thing.py", "year date"),
        ("src/cadrumo/application/thing.py", "year bound"),
    ]


def test_only_the_authority_data_root_is_not_read(tmp_path: Path) -> None:
    _tree(
        tmp_path,
        {
            "src/cadrumo/_data/registry/years.py": "HORIZON_YEAR = 2026\n",
            "src/cadrumo/data/years.py": "HORIZON_YEAR = 2026\n",
            "docs/_data/years.py": "HORIZON_YEAR = 2026\n",
        },
    )

    assert governed_sources(tmp_path) == ["docs/_data/years.py", "src/cadrumo/data/years.py"]
    assert {finding.path for finding in scan(tmp_path)} == {"docs/_data/years.py", "src/cadrumo/data/years.py"}


def test_the_gate_fails_on_a_finding_and_passes_a_clean_tree(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _tree(tmp_path, {"dev/tool.py": "def f(year: int) -> int:\n    return year\n"})
    assert main([], tmp_path) == 0

    _tree(tmp_path, {"dev/tool.py": "TAX_YEAR = 2025\n"})
    assert main([], tmp_path) == 1
    assert "dev/tool.py:1: year bound: TAX_YEAR=2025" in capsys.readouterr().out


def test_a_walk_that_reads_nothing_is_refused(tmp_path: Path) -> None:
    assert main([], tmp_path) == 1
