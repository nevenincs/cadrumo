---
tags:
  - '#research'
  - '#json-output-contract'
date: '2026-04-25'
modified: '2026-04-25'
related:
  - "[[2026-04-24-aeat-cli-wireframe-reference]]"
  - "[[2026-04-24-aeat-cli-wireframe-adr]]"
  - "[[2026-04-25-json-output-contract-adr]]"
  - "[[2026-04-25-json-output-contract-plan]]"
---



# `json-output-contract` research: `phase-1 --json output contract foundations for issue 399`

This research grounds issue `#399` against wireframe iterations 6, 7, and 12,
the controlling CLI wireframe ADR, issue `#399`, sibling issue `#398`, and
official CLI documentation for `gh`, `kubectl`, AWS CLI, and Docker. The scope
is restricted to Phase 1 contract foundations: success-envelope shape,
stdout/stderr separation, schema versioning, non-TTY behavior, exit-code
stability, log-level policy, pipe-safety, and scrubber boundaries.

## Findings

### Scope boundary and sibling dependency

- `#399` is a Phase A internal-infrastructure issue under EPIC `#392`. It is
  labelled `parallel-safe`, but the contract is not independent: `#398` owns
  the ErrorEnvelope, error-code registry, stderr prefixes, and category-to-exit
  linkage from iteration 6. Phase 1 for `#399` must consume that surface rather
  than re-specify it.
- Local worktree state confirms `feature/398-error-code-registry` and
  `feature/399-json-output-contract` are sibling branches from the same base
  commit `19a1054`. The ADR and plan should treat `#398` as a sibling-owned
  prerequisite for failure serialization, not as implementation scope to absorb
  here.
- Iteration 7 is the controlling starting point: `--json` switches commands
  into machine mode, stdout emits one JSON document on success, stderr carries
  everything else, and exit codes remain the stable table defined in iterations
  6 and 7.
- Iteration 12 extends the scrub list with certificate serial numbers redacted
  to the last 4 hex digits. Phase 1 should reserve that marker shape now so
  later credential-hygiene work can extend the scrubber without changing output
  semantics.

### External convention takeaways

- GitHub CLI keeps the machine contract narrow: only some commands support
  `--json`; `--jq` and `--template` are layered on top; TTY state affects
  pretty-printing; update notices go to stderr; and exit codes are documented as
  `0`, `1`, `2`, and `4`. Good pattern: machine mode is explicit, and non-result
  notices do not pollute stdout.
- `kubectl` exposes many output dialects: `json`, `yaml`, `name`,
  `go-template`, `jsonpath`, `jsonpath-as-json`, `custom-columns`, and `wide`.
  Its own scripting guidance says reusable scripts should request a
  machine-oriented form explicitly and avoid implicit state. Its Windows
  JSONPath quoting rules are awkward enough to need dedicated documentation.
  Good lesson: extra formatting and query languages expand shell-quoting risk
  and cross-platform support burden.
- AWS CLI separates human and machine concerns more aggressively: `--output`
  chooses among `json`, `yaml`, `yaml-stream`, `text`, `table`, and `off`;
  `--query` behavior changes by output format; errors can be formatted
  structurally on stderr; return codes are documented; and the docs explicitly
  warn that command output and logs can contain sensitive data. Good lesson:
  format proliferation creates surprising semantics unless the contract is very
  explicit.
- Docker uses per-command defaults plus `--format` Go templates. Its docs call
  out shell-specific quoting differences, including PowerShell escaping. Docker
  also documents log paths where environment variables and labels can surface.
  Good lesson: templating is powerful, but it is a contract multiplier and a
  leakage vector.

### Phase 1 recommendations

- Keep Phase 1 to one machine format: `--json` only. Do not introduce a general
  `--output`, built-in `--jq`, JSONPath, or Go-template surface in this issue.
  Users can keep piping to external `jq`, which is already the Kent success
  moment in `#399`.
- Make machine mode byte-stable: stdout should emit exactly one
  newline-terminated JSON document on success, with no TTY-dependent
  pretty-printing. Human readability is the default mode's job; machine mode
  should optimize for reproducibility, `jq`, `tee`, and snapshot tests.
