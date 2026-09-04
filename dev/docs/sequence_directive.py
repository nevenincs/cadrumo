"""The ``cli-sequence`` MyST directive: server-rendered frames plus one inline payload.

An author writes a backtick-fenced ``{cli-sequence}`` directive; at build time
this directive parses the body into typed frames, reads the sequence's committed
golden (it RENDERS from the golden, it never executes — the engine's check/refresh
CLI owns execution), tokenises each command line against the command graph, and
emits, in document order:

- each reader-facing frame as static HTML — setup scaffolding and expectation
  assertions remain build-only;
- exactly one inline ``script[type="application/json"]`` payload per sequence,
  carrying those same reader-facing frames and per-token command-path keys.

Both surfaces are rendered from ONE computed payload, so the JSON a widget reads
cannot drift from the visible frames. The browser widget (not yet built) only
toggles visibility and adds controls; it never injects content. A missing or
stale golden is an instructive build error naming the exact ``refresh`` command.

This module lives outside the ``dev/docs/sequences`` engine package; ``docs/conf.py``
registers the directive by calling :func:`register`.
"""

from __future__ import annotations

import html
import json
from functools import cache
from typing import TYPE_CHECKING, Any, ClassVar, override

from docutils import nodes
from docutils.parsers.rst import Directive, directives

if TYPE_CHECKING:
    from sphinx.application import Sphinx

    from .cli_tree import CliTree
    from .sequences import CommandToken, GoldenFrame, ParsedSequence, SequenceFrame, SequenceGolden

__all__ = [
    "CliSequenceDirective",
    "build_sequence_payload",
    "parse_shells",
    "register",
    "render_sequence_html",
    "wrap_token_lines",
]

#: The pseudo-path an ``@expect`` uses to assert a frame's process exit code.
_EXIT_CODE_PATH = "exit_code"

#: The supported reader-facing shells, in canonical order. The ``:shells:``
#: directive option is an ordered subset of these; the first entry is the tab
#: shown by default. bash covers Linux/macOS terminals, pwsh covers Windows.
_SUPPORTED_SHELLS: tuple[str, ...] = ("bash", "pwsh")

#: The default ``:shells:`` set when the option is omitted (both, bash first).
_DEFAULT_SHELLS: tuple[str, ...] = _SUPPORTED_SHELLS

#: Per-shell line-continuation marker: a trailing ``\`` in bash, a trailing
#: backtick in PowerShell. Rendered as its own ``cli-continuation`` span so it
#: is styleable and excluded from copied command text.
_SHELL_CONTINUATION: dict[str, str] = {"bash": "\\", "pwsh": "`"}

#: Display-column budget for the wrapped command line.
_WRAP_WIDTH: int = 88

#: Continuation-line indent, in spaces, for wrapped command lines.
_CONTINUATION_INDENT: str = "  "


def parse_shells(raw: str | None) -> list[str]:
    """Parse the ``:shells:`` option into an ordered, de-duplicated shell list.

    ``None`` or blank yields the default (``bash pwsh``). Every entry must be a
    supported shell; an unknown value raises with the accepted set named.

    Raises:
        ValueError: When a value is not one of the supported shells.
    """
    if raw is None or not raw.strip():
        return list(_DEFAULT_SHELLS)
    ordered: list[str] = []
    for shell in raw.split():
        if shell not in _SUPPORTED_SHELLS:
            raise ValueError(
                f":shells: value {shell!r} is not a supported shell; "
                f"accepted values are {', '.join(_SUPPORTED_SHELLS)}",
            )
        if shell not in ordered:
            ordered.append(shell)
    return ordered


def wrap_token_lines(token_texts: list[str], *, width: int = _WRAP_WIDTH) -> list[list[int]]:
    """Pack whole tokens onto display lines within ``width``, never splitting a token.

    Greedy, token-boundary wrapping computed from the display widths of the
    token texts: the first line has no indent, every continuation line is
    indented by :data:`_CONTINUATION_INDENT`. A token that alone exceeds the
    budget occupies its own line (it is never split). Returns the token indices
    grouped per line; a command that fits on one line yields a single line.
    """
    indent = len(_CONTINUATION_INDENT)
    lines: list[list[int]] = []
    current: list[int] = []
    for index, text in enumerate(token_texts):
        if not current:
            current.append(index)
            continue
        line_indent = 0 if not lines else indent
        content = line_indent + sum(len(token_texts[i]) for i in current) + (len(current) - 1)
        if content + 1 + len(text) <= width:
            current.append(index)
        else:
            lines.append(current)
            current = [index]
    if current:
        lines.append(current)
    return lines


