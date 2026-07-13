"""The ``cli-sequence`` MyST directive: server-rendered frames plus one inline payload (ADR D5).

An author writes a backtick-fenced ``{cli-sequence}`` directive; at build time
this directive parses the body into typed frames, reads the sequence's committed
golden (it RENDERS from the golden, it never executes — the engine's check/refresh
CLI owns execution), tokenises each command line against the live Click tree, and
emits, in document order:

- every frame as static HTML — the tokenised command line and its full output in
  a ``pre`` — so a reader without JavaScript sees the complete linear transcript;
- exactly one inline ``script[type="application/json"]`` payload per sequence,
  carrying the same frames and per-token command-path keys.

Both surfaces are rendered from ONE computed payload, so the JSON a widget reads
cannot drift from the visible frames (ADR D5). The frontend widget (a later wave)
only toggles visibility and adds controls; it never injects content. A missing or
stale golden is an instructive build error naming the exact ``refresh`` command.

This module lives outside the ``dev/docs/sequences`` engine package and imports
its public facade; ``docs/conf.py`` registers the directive by calling
:func:`register`.
"""

from __future__ import annotations

import html
import json
from typing import TYPE_CHECKING, Any, override

from docutils import nodes
from docutils.parsers.rst import Directive, directives

if TYPE_CHECKING:
    from sphinx.application import Sphinx

    from dev.docs.sequences._golden_store import GoldenFrame, SequenceGolden
    from dev.docs.sequences._schema import ParsedSequence, SequenceFrame

__all__ = [
    "CliSequenceDirective",
    "build_sequence_payload",
    "register",
    "render_sequence_html",
]

#: The pseudo-path an ``@expect`` uses to assert a frame's process exit code.
_EXIT_CODE_PATH = "exit_code"


