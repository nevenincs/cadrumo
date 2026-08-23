"""Directive and tokeniser gate for the ``cli-sequence`` MyST directive.

Two tiers, both real, no mocks or skips:

- **Pure-function tier.** The Python tokeniser (``dev/docs/sequences/_tokeniser``)
  classifies a frame's argv against the command graph, and the directive's
  render pipeline (``dev/docs/sequence_directive``) projects a parsed sequence
  plus its golden into one payload and renders the static HTML from that single
  source. These assert token classification, the payload shape the browser
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

from ..sequence_directive import (
    build_sequence_payload,
    parse_shells,
    render_sequence_html,
    wrap_token_lines,
)
from ..sequences import (
    FrameKind,
    GoldenFrame,
    ParsedSequence,
    SequenceGolden,
    TokenKind,
    parse_sequence,
    tokenise_command,
)

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


def test_payload_shape_and_render_exclude_authoring_metadata() -> None:
    """The reader payload omits setup scaffolding and build-only assertions."""
    sequence = _parsed_sequence()
    payload = build_sequence_payload(sequence, _golden())

    assert payload["sequence_id"] == _SEQUENCE_ID
    assert payload["verify"] == "Verify the calculation before exporting."
    assert [frame["kind"] for frame in payload["frames"]] == ["command", "command", "result"]

    # The authored command line keeps its placeholder (the reproducible form),
    # not the golden's resolved id.
    calculate = payload["frames"][1]
    assert calculate["command_line"] == "aeat app modelo work calculate {work_unit_id}"
    assert any(tok["kind"] == "placeholder" and tok["text"] == "{work_unit_id}" for tok in calculate["tokens"])

    # The create frame's masked JSON output hides the central surrogate ids.
    create_output = payload["frames"][0]["output"]
    assert create_output["format"] == "json"
    assert "snap_demo" not in create_output["body"]
    # The displayed body is the human-readable canonical JSON DOCUMENT itself —
    # re-parsing it yields the mapping, never a double-encoded string of JSON,
    # and it carries real newlines rather than literal `\n` escape noise.
    reparsed = json.loads(create_output["body"])
    assert isinstance(reparsed, dict), "JSON output body must be the document, not a re-dumped string"
    assert "\n" in create_output["body"]
    assert "\\n" not in create_output["body"]

    assert all("expects" not in frame for frame in payload["frames"])

    html = render_sequence_html(payload)
    # No-JS transcript: every frame's command tokens appear as spans and the
    # verify caption renders; the word "sequence" is never user-facing text.
    assert 'class="cadrumo-sequence"' in html
    assert f'data-sequence-id="{_SEQUENCE_ID}"' in html
    assert 'class="cli-tok cli-tok-leaf" data-command-path="aeat app modelo work calculate"' in html
    # Setup scaffolding and expectation assertions are not user-facing.
    assert "cadrumo-setup" not in html
    assert "<details" not in html
    assert 'data-frame-kind="setup"' not in html
    assert "Imported 3 transactions." not in html
    assert "Confirm result.status reads verified_complete." not in html
    # Every visible frame carries a per-step header.
    assert html.count('class="cadrumo-frame-header"') == 3
    assert '<span class="cadrumo-frame-step">1</span>' in html
    assert '<span class="cadrumo-frame-step">3</span>' in html
    # JSON outputs render as the readable highlighted document: the Pygments
    # token spans are present, the double-encoded `"{\n` noise signature is not,
    # and the panel NEVER borrows the docs' `.highlight` code-block class (its
    # box chrome would out-specify the panel's own layout rules).
    assert 'class="cadrumo-frame-output" data-format="json">' in html
    assert "cadrumo-frame-output highlight" not in html
    assert '<span class="nt">' in html, "JSON output must carry Pygments key highlighting"
    assert "&quot;{" not in html, "JSON output must never render double-encoded"
    assert "Verify the calculation before exporting." in html

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


def _write_site(
    root: Path,
    *,
    index_body: str,
    goldens_root: Path,
    sequence_id: str,
    contract_body: str,
) -> None:
    """Write a minimal MyST site with a public directive and private contract."""
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
    contract_dir = root / "_sequences" / "contracts" / "index"
    contract_dir.mkdir(parents=True)
    (contract_dir / f"{sequence_id}.seq").write_text(contract_body.strip() + "\n", encoding="utf-8")


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


from ._sequence_storage_fixtures import _isolated_sequence_storage

__all__ = ["_isolated_sequence_storage"]

_INDEX_WITH_DIRECTIVE = (
    f"# Modelo 303\n\n```{{cli-sequence}} {_SEQUENCE_ID}\n:verify: Verify the calculation before exporting.\n```\n"
)


def test_directive_build_renders_frames_and_payload(tmp_path: Path, _isolated_sequence_storage: None) -> None:
    """A real Sphinx build renders the static frames plus one inline payload, no-JS complete."""
    site = tmp_path / "site"
    site.mkdir()
    goldens_root = tmp_path / "goldens"
    (goldens_root / _PAGE).mkdir(parents=True)
    (goldens_root / _PAGE / f"{_SEQUENCE_ID}.json").write_text(
        json.dumps(_golden().model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    _write_site(
        site,
        index_body=_INDEX_WITH_DIRECTIVE,
        goldens_root=goldens_root,
        sequence_id=_SEQUENCE_ID,
        contract_body="\n".join(_DIRECTIVE_BODY.splitlines()[1:]),
    )

    html, warnings = _build(site, warningiserror=True)

    assert "cadrumo-sequence" in html, warnings
    # No-JS degradation: the full linear transcript is present in the static HTML.
    assert "aeat" in html
    assert 'data-command-path="aeat app modelo work verify"' in html
    assert "Imported 3 transactions." not in html
    assert "Verify the calculation before exporting." in html
    # One inline JSON payload, well-formed and containing only reader-facing frames.
    match = re.search(
        r'<script type="application/json" class="cadrumo-sequence-payload">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert match is not None
    payload = json.loads(match.group(1).replace("<\\/", "</"))
    assert payload["sequence_id"] == _SEQUENCE_ID
    assert [frame["kind"] for frame in payload["frames"]] == ["command", "command", "result"]
    # Shell-aware display flows through the real build: the default shell is on the
    # root, both variants render per frame, and the payload carries the shells.
    assert 'data-cadrumo-shell="bash"' in html
    assert 'class="cadrumo-cmd-variant" data-shell="bash"' in html
    assert 'class="cadrumo-cmd-variant" data-shell="pwsh"' in html
    assert payload["shells"] == ["bash", "pwsh"]
    assert "wrapped" in payload["frames"][0]


def test_directive_missing_golden_is_instructive_build_error(tmp_path: Path, _isolated_sequence_storage: None) -> None:
    """A directive with no committed golden fails the build naming the refresh command."""
    site = tmp_path / "site"
    site.mkdir()
    goldens_root = tmp_path / "empty-goldens"
    goldens_root.mkdir()
    _write_site(
        site,
        index_body=_INDEX_WITH_DIRECTIVE,
        goldens_root=goldens_root,
        sequence_id=_SEQUENCE_ID,
        contract_body="\n".join(_DIRECTIVE_BODY.splitlines()[1:]),
    )

    html, warnings = _build(site, warningiserror=False)

    assert "no committed golden" in warnings
    assert "python -m dev.docs.sequences refresh" in warnings
    # The failed directive rendered no sequence container.
    assert "cadrumo-sequence" not in html


_INDEX_LIVE_AEAT = "# Pull\n\n```{cli-sequence} live-pull-demo\n:verify: Confirm the justificante downloaded.\n```\n"
_CONTRACT_LIVE_AEAT = "@result aeat app live justificante pull\n@expect exit_code == 0"


def test_directive_refuses_live_aeat_in_an_executed_frame(tmp_path: Path, _isolated_sequence_storage: None) -> None:
    """A live-AEAT command in an EXECUTED frame is refused at build time.

    The refusal fires statically, before any golden is read, so an ``app live``
    or ``pull`` command in an executed (@result) frame cannot be enrolled. The
    error points the author at the @static carve-out.
    """
    site = tmp_path / "site"
    site.mkdir()
    goldens_root = tmp_path / "goldens"
    goldens_root.mkdir()
    _write_site(
        site,
        index_body=_INDEX_LIVE_AEAT,
        goldens_root=goldens_root,
        sequence_id="live-pull-demo",
        contract_body=_CONTRACT_LIVE_AEAT,
    )

    html, warnings = _build(site, warningiserror=False)

    assert "cannot be executed" in warnings
    assert "@static" in warnings  # the remediation is named
    assert "no committed golden" not in warnings  # refused before the golden lookup
    assert "cadrumo-sequence" not in html


# ---------------------------------------------------------------------------
# Shell-aware wrapping, shell switcher metadata, and copy affordance
# ---------------------------------------------------------------------------


def test_short_command_is_not_wrapped() -> None:
    """A command that fits in the width budget renders on a single line."""
    tokens = ["aeat", "app", "modelo", "work", "create", "303", "--year", "2026", "--period", "1T"]
    lines = wrap_token_lines(tokens)
    assert lines == [list(range(len(tokens)))]


def test_long_command_wraps_at_token_boundaries_and_reassembles() -> None:
    """Wrapping packs whole tokens; reassembling the lines reproduces the token stream."""
    tokens = [
        "aeat",
        "app",
        "ledger",
        "import",
        "--file",
        "fixtures/2026-first-quarter-bank-statement.csv",
        "--provider",
        "caixabank",
        "--year",
        "2026",
        "--period",
        "1T",
        "--verbose",
    ]
    lines = wrap_token_lines(tokens)
    assert len(lines) > 1, "a command past the budget must wrap onto multiple lines"
    # No token is split, and the flattened line order reproduces the original stream.
    flattened = [tokens[i] for line in lines for i in line]
    assert flattened == tokens
    # Every display line stays within the 88-column content budget (indent + tokens
    # + inter-token spaces), the packing invariant the markers ride beyond.
    for line_index, line in enumerate(lines):
        indent = 0 if line_index == 0 else 2
        content = indent + sum(len(tokens[i]) for i in line) + (len(line) - 1)
        assert content <= 88 or len(line) == 1, f"line {line_index} overflows the budget without being a lone token"


def test_token_longer_than_budget_renders_alone() -> None:
    """A single token wider than the budget occupies its own line (never split)."""
    tokens = ["aeat", "x" * 120, "app"]
    lines = wrap_token_lines(tokens)
    assert [1] in lines, "an over-budget token must be alone on its line"
    # And it is never split into pieces.
    flattened = [tokens[i] for line in lines for i in line]
    assert flattened == tokens


def _wrapping_golden(sequence_id: str) -> SequenceGolden:
    """A single-result-frame golden for a long command that wraps."""
    return SequenceGolden(
        sequence_id=sequence_id,
        frames=(
            GoldenFrame(
                kind=FrameKind.RESULT,
                argv=("aeat", "x"),
                exit_code=0,
                envelope={
                    "schema_version": 1,
                    "command": "modelo.work.calculate",
                    "status": "ok",
                    "notices": [],
                    "result": {"status": "ok"},
                },
                envelope_source="stdout",
            ),
        ),
    )


_LONG_BODY = (
    "@result aeat app ledger import --file fixtures/2026-first-quarter-bank-statement.csv "
    "--provider caixabank --year 2026 --period 1T --verbose\n"
    "@expect exit_code == 0"
)


def test_payload_carries_shells_and_per_frame_wrapping() -> None:
    """The payload carries the ordered shells and per-shell wrapped line groupings."""
    sequence = parse_sequence(
        sequence_id="wrap-demo",
        options={"verify": "Confirm the import."},
        body=_LONG_BODY,
    )
    payload = build_sequence_payload(sequence, _wrapping_golden("wrap-demo"), shells=["bash", "pwsh"])
    assert payload["shells"] == ["bash", "pwsh"]
    frame = payload["frames"][0]
    assert set(frame["wrapped"]) == {"bash", "pwsh"}
    # The packing is shell-independent, so both shells share the line groupings.
    assert frame["wrapped"]["bash"] == frame["wrapped"]["pwsh"]
    # The groupings index into the frame's flat token list and reassemble the argv.
    texts = [tok["text"] for tok in frame["tokens"]]
    flattened = [texts[i] for line in frame["wrapped"]["bash"] for i in line]
    assert flattened == texts
    assert len(frame["wrapped"]["bash"]) > 1  # this command wraps


def test_render_emits_per_shell_variants_with_markers_and_default() -> None:
    """The HTML renders one command variant per shell, with markers and a default shell."""
    sequence = parse_sequence(
        sequence_id="wrap-demo",
        options={"verify": "Confirm the import."},
        body=_LONG_BODY,
    )
    payload = build_sequence_payload(sequence, _wrapping_golden("wrap-demo"), shells=["bash", "pwsh"])
    html = render_sequence_html(payload)

    # The sequence root declares the default (first) shell so the correct variant
    # shows without JavaScript.
    assert 'data-cadrumo-shell="bash"' in html
    # One command variant per declared shell.
    assert 'class="cadrumo-cmd-variant" data-shell="bash"' in html
    assert 'class="cadrumo-cmd-variant" data-shell="pwsh"' in html
    # Each shell's continuation marker renders as its own muted span.
    assert r'<span class="cli-continuation">\</span>' in html  # bash trailing backslash
    assert '<span class="cli-continuation">`</span>' in html  # pwsh trailing backtick
    # The frame carries the single-line authored command for the copy control.
    assert 'data-command-line="aeat app ledger import --file' in html


def test_single_shell_renders_one_variant_no_switcher_metadata() -> None:
    """Declaring one shell renders a single variant and defaults to that shell."""
    sequence = parse_sequence(
        sequence_id="one-shell",
        options={"verify": "Confirm the import."},
        body=_LONG_BODY,
    )
    payload = build_sequence_payload(sequence, _wrapping_golden("one-shell"), shells=["pwsh"])
    assert payload["shells"] == ["pwsh"]
    html = render_sequence_html(payload)
    assert 'data-cadrumo-shell="pwsh"' in html
    assert html.count('class="cadrumo-cmd-variant"') == 1
    assert 'data-shell="pwsh"' in html
    assert 'data-shell="bash"' not in html


def test_parse_shells_default_and_validation() -> None:
    """The :shells: option defaults to bash+pwsh and refuses an unknown shell."""
    assert parse_shells(None) == ["bash", "pwsh"]
    assert parse_shells("  ") == ["bash", "pwsh"]
    assert parse_shells("pwsh bash") == ["pwsh", "bash"]
    assert parse_shells("bash bash") == ["bash"]  # de-duplicated
    with pytest.raises(ValueError, match="not a supported shell"):
        parse_shells("fish")


_INDEX_UNKNOWN_SHELL = "# Bad shell\n\n```{cli-sequence} bad-shell-demo\n:verify: Confirm it.\n```\n"
_CONTRACT_UNKNOWN_SHELL = ":shells: fish\n@result aeat app modelo work verify wu\n@expect exit_code == 0"


def test_directive_refuses_unknown_shell(tmp_path: Path, _isolated_sequence_storage: None) -> None:
    """An unknown :shells: value fails the build with the accepted set named."""
    site = tmp_path / "site"
    site.mkdir()
    goldens_root = tmp_path / "goldens"
    goldens_root.mkdir()
    _write_site(
        site,
        index_body=_INDEX_UNKNOWN_SHELL,
        goldens_root=goldens_root,
        sequence_id="bad-shell-demo",
        contract_body=_CONTRACT_UNKNOWN_SHELL,
    )

    html, warnings = _build(site, warningiserror=False)

    assert "not a supported shell" in warnings
    assert "bash" in warnings and "pwsh" in warnings  # the accepted set is named
    assert "cadrumo-sequence" not in html


# ---------------------------------------------------------------------------
# Per-step headers and private setup scaffolding
# ---------------------------------------------------------------------------


def test_authored_step_header_flows_to_payload() -> None:
    """An authored @step sentence becomes the frame's header, over the help fallback."""
    sequence = parse_sequence(
        sequence_id="step-demo",
        options={"verify": "Confirm the verification."},
        body=("@step Create the quarterly draft.\n@result aeat app modelo work verify wu\n@expect exit_code == 0"),
    )
    golden = SequenceGolden(
        sequence_id="step-demo",
        frames=(
            GoldenFrame(
                kind=FrameKind.RESULT,
                argv=("aeat", "app", "modelo", "work", "verify", "wu"),
                exit_code=0,
                envelope={"schema_version": 1, "command": "c", "status": "ok", "notices": [], "result": {}},
                envelope_source="stdout",
            ),
        ),
    )
    payload = build_sequence_payload(sequence, golden)
    assert payload["frames"][0]["header"] == "Create the quarterly draft."


