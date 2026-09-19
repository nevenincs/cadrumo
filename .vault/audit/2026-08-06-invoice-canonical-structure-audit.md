---
tags:
  - '#audit'
  - '#invoice-canonical-structure'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:28bbf53f3db5d9a94fb5e3b847585def9c61f9ecccbe52d13f0face22f407d6b'
related:
  - "[[2026-08-06-invoice-canonical-structure-adr]]"
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---
# `invoice-canonical-structure` audit: `Fresh-context honesty review of the campaign`

## Scope

A fresh-context honesty review of the `invoice-canonical-structure` campaign, mandated by
`aeat-campaign-close-honesty-review`. The auditor authored none of the reviewed documents.
Read-only: no file in the worktree was modified, staged, or committed.

Reviewed: this feature's research, ADR and plan as they stood before the rewrite, plus the
superseded `2026-06-10-ledger-invoice-unification-adr` read in full, and the source
discovery sweep landed alongside this record.

Repo HEAD at audit time was `daa9876ed3`; the source findings had been verified at
`0b1e3f040b`, twenty-four commits earlier, two of them on the invoice surface. That gap is
itself one of the findings.

**Why this record exists in the vault.** The review was originally written to a scratch
directory outside the git tree, where a team opening this repository would never have found
it. Its verdict is the reason the plan was rewritten from seven Steps to thirty-one, so the
evidence chain must be repo-resident. The content below is the review as written, with its
headings demoted one level to nest under Findings. Its citations were accurate at
`daa9876ed3` and the tree has since moved: re-read every cited site at HEAD before acting
on it.

## Findings

Auditor: fresh context, did not author any reviewed document. Mandated by
`aeat-campaign-close-honesty-review`. Read-only; no file in
`Y:\code\aeat-worktrees\main` was modified, staged, or committed.

Documents reviewed:
- `.vault/research/2026-08-06-invoice-canonical-structure-research.md` (475 lines)
- `.vault/adr/2026-08-06-invoice-canonical-structure-adr.md` (334 lines)
- `.vault/plan/2026-08-06-invoice-canonical-structure-plan.md` (90 lines)
- `.vault/adr/2026-06-10-ledger-invoice-unification-adr.md` (241 lines, read in full)
- Source findings `Y:\code\llm-invoice-smoke\findings\LANES.md` (692 lines, read in full)

Repo HEAD at audit time: `daa9876ed3`. The source findings were verified at
`0b1e3f040b`; **24 commits have landed since**, two of them on the invoice
surface (`7502ee65ed`, `ef0438561d`).

---

### Verdict in one line

**The decision to canonicalise is right and the supersession holds. Almost
nothing else does.** The plan is 60% empty, and the empty 60% is the entire
reason the campaign exists — executing what it actually contains would leave
the tree *worse* than today. Beneath that, the ADR's two load-bearing
feasibility claims are both false at HEAD: neither model is a superset of the
other (F3), and the fold crosses a storage-scope boundary the ADR's only
storage-safety constraint describes backwards (F3b). Three of seven Steps are
already satisfied or vacuous, one of them closed by the campaign's own commit
(F5, F6).

The research is the strongest document of the three — it records its own
instrument caveat and its own falsified earlier claim, which is why several
findings below could be checked at all.

---

### THE HEADLINE FINDING — three of five phases contain zero Steps

`vaultspec-core status` reports `P0/5  0/7 steps`. The seven Steps all sit in
P01 and P02. **P03, P04 and P05 are bare headings with prose and no Step rows.**

| Phase | Subject | Steps |
| --- | --- | --- |
| P01 | Prove canonical coverage | 3 |
| P02 | Extend the writer surface | 4 |
| **P03** | **Fold and delete the slim store** | **0** |
| **P04** | **Second-authority and boundary gaps** | **0** |
| **P05** | **M303 screen blind spots + M390 equivalent** | **0** |

Mapped against the ADR's eleven decisions, **seven have no Step at all**:

| Decision | Subject | Step |
| --- | --- | --- |
| D-A | Delete the slim store | **none** (P03) |
| D-B | Collapse the operator noun | **none** (P03) |
| D-C | Prove coverage first | P01.S01, P01.S02 (both defective — see F4, F5) |
| D-D | Retire the blessing test | **none** (P03) |
| D-E | Writer surface reaches the model | P02.S04–S06 |
| D-F | Retención stays off the draft | n/a (negative decision) |
| D-G | Mixed-rate at the writer | P02.S07 (incomplete — see F8) |
| D-H | Resolve the second `Invoice` writer | **none** (P04) |
| D-I | M303 blind spots + M390 equivalent | **none** (P05) |
| D-J | Rename `InvoiceLine.category_id` | **none** (P04) |
| D-K | Confirm-boundary plausibility gate | **none** (P04) |

The reverse direction is clean: every one of the seven Steps traces to a
decision. There is no unauthorised scope. The failure is entirely
one-directional — **decisions with no Steps.**

#### Why this is a filing-consequence finding and not a documentation wart

P02 is additive and independently landable. P03 is where the fold happens.
Shipping P01+P02 and stopping — which is exactly what a plan containing only
P01 and P02 invites — produces this state:

- `aeat app ledger invoice add` still writes the **slim** store.
- `aeat app ledger invoice catalogue create` still writes the **rich** store.
- Both still union into M347/M349 at `_source_resolver.py:200-202` with no dedup.
- The rich writer is now *substantially more attractive* (retención, recargo,
  `iva_category`, `invoice_class`, `series`, `operation_date`, multi-line), so
  more operators migrate to `catalogue create` — while `invoice add` remains
  the shorter, more discoverable verb.

That is a **higher** double-count exposure than today, not a neutral partial
landing. The campaign's own risk analysis (ADR Consequences: "the double-count
cannot recur… closed structurally") is only true after P03, and P03 does not
exist.