def _first_sentence(text: str) -> str:
    """Return the first sentence of a help string (whitespace collapsed)."""
    collapsed = " ".join(text.split())
    if not collapsed:
        return ""
    dot = collapsed.find(". ")
    if dot != -1:
        return collapsed[: dot + 1]
    return collapsed


@cache
def _cli_tree() -> CliTree:
    """Build and cache the in-process ``cli-tree.json`` projection for header fallback."""
    from .cli_tree import build_cli_tree

    return build_cli_tree()


def _leaf_help_summary(tokens: tuple[CommandToken, ...]) -> str:
    """Return the deepest verb's help first sentence, or the bare verb path.

    The header falls back to the leaf command's own help so an un-annotated frame
    still reads as an instruction; when no leaf help resolves in the projection,
    the bare command path is the last resort.
    """
    from .cli_tree import resolve_command_path

    verb_kinds = {"executable", "group", "leaf"}
    verb_paths = [token.command_path for token in tokens if token.kind.value in verb_kinds and token.command_path]
    leaf_path = verb_paths[-1] if verb_paths else "aeat"
    try:
        node = resolve_command_path(_cli_tree(), leaf_path)
    except LookupError:
        return leaf_path
    return _first_sentence(node.help) or leaf_path


def _frame_header(parsed_frame: SequenceFrame, tokens: tuple[CommandToken, ...]) -> str:
    """Return one frame's imperative header line (the "do this" instruction).

    The authored ``@step`` sentence (``SequenceFrame.step_description``) wins when
    present; otherwise the leaf verb's help summary carries the instruction.
    """
    authored = getattr(parsed_frame, "step_description", None)
    if authored and authored.strip():
        return authored.strip()
    return _leaf_help_summary(tokens)


def _output_view(golden_frame: GoldenFrame) -> dict[str, str]:
    """Project a golden frame's primary stream to a ``{format, body}`` view.

    The pre-mask envelope is masked with exactly the central mask and canonically
    rendered so the displayed JSON is deterministic; otherwise the frame's
    normalised stdout text is shown, or an empty view when the frame produced no
    stdout content.
    """
    from cadrumo.tests.golden_comparison import canonicalise, mask_document

    if golden_frame.envelope is not None:
        # canonicalise already renders the key-sorted, indented JSON string;
        # dumping it again would double-encode the display into `\n`-escape noise.
        return {"format": "json", "body": canonicalise(mask_document(golden_frame.envelope))}
    if golden_frame.text:
        return {"format": "text", "body": _with_live_version(golden_frame.text)}
    return {"format": "empty", "body": ""}


def _with_live_version(body: str) -> str:
    """Substitute the running version back into a rendered golden body.

    The golden stores :data:`PACKAGE_VERSION_TOKEN` rather than a version
    literal, so it never rots at a release and never disagrees with the build the
    reader has. Rendering resolves it from the package's single release-managed
    declaration, which is what makes the displayed version derived rather than
    hardcoded. A body carrying no token is returned unchanged.
    """
    from cadrumo import __version__

    from .sequences.golden_store import PACKAGE_VERSION_TOKEN

    return body.replace(PACKAGE_VERSION_TOKEN, __version__)


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
    golden_frame: GoldenFrame | None,
    index: int,
    shells: list[str],
) -> dict[str, Any]:
    """Build one frame's payload dict from the authored frame and its golden.

    The command line and its tokens come from the AUTHORED frame (``{name}``
    placeholders intact, so the reader sees the reproducible form); the output
    and exit code come from the committed golden. ``wrapped`` carries
    the token-index groupings per display line for each declared shell — the
    packing is shell-independent (only the continuation marker differs), so the
    groupings are identical across shells and the render appends the shell's
    marker at build time. A ``@static`` frame passes ``golden_frame=None``: it is
    display-only, so it carries no output, no stderr, and no exit code (output is
    never fabricated).
    """
    from .sequences import tokenise_command

    tokens = tokenise_command(parsed_frame.argv)
    token_dicts = [token.model_dump(mode="json") for token in tokens]
    lines = wrap_token_lines([token["text"] for token in token_dicts])
    payload: dict[str, Any] = {
        "index": index,
        "kind": parsed_frame.kind.value,
        "header": _frame_header(parsed_frame, tokens),
        "command_line": parsed_frame.command_line,
        "tokens": token_dicts,
        "wrapped": {shell: [list(line) for line in lines] for shell in shells},
        "exit_code": golden_frame.exit_code if golden_frame is not None else None,
        "output": _output_view(golden_frame) if golden_frame is not None else {"format": "empty", "body": ""},
        "stderr": _stderr_view(golden_frame) if golden_frame is not None else None,
    }
    return payload


