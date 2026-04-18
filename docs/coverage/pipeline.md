# pipeline coverage matrix

Per-stage implementation state for the T1–T6 Transaction Data Pipeline. Refreshed every month via audit [#241](https://github.com/wgergely/aeat/issues/241).

Legend: ✅ shipped · 🚧 in progress · ⏳ scheduled · ❌ not yet scoped

| Stage | Name | Implementation | CLI | Tests | Observability | Review surface | Error-path quality | Tracking |
|---|---|---|---|---|---|---|---|---|
| T1 | Ingest (CSV/XLSX/OFX → RawTransaction) | ✅ | 🚧 (no persist) | ✅ | ❌ | N/A | partial | [#216](https://github.com/wgergely/aeat/issues/216) |
| T2 | Normalise (RawTransaction → Transaction in catalogue) | ✅ | ✅ | ✅ | ❌ | N/A | partial | [#216](https://github.com/wgergely/aeat/issues/216) |
| T3 | Enrich (metadata, invoice/attachments) | partial | partial | partial | ❌ | ✅ [#232](https://github.com/wgergely/aeat/issues/232) | ❌ | ⏳ TBD |
| T4 | Classify (BusinessClassification + confidence + rules/LLM) | ✅ manual; ❌ bulk | partial | partial | ⏳ [#236](https://github.com/wgergely/aeat/issues/236) | ✅ [#232](https://github.com/wgergely/aeat/issues/232) | 🚧 | [#217](https://github.com/wgergely/aeat/issues/217) |
| T5 | Persist (catalogue + one-way Sheets export) | ✅ | ✅ | ✅ | partial | N/A | good | existing |
| T6 | Period close + casilla derivation | ❌ (load-bearing blocker) | ❌ | ❌ | ❌ | N/A | ❌ | [#218](https://github.com/wgergely/aeat/issues/218) |

## cross-cutting observables

| Concern | State | Tracking |
|---|---|---|
| Confidence on every decision | ❌ | [#236](https://github.com/wgergely/aeat/issues/236) |
| Decision provenance (`decided_by`, `reason`) | partial (classified_by only) | [#231](https://github.com/wgergely/aeat/issues/231) |
| Classification history (versioned) | ❌ | [#237](https://github.com/wgergely/aeat/issues/237) |
| `PROCESSED_UNCLASSIFIED` state distinct from `NOT_YET_PROCESSED` | ❌ | [#237](https://github.com/wgergely/aeat/issues/237) |
| Per-catalogue findings (not just per-draft) | ❌ | [#238](https://github.com/wgergely/aeat/issues/238) |
| Unified review queue | ✅ | [#232](https://github.com/wgergely/aeat/issues/232) |
| `aeat pipeline status` dashboard | ❌ | [#238](https://github.com/wgergely/aeat/issues/238) |
| Staleness detection on approved drafts | ❌ | [#230](https://github.com/wgergely/aeat/issues/230) |
| Verification against AEAT post-upload | ❌ | [#239](https://github.com/wgergely/aeat/issues/239) |

## provenance

Last updated **2026-04-17**. Refreshed via [#241](https://github.com/wgergely/aeat/issues/241) monthly-audit PRs.