def test_frame_headers_fall_back_to_leaf_help() -> None:
    """Without @step every frame still carries an imperative header from the leaf help."""
    sequence = _parsed_sequence()
    payload = build_sequence_payload(sequence, _golden())
    headers = [frame["header"] for frame in payload["frames"]]
    # Every frame carries a non-empty header (payload contract for the widget).
    assert all("header" in frame for frame in payload["frames"])
    assert all(header for header in headers)
    # The verify frame's header is drawn from the verb's help, not the bare path.
    verify_header = payload["frames"][2]["header"]
    assert verify_header != "aeat app modelo work verify"
    assert len(verify_header) > 3


def test_setup_frames_are_not_published() -> None:
    """Setup frames execute for verification but never enter reader-facing HTML."""
    sequence = _parsed_sequence()
    payload = build_sequence_payload(sequence, _golden())
    html = render_sequence_html(payload)
    assert 'data-frame-kind="setup"' not in html
    assert "Imported 3 transactions." not in html
    assert [frame["kind"] for frame in payload["frames"]] == ["command", "command", "result"]
    assert '<span class="cadrumo-frame-step">1</span>' in html


# ---------------------------------------------------------------------------
# @static non-executed display frames (mandatory-display doctrine)
# ---------------------------------------------------------------------------

