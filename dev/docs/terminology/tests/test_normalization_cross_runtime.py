"""The compiler and the browser reader must normalize a query identically.

Rung-2 matches a typed query against precompiled rows by normalizing both sides
and comparing the result. The normalization therefore exists twice -- in Python
in :mod:`dev.docs.terminology._static_matrix` and in JavaScript in
``docs/_static/cadrumo-docs.js`` -- and a divergence between them is silent: the
page loads, the query normalizes, and the row simply never matches.

The gate runs the SHIPPED reader. It extracts the token pattern, the mark
pattern and the body of ``rung2Normalize`` out of the deployed file and executes
them under Node, rather than restating the algorithm here. A restatement would
agree with itself while the file the browser loads drifted -- the failure this
gate exists to catch.

``normalization_version`` is the fail-closed contract between the two. Bumping
the algorithm without bumping the string in both places would let an old
precompiled bundle be read under new rules; the last test proves the reader
refuses that rather than mis-matching quietly, and that both sides declare the
same version today.

The current contract PRESERVES accents, so an accented query and its unaccented
spelling are different rows. Folding them together is a wanted change, but it
invalidates every precompiled row and therefore has to land with a recompiled
matrix; this gate is what makes that change safe to attempt, by proving the two
runtimes still agree afterwards.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from .._static_matrix import NORMALIZATION_CONTRACT_VERSION, normalise_query_tokens

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

_REPO_ROOT = Path(__file__).resolve().parents[4]
_READER = _REPO_ROOT / "docs" / "_static" / "cadrumo-docs.js"

#: Real query shapes across the four shipped languages, chosen so that a
#: fold-only, a case-only and a separator-only difference each appear, plus the
#: Hungarian pair whose accents change the word's meaning.
_CASES: tuple[str, ...] = (
    "arányosítás",
    "aranyositas",
    "ARÁNYOSÍTÁS",
    "prorrata",
    "año",
    "AÑO",
    "Impost sobre el Valor Afegit",
    "Impuesto sobre el Valor Añadido",
    "béns",
    "bens",
    "közzététel",
    "szójegyzék",
    "modelo 303",
    "casilla-0435",
    "  espacios   multiples  ",
    "Ley 37/1992, art. 92",
    "recàrrec d'equivalència",
    "Ceuta i Melilla",
    "ő ű á é í ó ö ü",
)

_HARNESS = """
const fs = require("fs");
const src = fs.readFileSync(process.argv[2], "utf8");
const tokenStmt = /RUNG2_TOKEN_PATTERN = new RegExp\\(.*?, "gu"\\);/.exec(src)[0];
/* The mark pattern exists only while the contract folds accents. Extract it
 * when present so this harness reads whichever policy the reader ships. */
const markMatch = /RUNG2_MARK_PATTERN = new RegExp\\(.*?, "gu"\\);/.exec(src);
let RUNG2_TOKEN_PATTERN, RUNG2_MARK_PATTERN = null;
eval(tokenStmt);
if (markMatch) eval(markMatch[0]);
const body = /function rung2Normalize\\(value\\) \\{([\\s\\S]*?)\\n  \\}/.exec(src)[1];
const fn = new Function("value", "RUNG2_TOKEN_PATTERN", "RUNG2_MARK_PATTERN", body);
const cases = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const out = {};
for (const c of cases) {
  const r = fn(c, RUNG2_TOKEN_PATTERN, RUNG2_MARK_PATTERN);
  out[c] = r ? r.tokens : null;
}
process.stdout.write(JSON.stringify(out));
"""


def _node() -> str:
    """Return the Node executable, failing loudly when the toolchain lacks it."""
    node = shutil.which("node")
    assert node is not None, (
        "node is required to run the shipped reader against the compiler; "
        "the alternative is restating the algorithm in the test, which would prove nothing"
    )
    return node


def _browser_tokens(tmp_path: Path, cases: tuple[str, ...]) -> dict[str, list[str]]:
    """Normalize every case with the deployed browser implementation."""
    harness = tmp_path / "harness.js"
    harness.write_text(_HARNESS, encoding="utf-8")
    payload = tmp_path / "cases.json"
    payload.write_text(json.dumps(list(cases), ensure_ascii=False), encoding="utf-8")
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [_node(), str(harness), str(_READER), str(payload)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, f"browser harness failed:\n{result.stderr}"
    return json.loads(result.stdout)


def test_compiler_and_browser_normalize_every_case_identically(tmp_path: Path) -> None:
    """Both runtimes return the same token sequence for every real query shape."""
    browser = _browser_tokens(tmp_path, _CASES)
    compiler = {case: list(normalise_query_tokens(case)) for case in _CASES}

    divergent = {case: (compiler[case], browser.get(case)) for case in _CASES if compiler[case] != browser.get(case)}

    assert not divergent, "compiler and browser normalization disagree:\n" + "\n".join(
        f"  {case!r}: python={py!r} javascript={js!r}" for case, (py, js) in divergent.items()
    )


def test_accent_sensitivity_is_the_same_on_both_sides(tmp_path: Path) -> None:
    """Whatever the accent policy is, both runtimes apply it identically.

    Stated against the pair that motivated the question: Hungarian
    ``arányosítás`` (pro rata, from ``arány``) and the unaccented spelling a
    keyboard produces. The gate does not assert WHICH policy is in force -- that
    is the contract's business and it is versioned -- only that the compiler and
    the browser never disagree about it, which is the failure that would be
    silent.
    """
    browser = _browser_tokens(tmp_path, ("arányosítás", "aranyositas"))
    compiler = {case: list(normalise_query_tokens(case)) for case in ("arányosítás", "aranyositas")}

    assert browser["arányosítás"] == compiler["arányosítás"]
    assert browser["aranyositas"] == compiler["aranyositas"]
    assert (browser["arányosítás"] == browser["aranyositas"]) == (compiler["arányosítás"] == compiler["aranyositas"]), (
        "the two runtimes disagree about whether an accented query matches its unaccented spelling"
    )


def test_the_reader_refuses_a_bundle_normalized_under_another_version(tmp_path: Path) -> None:
    """A version mismatch is refused, never read under the wrong rules.

    Exercised against the deployed reader's own constant and its own refusal
    branch, so the guard cannot pass by being absent.
    """
    source = _READER.read_text(encoding="utf-8")
    declared = re.search(r'var RUNG2_NORMALIZATION_VERSION = "([^"]+)";', source)
    assert declared is not None, "the reader no longer declares a normalization version"

    # The two sides agree today...
    assert declared.group(1) == NORMALIZATION_CONTRACT_VERSION

    # ...and the reader refuses anything else rather than matching under it.
    refusal = re.search(
        r"if \(config\.normalization_version !== RUNG2_NORMALIZATION_VERSION\) \{\s*"
        r'throw new Error\("Rung-2 normalization version mismatch"\);',
        source,
    )
    assert refusal is not None, "the reader no longer fails closed on a normalization-version mismatch"
