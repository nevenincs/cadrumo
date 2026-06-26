# C0 Decision B — precise implementation handoff (traced & safe-by-construction)

> ## ⛔ GROUNDING UPDATE (2026-06-19) — DO NOT IMPLEMENT DECISION B AS WRITTEN
> A RAG-grounding pass plus a peer's independent deep audit reversed the premise of this
> handoff. The cross-period "deadlock" is substantially **by design**, not a bug:
> - `_engine.py:477` and `test_file_flow_filing.py` document that **`export` is the local
>   finish line** and **`work file` is OPTIONAL and only works while the obligation window is
>   open** — every period independently reaches `.boe` via `export` regardless of window
>   (`2026-05-21-work-verify-deadline-independence-adr`).
> - `test_local_cross_period_carry.py` test **D1** now explicitly PINS that an `app_filing`
>   local chain MUST still BLOCK a dependent-period filing with
>   `LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE` (safety gate / `no-silent-under-declaration` /
>   `local-filed-observations-are-non-official-evidence`).
>
> Therefore **Decision B (relax that block to a non-blocking advisory) directly contradicts a
> test-pinned safety invariant and MUST NOT be implemented.** **Decision A (allow overdue local
> `work file`) likewise contradicts the documented in-window-only design** and should be dropped/
> reworked rather than landed. The genuine supported paths already exist: file each period in its
> open window (auto-carry works) or import official AEAT evidence (`pull-sources` / `reconcile
> file`) for prior periods. Keep C1 + H1 + the carry-test fix (all grounded-clean); do NOT carry
> the design below forward except as a record of what was rejected and why.
>
> The detail below is retained only for historical traceability of the rejected approach.

Status as of 2026-06-19: **Decision A is implemented + verified** (uncommitted in `_engine.py`;
overdue local `work file` now reaches the filing path — confirmed by the flagship persona's
HEAD re-test). The **H1 carry-test regression is fixed** (`test_local_cross_period_carry.py` 5/5).
This note specifies the remaining **Decision B** (the verify-side advisory tier) so it can be
implemented and **E2E-verified on a stable tree** — it is NOT landed yet because it changes a
safety-adjacent verify gate and cannot be E2E-verified in the current volatile tree (see "Why not yet").

## The exact, safe design (traced from the code)
A clean local `app_filing` chain produces **exactly** these blockers
(`_cross_period_clean_state.py:1027-1034`, `_filing_external_evidence_blockers`):
- `MISSING_AEAT_ACCEPTANCE` (filing not aeat_accepted)
- `MISSING_EXTERNAL_EVIDENCE` (no external_evidence)
- `LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE` (the above + non-official source)

Any *other* condition adds a blocker NOT in that set: value divergence →
`OBSERVATION_REVISION_VALUE_DIVERGENCE`; stale revision → `REGISTRY_REVISION_DIVERGENCE`;
operator-manual source → `OPERATOR_MANUAL_SOURCE`; missing observation/filing →
`MISSING_OBSERVATION`/`MISSING_CURRENT_FILING_RECORD`; group gaps →
`INCOMPLETE_GROUP_MEMBER_COVERAGE` etc. So the boundary below is **safe by construction**.

### 1. `_cross_period_clean_state.py`
Add the delta set (near the blocker enum):
```python
_OFFICIAL_EVIDENCE_DELTA_BLOCKERS: Final = frozenset({
    CrossPeriodCleanStateBlocker.MISSING_AEAT_ACCEPTANCE,
    CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE,
    CrossPeriodCleanStateBlocker.LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE,
})
```
Add a property on `CrossPeriodDependencyEvidence` (mirror the `suppressed_pre_activity` facet style):
```python
@property
def non_official_local_chain(self) -> bool:
    """A complete LOCAL app_filing chain whose ONLY blockers are the official-evidence
    delta. Decision B: the local export path treats this as sufficient-with-disclosure
    (non-blocking advisory). NOT clean (still lacks official evidence), but the operator
    files every period at AEAT externally and the advisory discloses the non-official basis.
    Any non-delta blocker (value/revision divergence, operator-manual, missing obs, group
    gaps) keeps it blocking — it is excluded here because such a blocker is not in the set."""
    if not self.blockers:
        return False  # already fully clean
    if self.observation_source_kind is None or self.observation_source_kind in _OFFICIAL_SOURCE_KINDS:
        return False  # must be a genuine non-official (app_filing) source
    return all(b in _OFFICIAL_EVIDENCE_DELTA_BLOCKERS for b in self.blockers)
```
Add a verdict-level helper:
```python
@property
def locally_clean_or_clean(self) -> bool:
    return all(d.clean or d.non_official_local_chain for d in self.dependencies)
```

### 2. `_verification_actions.py` (routing — the behaviour change)
In `_cross_period_clean_state_findings`: for a dependency where `evidence.non_official_local_chain`
is True, emit a **non-blocking ADVISORY (WARNING)** finding — message: "this filing rests on a
non-official local-only chain; file all periods at AEAT and reconcile the official justificantes" —
instead of the BLOCKING `CROSS_PERIOD_DEPENDENCY_UNCLEAN`. Keep the existing legal_refs.
In `_require_cross_period_clean_state` (the gate that blocks verify): block only when the verdict is
NOT `locally_clean_or_clean` (i.e. some dependency is neither clean nor a non-official local chain).

### 3. Tests (must pin the boundary — exhaustive, no mocks)
- `non_official_local_chain` True for app_filing + {only delta blockers}.
- False (stays blocking) for EACH of: `OBSERVATION_REVISION_VALUE_DIVERGENCE`,
  `REGISTRY_REVISION_DIVERGENCE`, `OPERATOR_MANUAL_SOURCE`, `MISSING_OBSERVATION`,
  `MISSING_CURRENT_FILING_RECORD`, `INCOMPLETE_GROUP_MEMBER_COVERAGE`, and for an OFFICIAL source.
- The verify gate: a locally-clean dependency → verify GRANTS with a WARNING advisory; a
  value-divergent prior → verify still BLOCKS. `app_filing` stays out of `_OFFICIAL_SOURCE_KINDS`
  (existing `test_cross_period_clean_state_enforcement.py` pin must stay green).
- E2E (the acceptance test): M130 1T→2T→3T→4T full local chain — each quarter `work file`
  (Decision A, extemporánea) then next quarter calculate auto-carries casilla 05 and verify
  GRANTS with the advisory and EXPORTS → 4/4 .boe; M100 folds in the four casilla-19 values.
  M303 1T→2T compensación carries 420 → 2T resultado 525, both export.

## Why not landed yet (verification blockers)
- The full chain can only be E2E-tested with a profile that GENERATES the past-year quarterly
  obligation. Local profiles created with `--accept-defaults` show `censo.enrolment_unverified`
  and do NOT generate the 2024 quarterly obligation (only today-year). The flagship persona's
  profile (carrying `censo.activity_start_date`) does — reproduce that config.
- A transient peer gap (`ModeloExportOutputPathError` not in the error registry) blocked the
  flagship's chain at export; it now appears registered at HEAD (`_export.py` + `_application_part2.py`),
  so the chain should be testable again — confirm before relying on it.
- The tree is volatile (peer/user commits every few minutes in the modelo area). Land Decision B
  when the tree is calm and run the full E2E acceptance test above before trusting it.
