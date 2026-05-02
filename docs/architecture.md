# Architecture

This document is a reading map for the layered packages. The
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
[self-healing sync] ↔ [persistence storage]
     ↓
[inbox] ← [Mis notificaciones]
```

## Arrow-by-arrow

**`[setup wizard] → [config + auth provider]`** — `aeat.application.setup`
walks the operator through the env-file fields documented in
`env/.env.example`. Its only output is a populated `env/.env` plus a
verified path to the operator's PKCS#12 certificate; it never moves
the certificate file itself and never persists the passphrase.

**`[workflow engine] ← [deadline engine] ← [modelo catalogue]`** —
`aeat.application.workflow` asks `aeat.domain.deadlines` for the next
filing that is due. The deadline engine reads `aeat.domain.modelos`, the
closed catalogue of supported modelos, to compute period boundaries
and tolerance windows. The catalogue is a typed enum, not a
configurable list — adding a modelo is a code change.

**`[filing draft engine] ← [casilla DB] ← [manual práctico]`** —
`aeat.application.filing` builds a typed draft for the chosen modelo by joining
the casilla schema with the structured manual práctico ingested by
`aeat.domain.manuals`. Every casilla in the draft is annotated with its
manual reference, so the operator can audit any value back to its
source paragraph.

**`[submission preflight + local records]`** — `aeat.domain.submission`
is the canonical home for submission records and preflight contracts.
`aeat.adapters.outbound.aeat.export` executes the read-only export-side
preflight against those domain contracts. It does not own a browser
transport to AEAT and it does not expose any live submit or dry-run
submit command.

**`[auth provider]`** — `aeat.adapters.outbound.aeat.auth` contains
the AEAT-side provider implementations, while provider selection lives
in `aeat.application.auth`. The browser, workflow, and export paths do
not depend on one hard-coded authenticator shape. The operator may
use the configured PKCS#12 certificate path or Cl\@ve Móvil where
configured.

**`[justificante parser] ← [imported historical receipt]`** —
operators may import justificante PDFs they obtained manually from
AEAT. The parser extracts the receipt number, timestamp, and canonical
PDF hash for local reconciliation.

**`[sede walker] ← [Mis expedientes]`** — `aeat.adapters.outbound.aeat.sede` reads
*Mis expedientes* through the authenticated browser session. It is the
authoritative AEAT-side state for what filings exist and their
processing status; it never trusts the local store as the source of
truth. Backed by ground truth captured live against a real
Cl\@ve-móvil session — every URL, selector, and record shape has at
least one live observation. Read-only by construction.

**`[self-healing sync] ↔ [persistence storage]`** — `aeat.domain.sync` owns
the divergence taxonomy, live-wire records, validation, and classification
for schema-level divergence (modelo / casilla catalogue). `aeat.application.sync`
orchestrates the live read, dispatch, and encrypted divergence persistence.
Filing-instance reconciliation (local `FilingDraft` vs AEAT-recorded
`Justificante`) is handled separately by `aeat.application.filing.reconciliation`.

**`[notifications reader] ← [Mis notificaciones]`** — `aeat.adapters.outbound.aeat.sede`'s
notifications reader pulls the *ResumenInteresados* + *SvInteresados-
Query* surfaces, surfacing both unread-summary and full-table views.
Acknowledgement is strictly local — we never tell AEAT a notification
was read.

## Cross-cutting

- **`aeat.core.i18n`** carries the quadlingual (es / en / ca / hu) message
  catalogue used by every user-facing surface.
- **`aeat.adapters.outbound.llm`** is a bounded client used only by `aeat.domain.manuals` for
  structured extraction from the manual práctico — it never sees a
  filing draft or a credential.
- **`aeat.domain.normatives`** carries the live normative corpus (BOE
  references, vigencia windows) and is consulted by `aeat.domain.deadlines`
  and `aeat.application.filing` for legal-effect dates.
- **`aeat.application.filing.testing`** provides synthetic filing factories and shared
  fixtures for both the unit suite (default) and the live suite
  (gated behind `AEAT_LIVE_TESTS_ENABLED=1`).

For the conventional-commits mandate, the dev loop, and the worktree
workflow, see [`../README.md`](../README.md). For the release flow,
see [`../RELEASING.md`](../RELEASING.md). For the new-autónomo
walkthrough, see [`getting-started.md`](getting-started.md).
