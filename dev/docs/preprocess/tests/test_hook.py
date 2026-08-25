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

from cadrumo.core.directory_scan import iter_directory, scan_directory

from ...._paths import REPO_ROOT
from ..hook import (
    UPSTREAM_SCHEMA_VERSION,
    adapt_outputs,
    build_for_source,
)

pytestmark = [pytest.mark.unit, pytest.mark.docs, pytest.mark.hex_core]

_REPO_ROOT = REPO_ROOT
_RULE_FILE = _REPO_ROOT / ".vaultragpreprocess.toml"
_CORPUS = _REPO_ROOT / "src" / "cadrumo" / "_data" / "corpus"
_HOOK_COMMAND = "python -m dev.docs.preprocess.hook {path}"
#: The upstream ``.vaultragpreprocess.toml`` schema major the rule file
#: declares. Pinned so an upstream migration requirement fails here rather
#: than silently degrading every index job for this root to zero rules.
_RULE_SCHEMA_VERSION = 2
_TERMINOLOGY = _REPO_ROOT / "src" / "cadrumo" / "_data" / "terminology" / "concepts"


def _smallest(pattern: str) -> Path:
    """Return the smallest committed corpus file matching ``pattern``."""
    candidates = sorted(scan_directory(_CORPUS, pattern=pattern, recursive=True), key=lambda p: p.stat().st_size)
    assert candidates, f"no committed corpus file matches {pattern!r}"
    return candidates[0]


def test_rule_file_is_wellformed_and_targets_the_hook() -> None:
    """Every rule routes a corpus pattern through the hook adapter command."""
    data = tomllib.loads(_RULE_FILE.read_text(encoding="utf-8"))
    assert data["version"] == _RULE_SCHEMA_VERSION == 2
    rules = data["rule"]
    assert len(rules) == 6
    for rule in rules:
        assert rule["pattern"].startswith(("src/cadrumo/_data/corpus/", "src/cadrumo/_data/terminology/concepts/"))
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
    golden-query miss-rate runs, and ``_reindex`` all read. A rule's
    ``extractor_version`` must equal the declared version of the extractor
    family that owns its suffix, so an extractor bump invalidates the
    upstream preprocess cache instead of serving stale extractions.
    """
    from .._html import HTML_EXTRACTOR_VERSION
    from .._pdf import PDF_EXTRACTOR_VERSION
    from .._terminology import TERMINOLOGY_EXTRACTOR_VERSION
    from .._workbook import WORKBOOK_EXTRACTOR_VERSION

    owning_version = {
        ".html": HTML_EXTRACTOR_VERSION,
        ".pdf": PDF_EXTRACTOR_VERSION,
        ".xls": WORKBOOK_EXTRACTOR_VERSION,
        ".xlsm": WORKBOOK_EXTRACTOR_VERSION,
        ".xlsx": WORKBOOK_EXTRACTOR_VERSION,
        ".toml": TERMINOLOGY_EXTRACTOR_VERSION,
    }
    rules = tomllib.loads(_RULE_FILE.read_text(encoding="utf-8"))["rule"]
    for rule in rules:
        pattern = cast(str, rule["pattern"])
        assert rule["target"] == "code", pattern
        suffix = Path(pattern).suffix.lower()
        assert rule["extractor_version"] == owning_version[suffix], pattern


def test_every_rule_pattern_matches_committed_sources() -> None:
    """A rule over zero files is dead configuration; each must match today."""
    for pattern in ("*.html", "*.pdf", "*.xlsm", "*.xlsx"):
        assert _smallest(pattern).is_file()
    assert any(iter_directory(_TERMINOLOGY, pattern="*.toml")), "no Handbook concept TOML matches the terminology rule"


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
    sidecar_files = scan_directory(source.parent, pattern=f"{source.name}*.extracted.json")
    assert sidecar_files, f"no committed sidecar next to {source}"
    sidecar_texts: list[str] = []
    for candidate in sidecar_files:
        record = json.loads(candidate.read_text(encoding="utf-8"))
        sidecar_texts.extend(unit["text"] for unit in record.get("units", []))
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
