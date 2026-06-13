---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - "[[2026-05-20-testimonial-driven-cli-verification-playbook-reference]]"
  - "[[2026-05-20-cli-testimonial-findings-inventory-audit]]"
  - "[[2026-05-21-state-architecture-plan]]"
---

# Persona-fleet bug inventory

Consolidated findings from a 12-persona testimonial fleet operating the
`aeat` CLI autonomously, each a Catalan or Spanish taxpayer briefed
with one specific profile/ledger/work-state task, CLI-only, isolated
storage, no live rights. Method: the testimonial playbook.

## Persona roster and verdict

| Persona | Task | Verdict |
|---|---|---|
| Antonio Ramírez | Duplicate a profile | clean |
| María Hernández | Rename a profile | clean |
| Carmen Ortega | Switch profiles | clean |
| Roger Puigdemont | Create a profile | minor UX only |
| Jordi Vilanova | Edit profile info | 1 major + UX |
| Montserrat Soler | Rename + ledger persistence | rename+ledger **confirmed sound**; ledger UX majors |
| Núria Ferrer | Delete a profile | **1 blocker** + majors |
| Francisco Delgado | Log out / log back in | auth-coherence majors |
| Arnau Bosch | Checkpoint WIP calculations | majors (1 downgraded) |
| Laia Margall | Complete profile + ledger | ledger UX majors |
| Rosario Giménez | Manage work state | **1 blocker** + majors |
| Pilar Castro | Cross-session persistence | persistence **confirmed sound**; transient-WIP crash (resolved) |

## Confirmed positives (verified from an operator's seat)

- Profile **duplicate** copies every field, gives the copy its own
  UUID, and edits to the copy never touch the original (Antonio).
- Profile **rename** is stable across `list`/`show`/`status`/`switch`;
  `profile_id` is unchanged; accents and spaces work (María).
- **Rename preserves all persisted ledger data** - 5 transactions
  identical before and after, anchored to the stable UUID (Montserrat).
- Profile **switch** is unambiguous; profiles keep separate data
  (Carmen).
- `overview status` **does** report modelo work units distinctly from
  declaration drafts (reproduced - the W04 read-projection holds).
- Work calculations **are** checkpointed: every `work calculate`
  persists a `borrador` revision that survives across sessions, with
  an auditable history (Arnau).

## BLOCKER

### B1 - Deleting the active profile locks the operator out of surviving profiles
Reported by Núria; **reproduced directly**. After
`config profile delete <active> --yes` the active-profile pointer is
cleared, and `config profile switch <surviving>` then fails with
`Refused. no active bucket session; run aeat config profile switch
NAME to unlock` - the recommended recovery command is the one that
fails. Only `profile create` escapes the state. Root cause: the
"active bucket session required" guard is applied to `profile switch`
itself, but `switch` is the command that establishes the session
(`create` is correctly exempt). Remediation cluster: **A**.

### B2 - `work verify` dumps a raw `WorkflowRunResult` repr into the error output
Reported by Rosario; **reproduced directly**. `work verify` on a
revision with no pending obligation prints, after the refusal line, a
`result: run_id=... started_at=datetime.datetime(...) steps=(WorkflowStep(
stage=<WorkflowStage.LOADING_PROFILE: ...>, ...))` raw object repr -
internal enums, datetime objects, nested step tuples - to the
operator. An error-boundary serialization leak. Remediation cluster:
**B**.

## MAJOR

