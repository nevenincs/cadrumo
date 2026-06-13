---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity Code Review


## S353 — casilla 0505 formula (commits 94b424c6b / eb8793d07 / 227350dc9)

**Verdict: APPROVE with follow-up (APPROVE+FU)**

Status: **PASS** — no Critical or High blockers. One Medium grounding note requires a follow-up fix.

---

### Standing Gates

**G1 — no naked env reads:** PASS. No `os.environ` or `os.getenv` in any touched file.

**G2 — typed pydantic at boundaries:** PASS. No `dict[str, Any]` introduced.

**G3 — user-facing messages via `tr()`:** PASS. No user-facing strings in the changed files; test assertions are diagnostic only.

**G4 — no locale yml hand-edits:** PASS. No locale files touched.

**G5 — no shims, duplication, gratuitous copy-paste:** PASS with observation. The 2024 and 2025 formula TOML bodies are structurally identical (`max(0, [0500]-[0527])`, same rounding, same source_citation block). The registry TOML loader does not expose a cross-revision fragment mechanism; each revision is an independent TOML file and the duplication is intentional by design. The 2025 formula carries additional `legal_refs` entries (`art-49`, `rd-439-2007:art-109`, `orden-hac-277-2026:art-3`) reflecting its revision-specific regulatory additions, so the two files are not gratuitously identical. No remediation required.

**G6 — no tautological calculation tests:** PASS. The oracle values are derived independently from the LIRPF 2024 Art. 63 escala estatal brackets. Both cuota figures (949.02 EUR for base 14,896 no-anualidades; 602.87 EUR for base 11,896 with 3,000 anualidades) were verified by independent bracket arithmetic and match exactly. The test inputs are not derived from the formula under test; they flow through a real registry snapshot via leaf casilla 0003.

---

### Grounding Gate

**GROUNDING-001 | MEDIUM | `art-56` cited as primary formula authority but registry maps Art. 56 to mínimo personal y familiar**

The formula TOML for both revisions lists `ley-35-2006:art-56` as first `legal_refs` entry. The commit message also cites "LIRPF Art. 56" as the operative article.

In the project's legal registry (`src/aeat/_data/registry/aeat/legal/irpf.toml` line 1779), `ley-35-2006:art-56` is annotated:

> "Base legal para el minimo personal y familiar en Modelo 100, casillas 0511-0524."

Its `required_text` contains `"mínimo personal y familiar"` and `"necesidades básicas"` — nothing about base liquidable general sometida a gravamen or anualidades alimentos.

`ley-35-2006:art-50` (line 2018) is correctly the authority for base liquidable general (casillas 0500/0510) and its `required_text` matches. Art. 50 was already wired to the upstream `renta-2024-anualidades-alimentos-hijos-suma` formula that produces 0527.

The correct primary authority for the 0505 subtraction step is most likely **Art. 63** (escala general applied to the base liquidable general sometida a gravamen) or a direct read of the Modelo 100 dictionary note under `source_refs`. The plan step itself says "verify the anualidades operand from `aeat-dr-100-2024-dictionary`" as the source grounding path; that source_ref is present in the casilla TOML but not in the formula TOML.

Remediation: Remove `ley-35-2006:art-56` from both formula `legal_refs` arrays (it belongs to the mínimo cluster, not 0505). Add `ley-35-2006:art-63` if it is the consuming article, or retain only `art-50` if Art. 50 transitively covers the "sometida a gravamen" designation. Add `aeat-dr-100-2024-dictionary` (and the 2025 equivalent) to the formula `source_refs` to satisfy the plan gate. This is a metadata-only TOML change with no runtime impact.

---

### Intent & Completeness

Plan step W07.P31.S353 requires: formula targeting 0505, expression `max(0, 0500 - anualidades_alimentos_hijos_judicial)`, `input_kind=computed` in both 2024 and 2025 revision casilla TOMLs, G6 gate, source grounding against `aeat-dr-100-2024-dictionary`. All structural deliverables are present and correctly wired. The construct registration is in the right position in both `0001-renta-cuota-chain.toml` files.

The R7 cluster-T Eva/David round-10 finding (0532=0 because 0505 was manual) is correctly closed by the `input_kind=computed` change.

---

### Safety & Correctness

The formula expression `max(0, subtract(0500, 0527))` is safe: both casillas are computed upstream, `max` with literal 0 floor prevents negative base, rounding is `money-2` consistent with adjacent formulas. No crash paths. Construct ordering places the formula after `renta-2024-base-liquidable-general` (which produces 0500) — dependency order is correct.

The three new tests exercise: (1) zero-anualidades path, (2) non-zero anualidades with independent cuota oracle, (3) anti-tautology delta assertion. The migrated existing 7 tests correctly switch from supplying computed casilla 0505 directly (now rejected) to the leaf manual casilla 0003.

---

GROUNDING-001 | MEDIUM | Remove `ley-35-2006:art-56` from formula legal_refs (Art. 56 is mínimo personal y familiar; the 0505 subtraction authority is Art. 50 / Art. 63); add `aeat-dr-100-2024-dictionary` to formula source_refs per plan gate.