- Version the success envelope explicitly. Add a stable `schema_version` field
  that versions the JSON contract independently from `aeat_cli_version`. Scripts
  should branch on schema version, not package version. Recommended minimum
  success shape is `schema_version`, `command`, `status`, `result`, and
  `metadata`.
- Keep `metadata` transport-oriented and low-sensitivity: `aeat_cli_version`,
  `invoked_at`, and normalized `invocation` belong here. Do not make
  `profile_tax_id` part of the generic metadata contract; include taxpayer
  identifiers only in command-specific `result` objects when they are
  semantically required. This reduces record duplication and leak surface in
  redirected outputs.
- In `--json` mode, stderr should be structured-only. Human prose on stderr is
  correct for default mode, but machine mode should not mix prose with JSON. The
  ErrorEnvelope from `#398` should be the only failure payload on stderr, and
  any progress or warning lines in machine mode should be one JSON object per
  line with an explicit type discriminator. This is the cleanest pipe-safe
  outcome and aligns better with AWS structured-error behavior than mixed
  human-and-machine stderr.
- Preserve the stable exit-code table from iterations 6 and 7 without adding
  new codes in Phase 1. `#399` should consume the category-to-exit mapping from
  `#398`; the output-contract work should not create a second exit registry or
  any command-local bare exit values.
- Treat non-TTY as contract input, not presentation trivia:
  - stdout non-TTY must never change JSON shape
  - stderr non-TTY should suppress spinner-style progress
  - stdin non-TTY must refuse interactive-only flows deterministically via the
    `#398` ErrorEnvelope and stable exit code
- Keep log levels named, not numeric: `--quiet`, default, `--verbose`,
  `--debug`, plus `AEAT_DEBUG=1`. This is easier for Kent than
  `kubectl`-style `-v=7`, and iteration 7 already defines the intended
  semantics. Log level must never change stdout payload shape.
- Make scrubbing record-level and pre-serialization on every stderr and log
  path. Minimum Phase 1 scrub classes should include taxpayer identifiers,
  justificante codes, session IDs, cookies, OAuth secrets, authorization
  headers, LLM or API keys, and the iteration-12 certificate-serial marker
  shape. Do not rely on user-side log hygiene alone; AEAT handles regulated tax
  data and needs an active scrubber.
- Use an allow-list for identifiers that are safe and useful to keep visible in
  diagnostics: `draft_id`, `run_id`, `submission_id`, `amendment_id`,
  `bundle_id`, `modelo`, `period`, and command names. Everything else should
  default to redaction on stderr, debug output, and error context.
- Seed the schema catalogue with shared envelope and event schemas only in Phase
  1. Command-specific `result` schemas for every Kent-first command belong to
  Phase 2 once the transport contract is fixed.
- Phase 1 verification should prove transport invariants, not full command
  coverage. Minimum useful regression coverage is:
  - representative success path: stdout is exactly one valid JSON document,
    stderr empty or structured-only, exit `0`
  - representative failure path: stdout empty, stderr carries only the
    ErrorEnvelope, exit code matches the registered category
  - TTY and non-TTY path: JSON bytes do not change, progress behavior changes
    only on stderr
  - debug path: scrubber redacts blocked fields before emission

### ADR-ready contract decisions

- `#398` owns error serialization. `#399` owns success serialization and the
  shared stdout/stderr transport rules.
- The ADR should state that `--json` is a v1 contract surface, not a convenience
  flag.
- The ADR should promote `schema_version` to a first-class compatibility field.
- The ADR should require zero prose on stdout in machine mode and zero
  unstructured stderr in machine mode.
- The ADR should narrow generic metadata to non-sensitive transport fields.
- The ADR should ban built-in query and template dialects from Phase 1.

### Phase 2 and Phase 3 dependencies

- Phase 2 should backfill per-command schema registration, command-by-command
  adoption across Kent-first commands, and fixture-backed canonical pipeline
  tests covering `jq`, `tee`, and `xargs` patterns.
- Phase 2 should also align success-envelope versioning with the shipped
  ErrorEnvelope from `#398` so success and failure paths present one coherent
  contract story.
- Phase 3 should carry docs, migration notes, and any optional ergonomics such
  as query helpers or additional output formats if real demand appears. Those
  are not prerequisites for shipping the Phase 1 foundation.
