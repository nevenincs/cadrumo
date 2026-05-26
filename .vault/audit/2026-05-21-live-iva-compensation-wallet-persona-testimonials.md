---
tags:
  - '#audit'
  - '#live-iva-compensation-wallet'
date: '2026-05-21'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-20-live-iva-compensation-wallet-review]]'
---

# Live IVA compensation wallet W04 persona testimonials

Date: 2026-05-21

Environment: disposable local CLI state under `.tmp/w04-persona-cli`.

Safety boundary: no live AEAT command was executed. No real taxpayer secret was entered. The live wallet persona inspected help and local history only.

## Commands and redacted outputs

### First-run autónomo persona

Commands:

- `uv run aeat config profile create persona-autonomo --quiet --accept-defaults --tax-id 00000000T --name Persona --surnames Autonomo --iva-regime GENERAL --tax-residence-ccaa madrid`
- `uv run aeat config profile create persona-autonomo --quiet --accept-defaults --tax-id 00000000T --name Persona --surnames Autonomo --activity consultoria --iva-regime GENERAL --tax-residence-ccaa madrid`
- `uv run aeat app modelo work create --modelo 303 --year 2026 --period 1T --revision 2009-y-siguientes --by persona-autonomo`
- `uv run aeat app modelo work calculate <work-unit-id> --by persona-autonomo`

Observed:

- Profile creation refused the first attempt because `activity` was still required under `--quiet --accept-defaults`.
- The successful create output showed `next aeat app modelo work create`.
- Modelo 303 work-unit creation returned a work-unit id.
- Calculation succeeded with all IVA values at zero before any accepted ledger evidence existed.

Testimonial:

"The profile setup told me the next command, which helped. The friction was that `--accept-defaults` still needed `activity`, and the Modelo 303 calculation looked successful even though I had not entered usable ledger evidence."

### Returning accountant persona

Commands:

- `uv run aeat app ledger add --date 2026-02-10 --amount 121.00 --direction INCOMING --description "Persona sale" --classification BUSINESS --business-pct 1 --taxable-base 100.00 --iva-rate 0.21 --iva-amount 21.00 --category-id ventas --actor persona-autonomo`
- `uv run aeat app ledger categories`
- `uv run aeat app ledger add --date 2026-02-10 --amount 121.00 --direction INCOMING --description "Persona sale" --classification BUSINESS --taxable-base 100.00 --iva-rate 0.21 --iva-amount 21.00 --actor persona-autonomo`
- `uv run aeat app ledger preflight --period 2026Q1`
- `uv run aeat app modelo bindings list --modelo 303 --year 2026 --period 1T --missing`
- `uv run aeat app modelo readiness --modelo 303 --revision-id 2009-y-siguientes --year 2026 --period 1T`
- `uv run aeat app modelo work calculate <work-unit-id> --by persona-autonomo`

Observed:

- `--category-id ventas` was rejected and the CLI correctly pointed to `aeat app ledger categories`.
- `--business-pct 1` was rejected for `classification BUSINESS`; the message explained that `business_pct` is only valid for `MIXED`.
- A ledger row without `category_id` was accepted.
- `ledger preflight --period 2026Q1` reported `ready false` with `missing_category`.
- `modelo readiness` still reported `ready True` for Modelo 303.
- Re-running Modelo 303 calculation after the ledger row still returned the existing zero-valued draft revision.

Testimonial:

"The ledger preflight correctly found the missing category, but Modelo readiness did not inherit that blocking state. I would not know that the zero Modelo 303 draft is unsafe unless I remembered to run ledger preflight separately."

### Live-wallet reviewer persona

Commands:

- `uv run aeat app live iva-wallet --help`
- `uv run aeat app live iva-wallet pull --help`
- `uv run aeat app live iva-wallet history`

Observed:

- The live wallet group describes itself as read-only capture.
- `pull` requires `--year` and `--period`; `--taxpayer-nif` is optional.
- Local history returned `row_count=0`.
- No live `pull` command was run.

Testimonial:

"The help text says read-only, which is good. The safer boundary would be even clearer if `pull --help` stated that representation-gate submission is refused and that no form choices are posted to AEAT."

### Multiyear compensation reviewer persona

Commands:

- `uv run aeat app live iva-wallet history --help`
- `uv run aeat app live iva-wallet capture-history --help`
- `uv run aeat app modelo work revisions --work-unit-id <work-unit-id>`
- `uv run aeat app modelo bindings list --modelo 303 --year 2026 --period 1T --missing`

Observed:

- `iva-wallet history` help states that it lists secure local compensation history, but the command output for an empty store is only `row_count=0`.
- The Modelo 303 bindings list shows `modelo-303-compensacion-pendiente-anteriores` as `previous_filing`, but does not show source-period age or authority decision state.
- No CLI output currently exposes carry-forward lot age, expiry review state, or wallet/local/override authority-source records.

Testimonial:

"I can see that prior compensation is a previous-filing binding, but I cannot inspect the source-year/source-period lot, age, remaining amount, or authority decision from the CLI."

## Safety observations

- No CLI dry-run contacted AEAT.
- No live wallet pull was executed.
- `modelo work file` help explicitly says it marks an internal filing and does not submit to AEAT.
- `modelo export` help explicitly says local-only and never contacts AEAT, but export remains legally sensitive because it creates a submission-ready local artifact.

