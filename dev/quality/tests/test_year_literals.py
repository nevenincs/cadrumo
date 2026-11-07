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

from dev.quality.year_literals import (
    blank_text,
    governed_sources,
    main,
    python_findings,
    scan,
    typescript_findings,
)

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
        ("ejercicio = '2025'\n", "year text"),
        ("expected = {'year': '2026'}\n", "year text"),
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
        "stamp = '2026-03-02T10:00:00Z'\n",
        "day = '2026-03-02'\n",
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
        'const date = "2026-03-02T10:00:00Z";',
        'const day = "2026-03-02";',
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
