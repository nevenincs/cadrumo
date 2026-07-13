"""Directive and tokeniser gate for the ``cli-sequence`` MyST directive (ADR D1 / D5).

Two tiers, both real, no mocks or skips:

- **Pure-function tier.** The Python tokeniser (``dev/docs/sequences/_tokeniser``)
  classifies a frame's argv against the live Click tree, and the directive's
  render pipeline (``dev/docs/sequence_directive``) projects a parsed sequence
  plus its golden into one payload and renders the static HTML from that single
  source. These assert token classification, the payload shape the frontend
  widget consumes, and that the inline JSON cannot drift from the visible frames.

- **Real-build tier.** A minimal Sphinx site is built in-process with the
  directive registered and a committed golden fixture: the rendered ``index.html``
  must carry the server-side static frames (the no-JS transcript), the tokenised
  spans, and one well-formed inline ``application/json`` payload that matches the
  static content; a directive whose golden is absent must fail the build with an
  instructive error naming the exact ``refresh`` invocation.
"""

from __future__ import annotations

import json
import re
from io import StringIO
from pathlib import Path

import pytest
from sphinx.application import Sphinx

from dev.docs.sequence_directive import build_sequence_payload, render_sequence_html
from dev.docs.sequences import parse_sequence
from dev.docs.sequences._golden_store import GoldenFrame, SequenceGolden
from dev.docs.sequences._schema import FrameKind, ParsedSequence
from dev.docs.sequences._tokeniser import TokenKind, tokenise_command

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

_SEQUENCE_ID = "modelo-303-first-quarter"
_PAGE = "index"

_DIRECTIVE_BODY = """:verify: Verify the calculation before exporting.
@setup aeat app ledger import --file fixtures/x.csv
aeat app modelo work create 303 --year 2026 --period 1T
@capture work_unit_id result.work_unit_id
aeat app modelo work calculate {work_unit_id}
@result aeat app modelo work verify {work_unit_id}
@expect result.status == "verified_complete\""""


def _parsed_sequence() -> ParsedSequence:
    """Parse the fixture directive body into a ParsedSequence (no execution)."""
    return parse_sequence(
        sequence_id=_SEQUENCE_ID,
        options={"verify": "Verify the calculation before exporting."},
        body="\n".join(_DIRECTIVE_BODY.splitlines()[1:]),
    )