| # | Finding | Persona | Repro | Cluster |
|---|---|---|---|---|
| M1 | `profile edit --taxpayer-birth-date` accepts impossible/non-ISO dates (`1978-13-45`, `15/03/1978`) stored raw, exit 0 | Jordi | confirmed | G |
| M2 | `auth configure --provider certificate` without `--file` returns exit 0 "success" though not configured | Francisco | reported | C |
| M3 | `auth status` vs `auth test` disagree on `provider`/`available` when no provider is configured | Francisco | reported | C |
| M4 | `configured: True` co-exists with `health_summary: certificate path not configured` when the path does not resolve | Francisco | reported | C |
| M5 | `profile show` of a tombstoned profile differs by session context (shows data vs "unknown profile") | Núria | reported | A |
| M6 | Deleting the active profile gives no warning the session will be lost | Núria | reported | A |
| M7 | `profile delete` with no active session cannot distinguish "no session" from "unknown profile" | Núria | reported | A |
| M8 | `ledger add --classification BUSINESS` + IVA fields fails with opaque "command input failed validation, run config repair" | Laia | reported | B/D |
| M9 | No command lists valid `--category-id` values; free text accepted unvalidated (silent miscategorization) | Laia | reported | D |
| M10 | `ledger review --id <ID>` always fails with the same opaque validation error | Laia | reported | B/D |
| M11 | `ledger import --provider` has no discoverable value list | Montserrat | reported | D |
| M12 | `csv` ledger provider silently imports 0 rows, no required-column guidance | Montserrat | reported | D |
| M13 | `config repair` reported `registry.integrity fail` - Modelo 100 `renta-cuota-chain` missing `ley-35-2006:art-76` | Jordi, Montserrat | **resolved meanwhile** - `registry.integrity` now `ok` (sibling registry-hardening campaign) | F |
| M14 | `config repair` reports "31/40 keys" / `fail` without naming what is missing or wrong | Jordi, Laia, Montserrat | reported | F |
| M15 | `census show` returns opaque "Refused. Refused cli boundary" | Jordi | reported | B |
| M16 | `work create` revision id is not discoverable without failing first | Rosario | reported | E |
| M17 | `work history` does not record the work-unit creation event | Rosario | reported | E |
| M18 | First `work calculate` binding error gives no guidance toward `bindings list --missing` | Arnau | reported | E |
| M19 | `overview status` next-step suggests "import bank movements" after manual ledger entries exist | Laia | reported | E |

## MINOR / POLISH (selected)

- **NIF error message gives no correction guidance** - reported
  independently by Roger, Jordi, Núria, Arnau (4x). High consensus.
- `profile create` with a bare name refuses (`--quiet` wizard) instead
  of guiding a first-timer - Roger (also Marta, earlier round).
- `work revisions <id>` rejects the positional arg its sibling
  `work status <id>` accepts - Rosario, Arnau.
- Idempotent `work create` silently ignores a new `--name` and reports
  `modelo.work.create` as if created - Rosario.
- No "work saved / resume later" confirmation after `work calculate` -
  Arnau.
- `overview status` "5 work units" does not separate discarded - Rosario.
- 64-char work-unit ids with no short alias / name lookup - Arnau.
- `ledger view <id>` omits IVA / counterparty / notes detail - Laia.

## Resolved during inventory verification (transient concurrent-worktree state)

This worktree carries many concurrent campaigns; two persona findings
were snapshots of in-flight sibling work and no longer reproduce:

- **Pilar's BLOCKER** - `work verify` / `config repair` / `config auth`
  crashing with `ValueError: AuthProfileIdentityMismatchError is
  missing a declared ErrorCode registry entry`. The error class
  existed for a window without its registry entry while a sibling
  campaign was mid-flight. Verified resolved: the entry is committed
  (`core/errors/registry/_application.py:348`,
  `REFUSED_AUTH_PROFILE_IDENTITY_MISMATCH`) and `config repair` now
  exits 0.
- **M13** - the `registry.integrity fail` Jordi and Montserrat saw is
  resolved; `config repair` now reports `registry.integrity ok`.

Note `work verify`'s **B2 raw-repr leak is a separate, still-real
defect** (the `NO_PENDING_OBLIGATION` exit-2 path, reproduced
independently) - not the transient crash above.

## Downgraded / not a defect

- "`overview status` hides my work" (Arnau AND Pilar) - **not a data
  bug**. Reproduced: `overview` correctly reports "1 unidad de trabajo
  de modelos existen". Both personas read the separate, correct "no
  declaration drafts" line and missed the work-units line. That two
  independent operators misread it the same way makes the wording a
  genuine **POLISH** finding (cluster E): the "no declaration drafts"
  line shown next to a non-zero work-units line reads as "your work is
  lost"; the `overview status` wording must make the distinction
  unmistakable.
- Pilar's "no manual ledger entry, only CSV import" - **not a defect**:
  `aeat app ledger add` accepts a fully manual transaction (Laia used
  it). A discoverability gap - the persona checked only
  `ledger import --help` - not a missing feature.
- Roger's "11 unrelated profiles in `profile list`" - not a product
  defect; the persona did not keep `AEAT_LOCAL_STORAGE_ROOT` set
  across separate shell invocations and operated against the shared
  default store. Persona-discipline slip; brief methodology tightened.

## Remediation clusters

- **A - profile lifecycle** (B1, M5, M6, M7): the delete-active
  lockout and the tombstone/no-session surface. The state-architecture
  campaign's own domain. **Priority 1.**