The plan's Description asserts "The work has five phases with load-bearing
ordering between them" and spends a paragraph justifying tier `L2` over `L1`
and `L3` on the strength of that ordering. Three-fifths of the structure being
argued over is not written. This is precisely the
"self-reports complete while structurally incomplete" pattern
`aeat-campaign-close-honesty-review` exists to catch.

---

### Disposition register — every source finding, marked

Built independently from `LANES.md`. `LANES` carries six TANGLES, six GAPS
(plus G3b), and a jointly-agreed D1–D4 scope.

**Scope caveat, stated rather than glossed:** this register covers `LANES.md`
in full and `INGEST.md` only through the joint D1–D4 scope that `LANES`
restates. `INGEST.md`'s own independent findings are **not** enumerated here.
Given that three of the four joint items were dropped or mislabelled (D2, D4 —
see F7), the INGEST-only findings should be assumed to have a similar drop rate
until someone builds that half of the register. That is unfinished audit work,
not a clean result.

#### TANGLES

| # | Finding | Disposition |
| --- | --- | --- |
| T1 | One operator noun, two stores, unguarded double-count | **Actioned in ADR** (D-A, D-D). **No Step** — P03 empty. |
| T2 | Lane derived from bank-money direction (`_iva_ledger.py:1518-1547`) | **Out of scope, honestly** — ADR names it, gives a reason (blast radius across the IVA path, not a duplication defect), defers to its own campaign. Adequate. |
| T3 | Purchase evidence confirmable as ISSUED | **Actioned in ADR** (D-K). **No Step** — P04 empty. |
| T4 | `IvaCategory` derivable only from `--operation-type` | **Actioned** — D-E → P02.S05. Genuinely covered. |
| T5 | Two "category" concepts | **Partly actioned** — D-J renames `InvoiceLine.category_id`. **No Step** (P04). The research's own **third site** (`_preflight.py:304-320`, uses `category_id` with the `SpendingCategory` meaning) is **dropped** — D-J does not mention it. |
| T6 | Rich catalogue is one mixed-kind container; lane discipline is per-consumer | **Left open** — ADR Considerations names the trade, Open Questions defers "reproduced or consciously dropped". **This is a P03 decision with no P03.** Deleting the slim store removes a structural guarantee; the ADR requires that dropping it be "a stated decision, not an oversight", and no Step states it. |

#### GAPS

| # | Finding | Disposition |
| --- | --- | --- |
| G1 | M303 screen country-scoped, cuota-scoped, M390-less. LANES: **"the highest-consequence finding in the sweep"**, and **"Act on G1 and G2 first, in that order."** | **Actioned in ADR** (D-I). **No Step, and no Verification criterion** — see F2. Downgraded to "severable". |
| G2 | No CLI route to retención on a single invoice | **ALREADY CLOSED AT HEAD — and misstated in both directions.** When written it was *understated* (the route it cites, `_importing.py`, is orphaned; the live `_bulk_import.py` cannot write retención at all). It was then closed outright by `ef0438561d` — **the same commit that landed the campaign documents**. P02.S04's code is done. See F6, F8b. |
| G3 | `catalogue create` cannot express most regimes | **Actioned and genuinely open** — D-E → P02.S05, S06. Re-measured at HEAD: `--recargo` / `--iva-category` / `--invoice-class` / `--series` absent, and `--operation-date` still missing from `catalogue_wizard`. Correctly scoped. |
| G3b | Mixed-rate collapses at both ends | **Half-actioned** — D-G takes the writer half only; reader half deferred to Dependencies. See F8 — the deferral omits LANES's own conclusion that the writer half alone changes nothing. |
| **G4** | **`source_jurisdiction` exists on no invoice model**; required on `Transaction` (`_models.py:808`) and mandatory for IRNR and art. 93 impatriado (`_ledger_support.py:260-272`); M151 scoping depends on it | **SILENTLY DROPPED.** Appears in **none** of research, ADR, or plan — verified by grep across all three. Not actioned, not deferred, not in "Deliberately out of scope". |
| **G5** | **The evidence lane cannot represent recargo and says so** (`_evidence_draft.py:488-508` — extraction reads it and discards it) | **SILENTLY DROPPED as a lane finding.** `--recargo` appears only as a *writer* CLI option (D-E) and in the M303 screen extension (D-I). Recargo on the extraction draft is decided nowhere. This is joint-scope **D4** — see F7. |
| *(new)* | **`_bulk_import.py`, the live import surface, is named in no campaign document** — while D-H reasons about the dead `_importing.py` as though it were the only import path | **SILENT DROP.** A duplication finding missed by a duplication campaign; it also answers D-H's open question (delete, not route). See F8b. |
| G6 | No single record carries both the IVA and the jurisdiction axis | **Dropped.** LANES calls it "a design consequence rather than a defect", so silence is defensible — but it is unnamed, and it is the same axis as G4. |

#### The jointly-agreed D1–D4 scope

