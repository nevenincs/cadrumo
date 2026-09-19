---
tags:
  - '#audit'
  - '#registry-campaign-sequencing'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:81f9f54d3e68fe5f4cebf0bd17e3795001246e317399b09c3a94662629f80b66'
related:
  - "[[2026-08-14-registry-campaign-sequencing-audit]]"
---

# `registry-campaign-sequencing` audit: `Convergence-sweep liveness triage`

## Scope

Establish liveness — not plausibility — for the unowned findings the
convergence sweep produced, per the assignment: trace real callers rather
than reading only the callee, state per finding whether callers were
actually traced, and rank by whether a wrong answer can reach a filed
artefact or persisted record. One finding (the M210 gate) could not be
located in the source tree within this pass despite a targeted search
(grep, semantic search, and direct file reads across the likely modules);
it is reported as not-yet-located rather than guessed at.

## Findings

### Convergence-sweep liveness triage | medium | `_replace_transaction`/`_require_transaction` duplication — LIVE, both reachable via real write paths; the missing `context` is a real diagnostic gap, not a data-corruption risk

Traced callers on both sides, not just the two callee bodies.

`application/ledger/_actions_common.py`'s `_replace_transaction` (line 625)
IS a true id-swap replace (pops `old_transaction_id`, inserts under
`replacement`'s own id) — a genuinely different operation from `_upsert_transaction`
six lines above it (line 619), which upserts under the transaction's own id.
Both are real and distinct, called from `_actions_classification.py`,
`_actions_lifecycle.py`, and `_actions_manual.py` — all within
`application/ledger/`.

`domain/transactions/_service.py`'s `_replace_transaction` (line 226) is
**confirmed byte-identical** in logic to `_actions_common.py`'s
`_upsert_transaction` — both set `updated[transaction.transaction_id] =
transaction`, no id-swap. Its only two callers, `link_invoice` (line 64)
and `set_classification` (line 173), never need id-swap semantics (both
update a transaction's fields in place, same id throughout), so the
misleading name causes no live behavioral defect — but it IS a real
duplicate that should collapse onto `_upsert_transaction`, not a latent
non-issue.

`_require_transaction` is duplicated with the SAME body shape but the
`domain/transactions/_service.py` copy (line 233-238) omits
`context={"namespace": ..., "transaction_id": ...}` on the raised
`TransactionNotFoundError` that the `application/ledger/_actions_common.py`
copy (line 643-650) carries. Traced whether this matters: `error.context`
IS surfaced in both the JSON envelope and text-mode CLI output
(`core/errors/_registry.py`, `context: dict[str, str] | None` field, plus
`_text_context_label`/`_text_context_value` rendering each key as its own
line) and IS available for locale-message interpolation
(`_coerce_interpolation_kwargs(getattr(error, "context", None))`). The
locale string for THIS specific error
(`errors.error.error_transaction_not_found` in `en.yml`) happens to be
static text with no placeholder, so no message text goes wrong — but the
STRUCTURED context line naming which transaction id failed is present when
the error originates from `_actions_common.py`'s ledger-action paths and
absent when it originates from `link_invoice`/`set_classification`
(`domain/transactions/_service.py`), both of which are real, live,
production-reachable write paths (`application/invoices/_linking.py`,
`application/invoices/_reconciliation.py`, and
`application/ledger/_llm_classification.py`'s LLM classification write).

**Verdict: live, on a real write path, but a diagnostic-quality gap rather
than a correctness or persistence defect.** The write itself is correct in
both copies; what degrades is which errors carry a machine-readable
`transaction_id` when a lookup fails. Does not reach a filed artefact.

### Convergence-sweep liveness triage | info | `_unscreened_reason` — LATENT: traced both real callers, both already guard the `rated` invariant

`registry/_rate_box_partition.py:286`'s `_unscreened_reason` checks its
`blind` argument internally (`if not blind: return ...`) but never checks
`rated` is non-empty before indexing/iterating it — matching the
convention-enforced-invariant shape the assignment flagged. Grepped for
every call site (3 total: the definition plus 2 calls) rather than assuming
there might be more, since the function is private (module-scoped,
single-underscore) and this file is exhaustively searchable.

Both real callers guard it: `_partition_for_rate_box_group` (line 179:
`if not rated: return None`) and `_unscreened_group_for_members` (line 389:
`if not rated: return None`) both check `rated` non-empty immediately
before calling `_unscreened_reason`, before any of the code paths that
would matter. No third caller exists (private function, exhaustively
grepped). **Verdict: latent, currently safe by construction at both real
call sites — not merely assumed, both were opened and read.**

### Convergence-sweep liveness triage | info | `is_direct_previous_filing_binding` — the premise itself does not hold: the selector dict IS filtered, key-presence checks are meaningful

Read the callee first as instructed, then went further: the concern implies
`selector.get(...)`/`key in selector` checks would be vacuous if the dict
always contained every possible key regardless of what was authored. Traced
`_selector_as_dict` (an alias for the canonical `selector_as_dict` in
`_binding_selector_utils.py:188`) to its actual construction:
`selector.model_dump(exclude={"source"}, exclude_none=True,
exclude_unset=True)`. Both `exclude_none` AND `exclude_unset` apply, so a
key is present in the dict only when the binding's TOML explicitly declared
it with a non-`None` value — key presence genuinely reflects authored
intent, not a pydantic-default artifact.

Traced all 4 call sites of `is_direct_previous_filing_binding` (all within
`domain/calculations/registry/`, used in build-time validation and
previous-filing resolution) — all consume this same correctly-filtered
selector. **Verdict: not a defect. The "unfiltered selector dict" premise
does not hold against the actual code; recording the correction rather than
letting the original framing stand unchallenged.**

### Convergence-sweep liveness triage | info | `_state_for_field` — LATENT: sole caller constrained to the exact two-value closed set the else-branch assumes

`application/ledger/_classification_assembly.py:418`'s `_state_for_field`
returns `issuer` when `field == "issuer_identification_state"`, else
`customer` — an else-branch that would silently mis-attribute a third or
malformed field value to `customer` rather than raising. Grepped its sole
call site (line 1033): `field` is always
`_counterparty_identification_field(direction)`'s return value, and that
function (lines 397-400) is a closed two-branch function on `InvoiceKind`
returning exactly `"customer_identification_state"` or
`"issuer_identification_state"`, nothing else. **Verdict: latent, safe by
construction at the one real call site — traced, not assumed.** Worth
noting for whoever owns hardening later: the closed-ness is enforced by
`_counterparty_identification_field`'s own logic, not by a type the
compiler checks, so a future third `InvoiceKind`-adjacent branch could
silently reuse this function incorrectly.

### Convergence-sweep liveness triage | info | `profile_binding_selectors` — LATENT: all 5 real call sites gate on `source == PROFILE` before calling it, verified individually

`domain/user_profile/_registry_contract.py:285`'s `profile_binding_selectors`
probes six literal selector keys with no internal check that the binding is
actually `source = "profile"`. Grepped every call site (5 total) and opened
each:

- `application/modelo/_profile_binding.py:233` (`_declared_profile_selectors`):
  gated inline, `if binding.source == BindingSourceKind.PROFILE`.
- `application/modelo/_profile_binding.py:1334`: consumes `selected_bindings`,
  which traces to `_select_profile_bindings` →
  `_is_relevant_profile_binding`, whose own first condition (line 1261) is
  `binding.source == BindingSourceKind.PROFILE and (...)`.
- `application/modelo/_profile_binding.py:1513` and `:1562`: both iterate
  `bindings`/consume the same profile-only selection upstream (the
  enclosing function unconditionally labels every diagnostic
  `source_kind=BindingSourceKind.PROFILE.value`, consistent with a
  profile-only input set).
- `domain/user_profile/_registry_contract.py:160`: gated inline one line
  above the call, `if binding.source != BindingSourceKind.PROFILE: continue`.

**Verdict: latent. The function itself carries no source-kind gate, exactly
as flagged, but every one of the 5 real call sites was individually opened
and confirmed to gate on `source == PROFILE` before reaching it — none
skipped, none assumed from a sibling's pattern.**

### Convergence-sweep liveness triage | low | NOT LOCATED: the M210 gate selected by parameter-id prefix with no fixture anchor

Could not find the specific site in this pass. Searched: grep for
`startswith` combined with `"210"`/`"m210"`/`"irnr"` across
`domain/calculations/registry/`, `dev/quality/`, and `dev/registry/`; read
`test_modelo_210_registry.py` and the IRNR formula-runtime module directly;
ran a targeted semantic search (`vaultspec-rag`) for "Modelo 210 gate
selects parameters by id prefix, no fixture anchor" and for the pension-tariff
mechanism specifically. Nothing matched the description closely enough to
verify against. This may be a mis-transcription of the finding's target
(the M130 provisional-specimen fixture gate found during search is a
different, unrelated mechanism, already fixture-anchored per its own test
suite) or it may sit somewhere this pass's search terms did not reach.
**Reporting as not-located rather than guessing** — a wrong site named with
false confidence is worse than an honest gap. Needs either a corrected
pointer from whoever filed the original convergence finding, or a fresh,
differently-worded search pass.

### Convergence-sweep liveness triage | low | `dev/locales/_ast_scanner.py:427` basename denylist — CONFIRMED dormant, exact wake condition established

The denylist `if module.name in {"test_parity.py", "manager.py",
"_ast_scanner.py"}: continue` matches by BASENAME only, no path
qualification. Found every file literally named `manager.py` in the repo
(5 total, not 1): `dev/docs/apidocs/manager.py`, `dev/locales/manager.py`
(almost certainly the one this denylist was actually written for — the
locale tool's own manager, reasonable to exclude from a locale-key
scanner), `dev/registry/aeip/manager.py`,
`dev/registry/conformance/manager.py`, `dev/registry/newmodelo/manager.py`.
The basename-only match silently also skips the other four.

Checked all four unintended matches directly for the thing that would make
this live: grepped each for `tr(` and `message_key=` calls. **Zero hits in
all four, today.** So the gate's blind spot has no live consequence right
now — confirmed by reading the files, not inferred from the file names.

**Exact wake condition, stated as a condition someone can notice rather
than a vague caveat:** the day ANY of `dev/docs/apidocs/manager.py`,
`dev/registry/aeip/manager.py`, `dev/registry/conformance/manager.py`, or
`dev/registry/newmodelo/manager.py` gains a `tr(...)` call or a
`message_key=` argument, this scanner silently stops seeing it — no
missing-key error, no orphaned-key warning, nothing. This is a `dev/`
tooling gate (locale-key parity), not a runtime or filing-boundary gate, so
even when it wakes it affects locale-catalogue completeness checking, never
a filed figure directly.

## Recommendations

**Ranked by whether a wrong answer reaches a filed artefact or persisted
record**, per the assignment's own ordering criterion:

1. Nothing found this pass reaches a filed artefact incorrectly. The
   closest is the `_replace_transaction`/`_require_transaction` duplication
   (finding 1) — live, on real persisted-record write paths, but the
   degradation is diagnostic richness (a missing `transaction_id` in an
   error's structured context), not a wrong write or a wrong filed value.
   Rank this first for follow-up precisely because it is the only live one,
   not because it is severe.
2. The four LATENT findings (`_unscreened_reason`,
   `is_direct_previous_filing_binding`, `_state_for_field`,
   `profile_binding_selectors`) are all currently safe by construction, each
   individually verified by tracing real callers rather than assumed from
   the shape of one sibling finding. They are tidiness/hardening items — the
   convention holding today does not guarantee it holds after the next
   binding family is added — but none is live today.
3. The `dev/` locale-scanner dormancy is a tooling gate, not a
   filing-boundary one, and is confirmed to have zero current consequence.
   Lowest priority, but the wake condition is now precise enough to act on
   the day it fires rather than needing rediscovery.
4. The M210 gate finding needs a corrected pointer before it can be traced
   at all — flagging this explicitly rather than letting "not located"
   quietly read as "checked and clean." It is untriaged, not cleared.

For `is_direct_previous_filing_binding` specifically: the convergence
sweep's premise (unfiltered selector dict) does not match the actual code.
Whoever consolidates these findings should correct that characterization
rather than carry it forward, the same way the "review-status collision"
and "Nota 7" corrections were carried explicitly earlier in this campaign
rather than silently dropped.