def _golden() -> SequenceGolden:
    """A schema-valid golden fixture matching the fixture directive's four frames.

    This mirrors what ``python -m dev.docs.sequences refresh`` would commit; the
    directive renders from it. Non-default fields (real captured id, masked
    surrogate ids in the envelopes) are populated so the render exercises masking.
    """
    return SequenceGolden(
        sequence_id=_SEQUENCE_ID,
        frames=(
            GoldenFrame(
                kind=FrameKind.SETUP,
                argv=("aeat", "app", "ledger", "import", "--file", "fixtures/x.csv"),
                exit_code=0,
                text="Imported 3 transactions.",
            ),
            GoldenFrame(
                kind=FrameKind.COMMAND,
                argv=("aeat", "app", "modelo", "work", "create", "303", "--year", "2026", "--period", "1T"),
                exit_code=0,
                envelope={
                    "schema_version": 1,
                    "command": "modelo.work.create",
                    "status": "ok",
                    "notices": [],
                    "result": {"work_unit_id": "wu_demo", "snapshot_id": "snap_demo"},
                },
                envelope_source="stdout",
            ),
            GoldenFrame(
                kind=FrameKind.COMMAND,
                argv=("aeat", "app", "modelo", "work", "calculate", "wu_demo"),
                exit_code=0,
                envelope={
                    "schema_version": 1,
                    "command": "modelo.work.calculate",
                    "status": "ok",
                    "notices": [],
                    "result": {"casillas_computed": 4},
                },
                envelope_source="stdout",
            ),
            GoldenFrame(
                kind=FrameKind.RESULT,
                argv=("aeat", "app", "modelo", "work", "verify", "wu_demo"),
                exit_code=0,
                envelope={
                    "schema_version": 1,
                    "command": "modelo.work.verify",
                    "status": "ok",
                    "notices": [],
                    "result": {"status": "verified_complete"},
                },
                envelope_source="stdout",
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Pure-function tier: tokeniser + payload + render
# ---------------------------------------------------------------------------


def test_tokeniser_classifies_against_the_live_tree() -> None:
    """The tokeniser classifies verbs, options, values, and placeholders from the real tree."""
    tokens = tokenise_command(
        ("aeat", "app", "modelo", "work", "calculate", "{work_unit_id}", "--format=json"),
    )
    by_text = {token.text: token for token in tokens}

    assert by_text["aeat"].kind is TokenKind.EXECUTABLE
    assert by_text["aeat"].command_path == "aeat"
    assert by_text["app"].kind is TokenKind.GROUP
    assert by_text["work"].kind is TokenKind.GROUP
    # A leaf verb carries the full space-joined command-path key (the cli-tree.json
    # lookup key the widget resolves against).
    assert by_text["calculate"].kind is TokenKind.LEAF
    assert by_text["calculate"].command_path == "aeat app modelo work calculate"
    # A {name} interpolation is a placeholder, not a positional value.
    assert by_text["{work_unit_id}"].kind is TokenKind.PLACEHOLDER
    # An inline --opt=value token is a single option carrying its owning path.
    assert by_text["--format=json"].kind is TokenKind.OPTION
    assert by_text["--format=json"].command_path == "aeat app modelo work calculate"


def test_tokeniser_links_value_option_to_its_value() -> None:
    """A value-consuming option marks the following token as its option value."""
    tokens = tokenise_command(("aeat", "app", "ledger", "import", "--file", "fixtures/x.csv"))
    kinds = [(t.text, t.kind) for t in tokens]
    assert ("--file", TokenKind.OPTION) in kinds
    value = next(t for t in tokens if t.text == "fixtures/x.csv")
    assert value.kind is TokenKind.OPTION_VALUE
    assert value.option_name == "--file"


def test_payload_shape_and_render_match_static_frames() -> None:
    """The payload carries every frame; the static HTML renders from that one source."""
    sequence = _parsed_sequence()
    payload = build_sequence_payload(sequence, _golden())

    assert payload["sequence_id"] == _SEQUENCE_ID
    assert payload["verify"] == "Verify the calculation before exporting."
    assert [frame["kind"] for frame in payload["frames"]] == ["setup", "command", "command", "result"]

    # The authored command line keeps its placeholder (the reproducible form),
    # not the golden's resolved id.
    calculate = payload["frames"][2]
    assert calculate["command_line"] == "aeat app modelo work calculate {work_unit_id}"
    assert any(tok["kind"] == "placeholder" and tok["text"] == "{work_unit_id}" for tok in calculate["tokens"])

    # The create frame's masked JSON output hides the central surrogate ids.
    create_output = payload["frames"][1]["output"]
    assert create_output["format"] == "json"
    assert "snap_demo" not in create_output["body"]

    # The result frame carries the imperative expect narration (ADR D4).
    result = payload["frames"][3]
    assert result["expects"][0]["json_path"] == "result.status"
    assert result["expects"][0]["narration"] == "Confirm result.status reads verified_complete."

    html = render_sequence_html(payload)
    # No-JS transcript: every frame's command tokens appear as spans and the
    # verify caption renders; the word "sequence" is never user-facing text.
    assert 'class="cadrumo-sequence"' in html
    assert f'data-sequence-id="{_SEQUENCE_ID}"' in html
    assert 'class="cli-tok cli-tok-leaf" data-command-path="aeat app modelo work calculate"' in html
    assert '<details class="cadrumo-setup"><summary>Preparation</summary>' in html
    assert "Verify the calculation before exporting." in html
    assert "Confirm result.status reads verified_complete." in html

    # The inline payload is present, well-formed, and equal to the computed payload.
    match = re.search(
        r'<script type="application/json" class="cadrumo-sequence-payload">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert match is not None
    inline = json.loads(match.group(1).replace("<\\/", "</"))
    assert inline == payload


def test_stale_golden_frame_count_is_refused() -> None:
    """A golden whose frame count disagrees with the body is refused (stale golden)."""
    sequence = _parsed_sequence()
    truncated = SequenceGolden(sequence_id=_SEQUENCE_ID, frames=_golden().frames[:2])
    with pytest.raises(ValueError, match="refresh the golden"):
        build_sequence_payload(sequence, truncated)


# ---------------------------------------------------------------------------
# Real-build tier: a minimal in-process Sphinx build
# ---------------------------------------------------------------------------


def _write_site(root: Path, *, index_body: str, goldens_root: Path) -> None:
    """Write a minimal MyST Sphinx site whose only page carries the directive."""
    conf = (
        'extensions = ["myst_parser"]\n'
        'myst_enable_extensions = ["colon_fence"]\n'
        "nitpicky = True\n"
        f"cadrumo_sequences_goldens_root = {str(goldens_root)!r}\n"
        "\n"
        "def setup(app):\n"
        "    from dev.docs.sequence_directive import register\n"
        "    register(app)\n"
    )
    (root / "conf.py").write_text(conf, encoding="utf-8")
    (root / "index.md").write_text(index_body, encoding="utf-8")


def _build(root: Path, *, warningiserror: bool) -> tuple[str, str]:
    """Build the site in-process, returning the rendered index.html and the warning log."""
    warning = StringIO()
    out = root / "_out"
    app = Sphinx(
        srcdir=str(root),
        confdir=str(root),
        outdir=str(out),
        doctreedir=str(root / "_doctree"),
        buildername="html",
        status=StringIO(),
        warning=warning,
        freshenv=True,
        warningiserror=warningiserror,
    )
    app.build()
    html = (out / "index.html").read_text(encoding="utf-8") if (out / "index.html").is_file() else ""
    return html, warning.getvalue()


@pytest.fixture
def _isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin an isolated Cadrumo storage root and English output for the CLI-tree walk."""
    root = tmp_path / "cadrumo-store"
    root.mkdir()
    monkeypatch.setenv("CADRUMO_LOCAL_STORAGE_ROOT", str(root))
    monkeypatch.setenv("CADRUMO_OUTPUT_LANGUAGE", "en")


_INDEX_WITH_DIRECTIVE = "# Modelo 303\n\n```{cli-sequence} " + _SEQUENCE_ID + "\n" + _DIRECTIVE_BODY + "\n```\n"


def test_directive_build_renders_frames_and_payload(tmp_path: Path, _isolated_storage: None) -> None:
    """A real Sphinx build renders the static frames plus one inline payload, no-JS complete."""
    site = tmp_path / "site"
    site.mkdir()
    goldens_root = tmp_path / "goldens"
    (goldens_root / _PAGE).mkdir(parents=True)
    (goldens_root / _PAGE / f"{_SEQUENCE_ID}.json").write_text(
        json.dumps(_golden().model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    _write_site(site, index_body=_INDEX_WITH_DIRECTIVE, goldens_root=goldens_root)

    html, warnings = _build(site, warningiserror=True)

    assert "cadrumo-sequence" in html, warnings
    # No-JS degradation: the full linear transcript is present in the static HTML.
    assert "aeat" in html
    assert 'data-command-path="aeat app modelo work verify"' in html
    assert "Imported 3 transactions." in html  # the setup frame's output renders
    assert "Verify the calculation before exporting." in html
    # One inline JSON payload, well-formed and matching the four static frames.
    match = re.search(
        r'<script type="application/json" class="cadrumo-sequence-payload">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert match is not None
    payload = json.loads(match.group(1).replace("<\\/", "</"))
    assert payload["sequence_id"] == _SEQUENCE_ID
    assert [frame["kind"] for frame in payload["frames"]] == ["setup", "command", "command", "result"]


def test_directive_missing_golden_is_instructive_build_error(tmp_path: Path, _isolated_storage: None) -> None:
    """A directive with no committed golden fails the build naming the refresh command."""
    site = tmp_path / "site"
    site.mkdir()
    goldens_root = tmp_path / "empty-goldens"
    goldens_root.mkdir()
    _write_site(site, index_body=_INDEX_WITH_DIRECTIVE, goldens_root=goldens_root)

    html, warnings = _build(site, warningiserror=False)

    assert "no committed golden" in warnings
    assert "python -m dev.docs.sequences refresh" in warnings
    # The failed directive rendered no sequence container.
    assert "cadrumo-sequence" not in html