def build_sequence_payload(
    sequence: ParsedSequence,
    golden: SequenceGolden | None,
    *,
    shells: list[str] | None = None,
) -> dict[str, Any]:
    """Assemble the one inline payload for a sequence from its parse and golden.

    ``shells`` is the ordered reader-facing shell set (default ``bash pwsh``);
    the first entry is the default variant. ``@static`` frames render from the
    parse alone (no golden); ``golden`` is the executed-frames golden, aligned
    1:1 with the sequence's executed (non-static) frames, and is ``None`` for an
    all-static sequence (nothing executes, so there is no golden).

    Raises:
        ValueError: When the authored body's executed frames and its committed
            golden disagree on count or a frame's kind — the golden is stale and
            must be refreshed.
    """
    resolved_shells = shells if shells else list(_DEFAULT_SHELLS)
    golden_frames = golden.frames if golden is not None else ()
    executed = [frame for frame in sequence.frames if frame.kind.value != "static"]
    if len(executed) != len(golden_frames):
        raise ValueError(
            f"the golden for {sequence.sequence_id!r} has {len(golden_frames)} frames "
            f"but the directive body parses to {len(executed)} executed frames; refresh the golden",
        )
    frames: list[dict[str, Any]] = []
    golden_index = 0
    for source_index, parsed_frame in enumerate(sequence.frames):
        if parsed_frame.kind.value == "static":
            frames.append(_frame_payload(parsed_frame, None, len(frames), resolved_shells))
            continue
        golden_frame = golden_frames[golden_index]
        if parsed_frame.kind is not golden_frame.kind:
            raise ValueError(
                f"frame {source_index} of {sequence.sequence_id!r} is {parsed_frame.kind.value!r} in the "
                f"body but {golden_frame.kind.value!r} in the golden; refresh the golden",
            )
        golden_index += 1
        if parsed_frame.kind.value == "setup":
            continue
        frames.append(_frame_payload(parsed_frame, golden_frame, len(frames), resolved_shells))
    return {
        "sequence_id": sequence.sequence_id,
        "verify": sequence.verify,
        "shells": resolved_shells,
        "frames": frames,
    }


def _render_token_span(token: dict[str, Any]) -> str:
    """Render one classified token as a highlighted span."""
    attrs = [f'class="cli-tok cli-tok-{html.escape(token["kind"])}"']
    if token.get("command_path"):
        attrs.append(f'data-command-path="{html.escape(token["command_path"])}"')
    if token.get("option_name"):
        attrs.append(f'data-option="{html.escape(token["option_name"])}"')
    return f"<span {' '.join(attrs)}>{html.escape(token['text'])}</span>"


def _render_command_variant(tokens: list[dict[str, Any]], wrapped_lines: list[list[int]], shell: str) -> str:
    """Render one shell's command variant: the wrapped tokenised lines with markers.

    Each non-final display line ends with the shell's continuation marker (a
    ``cli-continuation`` span, excluded from copied text); continuation lines are
    indented. The variant carries ``data-shell`` so the widget can toggle it and
    the CSS can key the shell prompt.
    """
    marker = _SHELL_CONTINUATION[shell]
    rendered: list[str] = []
    for line_index, line in enumerate(wrapped_lines):
        indent = "" if line_index == 0 else _CONTINUATION_INDENT
        spans = " ".join(_render_token_span(tokens[i]) for i in line)
        is_final = line_index == len(wrapped_lines) - 1
        continuation = "" if is_final else f' <span class="cli-continuation">{html.escape(marker)}</span>'
        rendered.append(f"{indent}{spans}{continuation}")
    body = "\n".join(rendered)
    return f'<div class="cadrumo-cmd-variant" data-shell="{html.escape(shell)}"><pre><code>{body}</code></pre></div>'


