---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-21'
related:
  - "[[2026-05-20-testimonial-driven-cli-verification-playbook]]"
  - "[[2026-05-20-cli-testimonial-findings-inventory]]"
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
| M13 | `config repair` reports `registry.integrity fail` - Modelo 100 `renta-cuota-chain` missing `ley-35-2006:art-76`, 18 violations | Jordi, Montserrat | reported | F |
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

## Downgraded / not a defect

- Arnau's "`overview status` hides my work" - **not a bug**. Reproduced:
  `overview` correctly reports "1 unidad de trabajo de modelos
  existen". The persona read the separate, correct "no declaration
  drafts" line and missed the work-units line. Downgraded to a
  wording-clarity nit (the two adjacent lines can confuse).
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