- **B - error-boundary hygiene** (B2, M8, M10, M15, NIF message): raw
  object reprs and opaque "run config repair" refusals that leak
  internals or give the operator no path forward. **Priority 1.**
- **C - auth coherence** (M2, M3, M4): the auth status/test/configure
  surface, residual to the W04 read-projection.
- **D - ledger UX** (M9, M11, M12, and the M8/M10 input-validation
  overlap): category catalogue, import provider/format discoverability.
- **E - modelo work UX** (M16, M17, M18, M19): revision discovery,
  history completeness, binding guidance, overview next-step.
- **F - repair / registry** (M13, M14): the `registry.integrity`
  Modelo 100 data gap and `repair`'s detail-free verdicts.
- **G - field validation** (M1): birth-date calendar validation.

Clusters A and B are dispatched first (confirmed blockers). C-G follow
as tracked remediation waves; each fix lands with a real-behavior
regression test and a re-run of the originating persona task.

## Remediation progress

Wave 1 (landed, verified):

- **B1 + M5 + M6 + M7** - `623795a8d`. `switch`/`delete` open a
  target-scoped bucket session (matching how `create` is exempt), so
  deleting the active profile no longer locks the operator out;
  delete-active now states the pointer was cleared; `delete` resolves
  the name first so an unknown profile gets a clear refusal.
- **B2** - `0775cfb63`. `ModeloWorkflowGateError` holds a private
  `_result` with a clean primitive context; `_stringify_context_value`
  hardened as a defensive funnel so no error class can dump a raw
  object repr. `work verify` / `work file` now render cleanly.
- **M1** - `31d22895b`. Date-typed profile fields validate as real
  ISO-8601 calendar dates at `ProfileValidationService`; all nine
  schema date fields are covered, not just birth-date.

Note: a transient batch of ~6 pytest-collection-order failures in
`test_profile_lifecycle_verbs.py` traces to a sibling campaign's
uncommitted WIP in `auth/_sessions.py` + `core/errors/registry/_application.py`
(an import-order-fragile `AuthProfileIdentityMismatchError`
registration). At the real CLI level error rendering works; the
failures resolve when that campaign commits. Not actioned here -
foreign uncommitted WIP.

Wave 2 (landed, verified):

- **NIF message** - `364994987`. The NIF/NIE/CIF refusal now names the
  correct check letter and the corrected id; the highest-consensus
  finding (4 personas) closed.
- **Cluster C** - `1c8772ff4` (+ `a357d389f`). Auth coherence: M2
  configure-without-file reports incomplete; M3 `auth status` and
  `auth test` agree (verified byte-identical); M4 `configured`
  requires the certificate path to resolve.
- **Cluster D** - `84b66dd1c`. Ledger UX: M9 `ledger categories`
  catalogue + `--category-id` validation; M11 provider list
  discoverable; M12 silent-0 import explained; M8/M10 opaque
  "run config repair" errors traced to `pydantic.ValidationError`
  re-wrapping and given specific messages.
- **Cluster E** - `ed6668763`. Modelo-work UX: M16 revision-id
  discovery via `modelo describe`; M17 `modelo.work_unit.created`
  event (roundtrip-tested); M18 binding-error guidance; M19 and the
  overview wording made state-aware.
- **Cluster F** - `425db5d60`. `config repair` now names every unset
  key with its fix command and tags operator-fixable vs internal.
- **Wizard-UX** - `235ec2bd3`. `profile create` non-interactive
  refusal names both recovery paths; no `--quiet` precondition claim,
  no internal tokens leaked.
- **Residual polish P1-P6** - `6ee49857d`. `work revisions` positional
  arg; "draft saved" confirmation; new `work revision` view verb;
  overview active/discarded split; idempotent-create reuse signal;
  full `ledger view` detail.

## Outcome

All seven remediation clusters plus the NIF, wizard-UX, and residual
polish items are landed and verified. A consolidated independent code
review returned the remediation **SOUND** - no blocker, no major, no
cluster needing rework, test honesty intact throughout; its two MINOR
test/doc items were actioned in `5e931815b`. Two inventory findings
were transient concurrent-worktree state and resolved meanwhile; two
persona observations were correctly downgraded on reproduction. The
12-persona testimonial fleet -> inventory -> reproduce/triage ->
fix-with-regression-tests -> independent-review cycle is complete.
