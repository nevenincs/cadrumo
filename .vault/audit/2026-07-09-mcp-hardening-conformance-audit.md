---
tags:
  - '#audit'
  - '#mcp-hardening-conformance'
date: '2026-07-09'
modified: '2026-07-10'
body_hash: 'sha256:226a6eac0b151edeba51f05249004d26139a029c247363339f1fb825f4637ec4'
related:
  - "[[2026-07-08-mcp-hardening-conformance-plan]]"
---

# `mcp-hardening-conformance` audit: `honesty review (campaign close): verified findings + dispositions`

## Scope

Mandatory fresh-context honesty review (`aeat-campaign-close-honesty-review`) of the
MCP console campaign — the two ADR/plan pairs (`mcp-progressive-discovery` /
`mcp-protocol-hardening` conformance and `mcp-identity-linked-operation`) plus the
`released-data-durability` fix — over commit range `057744c473..e789a968c7`. An
independent Opus reviewer read the identity-gate, risk-table, durability, search, and
spine code in full and ran the safety-critical suites (22/22 in the integration lane;
the secure-object durability end-to-end proof passes on the real substrate). Every
finding below was RE-VERIFIED against HEAD by the coordinator before disposition.

**Verdict: REVISION RECOMMENDED — no critical, no blocking-high.** The safety-critical
spine is genuinely solid and verifiable (identity gate keys off the declared risk
table, fires on both call paths, `execute` cannot bypass it, fail-closed default;
H3 no-silent-default holds; secure-object + bundle durability chain-upgrade on read
with the KDF/key path untouched; whoami/spine carry a label not a UUID; the Erik/Erika
eval is non-tautological). Two MEDIUM over-claims are dispositioned below; findings 3–7
are accepted bounded residuals.

## Findings

### archive-durability-floor-gate-only | medium | archive tier has a range gate, not the upgrade dispatch the ADR claims

VERIFIED at HEAD: `ensure_archive_schema_readable` (`application/bucket_maintenance/_service.py:113-141`)
is only a `floor <= v <= ceiling` check with NO upgrader and NO transform on restore —
unlike secure-object (`_schema_lineage.upgrade_secure_object_payload`) and bundle
(`user_profile/_bundle.py:BUNDLE_PAYLOAD_UPGRADERS` + chain-upgrade at `:137`), which
both carry a real per-hop upgrader chain. The `released-data-durability` ADR / commit
`253cc5ce4f` claim forward-version-gating "across secure-object/bundle/archive" with an
upgrade dispatch; for archive that over-states. Latent today (floor==ceiling==2, nothing
to upgrade), but a future archive-version bump with the floor held would pass every gate
green while restore applied new logic to an old header with no transform — the exact
stranding the ADR says is "structurally impossible." Owned by the durability campaign
(fable), not the MCP console work. Disposition: flagged to the durability owner + tracked
follow-up — add an archive upgrader chain mirroring the other two OR narrow the ADR claim
and make `test_archive_schema_lineage` assert real restorability.

### semantic-search-reranks-lexical-candidates-only | medium | "hybrid" search cannot recall a pure-semantic match (over-claim)

VERIFIED at HEAD: `CommandIndex.search` (`application/command_search/_index.py`) builds
the candidate universe lexically (`_lexical_ranked_keys`; returns `()` when there is no
lexical hit), then `_reciprocal_rank_fusion` iterates the lexical keys and adds a semantic
contribution ONLY for keys already lexically matched. A zero-lexical-overlap concept query
is never surfaced whatever its embedding similarity; `total_matches`/`truncated` count the
lexical set. Disposition: FIXED by disclosure — an explicit accepted-limitation note added
to the `mcp-progressive-discovery` ADR (P2) recording the recall boundary and that admitting
the semantic top-k is a deferred enhancement. Acceptable for the small closed command corpus
where curated aliases cover the outcome-phrased gaps and the golden set proves the cases.

### family-granular-read-only-mislabels-read-verbs | low | genuine read verbs classify read_only=False on the model surface

VERIFIED: `_classification._mutability_for` resolves mutability by FAMILY, so `ledger view` /
`config profile show` classify `read_only=False`, flowing into `readOnlyHint` and making the
identity gate fire on them. Fail-closed and explicitly acknowledged in ADR I2's harness.load
refinement — a fidelity miss, not a safety hole. Disposition: accepted; optional future
per-command `read_only` declaration for genuine read leaves.

### block-tier-gate-ordering-divergence | low | the two call paths return different refusal text for an (unreachable) BLOCK-tier unconfirmed call

VERIFIED: direct path runs the identity gate before the live-write BLOCK; execute path emits
the BLOCK before `run`'s identity gate. For an unconfirmed call to a BLOCK-tier verb the paths
return different refusal text (identity vs live-write). Both refuse (no safety impact) and the
case is unreachable — no live-write verb is exposed (never-submit). Disposition: accepted +
recorded; optional order-alignment.

### out-of-band-profile-switch-does-not-rearm | low | a profile change outside the MCP session leaves the gate confirmed

VERIFIED: the gate re-arms only on console-mediated `PROFILE_SWITCHING_COMMANDS`. A raw
`config switch` or concurrent process leaves `identity_confirmed=True`, so a later MCP mutation
could run under an unseen profile. Narrow under single-session stdio. Disposition: accepted +
documented boundary of the "the agent saw who is active" guarantee; optional: re-resolve the
active bucket id at gate time and re-arm on change.

### wizard-edit-spine-null-plus-bespoke-dup | low | wizard EDIT envelope still emits null spine active_profile

VERIFIED: `wizard/_commands.py` populates the spine label on create but leaves it null on edit
(the active profile is not necessarily the edited one — an intentional bound, see the commit
comment), and a bespoke `payload["active_profile"]` result field duplicates the spine concept.
Create fixed in `efd6b00394`. Disposition: accepted (edit-null is by design); optional: resolve
the true active label on edit and fold the payload field into the spine.

### identity-tests-integration-lane-only | low | identity safety tests run only under -m integration

VERIFIED: the identity/harness/serving tests are `pytest.mark.integration`, deselected by the
default `-m unit` addopts — matching every MCP entrypoint test; all 22 pass under `-m integration`.
Not orphaning. Disposition: INFO — CI must include the integration lane for identity coverage.

## Recommendations

- Promote finding 1 (archive durability) to a tracked follow-up for the durability owner; it is
  latent, not active. Finding 2 is closed by the ADR disclosure landed alongside this audit.
- Findings 3–7 are accepted, bounded, documented residuals; no fix required for structural
  completeness. Each names an optional future improvement.
- With finding 2 disclosed and finding 1 tracked+flagged, the campaign is structurally complete:
  the safety-critical spine is verified sound and the residuals are honest and bounded.
