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
| See consistent error messages with copy-paste recovery commands | ✅ | ✅ | ✅ | ✅ | 0.0.2 | [#398](https://github.com/wgergely/aeat/issues/398) |
| Record WHY when manually classifying | ❌ | ❌ | ❌ | ❌ | 0.0.2 | [#223](https://github.com/wgergely/aeat/issues/223) |
| Import bank statement persisted in one command | ❌ | ❌ | ❌ | ❌ | 0.1.0 | [#216](https://github.com/wgergely/aeat/issues/216) |
| Bulk-classify via rules | ❌ | ❌ | ❌ | ❌ | 0.1.0 | [#217](https://github.com/wgergely/aeat/issues/217) |
| See how much he owes for Modelo 130 (T6) | ✅ | ✅ (`aeat financial aggregate --modelo 130 --period YYYY-Qn`, shared `--json`; `workflow` consumes catalogue-backed inputs for supported modelos) | ✅ | ✅ classified Q1 transactions produce a `CasillaAggregation` ledger (`01` income, `02` deductible expenses, provenance transaction IDs) and feed the Modelo 130 formula engine | 0.1.0 | [#218](https://github.com/wgergely/aeat/issues/218) |
| See confidence scores on every decision | ✅ | ✅ (`--confidence-below` on `txs list` + `review queue`; LLM path at `txs classify-llm`) | ✅ | ✅ live-verified on synthetic catalogue | 0.1.0 | [#236](https://github.com/wgergely/aeat/issues/236) |
| Classify transactions via an LLM (claude / gemini / codex) | 🚧 | ✅ (`aeat financial txs classify-llm`; tier-enforced model capability; reuses #253 CategoryProfile proportionality defaults) | ✅ | ✅ live-tested with codex end-to-end | 0.1.0 | [#236](https://github.com/wgergely/aeat/issues/236) (structured `DecisionProvenance` payload still missing — tracked by [#352](https://github.com/wgergely/aeat/issues/352)) |
| Distinguish pipeline-skipped from not-yet-seen | ✅ | ✅ | ✅ | ✅ | 0.1.0 | [#237](https://github.com/wgergely/aeat/issues/237) |
| Run one command for pipeline health | ❌ | ❌ | ❌ | ❌ | 0.1.0 | [#238](https://github.com/wgergely/aeat/issues/238) |
| Mark transaction reviewed-and-excluded | ❌ | ❌ | ❌ | ❌ | 0.1.0 | [#224](https://github.com/wgergely/aeat/issues/224) |
| See WHY each classification was made | ❌ | ❌ | ❌ | ❌ | 0.1.0 | [#231](https://github.com/wgergely/aeat/issues/231) |
| Configure personal usage-ratio coefficients once | ✅ | ✅ (`aeat financial usage-ratios`; default proportionality applied at classify time) | ✅ | ✅ | 0.1.0 | [#259](https://github.com/wgergely/aeat/issues/259) (shipped via PR #306) |
| See pending reviews in one dashboard | ❌ | ✅ | ✅ | ❌ | 0.1.0 | [#232](https://github.com/wgergely/aeat/issues/232) |
| Authenticate against AEAT Sede Electrónica | 🚧 | 🚧 | partial | ❌ | 0.1.1 | [#141](https://github.com/wgergely/aeat/issues/141) |
| Retrieve previously-filed casilla values | ❌ | ❌ | ❌ | ❌ | 0.1.1 | [#272](https://github.com/wgergely/aeat/issues/272), [#305](https://github.com/wgergely/aeat/issues/305) |
| Ask "what filings did I miss?" | ❌ | ❌ | ❌ | ❌ | 0.1.1 | [#215](https://github.com/wgergely/aeat/issues/215) |
| See live AEAT inbox notifications | ❌ | 🚧 | partial | ❌ | 0.1.1 | [#170](https://github.com/wgergely/aeat/issues/170) |
| Build Modelo 130 via wizard | ❌ | ❌ | ❌ | ❌ | 0.2.0 | [#219](https://github.com/wgergely/aeat/issues/219) |
| See formula + operand values inline during review | ❌ | ❌ | ❌ | ❌ | 0.2.0 | [#220](https://github.com/wgergely/aeat/issues/220) |
| Approve a draft (persisted) | ✅ | ✅ (`aeat review approve`; staleness detection) | ✅ | ✅ | 0.2.0 | [#230](https://github.com/wgergely/aeat/issues/230) (shipped via PR #269) |
| Export an AEAT-importable fichero BOE file | 🚧 | ✅ (`aeat submission export`; 130 + 303 shipped; 390 pending) | ✅ (golden SHA256 pinned per modelo; verify round-trip) | 🚧 (CLI produces byte-exact output; live portal upload untested) | 0.2.0 | [#201](https://github.com/wgergely/aeat/issues/201) |
| Verify an exported fichero BOE decodes back to the casilla values | ✅ | ✅ (`aeat submission verify <file> --modelo <m> --ejercicio <y>`) | ✅ (5 CLI tests + per-modelo round-trip) | ✅ | 0.2.0 | [#305](https://github.com/wgergely/aeat/issues/305) wave 95 |
| Compute 303 + 390 via formula engine | ❌ | ❌ | partial | ❌ | 0.3.0 | [#221](https://github.com/wgergely/aeat/issues/221) |
| Import a past filing made outside the tool (umbrella) | ❌ | ❌ | ❌ | ❌ | 0.3.0 | [#233](https://github.com/wgergely/aeat/issues/233) |
| Import past filing from justificante receipt PDF | ✅ | ✅ | ✅ | ✅ | 0.3.0 | [#271](https://github.com/wgergely/aeat/issues/271) |
| Import past filing from full declaración PDF (calc-verified) | ✅ | ✅ (Modelo 130 + 303 MVPs) | ✅ (L3 synthetic) | ✅ | 0.3.0 | [#305](https://github.com/wgergely/aeat/issues/305) cluster D |
| Import Modelo 100 pre-filing borrador (summary block) | ✅ | ✅ (`--from-borrador`) | ✅ (L3 synthetic) | ✅ | 0.3.0 | [#305](https://github.com/wgergely/aeat/issues/305) cluster F |
| Import Modelo 100 predeclaración / simulación (summary block) | ✅ | ✅ (`--from-borrador`) | ✅ (L3 synthetic) | ✅ | 0.3.0 | [#305](https://github.com/wgergely/aeat/issues/305) cluster F |
| Capture tax-residence CCAA for automatic RENTA | ✅ | ✅ (`aeat profile show/set tax-region/clear`; required by M100 imports) | ✅ | ✅ local JSON profile drives 0545/0551/0622 regional context | 0.3.0 | [#452](https://github.com/wgergely/aeat/issues/452) (Path A JSON; foral regimes deferred to [#424](https://github.com/wgergely/aeat/issues/424)) |
| See import verdict (verified / needs-review / unverifiable) | ✅ | ✅ | ✅ | ✅ | 0.3.0 | [#305](https://github.com/wgergely/aeat/issues/305) cluster E |
| File autoliquidación rectificativa | ❌ | ❌ | ❌ | ❌ | 0.3.0 | [#234](https://github.com/wgergely/aeat/issues/234) |
| Amend any supported modelo via wizard | ❌ | ❌ | ❌ | ❌ | 0.3.0 | [#235](https://github.com/wgergely/aeat/issues/235) |
| Fetch previously-filed casilla values from AEAT (wall 23) | ✅ | ✅ (`StatusReader.fetch_filing_detail`) | ✅ | ✅ | 0.1.0-pre-alpha | [#227](https://github.com/wgergely/aeat/issues/227) (read surface shipped via PR #248; Kent-facing import still blocked on [#272](https://github.com/wgergely/aeat/issues/272)) |
| Auto-derive rental income tier per Ley 12/2023 (50/60/70/90 %) | ✅ | ✅ (`aeat rental finca`, `contract`, `income`, `expense`, `anexo-c`) | ✅ (49 unit + 6 CLI tests; BOE-anchored tier resolver, art. 23.1.f amortización ledger with cap, art. 23.1.a) cap + 4-year carry-forward) | ✅ end-to-end pipeline cent-exact via `aeat rental anexo-c compute --json` | 0.3.0 | [#454](https://github.com/wgergely/aeat/issues/454) |
| Multi-currency income + expenses end-to-end | ❌ | ❌ | ❌ | ❌ | 0.3.1 | [#103](https://github.com/wgergely/aeat/issues/103) |
| Compute + export 111, 115, 190, 347 | ❌ | ❌ | ❌ | ❌ | 0.3.1 | TBD |
| Prove exported numbers match AEAT's record | ✅ | ✅ (`aeat filing reconcile`, MATCH / DIVERGENT / NOT_YET_FOUND triad) | ✅ (L3 synthetic + 40 sanitised real fixtures) | ✅ live (M100/2022, M130/2024 4T, M303/2024 4T, M111/2024 4T, M390/2023) | 0.4.0 | [#239](https://github.com/wgergely/aeat/issues/239) Tier 1; per-modelo deep extractors + aggregator cumulation deferred |
| Get proactive alerts (inbox, deadlines, staleness) | ❌ | ❌ | ❌ | ❌ | 0.4.0 | part of [#239](https://github.com/wgergely/aeat/issues/239) follow-on |
| Kent can pipe `aeat X --json \| jq` across every command | ✅ | 🚧 root `--json` and the shared envelope ship for a bounded registered set, not every command | ✅ representative pipe-safety tests cover root-flag success and failure paths for registered commands | 🚧 shared `stdout`/`stderr` behavior is live for representative registered commands; CLI-wide adoption is still intentionally not claimed | TBD | [#399](https://github.com/wgergely/aeat/issues/399) |
| Kent can pipe `aeat X --json \| jq` across every command | ✅ | 🚧 root `--json` and the shared envelope ship for a bounded registered set, not every command | ✅ representative pipe-safety tests cover root-flag success and failure paths for registered commands | 🚧 shared `stdout`/`stderr` behavior is live for representative registered commands; CLI-wide adoption is still intentionally not claimed | TBD | [#399](https://github.com/wgergely/aeat/issues/399) |

## auth protocol note

Issue [#281](https://github.com/wgergely/aeat/issues/281) is internal
groundwork. It generalises the auth/session boundary so future
providers can be added cleanly, but it does not ship a new
Kent-facing login method. Kent still logs in through the existing
certificate-based path.

## provenance

Footnote: the tool is **produce -> verify -> export**. Live AEAT
submission is permanently out of scope, and Kent uploads the exported
fichero via the AEAT portal himself.

Last updated **2026-04-30** (#218 — Kent can aggregate quarterly Modelo 130 from classified transactions via `aeat financial aggregate`, inspect casilla provenance, and feed the formula engine through the workflow inputs provider; Modelo 303 T6 aggregation remains deferred). Earlier refresh **2026-04-28** (#452 — tax-residence CCAA profile ships via `aeat.profile`, local JSON persistence, `aeat profile`, setup capture, and Modelo 100 import enforcement for RENTA regional context). Earlier refresh **2026-04-27** (#239 round-5 — `aeat filing reconcile` ships live MATCH / DIVERGENT / NOT_YET_FOUND triad against the live AEAT sede; declarations-presentadas register fallback enables quarterly modelos; 25 additional sanitised fixtures committed; live verification matrix covers 5 modelos × 8 (modelo, period, year) tuples). Earlier refresh **2026-04-25** (`#399` shipped-branch docs pass; JSON coverage row kept conservative to the registered command set). Earlier refresh **2026-04-22** (EPIC #305 wave 54 — 2024 backfill rulesets land; 2024 complementaria self-audit now supported for Modelos 111/115/123/130/131/180). Refreshed via [#241](https://github.com/wgergely/aeat/issues/241) monthly-audit PRs.
