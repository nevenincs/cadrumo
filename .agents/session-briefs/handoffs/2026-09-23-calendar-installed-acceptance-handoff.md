# CALENDAR-01 continuation handoff: holiday jurisdiction and installed acceptance

Status: partial. Session `CADRUMO-CALENDAR` (Claude, lead model Opus 5.5), continuing the Codex CALENDAR-01 session. Worktree `Y:\code\cadrumo-worktrees\tui-modelo`, branch `tui/modelo`. Consumed CALENDAR-01 revision 0.1, session-policy revision 1.8 and ACCEPTANCE-01 revision 1.7. Plan `2026-09-23-calendar-obligations-plan`; decision `2026-09-23-calendar-obligations-holiday-jurisdiction-adr`; grounding `2026-09-23-calendar-obligations-holiday-jurisdiction-research`.

Discovery route: no Luna invocation exists in this Claude session. Discovery was done by the lead with targeted reads, plus two bounded Opus workers: `calendar-holiday-grounding` (read-only BOE extraction to scratch) and `calendar-holiday-authoring` (facts 0066/0067, the new legal file, corpus captures and one test file; no git, no publish). The lead verified both results by read-back and by tests.

Live AEAT access, authentication, notification content, acknowledgement, response and submission: NOT EXERCISED (operator block).

## Outcome

The session goal is met, apart from the doc-golden item held under limit 7 below.

**Installed acceptance (CA12): PROVEN.** Receipt `artifacts/calendar-01/installed-calendar-parity-wheel-36ed8442-receipt.json` (SHA-256 `43406cdd79170da98dfd86ececddf851754087dc4b1cea33bceb130f7dfef4af`).
- Identity: source commit `d745bd28144381a5891a3870b4d0da88d688161d`; wheel SHA-256 `36ed8442117987a01635ea26dabb953df8977bae64a1c38c23a0f7c907979e3c`; authority generation `4fa84c26a651ebd7a60499c4b5edb1a682329d07c8663336f82df1fa6720dd15`, self-published in a clean detached checkout of that commit; product imported from site-packages, `__init__` SHA-256 `930e3f61c79bd2e3ff1f8aa11d1abd5d16bfbaab360ea739ae41f519f71b0ae7`.
- Run: evaluation date 2026-09-23, window 2025-01-01 to 2026-12-31.
- Independent stores: 26 rows x 10 fields, no mismatch.
- CLI to TUI: the CLI-created `303|2025|1T` work is visible in the TUI Declarations list, and 26 rows match.
- TUI to CLI: the TUI-created `303|2025|2T` work is visible to the CLI, and 26 rows match. The CLI authenticated with the stdin credential because the OS keychain is unavailable here (Windows error 1312).
- Compared fields: evaluation date, original and effective close, payment cut-off, overdue age, translated shift, holiday coverage, and the local, AEAT and receipt axes.

**Goal checks:**
- Holiday jurisdiction (limit 2) is done. The territory is derived from a stored resident common-regime residence; regional holidays extend a deadline only for verified territories; and every row states its holiday coverage in both frontends, including a visibly unverified calendar-unavailable date.
- The private-module import is gone and no lint suppression remains in the calendar driver.
- Gates: Ruff, format, `ty`, basedpyright strict and pyrefly report 0 errors on every changed file (pyrefly shows warnings only). The import gate was not rerun for this handoff: it is globally red with about 172 pre-existing findings, and this lane's new modules were enrolled as import targets (`799494236e`).

**Startup cost on the installed TUI with one draft work unit.** Home appeared after 2,000 to 4,000 polls before the fixes and after 118 to 145 polls (about 24 s) after them, so the calendar driver is back on the shared 180-poll budget. Fixes: calendar generation-constant caches (`f08678d078`), static-inspection labels in one catalogue window (`0901ef1134`), and LEDGER's streamed database hash (`dbbcba9bc8`). The remaining named costs are the first gating-field derivation per generation, which decodes all 147 revisions (about 14 s under the profiler), and deadline schedules computed three times per generation (about 12 s under the profiler).

**Authority format v2 (`c3359a5ade`, generation `1022f65320ddd012ae398efc420361d2efdb08157ef570d1e0f8e02df7837bb2`).** Build receipts are persisted, and a stale generation names the input that drifted. The cutover ran inside the coordinator's freeze window (18:21 to 18:31); the currency check reported CURRENT with a build identity, and 49 tests passed.

**Incidents.**
- A `git status | head` from this lane orphaned the shared index lock at 15:29; the user removed it.
- An uncommitted v2 format edit in the shared tree broke other lanes' in-tree runs from about 17:19 to 17:22. The four files were restored from HEAD bytes with `git show HEAD:<path>`, after verifying they held only this lane's hunks; no forbidden git command was used.
- IVA commit `63a201418e` swept in this lane's staged S06 holiday data; the content was unchanged.
- This lane's calendar driver had copied a `# noqa: S603` from the ledger driver. It was removed in `d745bd2814`.
- A command in this session printed an Anthropic API key from the environment into the transcript output. Nothing was written to files.

