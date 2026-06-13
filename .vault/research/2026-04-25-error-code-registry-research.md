---
tags:
  - '#research'
  - '#error-code-registry'
date: '2026-04-25'
modified: '2026-04-25'
related:
  - "[[2026-04-24-aeat-cli-wireframe-reference]]"
  - "[[2026-04-24-aeat-cli-wireframe-adr]]"
  - "[[2026-04-18-live-submit-cli-excision-adr]]"
---



# `error-code-registry` research: `iteration-6-error-registry-shape`

This research grounds issue #398 against EPIC #392, the 2026-04-24 CLI
wireframe iteration-6 contract, the 2026-04-24 CLI wireframe ADR, the
2026-04-18 live-submit excision ADR, the current `src/aeat/` error and CLI
layout, and prior-art behavior from Rich, Pydantic, Click, Typer, and
`click_didyoumean`. The goal is to determine the smallest defensible shape
that can satisfy iteration 6 without drifting from the current codebase.

## Findings

### Grounded requirements from issue #398 and iteration 6

- Issue #398 requires a central registry at `src/aeat/core/errors/_registry.py`
  backed by a frozen Pydantic v2 model, a registered `code` on every
  `AeatError` subclass, a CLI error-emission decorator, a JSON error envelope,
  stable stderr prefixes, and CI enforcement against freeform CLI errors.
- EPIC #392 places issue #398 in Phase A infrastructure, alongside the JSON
  schema work in issue #399. This means the design should optimize for
  cross-cutting adoption, not a one-subcommand local patch.
- The 2026-04-24 iteration-6 reference makes the category table the primary
  contract: closed-set categories, stable stderr prefixes, stable exit codes,
  exact redirect-message shape, stderr-only error framing, and clean stdout.
- The 2026-04-18 live-submit excision ADR matters directly because it already
  establishes refusal-style policy errors as a first-class operator-facing
  surface. Iteration 6 formalizes that into a stable `REFUSED:` category
  instead of ad hoc refusal wording.

### What the current codebase looks like today

- `src/aeat/errors.py` is a plain inheritance tree. It has no central error
  registry, no category taxonomy, no shared payload shape, and no CLI emission
  helper.
- The root CLI is `src/aeat/entrypoints/cli/__init__.py`, which registers many Typer
  sub-apps directly. There is no single error translator at the root.
- Error handling is fragmented:
  - many CLI paths raise `typer.BadParameter`;
  - many CLI paths print a string and then raise `typer.Exit(code=...)`;
  - some commands use `rich.console.Console.print()` with ad hoc prefixes such
    as `export REFUSED`, `export UNSUPPORTED`, `corpus drift`, or `replay
    refused`;
  - some domain exceptions carry local `code` values already, for example
    `src/aeat/domain/casillas/errors.py`, but those codes are local identifiers, not
    iteration-6 registry entries.
- The existing JSON error behavior is also inconsistent with iteration 6.
  `src/aeat/entrypoints/cli/submission/test_json_output_contract.py` and
  `src/aeat/entrypoints/cli/submission/test_verify.py` currently assert JSON error payloads
  on stdout. Iteration 6 requires human-readable stderr plus the machine
  envelope on stderr, while stdout remains clean.
- The current Typer default is already visible in tests as a problem.
  `src/aeat/entrypoints/cli/auth/test_auth_cli.py` has to strip Rich panel borders and ANSI
  escapes before asserting on error text. That is direct evidence that the
  default renderer is not grep-stable enough for iteration 6.
- Exit-code meaning is currently local, not global. For example:
  - `src/aeat/entrypoints/cli/submission/test_exit_code_contract.py` locks a submission-only
    contract where `1`, `2`, and `3` already mean specific things;
  - `src/aeat/entrypoints/cli/browser/health.py` maps browser health states to `0`, `2`,
    `3`, `4`, `5`, and `6`;
  - other commands use `1` or `2` opportunistically.
  Iteration 6 therefore introduces a repo-wide contract change, not just a new
  registry file.

### Prior-art patterns and what they imply

#### Click `ClickException`

- Click handles `ClickException` centrally in `Command.main()`, calls
  `ClickException.show()` to write to stderr, and exits with the exception's
  `exit_code`.
- `BadParameter` is useful because Click augments it with parameter context.
- This is the closest match to iteration 6's need for a central translation
  point.
- Limitation: Click's default user-facing shape is still generic `Error: ...`
  output and does not provide category vocabulary, JSON stderr envelopes, or a
  structured code registry.

#### Typer exception behavior

- Typer inherits Click's exception model but adds Rich-powered pretty
  exceptions by default for uncaught failures.
- Typer's official exception docs explicitly note that Rich is used to render
  friendlier tracebacks and can be disabled globally with `TYPER_USE_RICH` or
  via `pretty_exceptions_enable=False`.
- Typer also documents `typer.Exit()` as a control-flow mechanism whose default
  code is `0`, and `typer.Abort()` as a special abort path that prints
  `Aborted!`.
- This is valuable for developer debugging, but it conflicts with the
  iteration-6 operator contract because it introduces panel layout, frame
  elision, optional local-variable dumps, and wording that the AEAT CLI does
  not control tightly enough.

#### Rich tracebacks

- Rich's traceback support is intentionally presentation-heavy: syntax
  highlighting, code excerpts, optional locals, suppressed framework frames,
  and multi-line layout.
- The Rich docs explicitly position this for readability and debugging, not for
  machine-grep-stable operator contracts.
- This makes Rich tracebacks a good fit only for the `internal_error` path,
  gated behind verbose or debug output. They are the wrong default for
  iteration-6 business and policy failures.

#### Pydantic `ValidationError`

- Pydantic v2 `ValidationError` exposes both human and machine surfaces:
  `str(e)`, `json()`, `error_count()`, and `errors()`.
