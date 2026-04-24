# Architecture

This document is a reading map for the on-main subpackages. The
subpackage table in [`../README.md`](../README.md) is the index; the
diagram below is the data-flow story that connects them.

## Data flow

```
[setup wizard] → [config + auth provider]
     ↓
[workflow engine] ← [deadline engine] ← [modelo catalogue]
     ↓
[filing draft engine] ← [casilla DB] ← [manual práctico]
     ↓
[submission engine] → [browser session] → [AEAT]
                       ↑
                 [auth provider]
     ↓
[justificante parser] ← [submission receipt]
     ↓
[status reader] ← [Mis expedientes]
     ↓
[self-healing sync] ↔ [local storage]
     ↓
[inbox] ← [Mis notificaciones]
```

## Arrow-by-arrow

**`[setup wizard] → [config + auth provider]`** — `aeat.setup` (shipped via #61 / PR #66)
walks the operator through the env-file fields documented in
`env/.env.example`. Its only output is a populated `env/.env` plus a
verified path to the operator's PKCS#12 certificate; it never moves
the certificate file itself and never persists the passphrase.

**`[workflow engine] ← [deadline engine] ← [modelo catalogue]`** —
`aeat.workflow` asks `aeat.deadlines` for the next
filing that is due. The deadline engine reads `aeat.models`, the
closed catalogue of supported modelos, to compute period boundaries
and tolerance windows. The catalogue is a typed enum, not a
configurable list — adding a modelo is a code change.

**`[filing draft engine] ← [casilla DB] ← [manual práctico]`** —
`aeat.filing` builds a typed draft for the chosen modelo by joining
the casilla schema with the structured manual práctico ingested by
`aeat.manuals`. Every casilla in the draft is annotated with its
manual reference, so the operator can audit any value back to its
source paragraph.

**`[submission engine] → [browser session] → [AEAT]`** —
`aeat.submission` is dry-run by default. It hands the draft to
`aeat.browser`, which drives a controlled Playwright session against
AEAT. The submission engine never escalates from dry-run to a real
submit; the operator has to re-invoke with an explicit confirm flag
that the dry-run output prints.

**`[auth provider] → [browser session]`** — architecturally,
`aeat.auth` now hangs off a provider-generic seam so the browser,
workflow, and submission layers no longer depend on one hard-coded
authenticator shape. For Kent today, the only shipped login path is
still the PKCS#12 certificate configured in `env/.env`. Other
provider kinds are future work, not usable CLI login choices yet.

**`[justificante parser] ← [submission receipt]`** — after a real
submission AEAT returns a justificante PDF. The submission engine
hands it to the parser inside `aeat.submission`, which extracts the
receipt number, the timestamp, and the canonical PDF hash before
storing them.

**`[status reader] ← [Mis expedientes]`** — `aeat.status` reads
*Mis expedientes* through the same browser session. It is the
authoritative AEAT-side state for what filings exist and their
processing status; it never trusts the local store as the source of
truth.

**`[self-healing sync] ↔ [local storage]`** — `aeat.sync` reconciles
the status reader's view with `aeat.storage` after every run. If the
two disagree, AEAT wins; the local store is patched to match. This is
the self-healing rule: the next invocation always starts from ground
truth.

**`[inbox] ← [Mis notificaciones]`** — `aeat.inbox` reads pending
notifications from *Mis notificaciones* and surfaces them to the
workflow engine, which decides whether the next action is a filing or
an acknowledgement.

## Cross-cutting

- **`aeat.i18n`** carries the trilingual (es / en / hu) message
  catalogue used by every user-facing surface.
- **`aeat.llm`** is a bounded client used only by `aeat.manuals` for
  structured extraction from the manual práctico — it never sees a
  filing draft or a credential.
- **`aeat.normatives`** carries the live normative corpus (BOE
  references, vigencia windows) and is consulted by `aeat.deadlines`
  and `aeat.filing` for legal-effect dates.
- **`aeat.testing`** provides synthetic filing factories and shared
  fixtures for both the unit suite (default) and the live suite
  (gated behind `AEAT_LIVE_TESTS_ENABLED=1`).

For the conventional-commits mandate, the dev loop, and the worktree
workflow, see [`../README.md`](../README.md). For the release flow,
see [`../RELEASING.md`](../RELEASING.md). For the new-autónomo
walkthrough, see [`getting-started.md`](getting-started.md).