def _render_output_html(view: dict[str, str] | None, *, css_class: str) -> str:
    """Render a ``{format, body}`` output view as a ``pre`` block, or empty string.

    A JSON body is syntax-highlighted at build time with Pygments (the same
    engine and CSS classes the docs' code blocks use, so the theme palette
    applies in light and dark); text bodies render escaped and plain.
    """
    if not view or view["format"] == "empty" or not view["body"]:
        return ""
    data_format = html.escape(view["format"])
    if view["format"] == "json":
        from pygments import highlight
        from pygments.formatters import HtmlFormatter
        from pygments.lexers import JsonLexer

        # No `highlight` class here: the docs' `.content .highlight` code-block
        # chrome would out-specify this panel's layout. The token spans are
        # coloured by the panel's own palette in cadrumo-docs.css.
        body = highlight(view["body"], JsonLexer(), HtmlFormatter(nowrap=True)).rstrip("\n")
        return f'<pre class="{css_class}" data-format="{data_format}">{body}</pre>'
    body = html.escape(view["body"])
    return f'<pre class="{css_class}" data-format="{data_format}">{body}</pre>'


def _render_frame_html(frame: dict[str, Any], verify: str | None, shells: list[str]) -> str:
    """Render one frame's static HTML from its payload dict.

    The command block carries one ``cadrumo-cmd-variant`` per declared shell (the
    CSS shows the default shell without JavaScript); the frame div carries the
    single-line authored command in ``data-command-line`` so the widget's copy
    control works from the static DOM without parsing the payload.
    """
    variants = "".join(_render_command_variant(frame["tokens"], frame["wrapped"][shell], shell) for shell in shells)
    header = (
        '<div class="cadrumo-frame-header">'
        f'<span class="cadrumo-frame-step">{frame["index"] + 1}</span>'
        f'<span class="cadrumo-frame-desc">{html.escape(frame["header"])}</span>'
        "</div>"
    )
    parts: list[str] = [
        f'<div class="cadrumo-frame" data-frame-index="{frame["index"]}" '
        f'data-frame-kind="{html.escape(frame["kind"])}" '
        f'data-command-line="{html.escape(frame["command_line"])}">',
        header,
        f'<div class="cadrumo-frame-command">{variants}</div>',
    ]
    output_html = _render_output_html(frame["output"], css_class="cadrumo-frame-output")
    if output_html:
        parts.append(output_html)
    stderr_html = _render_output_html(frame.get("stderr"), css_class="cadrumo-frame-stderr")
    if stderr_html:
        parts.append(stderr_html)
    if frame["kind"] == "result" and verify is not None:
        parts.append(f'<p class="cadrumo-verify">{html.escape(verify)}</p>')
    parts.append("</div>")
    return "".join(parts)


def render_sequence_html(payload: dict[str, Any]) -> str:
    """Render the full server-side sequence HTML from its payload.

    The static frames and the inline ``application/json`` payload are both
    produced from ``payload``, so the two content sources cannot drift; a widget
    only enhances the already-complete transcript.
    """
    sequence_id = html.escape(payload["sequence_id"])
    shells = payload["shells"]
    default_shell = html.escape(shells[0])
    frames_html = "".join(_render_frame_html(frame, payload["verify"], shells) for frame in payload["frames"])
    payload_json = json.dumps(payload, ensure_ascii=False)
    # </script> in JSON content is escaped so the inline payload cannot break out
    # of its own script element.
    payload_json = payload_json.replace("</", "<\\/")
    # data-cadrumo-shell selects the visible variant; set to the default here so
    # the correct shell shows without JavaScript (the widget only updates it).
    return (
        f'<div class="cadrumo-sequence" data-cadrumo-sequence="1" data-sequence-id="{sequence_id}" '
        f'data-cadrumo-shell="{default_shell}">'
        f"{frames_html}"
        f'<script type="application/json" class="cadrumo-sequence-payload">{payload_json}</script>'
        "</div>"
    )