_INDEX_ALL_STATIC = "# Pull live data\n\n```{cli-sequence} live-all-static\n```\n"
_CONTRACT_ALL_STATIC = (
    "@step Pull the justificante from AEAT.\n"
    "@static aeat app live justificante pull\n"
    "@blocked live-aeat The pull verb fetches from the AEAT sede; the sandbox refuses it.\n"
    "@step View the stored justificante.\n"
    "@static aeat app live justificante latest\n"
    "@blocked live-aeat The app live group reads the operator's authenticated sede session.\n"
)


def test_all_static_sequence_builds_without_a_golden(tmp_path: Path, _isolated_sequence_storage: None) -> None:
    """An all-@static sequence renders from the parse alone: no golden, no verify caption.

    A live-AEAT page shows its commands as @static frames (execution is
    impossible in the hermetic sandbox). Nothing runs, so there is no golden and
    no :verify:; the build still succeeds under -n -W and the frames render as
    command cards with no output.
    """
    site = tmp_path / "site"
    site.mkdir()
    goldens_root = tmp_path / "goldens"
    goldens_root.mkdir()  # deliberately empty — an all-static sequence has no golden
    _write_site(
        site,
        index_body=_INDEX_ALL_STATIC,
        goldens_root=goldens_root,
        sequence_id="live-all-static",
        contract_body=_CONTRACT_ALL_STATIC,
    )

    # The build succeeds under warningiserror (a real directive fault would raise,
    # e.g. a missing-golden error); the benign cross-build "already registered"
    # setup noise is not a directive fault, so the content assertions below are
    # the real check that the all-static sequence rendered from the parse alone.
    html, _warnings = _build(site, warningiserror=True)

    assert 'class="cadrumo-sequence"' in html
    assert html.count('data-frame-kind="static"') == 2
    # No output blocks (nothing executed) and no verification caption.
    assert "cadrumo-frame-output" not in html
    assert "cadrumo-verify" not in html
    # The @static live commands are shown (not refused) and carry their copy handle.
    assert 'data-command-line="aeat app live justificante pull"' in html
    # The inline payload carries verify=null and static frames with empty output.
    match = re.search(
        r'<script type="application/json" class="cadrumo-sequence-payload">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert match is not None
    payload = json.loads(match.group(1).replace(r"<\/", "</"))
    assert payload["verify"] is None
    assert [frame["kind"] for frame in payload["frames"]] == ["static", "static"]
    assert all(frame["output"]["format"] == "empty" and frame["exit_code"] is None for frame in payload["frames"])


def test_mixed_sequence_renders_trailing_static_frame_without_output() -> None:
    """A @static frame after the @result renders output-less and aligns the golden 1:1.

    The golden carries only the executed frames; the parsed body's static frame
    is rendered from the parse alone (no golden), and the two executed frames
    align with the two golden frames.
    """
    sequence = parse_sequence(
        sequence_id="file-303",
        options={"verify": "Confirm the draft is verified before uploading."},
        body=(
            "aeat app modelo work create 303 --year 2026 --period 1T\n"
            "@result aeat app modelo work verify wu\n"
            '@expect result.status == "ok"\n'
            "@step Upload the exported file at the AEAT portal yourself.\n"
            "@static aeat app live justificante pull\n"
            "@blocked live-aeat The pull verb fetches from the AEAT sede; the sandbox refuses it."
        ),
    )
    golden = SequenceGolden(
        sequence_id="file-303",
        frames=(
            GoldenFrame(
                kind=FrameKind.COMMAND,
                argv=("aeat", "app", "modelo", "work", "create", "303", "--year", "2026", "--period", "1T"),
                exit_code=0,
                envelope={"schema_version": 1, "command": "c", "status": "ok", "notices": [], "result": {}},
                envelope_source="stdout",
            ),
            GoldenFrame(
                kind=FrameKind.RESULT,
                argv=("aeat", "app", "modelo", "work", "verify", "wu"),
                exit_code=0,
                envelope={
                    "schema_version": 1,
                    "command": "c",
                    "status": "ok",
                    "notices": [],
                    "result": {"status": "ok"},
                },
                envelope_source="stdout",
            ),
        ),
    )
    payload = build_sequence_payload(sequence, golden)
    assert [frame["kind"] for frame in payload["frames"]] == ["command", "result", "static"]
    static_frame = payload["frames"][-1]
    assert static_frame["exit_code"] is None
    assert static_frame["output"] == {"format": "empty", "body": ""}
    assert "expects" not in static_frame
    # The executed frames still carry their golden output.
    assert payload["frames"][0]["output"]["format"] == "json"

    html = render_sequence_html(payload)
    assert 'data-frame-kind="static"' in html
    # Two executed frames render output; the static frame does not.
    assert html.count("cadrumo-frame-output") == 2