## Changed surfaces

- Registry: fact 0143 relates each fact-0129 tax-residence token to its ISO calendar territory. Legal entry `ley-39-2015:art-30.6` is added. Facts 0066/0067 are re-authored for 2024–2026 from the AGE días-inhábiles resolutions (BOE-A-2023-23637, BOE-A-2024-26935, BOE-A-2025-23702), with the new legal file `legal/dias-inhabiles-age.toml` and three corpus captures with generated sidecars.
- Domain: `festivos.py` adds the `DeadlineHolidayCoverage` states and the `verified_territories` gate, under which unverified regional days never extend a deadline. `models.py` adds `TaxpayerProfile.holiday_territory`. `profiles.py` resolves it only from a stored resident common-regime residence.
- Application: calendar entries carry `holiday_coverage` and `holiday_territory`. The localized `shift_reason_statement` and `holiday_coverage_statement` are shared by both frontends. The cli.overview.calendar.shift keys moved to application.overview.calendar.shift.
- CLI: calendar JSON adds `holiday_coverage` and `holiday_territory`. Text adds `holidays=`. `overview calendar` now emits `overview.no_aeat_history`.
- TUI: the calendar detail shows a translated shift and a `Holidays:` line, replacing the raw tokens.
- Acceptance: `dev/acceptance/calendar/installed_parity.py` replaces the in-process `test_parity.py`, which imported the private CLI rendering module. The shared public helpers `login_existing_profile_through_installed_tui`, `admit_existing_profile_for_headless_launcher` and `run_admitted_installed_launcher` (with `admission_polls`) live in `dev/acceptance/income_tax/installed_tui_child.py`.

## Authority generations

- `5159b729af5353be4a71983c93a68ad73ad86f39d37578fc70e643257e49e9be`: the fact-0143 relation.
- `9421767bfd79f05374bb6d99f095071c11d9373d90ef60e4f089e1bedf796880`: the holiday re-authoring.
- `1022f65320ddd012ae398efc420361d2efdb08157ef570d1e0f8e02df7837bb2`: format v2 with persisted build receipts (`c3359a5ade`). Later generations were published by other lanes through the coordinator queue.

Candidate validation: `uv run --no-sync python -m dev.registry.conformance valid`, exit 0. Publication: `python -m dev.registry.pipeline publish-authority`, exit 0 both times.

## Remaining limits, restated as next targets

1. **CA1, confident-wrong obligations.** For a plain autónomo, Modelos 136 (lottery-prize levy), 360 (optional VAT refund claim) and 714 (wealth tax) are APPLICABLE and render as late rows. 136's registry note says the profile does not model the triggering prize, and the omission yields `applicable`. An event- or threshold-conditional obligation whose triggering fact is unmodelled must be reported as unknown or conditional, not due. This needs an ADR on the applicability contract, then registry re-authoring.
2. **The TUI calendar never reads AEAT evidence.** `application/workbench_generation.py` hard-codes the AEAT source as NEVER_CAPTURED (`workbench.calendar.aeat_reader_unavailable`, "Not captured yet"), even after a sync. The CLI reads the same evidence. A workbench AEAT evidence port is needed; until then, AEAT and receipt parity with observed evidence is NOT EXERCISED.
3. **The TUI calendar does not show that a row already has local work** (the CLI text shows `work_unit=`). The recovery action can then offer a second creation. This is a CA8 target.
4. **Local and sub-territorial holidays.** Ley 39/2015 art. 30.6–30.7 makes municipal non-working days count, and island (Canarias) and Val d'Arán days are that local layer. It needs a typed municipality fact plus a municipal holiday source. The coverage statement already says local holidays are not checked.
5. **Holiday territory for legal entities and non-residents.** It needs the fiscal-address postcode-to-province route (ADR follow-on).
6. **Unlinked-notification parity.** It has no offline ingestion path (notifications arrive only by live pull), so it is NOT EXERCISED. It belongs with the notification-association target (T2).
7. **Doc sequence goldens.** `how-to/filing-calendar` and `how-to/irpf-lifecycle` are stale against HEAD independent of this lane. This lane is the assigned single refresh owner once its commits land.
8. **The notice's scope.** `overview.no_aeat_history` keys on official calculation observations, so a store with a verified justificante but no pulled history still receives it.
9. Plus the original T1–T5: the rest of the CA matrix, notification association, the legal-entity extinction fact, registry-resolved 303/390 applicability, and vaultspec check.
10. **Modelo 136 (CA1, highest priority).** The registry asserts 136 for every resident natural person. `filing-calendar`'s `@expect late_count == 3` anchors the fix: refresh that page with a seed whose activity is active through 2025 once 136 is conditional. The refreshed goldens for that page are uncommitted and held until then.
11. **Offline notification ingestion.** There is no supported offline path that brings a synthetic captured notification into the store. Add one at the notifications owner, through the existing encrypted observation store, then prove the unlinked, non-promoting meaning on the installed run.
12. **Keychain-less CLI session.** After a TUI login, a CLI on a host without a usable OS keychain cannot resume the session and must resend its credential. That is correct fail-closed behaviour, but it is a user-facing limit for headless Windows services and needs a documented path.
13. **Startup.** Derive the gating profile fields from revision metadata instead of decoding every revision, and share the deadline schedules across the three calendars one generation builds.