LANES and INGEST negotiated a four-item scope and a sequencing
("**D2 first** — independently shippable, no reader change, no cascade, and it
unblocks the most fields per unit of work"). Sequencing was accepted by the
coordinator.

| Joint item | Subject | Disposition |
| --- | --- | --- |
| D1 | Writer emits N lines; reader emits per-rate breakdown | Writer half → D-G → P02.S07. Reader half deferred. |
| **D2** | **The confirm-boundary override set** (`confirm_invoice_draft_from_evidence`) — should it mirror the READER or the WRITER | **NOT DECIDED — and mislabelled as decided.** See F5. |
| D3 | Retención stays off the draft | → D-F. Correctly carried, reason preserved, orthogonality to D2 preserved. |
| **D4** | **Recargo goes ON the draft** — "the one point where reader-side and writer-side answers deliberately diverge, and the ADR should say why" | **SILENTLY DROPPED.** The ADR names D2 and D3 by label and never mentions D4. |

#### Is the ADR's "Deliberately out of scope" section honest?

**Partly.** What it lists is genuinely and well reasoned — T2 in particular is
a model deferral (names the defect, names the reason, names where it goes).
But the section is headed *"Named so they are not lost to silence"*, and three
source findings were lost to exactly that: **G4**, **G5/D4**, and the **real
D2**. Two of the three are items the source agents jointly agreed and
explicitly sequenced. The section is a short list that omits the inconvenient
items, which is the failure mode the review brief anticipated.

---

### Findings, ranked by consequence

#### F1 — BLOCKING. The deletion phase has no Steps

Stated above. **What would have to change:** P03, P04 and P05 need real Step
rows authored through `vaultspec-core vault plan step add`. Until then the plan
is not executable and the campaign cannot be declared structurally complete
under `plan-closure-requires-exec-records`.

#### F2 — BLOCKING. The source report's top-ranked finding has neither a Step nor a gate

LANES: G1 is *"the highest-consequence finding in the sweep"*; *"Act on G1 and
G2 first, in that order."*

The plan gives **G2 four Steps in P02** and **G1 zero Steps in P05**, marked
"severable". Worse: the plan's **Verification section never mentions M390 or
the screen at all.** So P05 can be closed with zero work and no gate detects
it — the plan is complete "when every Step is closed", and P05 has no Steps.

I confirmed the gap is real at HEAD:
- `rg "def _raise_if" src/cadrumo/application/aggregation/` returns **exactly
  one** hit, `_modelo_bindings.py:1005`.
- `rg -i "m390|modelo_390|\"390\"" src/cadrumo/application/aggregation/_modelo_bindings.py` returns **nothing**.
- The ES filter is live at `_modelo_bindings.py:1122`.
- The four-binding screened set is live at `_modelo_bindings.py:144`.

LANES also left one targeted question open: *"Whether an invoice-only bucket
can reach a filed M390 through that gap is one targeted question against the
M390 binding set… If it can, it outranks everything in this document."* That
question is **not answered** anywhere in the campaign, and D-I proceeds to
assert the fix without it.

**What would have to change:** P05 needs Steps, the Verification section needs
an M390 criterion, and the open M390-reachability question should be answered
before D-I's priority is settled.

#### F3 — HIGH. Neither model is a superset of the other, and the pre-filter the ADR cites was run backwards

The ADR's first Consideration is the load-bearing justification for folding
rather than choosing:

> *"Everything the slim record expresses, the rich record also expresses; the
> converse is false… **Applying the substitutability pre-filter, the rich
> aggregate's constraint shape is a superset.** There is no symmetric choice to
> agonise over."*

`aeat-swarm-audit-cadence` defines that pre-filter precisely:

> *"verify that Y's constraint shape is a superset of (more permissive than)
> X's current constraint… If Y carries additional constraints (min_length,
> pattern, max_length, or value-format restrictions) that X does not, the site
> is **NOT promotable**."*

The ADR checked **field presence** (rich has more fields — true) and concluded
superset. The pre-filter is about **constraint permissiveness**. Run correctly
at HEAD, the rich model carries **at least four constraints the slim model does
not**:

| Constraint | Rich | Slim |
| --- | --- | --- |
| counterparty name | `counterparty_name: str = Field(min_length=1)` — **required non-empty** (`_models.py:515`) | `counterparty_name: str = Field(default="", max_length=200)` — **defaults to empty** |
| counterparty country | `counterparty_country: str = Field(min_length=2, max_length=2)` — **required** (`:517`) | `country_code: str | None` — **nullable** |
| line items | `_require_lines` — **at least one line** (`_models.py:660-663`) | no `lines` field at all |
| totals identity | `_validate_totals_and_exempt_invariants` — *"grand_total must equal base_total + iva_total + recargo_amount + suplido_amount exactly"* (`:683-694`) | **no model_validator whatsoever**; `taxable_base` / `iva_amount` / `total_amount` are independent `ge=0` fields defaulting to zero |

I confirmed the slim model has **no `model_validator` at all** — only
field-level validators for `country_code`, `currency` and the date strings.

**And it fails in the field direction too.** The ADR says *"Everything the slim
record expresses, the rich record also expresses; the converse is false."*
Verified against `git show HEAD:` — **three slim fields have no rich
counterpart**:

| Slim field | Rich |
| --- | --- |
| `created_at: datetime` (`:195`, required) | **absent — the rich `Invoice` has no lifecycle timestamps at all** |
| `updated_at: datetime` (`:196`, required) | **absent** |
| `iva_rate: Decimal \| None` (`:180`, invoice-level) | only a per-line `IvaRate` enum tier |

I checked the entire rich class body, not just its field block: `created_at` /
`updated_at` appear nowhere. So folding **loses the record's audit
timestamps** — when it was entered and when it was last edited — on a
filing-evidence record. That interacts with
`single-subject-mutation-is-idempotent-guarded` (which wants identity
clock-free but expects a non-identity last-seen body field) and with
`ledger-derived-revisions-bundle-evidence`. Nothing in the campaign records the
loss or decides to accept it.

**This does not invalidate the decision to canonicalise.** The rich model being
stricter is arguably the point. What it invalidates is the ADR's stated
*reason*: **neither model is a superset of the other**, there **is** a cost to
agonise over, and the pre-filter the ADR cites by name says a site in this
shape is "NOT promotable" without documenting the mismatch.

**Concrete consequence the ADR does not record.** `aeat app ledger invoice add`
today accepts an invoice with an empty counterparty name, no country code, and
a `total_amount` inconsistent with base + IVA. Once D-B collapses the noun onto
the canonical aggregate, **all three are refused.** That is a live narrowing of
the operator input contract, and it appears nowhere in Consequences — which
instead says only *"A migration is not required and must not be written."*
(True for stored data, since pre-release records are discarded with the store;
irrelevant to the input contract.)

There is also an unaddressed interaction: folding a slim record into the rich
shape must **synthesise a line**, and single-line synthesis is precisely what
D-G/P02.S07 is changing. Neither decision references the other.

**What would have to change:** restate the Consideration as a documented
constraint-shape mismatch rather than a superset; add the input-contract
narrowing to Consequences; and decide, in P03, what the fold does with a slim
record that cannot satisfy the rich invariants.

