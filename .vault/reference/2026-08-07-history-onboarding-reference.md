---
tags:
  - '#reference'
  - '#history-onboarding'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:a44e853ae3baa10219d9f96190b8d00ce3c06d3f3e51e375e365e426482104fe'
related:
  - '[[2026-08-07-declarations-register-pagination-reference]]'
  - '[[2026-08-07-declarations-register-pagination-adr]]'
  - '[[2026-08-07-dehu-notification-legal-effect-reference]]'
  - '[[2026-05-04-live-filing-data-capture-adr]]'
  - '[[2026-07-12-justificante-reframing-audit]]'
---

# `history-onboarding` reference: `New-profile AEAT history onboarding grounding`

Grounds an ADR on letting a brand-new profile pull and reconcile its AEAT-held
history (filed declaraciones by modelo, justificantes, evidence bytes,
notificaciones, IVA balance). Sources consulted: `application/live/_filed_data_capture.py`,
`entrypoints/cli/_app_live.py`, `adapters/outbound/aeat/sede/_declarations.py`,
`application/storage_write_policy.py`, `application/calculations/_observations_repository.py`,
`application/calculations/_cross_period_clean_state.py`, `application/user_profile/_cotejo_apply.py`,
`application/modelo/_profile_readiness_gate.py`, `domain/calculations/registry/` dependency
classifications, and `.vault/audit/2026-07-12-justificante-reframing-audit.md`.

## Summary

**Bulk filed-declaration capture already exists and is enrolled.** `capture_filed_data_bulk`
(`application/live/_filed_data_capture.py:471`) walks a `(modelo, year_from, year_to)` grid
through one authenticated register session, persisting through the same path as
`capture_filed_data`: encrypted `FiledDeclaracionObservation`/`FiledDeclaracionArtefact` rows,
justificante metadata, and registry-grounded calculation observations. The CLI surface is
`aeat app live filed list|pull|pull-sources` (`entrypoints/cli/_app_live.py:910,1051,1245`);
`filed pull` and `filed pull-sources` are enrolled in `PROFILE_BOUND_WRITE_VERB_PATHS`
(`storage_write_policy.py:72-73`), `filed list` is not (read-only, persists nothing).

**The capture schema is canonical and sole.** `FiledDeclaracionObservation` /
`FiledDeclaracionArtefact` / `ObservedCasillaValue` (`adapters/outbound/aeat/sede/_schema.py:215-401`)
is the one shape every capture path writes. No new schema is needed for historical import —
only a new caller into the existing bulk capture.

**The year range and modelo set are both caller-bounded, never AEAT-derived.**
`filed_list_cmd`/`filed_pull_cmd` default `year_from`/`year_to` to the current calendar year
when omitted (`_app_live.py:934-935`); bulk mode with no `--modelo` iterates
`resources().modelos.all()` — every registry-configured modelo, not every modelo AEAT actually
issued to this NIF. A taxpayer whose real filing history predates the default year or covers a
modelo variant the registry does not compile is silently excluded: `capture_filed_data_bulk`
never asks AEAT what this NIF has, it only asks AEAT to confirm or deny each guessed pair.

**The register offers no listing of available (modelo, ejercicio) combinations.**
`DeclaracionesRegisterSession.walk` (`_declarations.py:231`) and `_drive_search` both take a
`(modelo, ejercicio)` pair as input and return rows or nothing; `_select_combobox_value`
(`_declarations.py:566`) reads `.z-comboitem-text` options but only to click a caller-named
target, never to enumerate what the combobox actually offers. There is no code path that reads
the full option list of either combobox to learn which pairs exist. Confirming this gap forced
reading `_declarations_listbox.py`'s pager handling too: see the sibling grounding below —
the register's per-query row parse also has no pager awareness, a related but distinct
completeness question.

**A sibling ADR is already scoping the WITHIN-query completeness question.**
`.vault/reference/2026-08-07-declarations-register-pagination-reference.md` and
`.vault/adr/2026-08-07-declarations-register-pagination-adr.md` (feature
`declarations-register-pagination`, in progress) document that `_parse_listbox` returns
exactly one page's rows with no reconciliation against any AEAT-declared total — a truncation
risk WITHIN one `(modelo, ejercicio)` query. That is a different gap from the one this document
grounds: whether the *set of `(modelo, ejercicio)` pairs queried at all* is complete. Both must
be closed for an honest history import; neither closes the other. `LedgerListResult`
(`entrypoints/cli/_ledger_payloads.py:648`) is cited there as the in-repo `total`/`truncated`
precedent shape.

