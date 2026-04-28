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
[submission preflight + local records]
     ↑
[auth provider]
     ↓
[justificante parser] ← [imported historical receipt]
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

**`[submission preflight + local records]`** — `aeat.submission`
runs read-only preflight gates and reads historical local submission
records. It does not own a browser transport to AEAT and it does not
expose any live submit or dry-run submit command.

**`[auth provider]`** — architecturally,
`aeat.auth` now hangs off a provider-generic seam so the browser,
workflow, and submission layers no longer depend on one hard-coded
authenticator shape. For Kent today, the only shipped login path is
still the PKCS#12 certificate configured in `env/.env`. Other
provider kinds are future work, not usable CLI login choices yet.

**`[justificante parser] ← [imported historical receipt]`** —
operators may import justificante PDFs they obtained manually from
AEAT. The parser extracts the receipt number, timestamp, and canonical
PDF hash for local reconciliation.

**`[sede walker] ← [Mis expedientes]`** — `aeat.sede` reads
*Mis expedientes* through the authenticated browser session. It is the
authoritative AEAT-side state for what filings exist and their
processing status; it never trusts the local store as the source of
truth. Backed by ground truth captured live on 2026-04-24 against a
real Cl@ve-móvil session — every URL, selector, and record shape has
at least one live observation. Read-only by construction.

**`[self-healing sync] ↔ [local storage]`** — `aeat.sync` reconciles
schema-level divergence (modelo / casilla catalogue) between AEAT's
published shape and the local corpus. Filing-instance reconciliation
(local `FilingDraft` vs AEAT-recorded `Justificante`) is handled
separately by `aeat.filing.reconciliation`.

**`[notifications reader] ← [Mis notificaciones]`** — `aeat.sede`'s
notifications reader pulls the *ResumenInteresados* + *SvInteresados-
Query* surfaces, surfacing both unread-summary and full-table views.
Acknowledgement is strictly local — we never tell AEAT a notification
was read. Captured live 2026-04-24.

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
