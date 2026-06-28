---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-26-cross-domain-continuity-plan]]'
---

# cross-domain-continuity Code Review

## Commit

814cb1c89 -- domain(deadlines): _plazo module + extemporaneidad test (new domain submodule)

## Status: PASS

No Critical or High issues. Safe to merge.

---

## Scope

Two new files added. No existing files modified.

- src/aeat/domain/deadlines/_plazo.py -- registry lookup for filing window close dates
- src/aeat/domain/deadlines/test_extemporaneidad.py -- extemporaneidad and Art. 27 LGT recargo tests

---

## Critical Question Answers

Q1. New _plazo submodule architecture -- clean integration with domain/deadlines/? G5.

Clean. _plazo.py is a pure domain module with no shim, no re-export alias, and no compatibility layer. It is integrated into domain/deadlines/__init__.py at the resolve_filing_closes_on export. _modelo.py imports directly via a deferred import inside _work_unit_plazo_lines. No duplication with _engine.py or _recargo.py. G5 passes.

Q2. Recargo Art. 27 LGT computation -- Ley 11/2021 bracket accuracy.

The ley-58-2003-recargo-bands.toml declares five bands that correctly implement the post-Ley 11/2021 ladder: 1% (1-30 days), 3% (31-90), 6% (91-180), 12% (181-365), 15% + intereses Art. 26 LGT (366+). All five tranches of current Art. 27.2 LGT are correctly covered.

Q3. Surface integration.

- aeat app modelo work status: YES -- _work_unit_lines calls _work_unit_plazo_lines (line 1308), feeding work.status output.
- aeat app modelo work calculate: YES -- plazo_lines appended to modelo.work.calculate output at line 3150.
- aeat app overview status: NO -- build_overview_status_report emits aggregate counters only; per-modelo plazo data not surfaced. Pre-existing scoping; the overview agenda verb covers overdue cohorts.
- aeat app review queue: NOT APPLICABLE -- review queue is transaction/ledger-item scoped, not work-unit-plazo scoped.
- PLAZO_VENCIDO finding: Surfaced as a translated warning line in work.status and work.calculate output. Not a typed VerificationFinding code in the verification engine.

Q4. Wizard parity (#228/#239). No new CLI flags added. Not applicable.

Q5. Locale parity es/en/ca/hu.

- es/en/ca: substantive translations present for plazo_days_remaining and plazo_vencido_warning.
- hu: both keys use scaffold passthrough references. Violates S176 LOCALE-001. See LOCALE-001 finding.

Q6. Per-modelo plazo derivation.

resolve_filing_closes_on queries the validated registry authority. Verified: M130 Q1 2026 resolves to April/May 2026; M100 2024 annual 0A resolves to June 2025. M650 (ISD, cedido tax) absent from registry, returns None gracefully.

Q7. Oracle test: M650 12-month extemporaneo.

M650 not in registry. Direct oracle test with closes_on = date(2024, 11, 30) and reference_today = date(2026, 5, 27) = 543 days late -- after_12_months band, 15% + interest. Test passes using calendar-derived day count, not a registry formula re-derivation.

Q8. Anti-tautology.

Suite covers all four band tiers with different days_late inputs (15, 120, 300, 543 days), each asserting a distinct band and surcharge. Anti-tautology criterion satisfied.

---

## Safety Domain (G1-G6)

- G1 No naked env reads: PASS
- G2 Typed pydantic at boundaries: PASS. RecargoBand and Recovery are strict frozen models. _plazo.py returns date|None.
- G3 tr() for user messages: PASS. Both plazo locale keys wrapped in tr().
- G4 No locale yml structure hand-edits: PASS for es/en/ca. See LOCALE-001 for hu.
- G5 No shims/re-exports/duplication: PASS
- G6 No tautological tests: PASS

---

## Findings

### LOCALE-001 | LOW | Hungarian locale uses scaffold passthrough for plazo keys

src/aeat/locales/hu.yml lines 721-722 carry unresolved scaffold key references instead of translated strings. The runtime tr() call emits the key path as literal text. Provide substantive Hungarian translations before next locale audit pass.

### ARCH-001 | LOW | _resolve_closes_on_cached lru_cache has no mtime invalidation

_plazo.py line 47 uses @lru_cache(maxsize=256) keyed on (modelo, filing_year, period) with no registry fingerprint. The established pattern in _recargo.py keys on (path, byte_count, modified_ns). Benign for CLI (short-lived process) but inconsistent.

### SAFETY-001 | LOW | Bare-except absorbs all exceptions in _resolve_closes_on_cached

_plazo.py line 63: except (RegistryError, Exception) is functionally bare-except with noqa: BLE001 suppressing the lint signal. Intent and docstring are sound. Consider narrowing to except RegistryError with a WARNING-level log for unexpected exceptions.

---

## Test Execution

9 passed in 55.59s (uv run pytest src/aeat/domain/deadlines/test_extemporaneidad.py)
