# Kent capability coverage matrix

Per-capability implementation state, anchored to Kent's observable actions. Refreshed every month via audit [#241](https://github.com/wgergely/aeat/issues/241).

Legend: ✅ shipped · 🚧 in progress · ⏳ scheduled · ❌ not yet scoped

| Kent capability | Documented | CLI supported | Tested | Success observable | Milestone | Tracking |
|---|---|---|---|---|---|---|
| Install on a clean laptop | 🚧 | 🚧 | ❌ | ❌ | 0.0.2 | [#209](https://github.com/wgergely/aeat/issues/209) |
| Know what a GCP project is and how to create one | ❌ | N/A | N/A | ❌ | 0.0.2 | [#210](https://github.com/wgergely/aeat/issues/210) |
| Store FNMT cert passphrase safely | ❌ | 🚧 | ❌ | ❌ | 0.0.2 | [#212](https://github.com/wgergely/aeat/issues/212) |
| Generate an AutonomoProfile without writing JSON | ❌ | ❌ | ❌ | ❌ | 0.0.2 | [#214](https://github.com/wgergely/aeat/issues/214) |
| See which modelos apply and when | ✅ | ✅ | ✅ | ✅ | 0.0.2 | existing deadline engine |
| Get Spanish CLI output by default | ❌ | ❌ | ❌ | ❌ | 0.0.2 | [#207](https://github.com/wgergely/aeat/issues/207) |
| Understand what the tool does from `aeat --help` | ❌ | ❌ | ❌ | ❌ | 0.0.2 | [#208](https://github.com/wgergely/aeat/issues/208) |
| See humane message from `aeat status` | ❌ | ❌ | ❌ | ❌ | 0.0.2 | [#213](https://github.com/wgergely/aeat/issues/213) |
| Record WHY when manually classifying | ❌ | ❌ | ❌ | ❌ | 0.0.2 | [#223](https://github.com/wgergely/aeat/issues/223) |
| Import bank statement persisted in one command | ❌ | ❌ | ❌ | ❌ | 0.1.0 | [#216](https://github.com/wgergely/aeat/issues/216) |
| Bulk-classify via rules | ❌ | ❌ | ❌ | ❌ | 0.1.0 | [#217](https://github.com/wgergely/aeat/issues/217) |
| See how much he owes for Modelo 130 (T6) | ❌ | ❌ | ❌ | ❌ | 0.1.0 | [#218](https://github.com/wgergely/aeat/issues/218) |
| See confidence scores on every decision | ❌ | ❌ | ❌ | ❌ | 0.1.0 | [#236](https://github.com/wgergely/aeat/issues/236) |
| Distinguish pipeline-skipped from not-yet-seen | ❌ | ❌ | ❌ | ❌ | 0.1.0 | [#237](https://github.com/wgergely/aeat/issues/237) |
| Run one command for pipeline health | ❌ | ❌ | ❌ | ❌ | 0.1.0 | [#238](https://github.com/wgergely/aeat/issues/238) |
| Mark transaction reviewed-and-excluded | ❌ | ❌ | ❌ | ❌ | 0.1.0 | [#224](https://github.com/wgergely/aeat/issues/224) |
| See WHY each classification was made | ❌ | ❌ | ❌ | ❌ | 0.1.0 | [#231](https://github.com/wgergely/aeat/issues/231) |
| See pending reviews in one dashboard | ❌ | ❌ | ❌ | ❌ | 0.1.0 | [#232](https://github.com/wgergely/aeat/issues/232) |
| Authenticate against AEAT Sede Electrónica | 🚧 | 🚧 | partial | ❌ | 0.1.1 | [#141](https://github.com/wgergely/aeat/issues/141) |
| Retrieve previously-filed casilla values | ❌ | ❌ | ❌ | ❌ | 0.1.1 | [#222](https://github.com/wgergely/aeat/issues/222) |
| Ask "what filings did I miss?" | ❌ | ❌ | ❌ | ❌ | 0.1.1 | [#215](https://github.com/wgergely/aeat/issues/215) |
| See live AEAT inbox notifications | ❌ | 🚧 | partial | ❌ | 0.1.1 | [#170](https://github.com/wgergely/aeat/issues/170) |
| Build Modelo 130 via wizard | ❌ | ❌ | ❌ | ❌ | 0.2.0 | [#219](https://github.com/wgergely/aeat/issues/219) |
| See formula + operand values inline during review | ❌ | ❌ | ❌ | ❌ | 0.2.0 | [#220](https://github.com/wgergely/aeat/issues/220) |
| Approve a draft (persisted) | ❌ | ❌ | ❌ | ❌ | 0.2.0 | [#230](https://github.com/wgergely/aeat/issues/230) |
| Export an AEAT-importable fichero BOE file | ❌ | ❌ | ❌ | ❌ | 0.2.0 | [#201](https://github.com/wgergely/aeat/issues/201) |
| Compute 303 + 390 via formula engine | ❌ | ❌ | partial | ❌ | 0.3.0 | [#221](https://github.com/wgergely/aeat/issues/221) |
| Import a past filing made outside the tool | ❌ | ❌ | ❌ | ❌ | 0.3.0 | [#233](https://github.com/wgergely/aeat/issues/233) |
| File autoliquidación rectificativa | ❌ | ❌ | ❌ | ❌ | 0.3.0 | [#234](https://github.com/wgergely/aeat/issues/234) |
| Amend any supported modelo via wizard | ❌ | ❌ | ❌ | ❌ | 0.3.0 | [#235](https://github.com/wgergely/aeat/issues/235) |
| Fetch previously-filed casilla values from AEAT (wall 23) | ❌ | 🚧 | ready | ❌ | 0.1.0-pre-alpha | [#227](https://github.com/wgergely/aeat/issues/227) |
| Multi-currency income + expenses end-to-end | ❌ | ❌ | ❌ | ❌ | 0.3.1 | [#103](https://github.com/wgergely/aeat/issues/103) |
| Compute + export 111, 115, 190, 347 | ❌ | ❌ | ❌ | ❌ | 0.3.1 | TBD |
| Prove exported numbers match AEAT's record | ❌ | ❌ | ❌ | ❌ | 0.4.0 | [#239](https://github.com/wgergely/aeat/issues/239) |
| Get proactive alerts (inbox, deadlines, staleness) | ❌ | ❌ | ❌ | ❌ | 0.4.0 | part of [#239](https://github.com/wgergely/aeat/issues/239) |
| Live-submit (opt-in) | ❌ | ❌ excised | inert | ❌ | 1.0.0 | [#197](https://github.com/wgergely/aeat/issues/197), [#198](https://github.com/wgergely/aeat/issues/198), [#116](https://github.com/wgergely/aeat/issues/116) — CLI removed 2026-04-18 per ADR; engine default is opt-in only |

## provenance

Last updated **2026-04-17**. Refreshed via [#241](https://github.com/wgergely/aeat/issues/241) monthly-audit PRs.