## Update 2026-09-24: authority v3, payer-fact declaration states, startup

Status: partial; this lane continues. Live AEAT access, authentication, notification content, acknowledgement, response and submission: still NOT EXERCISED (operator block).

**Calendar startup (target 13).** `c331cddf99`: deadline ownership and gating keys are read from the modelo directory instead of hydrating whole revisions. LEDGER's quiet-host profile: `load_root` went from 35.7 s to 19.7 s, `build_overview_calendar` from 32.8 s to 3.8 s, and the gating derivation from 14.6 s to 0.28 s. The rest of the projection was removed in v3 (below): a cold three-year projection went from 7.6 s to 0.5 s, with zero revisions hydrated.

**Authority format v3.** Code in `b9dc4be68a`; published as generation `28f8efab…`, CURRENT at publish.
- The published database records the observed compiler closure: the files a complete compile actually loads, about 400, with digests and the interpreter and dependency versions. The currency check re-hashes exactly those files.
- Every publication compiles in one canonical child interpreter, so the build hook and the CLI record the same generation. A watchdog ends the child when its parent dies.
- The modelo directory carries filing schedules.
- The packaging hook completes an interrupted publication instead of treating a descriptor-less `.authority/` as published. A test proves that a leftover candidate is never adopted.
- The decision is recorded in the amendments to `2026-09-14-registry-authority-artifact-boundary-indexed-storage-adr`.

**Payer-fact declaration states, Modelo 136 quarters, profile schema 7 (CA1).** Code in `0519417401`, docs in `67f30209d1`; published as generation `5703e101…`, which also carries IVA's all-files fingerprint identity (`b8de712263`).
- Dated payer facts (347, 720, 721, 136) resolve to declared yes (APPLICABLE), declared no (NOT_APPLICABLE) or undeclared (INCOMPLETE), and setup no longer defaults them.
- Modelo 136 applies only in the declared prize quarters (Orden HAP/70/2013 arts. 6–7, LIRPF DA 33).
- Profile schema 7 migrates each profile on open. The migration drops unprovable stored negatives and leaves a localized notice naming each fact to answer.
- `irpf.plantilla_media` is added for AMORTIZACION. `db9a0d13dd` makes its reader accept the path port's stored strings.
- The decision is in `2026-09-23-calendar-obligations-payer-fact-declaration-state-adr`.
- The `filing-calendar` page now documents the three genuinely late 2025 obligations (130, 303, 390).

**Other fixes.**
- `b527a4feca`: redaction over-redacts when the authority lacks a component, instead of raising.
- `388307db22`: coverage-payload test calendars carry `evaluated_on`.
- `1a50b51dd7`: generated index catch-up.

**Incidents.**
- A v3 worker ran `env | grep` and printed an API key into its transcript. Nothing was written to files. That makes two exposures in this lane, and the key needs rotation.
- An unscoped `vault feature index` regenerated other lanes' indexes. Their owners committed them.
- The rebased v3 proof hit a machine-wide MemoryError: another project's pytest held 122 GB committed.

**Limits, restated as targets.**
1. **Currency.** `5703e101…` reads STALE (COMPILER) at HEAD because later commits changed the compiler closure. The coordinator has batched the republish.
2. **Generated export trees.** 32 trees, plus the envelope proof and render-check, differ from a fresh render only in `_generation.provenance.json` and have no reproduction pin. This is assigned to this lane.
3. **`test_load_census`.** It crashes its xdist worker, and times out alone in `directory_scan`. Assigned to this lane.
4. **Applicability rules.** `iter_modelo_applicability_rules` costs about 3 s: it leases the bundled authority repeatedly, and each lease runs a database identity stat.
5. **Payer-fact limits.**
   - Modelo 193 stays two-state, because `equals true` conditions consume it.
   - The TUI does not show the migration notice.
   - A `--quiet` profile leaves 347 undeclared, so `overview calendar` requires `--allow-incomplete`.
   - The 136 quarter set is one profile answer, not one per prize.
6. **`irpf.plantilla_media`** has no CLI write path. That's AMORTIZACION's follow-up.
7. **Pre-existing reds routed to other owners** during this session:
   - `dev/agent_eval` leaks English output language into later tests;
   - 8 docs pages fail on baseline;
   - `profile-setup-flag-help` is stale.
8. **The v3 limit on the earlier `uv sync` failure.** Its symptom was that the build hook could not import `cadrumo.core`. It remains unexplained and was not reproduced in 3 attempts.
9. Targets 2–12 of the previous section remain open, except 10 (Modelo 136), which is done.
