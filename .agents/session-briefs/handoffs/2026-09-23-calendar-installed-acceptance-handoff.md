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