- The `errors()` entries carry machine-readable fields such as `type`, `loc`,
  `msg`, `ctx`, `input`, and a documentation `url`.
- The important pattern is not the exact text. It is the split between a stable
  machine payload and a separate human rendering. That maps cleanly to
  iteration 6's stderr line plus JSON envelope requirement.
- This also supports using Pydantic for the registry model itself, because the
  project already depends on Pydantic v2 and uses it widely.

#### `click_didyoumean`

- `click_didyoumean` works by overriding command resolution, catching
  `click.exceptions.UsageError`, computing close matches with
  `difflib.get_close_matches`, and appending a "Did you mean one of these?"
  block.
- The useful idea is the timing: suggestion logic belongs in command
  resolution, before the callback runs.
- The limitation is the output shape. Iteration 6 does not want a generic list
  of guessed names. It wants a registered category and an exact copy-paste
  command under `-> Run ...`.

### Recommended shape

#### 1. Separate category policy from code registry rows

The cleanest shape is a two-layer model:

- a closed `ErrorCategory` enum plus a single category-spec table owning
  `prefix` and `exit_code`;
- a frozen `ErrorCode` Pydantic model owning per-code metadata:
  `code`, `category`, `default_message_es`, `default_message_en`,
  `default_message_hu`, `default_suggestion`, `retryable`, and `runbook_id`.

This avoids duplicating the same prefix and exit-code values on every row while
keeping the category table visibly aligned with iteration 6.

#### 2. Make registered code mandatory on AEAT domain errors

`AeatError` should become the typed domain boundary for CLI-facing failures.
Each concrete subclass should declare a stable class-level `code`, and the
instance should carry only runtime fields such as resolved message override,
suggestion override, structured context, and chained cause.

That preserves the current inheritance style already used across
`src/aeat/`, while giving the registry a single lookup key.

#### 3. Add a central CLI translator, not only a decorator

Issue #398 asks for a decorator around every Click command, but a decorator by
itself is insufficient. Unknown commands, unknown options, missing arguments,
and parser-time `BadParameter` failures happen before the command callback is
invoked.

The recommended design therefore has two coordinated layers:

- callback wrapping for command bodies, catching `AeatError`,
  `pydantic.ValidationError`, and unexpected `Exception`;
- a root Click/Typer integration point that catches parser and resolver
  failures such as `ClickException`, including command suggestions.

Without both layers, the registry will cover only post-parse failures and the
CLI will still leak raw Click/Typer output at parse time.

#### 4. Keep Rich only for controlled bug output

The default operator path should emit plain stderr lines that the AEAT CLI owns
fully. Rich traceback output should be reserved for `internal_error`, ideally
only when a verbose or debug mode is active.

That keeps iteration 6's machine-stable prefixes intact while still preserving
high-value debugging output when needed.

#### 5. Treat suggestions as structured data, not appended prose

The registry should own the default suggestion text, and command-resolution
logic may compute a better concrete suggestion when the failure is a misspelled
command or alias.

The final emitted value should still collapse to one canonical copy-paste
command for the JSON envelope and the first `-> Run ...` line. If multiple
paths truly exist, iteration 6 already allows multiple arrow lines in human
stderr, but the machine envelope should stay singular and deterministic.

#### 6. Narrow the first enforcement boundary to CLI-reachable failures

A literal "every freeform raise in `src/aeat/` fails CI" sweep is larger than
issue #398's value and would force unrelated domain cleanup before the
infrastructure lands.

The defensible first boundary is:

- every `AeatError` subclass must declare a registered code;
- every CLI-raised user-facing failure under `src/aeat/entrypoints/cli/` must normalize
  into a registered code before emission;
- non-CLI deep internals may still raise native exceptions temporarily if the
  CLI boundary translates them into registered fallback codes such as
  validation, system failure, or internal error.

This still satisfies the spirit of iteration 6 while keeping the implementation
phaseable.

### Why this shape best matches iteration 6

- It preserves the closed-set category contract directly instead of burying it
  in scattered exception classes.
- It explains how to catch both parse-time and runtime failures, which the
  issue text alone does not spell out.
- It aligns with the current codebase's strong use of typed domain exceptions
  and Pydantic models, rather than inventing a parallel mechanism.
- It gives a clear home for the live-submit refusal contract from the
  2026-04-18 ADR.
- It provides a path to migrate today's ad hoc CLI output without rewriting the
  entire domain tree in one pass.
- It supports iteration 7 naturally because the same central translator can own
  the stderr JSON envelope once the schema contract is locked.

### Consequences and ADR inputs

- The root CLI construction in `src/aeat/entrypoints/cli/__init__.py` will need an explicit
  decision about whether to disable Typer pretty exceptions globally. The
  research recommendation is yes for the operator surface.
- Existing tests that assert JSON error documents on stdout will need to move
  to stderr-focused assertions when issue #398 and issue #399 land together.
- Existing submission/browser exit-code contracts will need reconciliation
  against the iteration-6 category table. That should be treated as a planned
  contract migration, not accidental fallout.
- Suggestion validation should be parser-based, not string-based. The issue
  text is correct to require that every registered suggestion parse against the
  live CLI tree.
- Runbook linkage should use the registry row, not hard-coded help text, so
  future operational docs stay keyed by error code.

### Recommendation

Adopt a category-table-plus-code-registry design, make `AeatError.code`
mandatory for concrete subclasses, add a central CLI translation layer that
handles both Click parse errors and command-body exceptions, disable Typer's
default pretty exception surface for normal operator failures, and reserve Rich
tracebacks for controlled internal-error debugging. This is the smallest shape
that satisfies issue #398 and the 2026-04-24 iteration-6 contract without
fighting the current codebase.