## Config-domain persona pass

Date: 2026-05-22

Environment: active local development profile with known unreadable secure-object rows. Outputs recorded here are redacted; active profile UUIDs and row ids are not retained.

Safety boundary: no live AEAT login, wallet pull, filing, payment, confirmation, or represented-taxpayer action was executed. The pass exercised only local `aeat config ...` help/status/repair surfaces.

### Config repair operator persona

Commands:

- `uv run aeat config --help`
- `uv run aeat config repair --help`
- `uv run aeat config repair list --help`
- `uv run aeat config repair profile`
- `uv run aeat config repair`

Observed:

- The config root clearly groups first-run, profile lifecycle, profile inspection, authentication, and diagnostics.
- `config repair` exposes destructive `quarantine` and `reset-state` as subcommands that require explicit confirmation; the default repair run remains read-only.
- `config repair` now reports relational SQL integrity as `ok` before secure-object integrity, and still routes unreadable rows to read-only `config repair list <namespace> --unreadable`.
- `config repair profile` reported the active profile pointer and profile record as ready, with next action `aeat app overview status`.

Testimonial:

"The repair surface now tells me the profile is usable and the relational database is structurally present before it asks me to look at unreadable secure objects. The important safety cue is that the next step is an inventory command, not quarantine."

### Profile lifecycle persona

Commands:

- `uv run aeat config profile status`
- `uv run aeat config profile show`
- `uv run aeat config profile list`
- `uv run aeat config repair list aeat.domain.filing.drafts --unreadable`

Observed:

- `profile status` and `profile show` could inspect the active profile.
- `profile list` initially failed on a legacy manifest missing lifecycle `status`, making the profile inventory unusable even though the active profile was healthy.
- W04.F23 changed the scan so malformed manifests are skipped from live profile resolution and the operator sees a skipped count. This preserves fail-closed behavior for switch/name resolution while keeping valid profiles visible.
- `config repair list aeat.domain.filing.drafts --unreadable` reported the filing-draft namespace as high-risk filing-history evidence and listed only encrypted row metadata plus redacted HMAC-context notes.

Testimonial:

"I need profile list to be my inventory command. It is acceptable to hide a malformed legacy bucket from live switching, but the command must tell me that something was skipped so I know to run repair or investigate the old bucket."

### Auth readiness persona

Commands:

- `uv run aeat config auth --help`
- `uv run aeat config auth status`
- `uv run aeat config auth test --provider clave_movil`
- `uv run aeat config auth clear --help`
- `uv run aeat config auth diagnostics list`
- `uv run aeat --format json config auth diagnostics list`

Observed:

- Initial `auth status` failed on an unrelated unreadable filing-draft secure-object row. That made an auth-only readiness question depend on workspace integrity.
- The fix scopes auth status/test projection away from workspace counters and period-obligation calculation. Re-running `auth status` now reports the configured Cl@ve Móvil provider, active-profile readiness, backend availability, and the warning that operator-mediated Cl@ve finalization is still required.
- `auth test --provider clave_movil` still correctly fails because the local persisted auth session is corrupt, but its error suggestion now points to `aeat config auth clear --sessions` instead of an unrelated certificate-provider test.
- `auth diagnostics list` initially printed profile label/id context and DNI/NIE identity kind in the list view. W04.F24 keeps the list as an inventory surface: diagnostic id, timestamp, reason, mode, headless flag, phone-state report, and capture flags remain; profile/identity/credential context is available only through deliberate `auth diagnostics show <id>` detail.
- `config repair list <namespace> --unreadable` initially printed the active profile bucket UUID in row context and embedded it into active-bucket object-key hints. W04.F25 keeps the row-level context but renders only `active_profile` and placeholder key hints such as `transaction-catalogue:<active-profile>`.
- The top-level `config repair` report also initially echoed the active profile bucket UUID in the profile summary and the `profile.storage` diagnostic row. W04.F26 redacts both text and JSON repair output to the generic `active_profile` marker while keeping readiness counts and recovery actions.
- W04.F27 turns the persona privacy expectation into a public CLI contract: a real profile is created through the CLI, a real encrypted secure-object row is written under the active backend, and `config repair` plus `config repair list` are asserted in text and JSON modes.
- W04.F28 extends the same public-CLI expectation to `config repair integrity attribution`: a real unreadable wallet-observation row is created under a different encryption key, and the attribution output must stay metadata-only while keeping enough namespace and owner-semantics context for the operator to decide what to inspect next.

Testimonial:

"I can now ask the config domain what auth provider is configured without being blocked by a filing draft I was not trying to inspect. The corrupt-session instruction is also more credible because it tells me to clear sessions before re-testing. The diagnostics list is safer when it looks like an inventory rather than a profile/identity report. Repair inventory also needs this discipline: I need to know whether an unreadable row belongs to the active profile context, but I do not need the raw profile bucket id copied into terminal output or JSON. Seeing this checked through the real CLI makes it feel like a workflow guarantee, not an implementation note. The attribution command is the next useful layer because it tells me the class of evidence at risk without showing the taxpayer, amount, or payload."