**A sibling reference is grounding notificacion legal effect.**
`.vault/reference/2026-08-07-dehu-notification-legal-effect-reference.md` (feature
`dehu-notification-legal-effect`, in progress, body not yet drafted) covers the DEHu
notificaciones side of history import; this document does not restate that grounding.

**IVA compensación wallet reconciliation is complete and canonical.**
`capture_iva_compensation_wallet`, `capture_iva_compensation_history`,
`capture_iva_remote_state`, and `reconcile_iva_compensation_wallet` already capture and
reconcile the AEAT-held IVA balance, gated by a divergence check blocking verify/file/export.
No new balance-reconciliation mechanism is needed; a history-onboarding flow composes these,
it does not re-implement them.

**`apply_cotejo` is the shipped precedent for local-vs-remote divergence adoption.**
(`application/user_profile/_cotejo_apply.py:180`) Adopts certificate facts and persists
divergence rows through `set_active_fields` in one atomic sequence, emits exactly one
`CENSO_APPLIED` bucket event per apply-commit (never one per fact), and a paired
`open_censo_divergences`/`censo_divergence_notice` (`:150`) surfaces a standing non-blocking
`WARNING` `Notice` while divergence stays open. This is the shape a history-import divergence
surface should mirror: one commit event, a standing advisory, never a silent auto-resolve.

**Provenance: `ObservationSourceKind` has exactly five members, three official.**
(`application/calculations/_observations_repository.py:64-99`) `APP_FILING`, `OPERATOR_MANUAL`
are non-official; `AEAT_SEDE_JUSTIFICANTE`, `AEAT_SEDE_LIVE_CAPTURE`, `AEAT_CSV_REGISTER` are
official (`is_official_aeat`), and only the official three satisfy the cross-period clean-state
gate (`_cross_period_clean_state.py:660,969`) and the calendar advisory
(`overview/_calendar_evidence.py:450`). A history-import capture that reuses
`capture_filed_data_bulk` reuses whichever of these three kinds that function already stamps —
no new kind is structurally required unless the import path diverges from live capture in a way
that changes what "official" should mean for a backfilled record.

**Profile bootstrap: a profile is born `SETUP_INCOMPLETE`, and filing-grade modelo work refuses
until it clears.** `_profile_readiness_gate.py:440` loads the profile record and hard-refuses
any filing-grade modelo call while `status is SETUP_INCOMPLETE`, suggesting
`aeat config profile create NAME` completion. This means a history-import step run mid-setup
has nothing yet to attach observations to in a filing-grade sense — the earliest a history pull
can run against a fully wired profile is post-setup-completion, though nothing blocks running the
read-only discovery/list step earlier.

**No onboarding hook exists today.** Nothing in the wizard catalogue (`application/wizard/_catalogue.py`)
or the overview surface prompts a new profile to pull prior AEAT history; the calendar
deliberately renders the full obligation universe as undetermined rather than empty for an
incomplete profile, but that is a display default, not a call to action.

**Verb-rename/addition sweep surfaces, confirmed by grep, not assumed:**
`storage_write_policy.py:122` (`PROFILE_BOUND_WRITE_VERB_PATHS`, hand-maintained tuple, currently
lists `app live filed pull` and `app live filed pull-sources` but no discovery or import verb);
error-registry `default_suggestion` fields; cross-period `next_action` builders; the operator
help surface (`operator_surface/_help.py`); envelope `command=` identifiers; and the agent-harness
docs under `src/cadrumo/_data/agent/`. None of these currently name a history-discovery or
history-import verb, because none exists yet.

## Open questions carried into the ADR

1. Is history discovery a new read-only capability under the register adapter (reading the
   combobox's own option list, or probing every modelo × a bounded year window), or does it stay
   bounded and instead rely on the operator naming years/modelos explicitly at onboarding time?
2. Does a history-import verb live under the existing `filed` group (`filed discover` / a wider
   `filed pull` default), or does it need a new top-level verb — and if new, what CLI-contract
   name avoids `capture`/`refresh`/`fetch`/`sync`?
3. Does an imported historical filing need a distinct `ObservationSourceKind`, or does reusing
   `AEAT_SEDE_LIVE_CAPTURE`/`AEAT_SEDE_JUSTIFICANTE` correctly describe it?
4. What `PROFILE_BOUND_WRITE_VERB_PATHS` entry, locale keys (in all four catalogues), and
   `_help.py`/harness doc updates does the chosen verb surface require?
5. Should a no-history Notice on the overview point at the new verb, and does a wizard step ever
   invoke it, or is it strictly post-setup operator-run?