#### F3b — BLOCKING. The fold is a storage-scope change, and the ADR's Constraints assert the opposite

The two stores do not merely differ in partitioning. They sit at **different
storage scopes**, verified in `_namespace_registry.py`:

| | Slim (`:520-528`) | Rich (`:906-915`) |
| --- | --- | --- |
| scope | `StorageNamespaceScope.BUCKET_LOCAL` | **`StorageNamespaceScope.PROFILE_LOCAL`** |
| key grammar | `"{bucket_id}:{source_kind}"` | `"catalogue"` |
| shape | two documents **per bucket** | **one document per profile** |
| bucket attribution | `bucket_id: BucketId` — **required**, and in the document key | `bucket_id: BucketId \| None = Field(default=None)` — **optional field** |

The ADR's Constraints section states:

> *"The canonical aggregate MUST remain the encrypted **bucket-scoped** secure
> object it is today; no plaintext sidecar, no parallel write path."*

**The canonical aggregate is not bucket-scoped.** It is profile-local. The
constraint describes the store being deleted, not the one being kept — so the
ADR's one storage-safety constraint is unsatisfiable as written, and would read
to an executor as "no change needed here".

Folding therefore moves financial records from bucket-partitioned storage into
a single profile-wide document, and **downgrades bucket attribution from a
required key component to an optional field**. That is a collapse of a data
partition boundary on `SensitivityClass.FINANCIAL` records, which is squarely
the concern of `sensitive-financial-data-secure-storage-only` and the custody
model. It is not addressed in the ADR, the research, the plan, or the Open
Questions — the ADR's Considerations frame the difference as *"physical
partition of the lanes"* (a within-bucket lane concern), which understates it.

There is a live consumer of the scope difference: `_custody_carry.py:78,322-327`
registers the slim namespace for backup/restore custody carry under
`"cadrumo.application.ledger.business_operation_invoices"`. Deletion must
deregister it, and the profile-local target has different custody semantics.

**This is BLOCKING rather than HIGH** because, unlike the empty phases, it is a
defect in the ADR's own safety constraint — the one place an executor would
look to confirm the fold is storage-safe.

#### F4 — HIGH. The deletion gate demands the canonical path reproduce the defect

The ADR's D-C is correctly worded:

> *"the slim store's **declarable coverage** is proven reproducible on the
> canonical path"*

The plan mutates this in both places it restates it:

> `P01.S01` — *"Prove the canonical path reproduces the M347 per-party totals
> and M349 operator rows **that the two-store union produces today**, for a
> bucket **exercising both stores**"*

> Verification — *"a test proves the canonical path produces **the same** M347
> per-party totals and **the same** M349 operator rows that the two-store union
> produces today, for a bucket exercising both stores"*

For a bucket exercising both stores with the same real invoice — the exact
configuration the campaign exists to fix — **the two-store union's totals are
doubled.** The gate as written demands the canonical path reproduce the
double-count. It is either unsatisfiable or, if satisfied, proves the wrong
thing.

This is a translation error from ADR to plan sitting in **the one gate that
guards the deletion**. `aeat-git-worktree-safety` framing applies: a retirement
whose replacement-proof is mis-specified is a retirement with no proof.

**What would have to change:** P01.S01 and the Verification paragraph must
adopt D-C's wording — *declarable coverage*, i.e. every declarable fact the
slim store contributes is reachable on the canonical path — not output-equality
with the union.

#### F5 — HIGH. P01.S02 is vacuous; its verification criterion is already green at HEAD

P01.S02: *"Make the iva_category clave fallback the surviving behaviour and
prove an invoice carrying a category but no operation_type is declared rather
than dropped."*

Verified at HEAD by direct read:
- `_intracommunity_clave` (`_source_resolver.py:436`) **already carries the full
  fallback** — six `iva_category` branches at `:444-463` (T, E, S, I, A).
- `_business_invoice_clave` (`:663`) returns `None` immediately when
  `operation_type is None` (`:665-666`); `_business_invoice_observation` drops
  at `:588-590`.
- The slim record **cannot hold an `iva_category` at all** — `rg "iva_category"
  src/cadrumo/application/ledger/_business_operation_invoice.py` returns
  nothing.

So: on the canonical path the fallback already exists and the invoice is
already declared. There is nothing to "make surviving". The asymmetry closes
**only** by deleting the slim path — i.e. in the empty P03. The Verification
claim *"where it is silently dropped today"* is **false for the canonical
path**; it is true only for the slim path, which this Step does not touch.

P01.S02 is a gate that passes without work being done.