def _literal_text(value: object) -> str:
    """Render a JSON literal for user-facing narration (strings without quotes)."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    return json.dumps(value)


def _expect_narration(json_path: str, expected: object) -> str:
    """Render one ``@expect`` as a singular imperative verification check (ADR D4)."""
    if json_path == _EXIT_CODE_PATH:
        return f"Confirm the command exits with status {_literal_text(expected)}."
    return f"Confirm {json_path} reads {_literal_text(expected)}."


def _output_view(golden_frame: GoldenFrame) -> dict[str, str]:
    """Project a golden frame's primary stream to a ``{format, body}`` view.

    The pre-mask envelope is masked with exactly the central mask and canonically
    rendered so the displayed JSON is deterministic; otherwise the frame's
    normalised stdout text is shown, or an empty view when the frame produced no
    stdout content.
    """
    from cadrumo.core.observability import canonicalise, mask_document

    if golden_frame.envelope is not None:
        masked = canonicalise(mask_document(golden_frame.envelope))
        return {"format": "json", "body": json.dumps(masked, indent=2, ensure_ascii=False)}
    if golden_frame.text:
        return {"format": "text", "body": golden_frame.text}
    return {"format": "empty", "body": ""}


def _stderr_view(golden_frame: GoldenFrame) -> dict[str, str] | None:
    """Project a golden frame's stderr text to a ``{format, body}`` view, if any.

    The stderr envelope (a refusal's error document) is already the primary
    output view; this surfaces only the non-envelope stderr text a frame emitted
    alongside its stdout.
    """
    if golden_frame.envelope_source != "stderr" and golden_frame.stderr_text:
        return {"format": "text", "body": golden_frame.stderr_text}
    return None


def _frame_payload(
    parsed_frame: SequenceFrame,
    golden_frame: GoldenFrame,
    index: int,
) -> dict[str, Any]:
    """Build one frame's payload dict from the authored frame and its golden.

    The command line and its tokens come from the AUTHORED frame (``{name}``
    placeholders intact, so the reader sees the reproducible form); the output,
    exit code, and captures come from the committed golden.
    """
    from dev.docs.sequences._tokeniser import tokenise_command

    tokens = tokenise_command(parsed_frame.argv)
    payload: dict[str, Any] = {
        "index": index,
        "kind": parsed_frame.kind.value,
        "command_line": parsed_frame.command_line,
        "tokens": [token.model_dump(mode="json") for token in tokens],
        "exit_code": golden_frame.exit_code,
        "output": _output_view(golden_frame),
        "stderr": _stderr_view(golden_frame),
        "expects": [
            {
                "json_path": assertion.json_path,
                "expected": assertion.expected,
                "narration": _expect_narration(assertion.json_path, assertion.expected),
            }
            for assertion in parsed_frame.expects
        ],
    }
    return payload


def build_sequence_payload(sequence: ParsedSequence, golden: SequenceGolden) -> dict[str, Any]:
    """Assemble the one inline payload for a sequence from its parse and golden.

    Raises:
        ValueError: When the authored body and its committed golden disagree on
            frame count or a frame's kind — the golden is stale and must be
            refreshed.
    """
    if len(sequence.frames) != len(golden.frames):
        raise ValueError(
            f"the golden for {sequence.sequence_id!r} has {len(golden.frames)} frames "
            f"but the directive body parses to {len(sequence.frames)}; refresh the golden",
        )
    frames: list[dict[str, Any]] = []
    for index, (parsed_frame, golden_frame) in enumerate(zip(sequence.frames, golden.frames, strict=True)):
        if parsed_frame.kind is not golden_frame.kind:
            raise ValueError(
                f"frame {index} of {sequence.sequence_id!r} is {parsed_frame.kind.value!r} in the "
                f"body but {golden_frame.kind.value!r} in the golden; refresh the golden",
            )
        frames.append(_frame_payload(parsed_frame, golden_frame, index))
    return {"sequence_id": sequence.sequence_id, "verify": sequence.verify, "frames": frames}


def _render_tokens_html(tokens: list[dict[str, Any]]) -> str:
    """Render a frame's classified tokens as space-joined highlighted spans."""
    spans: list[str] = []
    for token in tokens:
        attrs = [f'class="cli-tok cli-tok-{html.escape(token["kind"])}"']
        if token.get("command_path"):
            attrs.append(f'data-command-path="{html.escape(token["command_path"])}"')
        if token.get("option_name"):
            attrs.append(f'data-option="{html.escape(token["option_name"])}"')
        spans.append(f"<span {' '.join(attrs)}>{html.escape(token['text'])}</span>")
    return " ".join(spans)


def _render_output_html(view: dict[str, str] | None, *, css_class: str) -> str:
    """Render a ``{format, body}`` output view as a ``pre`` block, or empty string."""
    if not view or view["format"] == "empty" or not view["body"]:
        return ""
    data_format = html.escape(view["format"])
    body = html.escape(view["body"])
    return f'<pre class="{css_class}" data-format="{data_format}">{body}</pre>'


def _render_frame_html(frame: dict[str, Any], verify: str) -> str:
    """Render one frame's static HTML from its payload dict."""
    parts: list[str] = [
        f'<div class="cadrumo-frame" data-frame-index="{frame["index"]}" '
        f'data-frame-kind="{html.escape(frame["kind"])}">',
        '<div class="cadrumo-frame-command"><pre><code>'
        f'{_render_tokens_html(frame["tokens"])}</code></pre></div>',
    ]
    output_html = _render_output_html(frame["output"], css_class="cadrumo-frame-output")
    if output_html:
        parts.append(output_html)
    stderr_html = _render_output_html(frame.get("stderr"), css_class="cadrumo-frame-stderr")
    if stderr_html:
        parts.append(stderr_html)
    if frame["kind"] == "result":
        parts.append(f'<p class="cadrumo-verify">{html.escape(verify)}</p>')
        if frame["expects"]:
            checks = "".join(
                f'<li>{html.escape(expect["narration"])}</li>' for expect in frame["expects"]
            )
            parts.append(f'<ul class="cadrumo-expects">{checks}</ul>')
    parts.append("</div>")
    body = "".join(parts)
    if frame["kind"] == "setup":
        return f'<details class="cadrumo-setup"><summary>Preparation</summary>{body}</details>'
    return body


def render_sequence_html(payload: dict[str, Any]) -> str:
    """Render the full server-side sequence HTML from its payload (ADR D5).

    The static frames and the inline ``application/json`` payload are both
    produced from ``payload``, so the two content sources cannot drift; a widget
    only enhances the already-complete transcript.
    """
    sequence_id = html.escape(payload["sequence_id"])
    frames_html = "".join(_render_frame_html(frame, payload["verify"]) for frame in payload["frames"])
    payload_json = json.dumps(payload, ensure_ascii=False)
    # </script> in JSON content is escaped so the inline payload cannot break out
    # of its own script element.
    payload_json = payload_json.replace("</", "<\\/")
    return (
        f'<div class="cadrumo-sequence" data-cadrumo-sequence="1" data-sequence-id="{sequence_id}">'
        f'{frames_html}'
        f'<script type="application/json" class="cadrumo-sequence-payload">{payload_json}</script>'
        "</div>"
    )


class CliSequenceDirective(Directive):
    """The backtick-fenced ``{cli-sequence}`` MyST directive (ADR D1 / D5).

    Argument: the unique sequence id. Options: the required ``:verify:`` singular
    imperative sentence and the optional ``:seed:`` recipe name. Body: the frame
    lines. The directive parses the body, reads the committed golden for the
    current page, and emits server-rendered static frames plus one inline JSON
    payload. It never executes a command.
    """

    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = False
    has_content = True
    option_spec = {
        "seed": directives.unchanged,
        "verify": directives.unchanged,
    }

    @override
    def run(self) -> list[nodes.Node]:
        """Parse the body, render from the committed golden, and emit the frames + payload."""
        from pathlib import Path

        from dev.docs.sequences import parse_sequence, read_golden
        from dev.docs.sequences._errors import SequenceEngineError

        sequence_id = self.arguments[0].strip()
        env = self.state.document.settings.env
        page = env.docname
        # The golden and seed roots default to the committed ``docs/_sequences``
        # tree; a Sphinx config value (tests set it to a fixture directory)
        # overrides each so the directive is buildable in isolation.
        goldens_root = getattr(env.config, "cadrumo_sequences_goldens_root", None)
        seeds_root = getattr(env.config, "cadrumo_sequences_seeds_root", None)
        goldens_root = Path(goldens_root) if goldens_root else None
        seeds_root = Path(seeds_root) if seeds_root else None
        options = {"seed": self.options.get("seed"), "verify": self.options.get("verify")}
        body = "\n".join(self.content)

        try:
            sequence = parse_sequence(sequence_id=sequence_id, options=options, body=body, seeds_root=seeds_root)
            golden = read_golden(page, sequence_id, goldens_root=goldens_root)
            payload = build_sequence_payload(sequence, golden)
        except SequenceEngineError as exc:
            raise self.error(f"cli-sequence {sequence_id!r} on page {page!r}: {exc}") from exc
        except ValueError as exc:
            raise self.error(f"cli-sequence {sequence_id!r} on page {page!r}: {exc}") from exc

        return [nodes.raw("", render_sequence_html(payload), format="html")]


def register(app: Sphinx) -> None:
    """Register the ``cli-sequence`` directive and its config values on the Sphinx app.

    ``cadrumo_sequences_goldens_root`` and ``cadrumo_sequences_seeds_root`` default
    to ``None`` (the engine's committed ``docs/_sequences`` roots); a build sets
    them only to redirect the directive at a fixture tree in isolation.
    """
    app.add_config_value("cadrumo_sequences_goldens_root", None, "env")
    app.add_config_value("cadrumo_sequences_seeds_root", None, "env")
    app.add_directive("cli-sequence", CliSequenceDirective)
