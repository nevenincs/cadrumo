"""Gates for the upstream vaultspec-rag preprocess-hook adapter.

Three surfaces are locked together:

- the repo-root ``.vaultragpreprocess.toml`` rules — structurally validated
  here without importing the upstream package (CI has no vaultspec-rag; the
  end-to-end ``preprocess check`` / ``run-one`` validation is a dev-box
  procedure);
- the ``dev.docs.preprocess.hook`` adapter — its output must satisfy the
  pinned upstream contract shape and stay UTF-8-safe on Windows consoles;
- the committed extraction sidecars — the product's corpus payload — whose
  unit texts must PERMANENTLY equal the hook's for the same source
  (per-kind parity), proving one extraction truth feeds both the shipped
  payload and the dev index.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import cast

import pytest
from pathspec import PathSpec

from cadrumo.core.directory_scan import iter_directory, scan_directory
from dev._paths import REPO_ROOT

from ..hook import (
    UPSTREAM_SCHEMA_VERSION,
    adapt_outputs,
    build_for_source,
)
from ..sidecar import EXTRACTED_JSON_SUFFIX, matches_origin_name

pytestmark = [pytest.mark.unit, pytest.mark.docs, pytest.mark.hex_core]

_REPO_ROOT = REPO_ROOT
_RULE_FILE = _REPO_ROOT / ".vaultragpreprocess.toml"
_IGNORE_FILE = _REPO_ROOT / ".vaultragignore"
_CORPUS = _REPO_ROOT / "src" / "cadrumo" / "_data" / "corpus"
_HOOK_COMMAND = "python -m dev.docs.preprocess.hook {path}"
#: The upstream ``.vaultragpreprocess.toml`` schema major the rule file
#: declares. Pinned so an upstream migration requirement fails here rather
#: than silently degrading every index job for this root to zero rules.
_RULE_SCHEMA_VERSION = 2
_TERMINOLOGY = _REPO_ROOT / "src" / "cadrumo" / "_data" / "terminology" / "concepts"
#: Rule patterns rooted here target the Handbook concept tree rather than the
#: corpus, so they are resolved against a different directory below.
_TERMINOLOGY_PATTERN_PREFIX = "src/cadrumo/_data/terminology/concepts/"


def _smallest(pattern: str) -> Path:
    """Return the smallest committed corpus file matching ``pattern``."""
    candidates = sorted(scan_directory(_CORPUS, pattern=pattern, recursive=True), key=lambda p: p.stat().st_size)
    assert candidates, f"no committed corpus file matches {pattern!r}"
    return candidates[0]


def _hook_emission(pattern: str) -> dict[str, object]:
    """Return the hook's own record for the smallest committed file ``pattern`` matches.

    The extractor family is identified by what it emits rather than by a map
    kept in this module, so the rule file and the dispatch cannot be edited
    into agreement with each other through a single side.
    """
    suffix = Path(pattern).suffix.lower()
    if pattern.startswith(_TERMINOLOGY_PATTERN_PREFIX):
        candidates = sorted(iter_directory(_TERMINOLOGY, pattern=f"*{suffix}"), key=lambda path: path.stat().st_size)
        assert candidates, f"no Handbook concept file matches the terminology rule {pattern!r}"
        source = candidates[0]
    else:
        source = _smallest(f"*{suffix}")
    return adapt_outputs(build_for_source(source, repo_root=_REPO_ROOT), source=source, repo_root=_REPO_ROOT)


def test_rule_file_is_wellformed_and_targets_the_hook() -> None:
    """Every rule routes a corpus pattern through the hook adapter command."""
    data = tomllib.loads(_RULE_FILE.read_text(encoding="utf-8"))
    assert data["version"] == _RULE_SCHEMA_VERSION == 2
    rules = data["rule"]
    assert len(rules) == 6
    for rule in rules:
        assert rule["pattern"].startswith(("src/cadrumo/_data/corpus/", _TERMINOLOGY_PATTERN_PREFIX))
        assert _HOOK_COMMAND in rule["command"]
        assert rule["on_error"] == "skip"
        assert rule["timeout_s"] > 0
    patterns = {rule["pattern"] for rule in rules}
    assert patterns == {
        "src/cadrumo/_data/corpus/normatives/html/*.html",
        "src/cadrumo/_data/corpus/**/*.pdf",
        "src/cadrumo/_data/corpus/**/*.xls",
        "src/cadrumo/_data/corpus/**/*.xlsm",
        "src/cadrumo/_data/corpus/**/*.xlsx",
        "src/cadrumo/_data/terminology/concepts/*.toml",
    }


def test_every_rule_owns_the_code_index_and_versions_its_extractor() -> None:
    """Schema-2 ownership: corpus text stays in the code index, versioned.

    ``target`` is what admits these suffixes at all (none is a conventional
    source extension), and ``code`` is the domain the terminology sweep, the
    golden-query miss-rate runs, and ``reindex`` all read. A rule's
    ``extractor_version`` must equal the declared version of the extractor
    family that owns its suffix, so an extractor bump invalidates the
    upstream preprocess cache instead of serving stale extractions.

    The owning family is RUN, not restated. The previous form compared each
    rule against a suffix-to-version map authored in this module -- the test's
    own copy of ``hook._builders`` -- so both sides of the ownership assertion
    traced back here and it could not fail for the reason it names. Reassigning
    ``.xls`` to the PDF family in ``_builders`` left this module, and the whole
    preprocess package, green: per-kind sidecar parity is the only other check
    over that family and no committed ``.xls`` source carries a sidecar for it
    to run against.

    Now each rule is answered by the hook itself on a real file the rule
    matches, so the two sides are independent roots: the declaration is in the
    rule file, the emission comes from whichever extractor ``_builders``
    actually dispatches. A family that cannot read its own suffix raises here
    rather than passing.
    """
    rules = tomllib.loads(_RULE_FILE.read_text(encoding="utf-8"))["rule"]
    versions_by_family: dict[str, set[str]] = {}
    for rule in rules:
        pattern = cast(str, rule["pattern"])
        assert rule["target"] == "code", pattern
        emitted = _hook_emission(pattern)
        declared = cast(str, rule["extractor_version"])
        assert declared == emitted["preprocessor_version"], (
            f"{pattern}: the rule declares extractor_version {declared!r} but the hook "
            f"emits {emitted['preprocessor_version']!r}; bumping the extractor would not "
            "invalidate the upstream preprocess cache for this family"
        )
        versions_by_family.setdefault(cast(str, emitted["preprocessor_id"]), set()).add(declared)
    assert versions_by_family, "no rule produced an extraction, so the sweep above measured nothing"
    split = {family: sorted(seen) for family, seen in versions_by_family.items() if len(seen) > 1}
    assert not split, (
        f"one extractor family is declared at two versions across its rules: {split}; "
        "the family bumps as a whole, so the lower rules would serve cached stale text"
    )


def test_every_rule_pattern_matches_committed_sources() -> None:
    """A rule over zero files is dead configuration; each must match today.

    The families are READ FROM the rule file rather than restated here. A
    hand-listed subset is exactly how a rule stops being checked: this loop
    named four suffixes against six declared rules, so ``*.xls`` -- a whole
    source family, 47 committed workbooks -- was enumerated nowhere in this
    module, and its rule could have matched nothing with every gate green.
    Deriving the enumeration from the population makes omitting a family
    impossible rather than merely unlikely.
    """
    rules = tomllib.loads(_RULE_FILE.read_text(encoding="utf-8"))["rule"]
    patterns = sorted({cast(str, rule["pattern"]) for rule in rules})
    assert len(patterns) == len(rules) == 6, patterns
    for pattern in patterns:
        suffix = Path(pattern).suffix.lower()
        if pattern.startswith(_TERMINOLOGY_PATTERN_PREFIX):
            assert any(iter_directory(_TERMINOLOGY, pattern=f"*{suffix}")), (
                f"no Handbook concept file matches the terminology rule {pattern!r}"
            )
        else:
            assert _smallest(f"*{suffix}").is_file(), pattern


def test_manual_runtime_sidecars_are_excluded_without_excluding_pdf_hook_sources() -> None:
    """One manual's runtime derivative is ignored while its PDF remains hook-fed.

    The runtime JSON is a shipped, hash-validated evidence payload, not a
    development-index source.  The corresponding PDF must remain admitted so
    the hook supplies its extracted text under the authoritative source path.
    """
    ignore_lines = _IGNORE_FILE.read_text(encoding="utf-8").splitlines()
    ignore_spec = PathSpec.from_lines("gitignore", ignore_lines)
    manual_root = _CORPUS / "manuals"
    sources = sorted(
        scan_directory(manual_root, pattern="*.pdf", recursive=True),
        key=lambda path: path.stat().st_size,
    )
    assert sources, "no committed manual PDF is available to prove the hook path"
    source = sources[0]
    source_path = source.relative_to(_REPO_ROOT).as_posix()
    sidecar_path = (
        "src/cadrumo/_data/manual_corpus_text/" + source.relative_to(_CORPUS).as_posix() + ".corpus_text.json"
    )

    assert ignore_spec.match_file(sidecar_path), sidecar_path
    assert not ignore_spec.match_file(source_path), source_path

    rules = tomllib.loads(_RULE_FILE.read_text(encoding="utf-8"))["rule"]
    pdf_patterns = [cast(str, rule["pattern"]) for rule in rules if Path(cast(str, rule["pattern"])).suffix == ".pdf"]
    assert pdf_patterns == ["src/cadrumo/_data/corpus/**/*.pdf"]
    hook_spec = PathSpec.from_lines("gitignore", pdf_patterns)
    assert hook_spec.match_file(source_path), source_path


def test_terminology_concept_rule_emits_the_source_path_and_kind() -> None:
    """The explicit route feeds a real Handbook fragment without retargeting it."""
    from .._terminology import TERMINOLOGY_EXTRACTOR_ID

    source = _TERMINOLOGY / "prorrata-especial.toml"
    outputs = build_for_source(source, repo_root=_REPO_ROOT)
    payload = adapt_outputs(outputs, source=source, repo_root=_REPO_ROOT)
    assert payload["source_path"] == "src/cadrumo/_data/terminology/concepts/prorrata-especial.toml"
    units = cast(list[dict[str, object]], payload["units"])
    assert units and "prorrata especial" in str(units[0]["text"])
    metadata = cast(dict[str, object], payload["metadata"])
    assert metadata["source_kind"] == "terminology_concept"
    assert payload["preprocessor_id"] == TERMINOLOGY_EXTRACTOR_ID


def test_adapted_output_satisfies_the_pinned_upstream_shape() -> None:
    """The adapter emits the pinned schema major with well-formed units."""
    source = _smallest("*.html")
    outputs = build_for_source(source, repo_root=_REPO_ROOT)
    payload = adapt_outputs(outputs, source=source, repo_root=_REPO_ROOT)
    assert payload["schema_version"] == UPSTREAM_SCHEMA_VERSION == 1
    assert payload["source_path"] == source.resolve().relative_to(_REPO_ROOT).as_posix()
    units = cast(list[dict[str, object]], payload["units"])
    assert isinstance(units, list) and units
    for unit in units:
        text = unit["text"]
        assert isinstance(text, str) and text.strip()
    metadata = cast(dict[str, object], payload["metadata"])
    assert metadata["source_kind"] == "normatives_html"
    source_sha256 = metadata["source_sha256"]
    parts = metadata["parts"]
    assert isinstance(source_sha256, str) and len(source_sha256) == 64
    assert isinstance(parts, int) and parts >= 1
    # The payload must survive a strict UTF-8 JSON roundtrip byte-identically.
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    assert json.loads(encoded.decode("utf-8")) == payload


@pytest.mark.parametrize("pattern", ["*.html", "*.pdf", "*.xlsm", "*.xlsx"])
def test_hook_units_are_parity_with_committed_sidecars(pattern: str) -> None:
    """Per source kind, hook unit texts equal the committed sidecar texts.

    The sidecars and the hook share one extractor, so inequality means the
    committed sidecar is stale against the source on disk — regenerate it —
    or the adapter reordered or dropped units, which the atomic cutover
    (retiring the sidecars) must never inherit.
    """
    source = _smallest(pattern)
    outputs = build_for_source(source, repo_root=_REPO_ROOT)
    payload = adapt_outputs(outputs, source=source, repo_root=_REPO_ROOT)
    units = cast(list[dict[str, object]], payload["units"])
    hook_texts: list[str] = []
    for unit in units:
        text = unit["text"]
        assert isinstance(text, str)
        hook_texts.append(text)
    sidecar_files = [
        path
        for path in scan_directory(source.parent, pattern=f"{source.name}*{EXTRACTED_JSON_SUFFIX}")
        if matches_origin_name(path.name, source.name)
    ]
    assert sidecar_files, f"no committed sidecar next to {source}"
    sidecar_texts: list[str] = []
    for candidate in sidecar_files:
        record = json.loads(candidate.read_text(encoding="utf-8"))
        assert "units" in record, (
            f"{candidate} carries no units list; defaulting it to empty would let this "
            "parity hold by both sides being empty, which is the one way it must not pass"
        )
        sidecar_texts.extend(unit["text"] for unit in record["units"])

    assert hook_texts, (
        f"the hook produced no unit at all for {source}; an empty parity against an "
        "empty sidecar reports agreement having compared nothing"
    )

    assert hook_texts == sidecar_texts, (
        f"hook/sidecar unit-text divergence for {source.name}: "
        f"{len(hook_texts)} hook units vs {len(sidecar_texts)} sidecar units"
    )


def test_hook_cli_emits_utf8_json_bytes() -> None:
    """The CLI writes UTF-8 bytes so the upstream runner decodes on Windows."""
    source = _smallest("*.html")
    result = subprocess.run(  # noqa: S603 - fixed interpreter, repo-internal module
        [sys.executable, "-m", "dev.docs.preprocess.hook", str(source)],
        capture_output=True,
        check=True,
        cwd=_REPO_ROOT,
    )
    payload = json.loads(result.stdout.decode("utf-8"))
    assert payload["schema_version"] == UPSTREAM_SCHEMA_VERSION
    assert payload["units"]