*(Secondary note: the drop is M349-only. `_business_invoice_observation:586-587`
returns the M347 observation **before** the clave check, so M347 is unaffected.
The research states this correctly; the ADR's D-C prose does not scope it.)*

#### F6 — HIGH. The campaign asserts a gap that its own commit closed, and P02.S04 is already done

`ef0438561d` ("Aggregate wip commit of all current changes", 2026-08-06 20:04)
is **the commit that landed all three campaign documents.** It also landed the
retención writer. Both facts verified:

```
git log -S "retention_rate" -- src/cadrumo/application/invoices/_creation.py
  -> ef0438561d
git show 0b1e3f040b:.../_creation.py | rg -c retention_rate  -> 0   (absent)
git show HEAD:.../_creation.py       | rg -c retention_rate  -> 6   (present)
```

At HEAD:
- `build_catalogue_invoice` takes `retention_rate` / `retention_amount`
  (`_creation.py:112-113`), serialises both (`:189-192`).
- `create_catalogue_invoice` takes and forwards them (`:247-248`, `:277-278`).
- `--retention-rate` / `--retention-amount` exist on **both** entry verbs —
  `catalogue_create` (`_ledger_business_invoice_cli.py:602-603`) and
  `catalogue_wizard` (`:684-685`), declared at `:556` / `:570`.

So the research's *"`create_catalogue_invoice` accepts no retención
parameter"*, LANES G2, and ADR D-E's retención clause were **already false when
committed** — the assertion and its refutation are in the same commit.
**P02.S04's code is done**; only its roundtrip test may remain.

I re-measured the rest of P02 at HEAD rather than assuming:

| Option | At HEAD | Step status |
| --- | --- | --- |
| `--retention-rate` / `--retention-amount` | **present**, both verbs | **P02.S04 already landed** |
| `--recargo`, `--iva-category`, `--invoice-class`, `--series` | **absent** | P02.S05 genuinely open |
| `--operation-date` | on `catalogue_create` (`:601`) only; **absent from `catalogue_wizard`** | P02.S06 genuinely open (matches LANES G3) |
| single-line synthesis | still unconditional | P02.S07 genuinely open |

This is the third Step found to be already-satisfied or vacuous (with P01.S02,
F5). The pattern is the same: the campaign was written against `0b1e3f040b` and
never re-measured against the tree it was committed into.
`aeat-swarm-orchestration` requires exactly that re-read
(*"a peer fix can land between an agent's investigation and its
recommendation"*) — here the peer fix landed in the campaign's own commit.

**Consequence for the register:** G2's disposition is not "actioned" but
"already closed". An executor taking P02.S04 at face value would re-implement
a landed feature and, per the plan's own instruction to `git diff` before a
first edit, collide with it.

#### F7 — HIGH. Joint-scope D2 is undelivered under a label that says it is delivered

LANES D2 is specific: *"the confirm-boundary override set. Today it mirrors the
nine draft fields. The decision to settle is whether it should mirror the
READER or the WRITER."* Its subject is
`confirm_invoice_draft_from_evidence` (`_evidence_draft.py:702-718`).

The ADR's D-E says: *"`create_catalogue_invoice` and the CLI entry verbs gain
retención… **This is the D2 decision from the joint scope.**"*

It is not. D-E's subject is `_creation.py` and
`_ledger_business_invoice_cli.py`. Grep across all three campaign documents for
`override set` / `confirm_invoice_draft` finds the confirm boundary mentioned
only in **D-K** (the plausibility gate) and once in the research's Dependencies
paragraph. **The override set is decided nowhere, and no Step touches
`_evidence_draft.py`.**

This matters more than a mislabel: D2 is the item both source agents agreed
should ship **first**, on the stated ground that it is independently shippable
and unblocks the most fields per unit of work (retención, recargo,
`invoice_class`/`rectifies_invoice_number`, `iva_category` on the *evidence*
path in one move). The label makes an undelivered, top-priority item look
delivered.

Companion drop: **D4** (recargo on the draft) is absent entirely — see the
register. G5's consequence is concrete: a recargo-de-equivalencia taxpayer's
figure is lost at every hop before `Transaction`, and per G1 the recargo
bindings are also unscreened. That is a two-hop loss with no gate, and the
campaign closes neither hop.

#### F8 — MEDIUM-HIGH. D-G names one of two line-synthesis sites, and omits its own source's conclusion

P02.S07 scopes the mixed-rate writer fix to `_creation.py`. But
`_bulk_import.py` carries a **second** synthesis site — its own docstring at
`:95` says it *"synthesises a single line item exactly as
`build_catalogue_invoice` does"*, and it constructs at `:412` / `:437`. It is
CLI-reachable (`_ledger_business_invoice_cli.py:823` → `import_invoices_from_rows`).
Fixing only `_creation.py` leaves the bulk path collapsing mixed rates.

Separately, LANES states plainly of the two-end collapse: **"Closing either
alone changes nothing."** The ADR defers the reader half to Dependencies
without surfacing that its own bundled writer half therefore has no
operator-visible effect on its own. That is not dishonest, but a reader of the
ADR alone would not know that D-G as scoped ships zero behaviour change.

*(D-H's two-writer framing does hold: I checked `_bulk_import.py` and it routes
through `build_catalogue_invoice` / `create_catalogue_invoice` (`:54`, `:412`,
`:437`), so it is not a third authority. `_importing.py`'s own functions are
exported from the package facade but called by no CLI verb — the ADR's claim
is correct.)*

#### F8b — MEDIUM-HIGH. A second import surface exists and no campaign document names it

There are **two** invoice-import modules. Only one is live:

| Module | Reachability | Write path |
| --- | --- | --- |
| `_bulk_import.py` | **LIVE** — CLI `catalogue import` (`_ledger_business_invoice_cli.py:775`) calls `read_bulk_invoice_import_rows` + `import_invoices_from_rows` at `:823` | routes through `build_catalogue_invoice` / `create_catalogue_invoice` (`:54`, `:412`, `:437`) — **canonical** |
| `_importing.py` | **DEAD** — `import_invoices_from_path` / `merge_invoice_import` have zero production callers; exported via `application/invoices/__init__.py` `__all__`, called only by its own tests | own `Invoice.model_validate` (`:91`), own merge that **silently skips** a duplicate (`:111-113`) — **second authority** |

`_bulk_import.py` is named in **none** of the research, the ADR, or the plan.
Two consequences:

1. **It answers D-H's open question.** The ADR settles that both writers may not
   persist but leaves "deleted or routed" open, and the plan has no Step either
   way. A *routed* bulk importer **already exists** — so routing `_importing.py`
   would produce a third import surface duplicating `_bulk_import.py`. The
   disposition is **delete**, and that is determinable from code the campaign
   did not look at.
2. **It corrects a cited fact.** LANES G2 says the only retención write route is
   "the bulk CSV/XLSX importer", citing `_importing.py:57-58`. Two errors
   compound there: the CSV/XLSX importer is `_bulk_import.py`, not
   `_importing.py`; and `_bulk_import.py` has **no** retención support at all
   (`rg retention` returns nothing). So at `0b1e3f040b` the cited route was
   *dead* and the live one *could not write retención* — **G2 was understated
   when written**, then closed outright by `ef0438561d` (F6). Neither state
   matches what the ADR says.

#### F9 — MEDIUM. Peer-ADR constraint not carried; P02 would edit into it blind

`2026-08-05-ledger-invoice-decomposition-adr:194-202` pins the rich `Invoice`
totals discipline and the `derive_invoice_id` input set, and was **AMENDED on
2026-08-06 (D10)** to `grand_total == base_total + iva_total + recargo_amount`
— the amendment note records that the earlier omission of the recargo term
"was not a simplification but a defect".

D-E adds `--recargo` to the writer and D-G accepts a supplied line set. Both
land **inside** that identity. The new ADR cites the decomposition ADR only for
its deferred product-surface question and never for this constraint; the plan's
Parallelization section flags the *sequencing* collision but not the
*invariant* collision.

**What would have to change:** P02.S05 and P02.S07 must cite the amended totals
identity as a constraint, or the two records will disagree about what
`grand_total` contains.

#### F10 — MEDIUM. The ADR has no status, and the supersession is not recorded in frontmatter

Checked all 24 ADRs dated `2026-08-*` plus the superseded one:

- Every other ADR carries `| (**status:** \`accepted\`)` or `\`proposed\`` in
  its title line. **`2026-08-06-invoice-canonical-structure-adr` carries none.**
  It is uniquely statusless.
- Its frontmatter has **no `supersedes:` field**. The supersession exists in
  prose only.
- `2026-06-10-ledger-invoice-unification-adr` still reads
  `(**status:** \`accepted\`)`, its `supersedes:` field is empty, and **no Step
  in the plan marks it superseded.**
- The dependency it defers to — `2026-08-06-llm-package-split-adr` (proposed) —
  is described in prose ("under active decision") but **named nowhere** and
  absent from `related:`.

A statusless ADR has no authority to supersede an accepted one, and the
vaultspec pipeline requires an approved ADR before a plan. The plan exists.

This repeats a known failure: the 2026-06-10 ADR itself said its predecessor
"must be marked `superseded` by the coordinator (editing it is a separate step
outside this authoring pass)" — and the research found that predecessor file
**does not exist**. The same "separate step outside this pass" is being taken
again, with no Step to catch it.

#### F11 — LOW-MEDIUM. Drifted citations — line-precision, not false claims (with two exceptions)

**Stated plainly for the reader: the ADR's factual grounding was checked and it
held.** A dedicated verification pass covered all 19 citation groups. Every
functional and architectural assertion is true at HEAD. The drifts below are
line-precision misses — a function's edge, a docstring line quoted instead of
the code beneath it — and **none invalidates the claim it supports.** The
supersession argument in particular rests on citations that verify exactly.

I verified the load-bearing citations myself at HEAD `daa9876ed3`.

**Verified exactly** (the entire supersession argument rests on these):

| Citation | Status |
| --- | --- |
| `432fc96d29` = 2026-06-28, "fix(modelo): feed m349 from business invoices" | VERIFIED |
| `_source_resolver.py:200-202` union of both stores | VERIFIED — concatenation at exactly 200-202 |
| `_source_resolver.py:552` `_load_business_operation_invoices` | VERIFIED |
| `_source_resolver.py:579` `_business_invoice_observation` | VERIFIED |
| `_source_resolver.py:436` `_intracommunity_clave` | VERIFIED |
| `_source_resolver.py:663` `_business_invoice_clave` | VERIFIED |
| `_source_resolver.py:109` `invoice_direction_to_source_kind` | VERIFIED |
| `_source_resolver.py:588-590` drop | VERIFIED |
| `_modelo_bindings.py:1005` M303 screen | VERIFIED |
| `_modelo_bindings.py:144` four-binding set | VERIFIED |
| `_modelo_bindings.py:1113-1123` ES filter | VERIFIED (`:1122`) |
| `_importing.py:57-58` retención TypedDict | VERIFIED |
| No M390 screen anywhere | VERIFIED |

**DRIFTED — `src/cadrumo/domain/invoices/_models.py`, uniformly ~+31 lines:**

| ADR cites | Actual at HEAD |
| --- | --- |
| `Invoice` at `:469` | `:500` |
| rich field set `:474-505` | ~`:505-536` |
| `InvoiceLine.category_id` `:397` | `:428` |
| `_require_lines` `:605-610` | `:660` |
| `derive_invoice_id` `:85-124` | `:92` |

Cause: 24 commits since the verification HEAD, `7502ee65ed` and `ef0438561d`
on this surface. Low consequence in itself — the symbols are all present and
the claims hold — but D-J and D-G both cite this file, and per
`aeat-swarm-orchestration` a citation must be re-read at HEAD before an edit
is made on it. **`_models.py` currently shows `MM` in `git status`** (staged
*and* unstaged peer edits), so the plan's own "`git diff` before a first edit"
instruction is live on the canonical invoice model right now.

*Measurement conflict, resolved:* a verification pass reported these five
`_models.py` citations as VERIFIED. They are not. Re-measured decisively
against both the working tree and `git show HEAD:` — which agree — `class
Invoice` is at `:500`, `category_id` at `:428`, `_require_lines` at `:660`. The
same pass also reported the file as clean when `git status` shows `MM`. The
table above is the corrected reading; where the two disagree, trust this one.

**Additional drifts confirmed by that pass and independently plausible:**
`_creation.py:284-287` → raise begins `:282`; `build_catalogue_invoice` def is
`:95` not `:113`, and the single-line mechanism is at `:154-161` / `:175`;
`_business_operation_invoice.py:294` is docstring prose, the disambiguation
loop is `:579-600`; `:267-298` truncates an id derivation that runs to `:318`;
`_service.py:100-118` → `:99-119`; `_iva_ledger.py:1518-1547` spans two
functions, `_invoice_kind_for` ending at `:1530`.

**The two exceptions — citations that are now FALSE, not drifted:** the
research's *"`create_catalogue_invoice` (`:217-236`) accepts no retención
parameter"* and ADR D-E's retención clause. Both are contradicted by the tree
at HEAD; see F6.

Minor correction to a claim, not a drift: D-J calls `category_id` an *"untyped
`str | None`"*. It is untyped as to taxonomy, but it does carry a validator
(`_models.py:458-465`) rejecting blank. The direction of D-J is right; the
characterisation is slightly overstated.

---

### Verdict: does the supersession argument hold?

**Yes. It holds on the merits, and it is argued rather than asserted.** I
checked the reversal independently rather than taking the ADR's word.

The prior ADR did not merely note the split in passing. It stated at
`:78-84` that *"Two invoice aggregates exist for good reason… Merging them is
out of scope and **rejected**"*, made *"Both aggregates survive"* a **Constraint**
(`:97-99`), and recorded the sharp edge *"so a future agent does not 'unify'
them by mistake"* (`:221-224`). That is about as strong a guard as an ADR can
place.

The new ADR clears it, for three reasons I confirmed myself:

1. **The premise is falsified in the code, not in argument.** The prior ADR's
   stated architecture was *"The unified command drives the **slim**… The
   **rich** `Invoice` remains the calculation aggregate"* (`:135-141`). Commit
   `432fc96d29` (2026-06-28, 18 days later) put the slim store into the
   calculation mesh. I verified the commit, its date, its subject, and the
   union at `_source_resolver.py:200-202`. The division of labour the prior
   decision rested on no longer exists.
2. **It distinguishes what the predecessor actually reasoned about.** The
   "by mistake" warning is attached to the `link` verb's id-space confusion.
   The new ADR says so explicitly — *"It reasoned about an id-space confusion
   at the `link` verb; it did not reason about two stores feeding one
   aggregation"* — rather than pretending the warning does not exist. That is
   the honest engagement the rule requires.
3. **The new consequences are real and verified.** The double-count is
   invisible on M349 (`_invoice_bindings.py:822-859` groups without an
   `invoice_id` in the key); the clave asymmetry is a genuine under-declaration
   I read at HEAD; and the two id spaces are disjoint by construction, so
   reconciliation is not merely absent but impossible.

**Two caveats, neither fatal:**

- The ADR quotes only the prior record's Implementation §"Model boundary". It
  does **not** engage the stronger Considerations statement (*"out of scope and
  **rejected**"*). The research **does** engage it, and offers the narrower
  reading — *rejected as out of scope for that campaign, not on the merits* —
  which I find defensible on the wording. But the ADR read alone represents its
  predecessor as softer than the predecessor is. A reader who never opens the
  2026-06-10 record would not know a Constraint was overturned.
- Per F8 the ADR is statusless. **The argument holds; the authority does not
  yet exist.**

**Should the prior decision stand? No.** Two stores feeding one aggregation
with disjoint id spaces and no reconciliation is a filing-correctness defect in
both directions on informativas that name third parties by NIF. The prior
decision was correct when made and is not correct now. The reversal is the
right call.

---

### Verdict: deletion safety

**Cannot be assessed — and that is itself the finding.**

Question 4 of the brief asks whether P01 genuinely proves canonical coverage
before P03 deletes, whether every slim-store consumer has a named replacement,
and whether each deletion Step carries a real verification gate.

- **P03 has no Steps.** There are no deletion Steps to carry gates.
- The *ordering discipline is right*: the plan makes "P01 before P03" its one
  hard constraint and names it "the plan's most important property", and
  P01.S03 (inventory every consumer, refuse to proceed while any lacks a
  replacement) is exactly the correct instrument. **A gate on an empty phase
  gates nothing.**
- The two gates that do exist are both defective: P01.S01 demands
  reproduction of the double-count (F3), and P01.S02 is already satisfied at
  HEAD (F4).
- T6 — dropping the slim store's physical lane partition — is an
  Open Question the ADR insists "must be a stated decision, not an oversight".
  It is a P03 decision, and there is no P03.
- The fold's feasibility rests on a superset claim that does not hold **in
  either direction** (F3). Four rich invariants have no slim counterpart, and
  three slim fields — including both audit timestamps — have no rich
  counterpart. Nothing in the plan decides how a non-conforming slim record is
  handled, or whether losing `created_at`/`updated_at` is accepted.
- **The fold crosses a storage scope boundary (F3b), and the ADR's only
  storage-safety constraint describes the wrong store.**
- A consumer inventory surfaced sites a symbol-name grep would miss, and which
  P01.S03 must therefore be written to catch: the error registry
  (`core/errors/registry/_domain_part1.py:539,550`), six `BucketEventType` plus
  two `BucketEventObjectType` members (`domain/buckets/_event.py:254-259`,
  `:318-319`), the custody-carry registration (`_custody_carry.py:78,322-327`),
  and the namespace registry itself. Locale deletion also needs care:
  `kind_help`, `operation_type_help` and `operation_date_help` are **shared**
  with the surviving catalogue verbs and must not be removed.

For scale: the slim-store blast radius is modest and tractable —
`BusinessOperationInvoice` appears in 9 production and 6 test files;
`BusinessOperationInvoiceRepository` 4/4; `PayableInvoiceService` 3/5;
`CollectibleInvoiceService` 3/2; `LEDGER_BUSINESS_OPERATION_INVOICE_NAMESPACE`
3/1. The `payable_invoice` / `collectible_invoice` source-kind strings live in
`BindingSourceKind` (`core/aggregation.py:326-327`) and are untouched by the
fold, exactly as the ADR states. **The deletion is doable. It is simply not
planned.**

---

### What would have to change

Ordered by consequence.

1. **Re-measure every Step against HEAD before executing any of them.** Three of
   seven are already satisfied or vacuous (P01.S02, P02.S04, and P02.S06 in
   part). The campaign was written against `0b1e3f040b` and committed into a
   tree that had already moved.
2. **Author Steps for P03, P04 and P05** through the plan verbs. Seven ADR
   decisions currently have no implementation path.
3. **Fix the P01.S01 gate and its Verification twin** to prove *declarable
   coverage* (D-C's wording), not output-equality with the two-store union.
4. **Correct the ADR's storage constraint** — it names the store being deleted,
   not the one being kept — and decide explicitly whether bucket-local records
   may move into a profile-local document with optional bucket attribution.
5. **Correct the superset Consideration** and record the input-contract
   narrowing it hides; decide in P03 what the fold does with a slim record that
   cannot satisfy the rich invariants.
6. **Give D-I a Step and a Verification criterion**, and answer LANES's open
   M390-reachability question before settling its priority. LANES ranks it
   first; the plan ranks it last and ungated.
7. **Decide the real D2** (the confirm-boundary override set) or move it to
   "Deliberately out of scope" with a reason — and stop labelling D-E as D2.
8. **Decide D4** (recargo on the draft) — action or explicit deferral.
9. **Name G4** (`source_jurisdiction` on no invoice model) somewhere: actioned,
   deferred, or explicitly out of scope. Silence is the one option the ADR's
   own section heading forbids.
10. **Extend P02.S07 to `_bulk_import.py`**, and record in D-G that the writer
   half alone ships no behaviour change.
11. **Carry the peer totals-identity constraint** (`grand_total == base_total +
   iva_total + recargo_amount`, amended 2026-08-06) into P02.S05/S07.
12. **Give the ADR a status**, add `supersedes:` frontmatter, add
   `2026-08-06-llm-package-split-adr` to `related:`, and add a Step marking
   `2026-06-10-ledger-invoice-unification-adr` superseded.
13. **Delete `_importing.py` rather than route it** — a routed bulk importer
    already exists in `_bulk_import.py`; name that module in the ADR.
14. **Re-read `_models.py` at HEAD** before any edit citing it; every citation
    to that file is ~31 lines stale and the file currently carries peer WIP
    (`MM` in `git status`).

---

### What I checked, so this audit is falsifiable

Read in full: both ADRs, the research, the plan, LANES.md. Direct source reads
at HEAD `daa9876ed3` of `_source_resolver.py` (lines 195-210, 436-465, 585-595,
663-690), `_modelo_bindings.py` symbol map, `_models.py` symbol map,
`_bulk_import.py` writer path, `_business_operation_invoice.py` field probe,
`_namespace_registry.py` scope definitions for both stores (`:520-528`,
`:906-915`), retention options across both entry verbs, `git log -S` and
`git show <rev>:` dating of the retención writer, and a field-by-field plus
validator-by-validator comparison of both models.
Tree-wide `rg` for `def _raise_if`, M390 references, slim-store symbol counts,
`source_jurisdiction`, `override set`, `recargo`, and every `Invoice`
construction site outside tests. `git log`/`git show` for `432fc96d29`,
`0b1e3f040b..HEAD` range and per-file recency. `vaultspec-core status` for plan
state. Status-marker sweep across all 24 `2026-08-*` ADRs.

**Instrument caveat, recorded because several findings above are absence
claims:** the code index reported itself shrunken, so every negative claim here
(no M390 screen, no `source_jurisdiction` on invoice models, no `iva_category`
on the slim record, no Steps in P03–P05, D2/D4/G4 absent from the campaign
documents) is backed by targeted `rg` at HEAD or by direct file read, never by
semantic recall alone.

**One instrument error made and corrected during this audit:** an early sweep
for `_importing.py` callers used `rg -rn`, where `-r` is `--replace` and
silently rewrote every match to the literal `n`. The corrupted output appeared
to show a CLI caller for `_importing.py`, which would have made D-H false. The
corrected run showed the CLI calls `import_invoices_from_rows` from
`_bulk_import.py`, a different module — **D-H's claim is correct.** Recorded
because the corrupted output was plausible enough to have been reported as a
finding.

**Supplementary verification passes.** Three sub-agents were dispatched (full
citation table, slim-store consumer inventory, INGEST.md enumeration). Their
work is folded in above where it survived checking. One pass reported five
`_models.py` citations VERIFIED and the file clean; both were wrong. A second
pass gave a wrong line for the rich totals validator (`:630`; it is `:683-694`).
Their substantive contributions — the missing rich timestamps, the storage-scope
difference, the error-registry and bucket-event consumers — were each
re-measured here before being used. The
corrected measurement (working tree and `git show HEAD:` in agreement, `git
status` showing `MM`) is what this report carries. Agent output was treated as
inventory to confirm, per `aeat-swarm-audit-cadence`, not as evidence.

**Retract — nothing.**

**Upgrade on evidence — G2.** It entered this audit marked "Actioned —
genuinely covered" on a reading of the campaign documents alone. Measuring at
HEAD showed it was misstated when written *and* already closed by the
campaign's own commit. This is the finding that most changed on contact with
the tree, and the reason the register's other "genuinely covered" marks should
be read as *checked at HEAD* rather than *taken from the plan*.

## Recommendations

Every numbered item in the review's own closing list, plus the disposition register, was
carried into the rewritten ADR and plan. The dispositions are recorded in the ADR's
decisions and in the plan's per-Step verification criteria rather than restated here, so
there is one home per fact.

Three of the review's conclusions were **corrected on re-measurement** and the corrections
are the authoritative reading:

- The two Steps the review judged already-satisfied were confirmed, and one further Step
  was found already-landed. They were rewritten rather than dropped, each now carrying a
  proof that is red at HEAD.
- The review's scope caveat about the unenumerated half of the source findings stands. That
  half was enumerated during the rewrite and produced two decisions the campaign had lost
  to silence: the confirm-boundary override set, and recargo on the extraction draft.
- A later directive relayed a claim that the canonical invoice catalogue is excluded from
  profile export or import. That claim is **refuted at HEAD**: the namespace declares
  structured custody with a default object key, single-document stores resolve through a
  fixed key, an unresolvable namespace raises rather than dropping silently, and the custody
  store matrix already seeds and verifies the canonical catalogue. The real defect there is
  weaker and different: the custody verification asserts only that the reloaded catalogue is
  non-empty, which passes even when the boundary drops a field and reloads its default.