class CliSequenceDirective(Directive):
    """The backtick-fenced ``{cli-sequence}`` MyST directive.

    Argument: the unique sequence id. The sole public option is the
    reader-facing ``:verify:`` sentence. The directive body is empty; frame
    grammar and private seed/shell settings are read from the keyed contract
    under ``docs/_sequences/contracts``. The directive reads the committed
    golden and emits server-rendered static frames plus one inline JSON payload.
    It never executes a command.
    """

    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = False
    has_content = True
    option_spec: ClassVar[dict[str, object]] = {
        "seed": directives.unchanged,
        "verify": directives.unchanged,
        "shells": directives.unchanged,
    }

    @override
    def run(self) -> list[nodes.Node]:
        """Parse the body, render from the committed golden, and emit the frames + payload."""
        from pathlib import Path

        from .sequences import (
            parse_sequence,
            read_golden,
            read_sequence_contract,
            refuse_live_frames,
        )
        from .sequences.errors import SequenceEngineError

        sequence_id = self.arguments[0].strip()
        env = self.state.document.settings.env
        page = env.docname
        # The golden and seed roots default to the committed ``docs/_sequences``
        # tree; a Sphinx config value (tests set it to a fixture directory)
        # overrides each so the directive is buildable in isolation.
        goldens_root = getattr(env.config, "cadrumo_sequences_goldens_root", None)
        seeds_root = getattr(env.config, "cadrumo_sequences_seeds_root", None)
        contracts_root = getattr(env.config, "cadrumo_sequences_contracts_root", None)
        goldens_root = Path(goldens_root) if goldens_root else None
        seeds_root = Path(seeds_root) if seeds_root else None
        contracts_root = Path(contracts_root) if contracts_root else None
        body = "\n".join(self.content)

        try:
            if body.strip():
                raise SequenceEngineError(
                    "directive bodies must be empty; commands and development metadata "
                    "belong in the keyed private sequence contract",
                )
            public_private_options = sorted(set(self.options) - {"verify"})
            if public_private_options:
                rendered = ", ".join(f":{key}:" for key in public_private_options)
                raise SequenceEngineError(
                    f"private option(s) {rendered} must live in the keyed sequence contract",
                )
            contract_options, contract_body = read_sequence_contract(
                page,
                sequence_id,
                docs_root=Path(env.srcdir),
                contracts_root=contracts_root,
            )
            options = {**contract_options, "verify": self.options.get("verify")}
            shells = parse_shells(contract_options.get("shells"))
            sequence = parse_sequence(
                sequence_id=sequence_id,
                options=options,
                body=contract_body,
                seeds_root=seeds_root,
            )
            # Statically refuse an enrolled sequence that reads live AEAT (a pull
            # verb or the app-live group): it is unenrollable at build time, not
            # only at execution, so the author gets a clear error here rather
            # than an opaque missing-golden failure.
            refuse_live_frames(sequence)
            # An all-@static sequence executes nothing, so it has no golden; it
            # renders from the parse alone. A sequence with executed frames reads
            # its committed golden (executed frames only).
            golden = read_golden(page, sequence_id, goldens_root=goldens_root) if sequence.executed_frames else None
            payload = build_sequence_payload(sequence, golden, shells=shells)
        except SequenceEngineError as exc:
            raise self.error(f"cli-sequence {sequence_id!r} on page {page!r}: {exc}") from exc
        except ValueError as exc:
            raise self.error(f"cli-sequence {sequence_id!r} on page {page!r}: {exc}") from exc

        return [nodes.raw("", render_sequence_html(payload), format="html")]


def register(app: Sphinx) -> None:
    """Register the ``cli-sequence`` directive and its config values on the Sphinx app.

    The golden, seed, and contract config roots default to ``None`` (the
    engine's committed ``docs/_sequences`` roots); a build sets them only to
    redirect the directive at a fixture tree in isolation.
    """
    app.add_config_value("cadrumo_sequences_goldens_root", None, "env")
    app.add_config_value("cadrumo_sequences_seeds_root", None, "env")
    app.add_config_value("cadrumo_sequences_contracts_root", None, "env")
    app.add_directive("cli-sequence", CliSequenceDirective)
