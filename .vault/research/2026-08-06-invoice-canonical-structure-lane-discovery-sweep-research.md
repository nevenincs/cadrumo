---
tags:
  - '#research'
  - '#invoice-canonical-structure'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:500a288ec8bea7d0aa0ac93481cace5b76f85388f1d233123206aacc36ea662d'
related:
  - "[[2026-08-06-invoice-canonical-structure-adr]]"
  - "[[2026-08-06-invoice-canonical-structure-audit]]"
---
# `invoice-canonical-structure` research: `Source discovery sweep: tangles, gaps and the joint scope`

The discovery sweep that opened this campaign. It is the origin of the six tangles, the six
gaps, and the four-item joint scope that the ADR's decisions and the plan's Steps are
dispositioned against, so it is landed here rather than left in a scratch directory outside
the repository where a receiving team would never find it.

## Findings

**Read this with three corrections applied.** They were established after the sweep was
written and they change what parts of it mean. The sweep is preserved as written, because
rewriting it would destroy the record of what was believed when the campaign's decisions were
taken, but where it and the corrections disagree, the corrections govern.

1. **T1's claim that the slim record reaches nothing is refuted.** Both stores are live at the
   calculation boundary: the invoice source resolver loads the canonical catalogue and the
   slim store and unions their observations. That union is the double-count, and it is the
   reason the campaign exists. Do not carry the dormancy reading forward.
2. **G2 was understated when written and has since been closed outright.** It cited the
   retencion write route as the bulk importer, naming the wrong module: the module it cites
   is dead with no production callers, and the live CSV and XLSX importer had no retencion
   support at all. So at the time of writing the cited route was dead and the live one could
   not write the field. Retencion then landed on both entry verbs in `ef0438561d` - the same
   commit that landed this campaign's documents. Only the encrypted-roundtrip proof remains.
3. **G1's open question is still open and is now a Step.** The sweep asked whether an
   invoice-only bucket can reach a filed Modelo 390 through the screen gap, and said that if
   it can, it outranks everything else here. That question is unanswered; the plan makes
   answering it the first Step of its screen phase, and a negative answer legitimately
   re-scopes the rest of that phase rather than embarrassing it.

Two findings the sweep raised were lost to silence in the campaign's first pass and have
since been dispositioned: the jurisdiction axis, absent from both invoice models, is now a
reasoned deferral; and the recargo loss on the extraction draft is now a decision. The
confirm-boundary override set - the item both source agents agreed should ship first - was
mislabelled as delivered by an unrelated decision and is now decided on its own terms.

The sweep as written follows, with its headings demoted one level to nest here.

Discovery pass, read-only. Repo `Y:\code\aeat-worktrees\main`, HEAD `0b1e3f040b`
("feat(aggregation): attribute an invoice to the period it devengo'd in").
All `path:line` citations verified at that HEAD. No files modified.

Method: `vaultspec-rag` semantic sweeps over code and the ADR corpus, each paired
with a targeted `rg` confirming the declaration and call sites. Two parallel
sub-agents covered issuer-status enforcement and the territory/retención axes.

**Verification status: every `path:line` in this document was read at HEAD
`0b1e3f040b`. There are no unverified findings and none carried over from a
brief or a peer report without independent confirmation** — including the two
cross-agent items (G3b, contributed by the INGEST agent, and the `InvoiceDraft`
field list quoted in Lane 1), both of which were re-read here before being
written down. Nothing in this document rests on reasoning alone.

### Executive summary

The operator's three-lane model maps onto **five** code entities, not three. The
extra two are the reason the discussion keeps tangling:

| Operator lane | Code entities | Store |
| --- | --- | --- |
| 1. Purchase invoice (deductible evidence) | `PurchaseInvoiceEvidence` (the document) **+** `Transaction` (the categorised expense row) | two separate encrypted namespaces, joined by `Transaction.purchase_invoice_evidence_id` |
| 2. Operational catalogue — issued | slim `BusinessOperationInvoice` (source_kind `collectible_invoice`) **and** rich `Invoice` (`kind=ISSUED`) | two separate stores, no conversion path |
| 3. Operational catalogue — received | slim `BusinessOperationInvoice` (source_kind `payable_invoice`) **and** rich `Invoice` (`kind=RECEIVED`) | same two stores |

The **slim/rich duplication is a known, ADR-documented sharp edge**
(`.vault/adr/2026-06-10-ledger-invoice-unification-adr.md:221-224`: "`--invoice-id`
on `link` and `invoice_id` on the unified CRUD address two different stores (rich
vs slim). The ADR fixes this explicitly so a future agent does not 'unify' them
by mistake."). It is nevertheless the largest live tangle, because the two stores
now sit under **one operator noun** (`aeat app ledger invoice` vs
`aeat app ledger invoice catalogue`) with near-identical option sets and wildly
different downstream reach.

The operator's claim that the issued lane is "stringently mandated by issuer
status" is **half-confirmed**: the `ISSUED`/`RECEIVED` axis is enforced hard at
five sites (below), but there is no "issuer status" entity as such — the axis is
`InvoiceKind`, and the one genuine RD 1619/2012 issuance-obligation predicate is
declared **advisory, not a refusal**.

---

### LANE 1 — Purchase invoice: deductible expense evidence

#### Entities

- **`PurchaseInvoiceEvidence`** — `src/cadrumo/application/ledger/_evidence.py:123`.
  Fields: `evidence_id`, `bucket_id`, `source_path`, `attachment_id` (64-hex,
  content-addressed), `media_kind`, `supplier`, `invoice_number`, `invoice_date`,
  `taxable_base`, `iva_rate`, `iva_amount`, `notes`, timestamps
  (`_evidence.py:128-147`). Patch model at `:216`.
- **`InvoiceDraft`** — `src/cadrumo/application/ledger/_evidence_draft.py:194`,
  fields `:231-239`. The extraction output: `supplier_tax_id`, `invoice_number`,
  `invoice_date`, `taxable_base`, `iva_rate`, `iva_amount`, `grand_total`,
  `currency`, `raw_text_length`.
- **`Transaction`** — `src/cadrumo/domain/transactions/_models.py:600`. This is
  where the *deductibility* actually lives: `business_classification`,
  `category` (`SpendingCategory`), `iva_category` (`:792`), `exemption_article`
  (`:793`), `counterparty_eu_member_state` (`:794`), `source_jurisdiction`
  (`:808`, required), `recargo_amount` (`:768`),
  `purchase_invoice_evidence_id` (the join key).

#### Categorization taxonomy (the LLM allow-list)

- `SpendingCategory` — `src/cadrumo/domain/categories/_spending_category.py:15`,
  **42 members** (`:23-64`), grouped by `SpendingCategoryFamily` (`:67`, 14
  families).
- Deductibility rule per category:
  `src/cadrumo/domain/categories/_proportionality.py:170-176` —
  `FULL_DEDUCTIBLE`, `FIXED_PERCENTAGE`, `USAGE_RATIO_PERSONAL`,
  `USAGE_RATIO_HOME_AREA`, `STATUTORY_CAP`, `NON_DEDUCTIBLE`,
  `REQUIRES_EXCLUSIVE_USE`; grounding provenance enum at `:82-86`.
- LLM containment: the classifier's allow-list guard lives in the engine
  (`src/cadrumo/domain/transactions/_llm.py:307` `allowed_classifications`), so an
  out-of-allow-list value never reaches the application layer
  (`src/cadrumo/application/ledger/_llm_classification.py:24-27`).
- Staging is explicit
  (`_llm_classification.py:29-39`): **stage 1** persists only
  `business_classification` + `category`; **stage 2 saturation** additionally
  persists model-selected `iva_category` and *system-derived* `taxable_base` /
  `iva_rate` / `iva_amount` — "the model still never emits a number";
  `irpf_category` remains operator-only.

**This taxonomy is consumed by LANE 1 only.** Neither the slim nor the rich
invoice record carries a `SpendingCategory`. The rich `InvoiceLine` has a free
`category_id: str | None` (`src/cadrumo/domain/invoices/_models.py:397`) which is
*not* typed to `SpendingCategory`.

#### CLI surface

`aeat app ledger evidence {add|remove|update|view|list}` —
`src/cadrumo/entrypoints/cli/_ledger_evidence_cli.py`. Plus the confirm bridge
into Lane 2/3 (below).

#### Territory / regime / retención

**None. The evidence lane is entirely regime-blind and retención-blind.**
`PurchaseInvoiceEvidence` and `InvoiceDraft` both carry zero territory fields,
zero `iva_category`, zero `recargo_amount`, zero retención. The first territory
fact appears at the confirmation boundary as a *defaulted parameter*:
`confirm_invoice_draft_from_evidence(..., counterparty_country: str = "ES", ...)`
— `_evidence_draft.py:706`.

`InvoiceDraft`'s inability to carry recargo is **documented in-code as a known
hole**: `_evidence_draft.py:488-508` records that a printed
`base + cuota + recargo` invoice has "nowhere to go".

#### Downstream modelo consumers

- M100 / M130 gastos: `src/cadrumo/application/aggregation/_renta_ledger.py`
  (`ledger_renta_gastos_estimacion_directa_aggregation`,
  `ledger_renta_gastos_pago_fraccionado_aggregation`). Evidence is consumed as a
  *linkage gate*, with typed refusals at `_renta_ledger.py:127-131`.
- M303 soportado: via the `Transaction` row through `ledger_iva_aggregation`
  (`src/cadrumo/application/aggregation/_iva_ledger.py`).
- Deduction-grade evidence advisory:
  `src/cadrumo/application/aggregation/_evidence_advisory.py:85`
  `_row_has_deduction_grade_evidence` (LIVA art. 97 enumerative).

---

### LANE 2/3 — Operational invoice catalogue (issued / received)

These two lanes share every entity and are separated only by an enum member, so
they are documented together with the per-kind divergences called out.

#### The direction axis

- `InvoiceKind(StrEnum)` — `src/cadrumo/domain/iva/_classification.py:102`,
  `ISSUED = "issued"` (`:118`) / `RECEIVED = "received"` (`:119`).
- `BusinessOperationInvoiceDirection(StrEnum)` —
  `src/cadrumo/application/ledger/_business_operation_invoice.py:67`,
  `PAYABLE_INVOICE` (`:76`) / `COLLECTIBLE_INVOICE` (`:77`).
- Single contractual bridge:
  `invoice_direction_to_source_kind(kind) -> BusinessOperationInvoiceDirection`
  — `src/cadrumo/application/invoices/_source_resolver.py:109-122`. Totality is
  locked by an anti-collapse test:
  `src/cadrumo/application/invoices/tests/test_source_resolver.py:50-53`
  ("must resolve every InvoiceKind member to a distinct source kind, never
  collapse the two directions onto one").

#### Entity A — the SLIM record (operator CRUD)

`BusinessOperationInvoice` —
`src/cadrumo/application/ledger/_business_operation_invoice.py:154`, fields
`:171-196`: `invoice_id`, `source_kind`, `bucket_id`, `counterparty_nif`,
`counterparty_name`, `invoice_number`, `invoice_date`, `currency`,
`taxable_base`, `iva_rate`, `iva_amount`, `total_amount`, `fx_rate`,
`fx_rate_date`, `notes`, `country_code`, `eu_iva_id`, `operation_type`,
timestamps.

**Has NO:** `iva_category`, retención, `recargo_amount`, `suplido_amount`,
`lines`, `linked_transaction_ids`, `payment_status`, `invoice_class`,
`operation_date`.

Store: two physically distinct documents keyed by lane —
`BusinessOperationInvoiceRepository.extract_identifier` returns
`_document_key(payload.bucket_id, payload.source_kind)` (`:390-391`). Every CRUD
op is bound to one lane by a class attribute (`PayableInvoiceService.source_kind`
`:714`, `CollectibleInvoiceService.source_kind` `:720`), so there is no cross-lane
read path at all. `source_kind` is immutable and folded into the identity hash
(`:301`, patch docstring `:325-326`).

CLI: `aeat app ledger invoice {add|view|list|update|remove}` —
`src/cadrumo/entrypoints/cli/_ledger_business_invoice_cli.py:180-415, 958`.

#### Entity B — the RICH record (calculation / reconciliation authority)

`Invoice` — `src/cadrumo/domain/invoices/_models.py:469`, fields `:474-505`.
Carries everything the slim record lacks: `invoice_class`, `series`,
`operation_date` + `operation_date_role`, `counterparty_country`, `lines`
(`InvoiceLine`, `:386`), `payment_status`, `linked_transaction_ids`,
`iva_category` (`:494`), `operation_type` (`:495`), `oss_ioss_regime` (`:496`),
`oss_transaction_kind` (`:497`), **`retention_rate` (`:498`) /
`retention_amount` (`:499`)**, `recargo_amount` (`:500`), `suplido_amount`
(`:501`), `rectifies_invoice_number` (`:502`), `payment_id`, `fx_rate`,
`fx_rate_date`.

Identity: `derive_invoice_id` folds `kind` into the content hash
(`_models.py:115-124`), so the same document number in the other direction is a
different invoice.

Container: `InvoiceCatalogue` (`:1002`) — a **single mixed-kind store**;
`list_invoices(..., kind=None)` treats kind as an optional filter
(`src/cadrumo/domain/invoices/_service.py:100-118`). Lane separation here is
enforced *at the consumers*, not at the container.

CLI: `aeat app ledger invoice catalogue {create|wizard|import|list|view|remove}`
— `_ledger_business_invoice_cli.py:555-957`, mounted as a sub-typer of the same
`invoice` app (`:86-87`).

#### Issuer status — verified

There is **no `IssuerStatus` entity**. The one place RD 1619/2012's
"obligado a la expedición de la factura" is modelled:
`src/cadrumo/application/invoices/_issuer_establishment.py` (norm quoted `:6-8`).

- `issuer_established_in_tai(profile) -> bool` (`:86`), implemented at `:103` as
  `profile.fiscal_residency is not FiscalResidency.NON_RESIDENT_IRNR` — an
  approximation off the IRPF residency axis, deliberately over-strict (`:43-66`),
  with the Canarias / Ceuta-Melilla limitation pinned by test
  (`tests/test_issuer_establishment.py:160`).
- `simplificada_requires_tax_id_for_domestic_issuer(invoice, profile)` (`:106`),
  first guard `if invoice.kind is not InvoiceKind.ISSUED: return False` (`:150-158`).
- **Weight: advisory.** `:133-140` — "This is an ADVISORY-weight fact, not a
  construction-time or verify-time refusal … Callers should surface a positive
  result as a `Notice`, never as a hard refusal."

Where the `ISSUED`/`RECEIVED` lane **is** hard-enforced:

1. `Invoice._validate_class_consistency` — `_models.py:856-861`. The simplificada
   tax-id relief is ISSUED-only; on RECEIVED the counterparty tax id "names the
   issuer's own identity, which stays mandatory". Rationale `:819-828`.
2. OSS/IOSS projection is ISSUED-only — `_models.py:934-935`.
3. Evidence-reference classifier — `src/cadrumo/application/ledger/_evidence_reference.py:175-180`,
   `EvidenceReferenceOutcome.INVOICE_WRONG_KIND` (`:77`), excluded from
   `ACCEPTABLE_EVIDENCE_REFERENCE_OUTCOMES` (`:81`). An ISSUED invoice cannot
   stand as purchase evidence.
4. The write gate over it —
   `src/cadrumo/application/ledger/_actions_common.py:477-527`, terminal refusal
   at `:521-527`.
5. Aggregation refusals (soft — row withheld, not raised):
   `_renta_ledger.py:742-749` (`UNSUPPORTED_PURCHASE_INVOICE_EVIDENCE_KIND`),
   `_renta_income_ledger.py:697-698` (`SalesInvoiceEvidenceRefusal.UNSUPPORTED_KIND`),
   `_oss_ioss.py:325`.

Locking tests: `application/ledger/tests/test_evidence_reference.py:165`;
`domain/invoices/tests/test_invoice_simplificada.py:148, :168`;
`application/invoices/tests/test_source_resolver.py:39, :45, :50`;
`application/invoices/tests/test_issuer_establishment.py:125, :133, :160`.

**Verdict on the operator's claim:** the *direction* axis is stringently mandated
— structurally in the slim store (two files, immutable lane, lane in the id hash)
and by construction-time refusal + five consumer gates in the rich store. The
*issuer-obligation* fact is modelled once, approximated off residency, and is
advisory only.

#### Territory / regime

Modelled almost entirely as **`IvaCategory` membership**, not as flags.

- `IvaCategory` — `src/cadrumo/domain/iva/_schema.py:40`, 20 members `:49-88`,
  covering domestic tiers, `DOMESTIC_REVERSE_CHARGE`, four intracomunitario
  members (goods supply / acquisition-ISP / triangulation) plus two service
  members (`INTRA_COMMUNITY_SERVICE_SUPPLY` `:59`,
  `INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE` `:71`), exports/imports
  `:81-83`, `RECARGO_EQUIVALENCIA` `:84`, `REGIMEN_SIMPLIFICADO` `:85`,
  `OPERACION_NO_SUJETA` `:86`.
- Reverse charge: no boolean. `_REVERSE_CHARGE_CATEGORIES` frozenset —
  `src/cadrumo/domain/iva/_flow.py:121`; direction derived once by
  `derive_flow_for_classification` (`_flow.py:133`) into `IvaFlowDirection`
  (`:95`, includes `INVERSION_SUJETO_PASIVO`).
- Intracomunitario also carries `IntracomOperationType` (the M349 clave axis) on
  the rich `Invoice` (`_models.py:495`) and `EUMemberState`
  (`_schema.py:257-284`, 27 states + `XI`).
- Recargo de equivalencia is represented on **two axes**: the regime tag
  `IvaCategory.RECARGO_EQUIVALENCIA` and a separate money field
  `recargo_amount` (rich `Invoice:500`, `Transaction:768`).
- `source_jurisdiction` is a **different axis** — IRPF/IRNR source country, not
  IVA territory. `Transaction:808` (required), `LedgerEvidenceRow:165`, the
  manual-ledger models; resolution/enforcement at
  `src/cadrumo/entrypoints/cli/_ledger_support.py:260-272` (mandatory for IRNR and
  for the art. 93 impatriado regime). **It does not exist on any invoice model.**

#### Retención IRPF

Fully modelled — on the **rich `Invoice` only** (`retention_rate` `:498`,
`retention_amount` `:499`), with real invariants at `_models.py:667-722`:
retención is held *outside* the totals, non-negative, and a rate alone is
rejected ("a rate alone declares no withheld figure", `:709`). Base is the base
imponible, never the grand total (test `domain/invoices/tests/test_retencion_consistency.py:143`).

Routing (`src/cadrumo/application/aggregation/_invoice_retencion.py`, module
docstring `:1-46` is the authoritative explanation):

- ISSUED → the taxpayer is *retenido*, the amount is a **credit** against the
  pago fraccionado (RIRPF art. 110.3.a), reaching M130/M100 through the renta
  income ledger.
- RECEIVED → the taxpayer is the obligated *retenedor*, a **liability** →
  `project_received_invoice_retencion` (`:228`) emits a `RetencionObservation`
  with `source_kind=BindingSourceKind.PAYABLE_INVOICE` (`:262`) into the one
  per-perceptor store, read by `RetencionesAggregationSourceResolver`
  (`_modelo_bindings.py:1259`) → M111 / M115 / M123 / M180 / M190
  (`_retenciones.py:245-307`; M190 reuses M111's scheme frozenset, `:178, :182`).
- **The scheme is never inferred** (`_invoice_retencion.py:21-27`): the operator
  declares `(invoice, scheme)` pairs via `--received-invoice-retencion`; guessing
  would file a figure under a clave the taxpayer never asserted.

#### Downstream modelo consumers per lane

| Consumer | Reads | Source kind |
| --- | --- | --- |
| **M349** recapitulativa | rich `Invoice` | `payable_invoice` / `collectible_invoice` (only registry bindings for these kinds — `_data/registry/aeat/modelos/349/revisions/2020-y-siguientes/bindings/0008-payable-bindings.toml`) |
| **M347** | rich `Invoice` | same pair |
| **M111/115/123/180/190** | rich `Invoice.retention_*` → per-perceptor store | `retenciones_aggregation` |
| **M369** OSS/IOSS | rich `Invoice` (ISSUED only) | `ledger_oss_aggregation` (`_oss_ioss.py:325`) |
| **M130/M100** income | `Transaction`, with rich `Invoice` as *evidence* | `ledger_renta_income_aggregation` (`_renta_income_ledger.py`) |
| **M130/M100** gastos | `Transaction` + `PurchaseInvoiceEvidence` | `ledger_renta_gastos_*` |
| **M303 / M390** IVA | **`Transaction` ONLY** | `ledger_iva_aggregation` (`_iva_ledger.py`) |
| **M151** impatriado | `Transaction` (`source_jurisdiction` scoped to ES) | `ledger_impatriado_income_aggregation` |

---

Ranked by consequence. T1–T2 can change a filed number; T3–T6 are structural /
ergonomic.

#### T1 — One operator noun, two stores with wildly different downstream reach

`aeat app ledger invoice add` writes the **slim** record; `aeat app ledger invoice
catalogue create` writes the **rich** one
(`_ledger_business_invoice_cli.py:86-87` mounts `catalogue_app` *inside*
`invoice_app`). Their option sets overlap almost completely
(`--kind --counterparty-nif --counterparty-name --invoice-number --invoice-date
--taxable-base --iva-rate --currency --notes`), so the two verbs read as
synonyms. They are not:

> **CORRECTED 2026-08-06, and the correction makes this worse, not better.**
> This entry originally asserted "the slim record reaches nothing. No registry
> binding family consumes it." **That was false.** `InvoiceCatalogueSourceResolver`
> reads **both** stores and **unions** their observations —
> `application/invoices/_source_resolver.py:180-202`, slim loader at `:552-570`,
> slim→observation adapter at `:579-610`. The module docstring says so plainly
> (`:6-8`, "and also adapts slim `BusinessOperationInvoice` records"). The
> original claim was reasoned from the registry TOML (which names only the
> source-kind strings) without tracing the resolver that produces them — the
> exact failure mode of concluding absence from a partial sweep. What follows is
> the corrected reading.

- **Both** stores reach M347 and M349, through one resolver that unions them
  (`_source_resolver.py:200-202`).
- The rich record additionally reaches M369, the retención store (M111/M190) and
  the renta income evidence gate. The slim record reaches none of those — it has
  no retención, no lines, and no `linked_transaction_ids` to reach them with.
- The two identity spaces are disjoint by construction:
  `derive_invoice_id` hashes `(kind, invoice_number, issued_at,
  counterparty_tax_id, currency, grand_total)`
  (`domain/invoices/_models.py:85-124`); `derive_business_operation_invoice_id`
  hashes a different tuple including `source_kind`
  (`application/ledger/_business_operation_invoice.py:~269-301`). **No id
  correspondence exists, so no id-based dedup is even possible.**

So the operator-facing hazard is *two-sided*, and the second side is worse:

1. **Under-declaration** — an operator using only `invoice add` gets no M369, no
   retención observation, and no reconciliation linkage, with no advisory.
2. **Over-declaration** — an operator who records the same invoice in *both*
   stores (entirely reachable: the two verbs sit under one noun with
   near-identical options, and an operator who discovers `invoice add` cannot
   link will plausibly re-enter via `catalogue create`) has it counted **twice**
   in M347 and M349. `_load_business_operation_invoices` performs no dedup; its
   `rich_invoice_repository` parameter is consulted only as a
   storage-degradation fallback (`:567-570`).

The prior ADR (`2026-06-10-ledger-invoice-unification-adr.md:221-224`) documents
the two-store split as a deliberate sharp edge, but documents it at the `link`
verb — an id-space confusion — not at the CRUD verbs, and not as a double-count.
Its premise ("the rich `Invoice` remains the calculation aggregate … the slim is
the operator-CRUD record", `:135-141`) was **falsified 18 days later** by commit
`432fc96d29` (2026-06-28, "fix(modelo): feed m349 from business invoices"), which
put the slim store into the calculation mesh.

*Consequence: M347/M349 can be under-declared OR over-declared depending on
operator behaviour, with no guard in either direction. Over-declaration is the
more dangerous of the two because it produces a valid-looking filing and, per the
standing observation that every gate here watches one direction of error, nothing
in this codebase is watching that one.*

**Double-count status: under adversarial verification by a dedicated agent at
time of writing.** Treat as high-confidence-unconfirmed until that returns.

#### T2 — Lane is decided by bank-money direction, not by user intent

`src/cadrumo/application/aggregation/_iva_ledger.py:1518-1547`:
`_invoice_kind_for(direction: TransactionDirection)` maps `INCOMING → ISSUED`,
`OUTGOING → RECEIVED`, and `_iva_ledger.py:1230-1234` asserts it is non-`None`
before deriving `IvaFlowDirection` (repercutido vs soportado). The entire M303
repercutido/soportado split is therefore a function of **which way the money
moved in the bank**, not of what the taxpayer says the document is.

This is coherent for a paid domestic invoice and wrong for: a refund/abono, a
rectificativa, a reverse-charge acquisition where no money moves in the IVA
direction, and a netted settlement.

*Consequence: a mis-signed or mis-directed bank row silently flips a cuota
between repercutido and soportado — a two-sided error on the same filing.*

#### T3 — Purchase evidence can be confirmed as an ISSUED invoice

`confirm_invoice_draft_from_evidence(..., kind: InvoiceKind, ...)` —
`_evidence_draft.py:702-718`. The docstring is honest about why (`:741-742`:
"extraction cannot infer this; the operator must state it"), but the function
lives in the *purchase-evidence* lane and mints a record in the *catalogue* lane
in either direction. The reverse gate exists and is hard
(`_evidence_reference.py:175-180` refuses an ISSUED catalogue invoice as purchase
evidence) — the forward direction has no equivalent check that the document being
confirmed as ISSUED was ever plausibly issued by this taxpayer.

*Consequence: a supplier's invoice confirmed with `--kind issued` becomes
declared income and an M347/M349 collectible entry.*

#### T4 — `IvaCategory` on a catalogue invoice is derivable ONLY from `--operation-type`

`_ledger_business_invoice_cli.py:125-145`: `_OPERATION_TYPE_TO_IVA_CATEGORY` maps
the five intracom `IntracomOperationType` members to categories, and
`_catalogue_iva_category_for_operation_type` returns `None` for anything else.
`catalogue create` (`:562-576`) and `catalogue wizard` (`:638-651`) expose **no
`--iva-category` option at all**.

So via the CLI a catalogue invoice can *never* be stamped
`DOMESTIC_REVERSE_CHARGE`, `EXPORT_THIRD_COUNTRY_ZERO_RATED`,
`RECARGO_EQUIVALENCIA`, `DOMESTIC_EXEMPT`, or `IMPORT_THIRD_COUNTRY`. The field
exists on the model (`_models.py:494`) and is reachable only through
`import_invoices_from_rows`. The in-code comment at `:129-134` shows this hole was
already found and closed *once*, for the S/I service claves — "Before these
existed the operator could pick S or I and the record came back with NO category
at all, so an ordinary intracomunitaria de servicios was ungrounded to every
consumer that reads the IVA treatment." The same shape remains for every
non-intracom regime.

#### T5 — Two "invoice line/category" concepts that are not the same taxonomy

`InvoiceLine.category_id: str | None` (`domain/invoices/_models.py:397`) is an
untyped string. The real categorization taxonomy is `SpendingCategory`
(`domain/categories/_spending_category.py:15`, 42 typed members) and lives on
`Transaction`. Nothing binds them. A reader seeing "category" on an invoice line
will reasonably assume it is the deduction taxonomy; it is not.

#### T6 — The rich catalogue is one mixed-kind container; lane separation is
per-consumer

The slim store is physically partitioned by lane (`_business_operation_invoice.py:390-391`).
The rich `InvoiceCatalogue` is not (`_service.py:100-118`, `kind` is an optional
filter). Every rich-lane guarantee therefore rests on each consumer remembering
its own `if invoice.kind is not …` check — five such checks exist today
(`_models.py:856`, `:934`, `_evidence_reference.py:175`, `_renta_ledger.py:742`,
`_renta_income_ledger.py:697`, `_oss_ioss.py:325`). A sixth consumer that forgets
one gets no structural help.

---

Ranked by consequence. G1 is the only one that can currently change a filed
number without an operator error; G2–G3 block correct filing outright.

#### G1 — Catalogue invoice IVA is not an M303 filing source; the guard is
one-directional and country-scoped

`src/cadrumo/application/aggregation/_modelo_bindings.py:1005-1069`
(`_raise_if_m303_invoice_domestic_iva_would_be_silent`) states it plainly in its
own docstring (`:1013-1022`): *"there is no domestic-IVA invoice binding family
for M303 … the transaction ledger is the filing authority."*

**This is well-handled at the centre.** Rather than under-declaring, the code
refuses with an instructive `AggregationValidationError`
(`:1051-1069`, suggestion: "Link and classify the domestic IVA invoices into the
transaction ledger before calculating Modelo 303; invoice-only IVA evidence is
not a Modelo 303 filing source"). Credit where due.

But the screen's reach is narrower than the hole:

- **Country-scoped.** `_m303_standard_domestic_invoice_in_period`
  (`:1113-1123`) requires `invoice.counterparty_country.strip().upper() == "ES"`.
  An intracomunitaria, an import, or an export invoice sitting in the catalogue
  with no matching transaction is **not compared at all**.
- **Binding-scoped.** `_M303_STANDARD_DOMESTIC_IVA_CUOTA_BINDINGS` (`:144-149`)
  covers four cuota bindings: repercutido general/reducido/super-reducido and
  soportado interiores. **Recargo cuota bindings and every base binding are not
  screened.** A catalogue invoice carrying `recargo_amount` therefore contributes
  nothing to M303 casillas 18/21/24 and trips no guard — directly the failure
  shape `iva-cuota-devengada-includes-recargo-equivalencia` exists to prevent.
- **M303 only.** `:1029` early-returns for any other modelo. There is no
  equivalent screen on **M390** (the annual, which the
  `modelo-390-cuota-devengada-total-equals-reconciliacion-303` blocking rule
  reconciles against the summed quarters).

*Consequence: an invoice-only bucket filing M390, or an M303 with recargo or
non-ES counterparties, can under-declare without any refusal.* This is the
highest-consequence finding in the sweep.

#### G2 — No CLI route to record retención on a single invoice

`create_catalogue_invoice` — `src/cadrumo/application/invoices/_creation.py:217-236`
— has **no retention parameter**. Neither does `build_catalogue_invoice` as
called at `:246-262`. `catalogue create` (`:562`) and `catalogue wizard` (`:638`)
expose no `--retention-rate` / `--retention-amount`.

The only write route to `Invoice.retention_rate` / `retention_amount` is the bulk
CSV/XLSX importer, whose TypedDict declares them `NotRequired`
(`src/cadrumo/application/invoices/_importing.py:57-58`).

So a taxpayer who issues one invoice to a Spanish company with a 15% IRPF
retención, or receives one from a professional, **cannot record it through
single-invoice entry**. Downstream that means: no M111/M190 liability
observation (the `_invoice_retencion.py` path has nothing to project), and no
M130 credit unless the renta income ledger's *inference* path
(`_renta_income_ledger.py:792-839`, declared gross minus cash received, capped at
RIRPF art. 95.1) happens to fire.

*Consequence: the M111/M190 lane is unreachable from the primary operator verb.
This is the strongest counter-evidence to "the issued lane is robustly
implemented" — the model and the aggregation are excellent, and the front door is
missing.*

Note the coordinator's observation about `InvoiceDraft` having no retención field
is **correct-by-design for that lane**: `InvoiceDraft` is OCR/extraction output
for *purchase* documents, and the confirm boundary
(`_evidence_draft.py:702-718`) likewise takes no retention override. The real gap
is one layer up, at `create_catalogue_invoice`, and it affects **both** catalogue
lanes.

#### G3 — `catalogue create` cannot express most regimes

Consequence of T4, restated as a capability gap. Via the CLI the rich invoice
cannot be stamped with: `DOMESTIC_REVERSE_CHARGE`, `RECARGO_EQUIVALENCIA`
(category *or* `recargo_amount` — there is no `--recargo` option),
`EXPORT_*_ZERO_RATED`, `IMPORT_THIRD_COUNTRY`, `DOMESTIC_EXEMPT`,
`OPERACION_NO_SUJETA`, `suplido_amount`, `invoice_class` (so no
rectificativa/simplificada), `series`, or `payment_status`. All of these fields
exist on the model.

`catalogue wizard` is strictly weaker still than `catalogue create` — it does not
even accept `--operation-date` (compare `:562-575` with `:638-650`), so an
invoice entered through the "guided" path can only ever reach the *proxy* devengo
rank that HEAD `0b1e3f040b` was written to distinguish from a declared one.

#### G3b — Mixed-rate invoices collapse at BOTH ends; only the writer needs to change

Raised by the INGEST agent during cross-verification and confirmed here at HEAD,
with one correction to the framing.

`build_catalogue_invoice` — `src/cadrumo/application/invoices/_creation.py:113-137`
— docstring `:116-119`: *"A single line item is synthesised from `taxable_base`
and the resolved IVA rate slot; the invoice totals are derived from that line so
the `Invoice` arithmetic invariants hold."* It resolves exactly one
`_resolve_iva_rate_slot(iva_rate)` (`:133`) and fabricates one line
unconditionally. Every CLI entry verb (`catalogue create`, `catalogue wizard`)
and the evidence-confirm bridge route through it, so **no operator path can
produce a two-line invoice today.**

**Correction to the framing:** the *model* is not the constraint.
`Invoice._require_lines` (`src/cadrumo/domain/invoices/_models.py:605-610`)
raises only on an *empty* tuple — "invoice must carry at least one line". It
imposes no upper bound, and the M303 comparison screen already iterates
`invoice.lines` per line (`application/aggregation/_modelo_bindings.py:1093-1105`),
so the read side is multi-line-ready. This matters for fix scope: mixed-rate is a
**writer-side** gap plus a reader-side one, not a three-way change. The store can
already hold it.

So a 21% + 10% document — ordinary, not exotic — is collapsed twice: once by the
reader's single scalar `iva_rate`/`iva_amount` (`_evidence_draft.py:235-236`,
INGEST's finding) and once by the writer's single synthesised line. Closing
either alone changes nothing.

*Detection, not prevention:* the derived-vs-printed total diverges, so
`PrintedTotalDiscrepancy` (`_evidence_draft.py:471-510`, surfaced on
`InvoiceConfirmationResult.total_discrepancy` at `:572`) raises an advisory. That
is a detector on the evidence-confirm path only — `catalogue create` and
`catalogue wizard` have no printed total to compare against, so a hand-entered
mixed-rate invoice collapses with no signal at all.

*Consequence: the base is right and the cuota is wrong whenever the two rates
carry materially different weights, in whichever direction the single resolved
slot errs. On the repercutido side that under-declares.*

#### G4 — `source_jurisdiction` does not exist on any invoice model

`Transaction.source_jurisdiction` is **required** (`_models.py:808`) and is
mandatory for IRNR and impatriado profiles
(`_ledger_support.py:260-272`, art. 93 LIRPF). Neither the slim nor the rich
invoice carries it. For a non-resident or Beckham-regime taxpayer, invoice-lane
records therefore cannot assert the source-country fact that M151 scoping
(`core/aggregation.py:274`) depends on.

#### G5 — The evidence lane cannot represent recargo, and says so

`_evidence_draft.py:488-508` documents that a printed `base + cuota + recargo`
invoice has nowhere to put the recargo in `InvoiceDraft`. Extraction reads it and
discards it. Combined with G1's unscreened recargo bindings, a recargo-de-
equivalencia taxpayer's document trail loses the figure at every hop before the
`Transaction`, where `recargo_amount` (`_models.py:768`) finally exists.

#### G6 — `Invoice` and `Transaction` never carry both axes

`Invoice` has `iva_category` + retención but no `source_jurisdiction`;
`Transaction` has `iva_category` + `source_jurisdiction` but no retención field
(only the bounded inference at `_renta_income_ledger.py:792`). Joining the two
axes always requires the aggregation layer. This is a design consequence rather
than a defect, but it is the reason no single record can be inspected to answer
"what will this document contribute to my filings".

---

### Reading notes for the coordinator

- The **rich `Invoice` model is the good one.** Its field set, its retención
  invariants (`_models.py:667-722`), its devengo handling (HEAD `0b1e3f040b`), and
  its refusal to guess the retención scheme (`_invoice_retencion.py:21-27`) are
  all careful work. Almost every gap above is a *front-door* gap: the model can
  express the fact and the CLI cannot supply it.
- The **slim `BusinessOperationInvoice` is the questionable one.** It is
  structurally rigorous (partitioned store, immutable lane, lane-in-hash) and
  downstream-inert. Its existence under the same operator noun as the rich
  catalogue is T1.
- Per the standing observation that every gate here watches one direction of
  error: G1's M303 screen is genuinely two-sided (it screens soportado as well as
  repercutido), which is unusual and good. Its blind spots are recargo, non-ES
  counterparties, and M390 — not a direction bias.

### If an ADR follows

Recorded here rather than left in agent correspondence. G2, G3, G3b and the
INGEST agent's extraction-schema findings all land on **one surface**: the
confirm boundary (`_evidence_draft.py:702-718`) is simultaneously the last
reader-side hop and the first writer-side one. Two separate ADRs would put that
seam inside neither record, so a single joint decision is the right shape.
Proposed scope, agreed with the INGEST agent:

- **D1 — line items.** Writer emits N lines; reader emits a per-rate breakdown.
  The ADR authorises **no** `Invoice` schema change: the model already permits
  multi-line (`_models.py:605-610` bounds only the empty case) and the M303 read
  path already iterates per line.
- **D2 — the confirm-boundary override set.** Today it mirrors the nine draft
  fields. The decision to settle is whether it should mirror the READER or the
  WRITER. Mirroring the writer unblocks retención, recargo, `invoice_class` /
  `rectifies_invoice_number` and `iva_category` on the evidence path in one move.
- **D3 — retención stays OFF the draft**, with the reason recorded: a received
  invoice's retención is a fact about the taxpayer's own retenedor obligation,
  not a header field to trust an extraction pass with. Recorded as a decision so
  a later agent does not add it as an apparent omission.
- **D4 — recargo goes ON the draft.** It is printed on the document face and is
  a header-level fact. This is the one point where the reader-side and
  writer-side answers deliberately diverge, and the ADR should say why.

**D2 and D3 are not in tension** — an earlier draft of this section said they
were, and that was wrong (corrected on the INGEST agent's challenge). They answer
different questions about the same boundary: D3 governs **who may assert** the
fact (an extraction pass may not), D2 governs **where the operator may supply**
it (the override set). The confirm boundary has two input channels, and these
constrain one each. Retención absent from the draft *and* suppliable at confirm
is the coherent resolution, not a compromise between them — and the ADR should
say so, because framing it as a trade-off would push an author toward picking
one. The principle generalises: any fact an operator legitimately knows but a
document cannot assert belongs in D2's set and not in the draft.

The reason the record should not be split is simpler than the tension I claimed:
the confirm boundary is one function, and D1–D4 all change it.

**Suggested sequencing** (offered by the INGEST agent, endorsed here):
**D2 first** — independently shippable, no reader change, no cascade, and it
unblocks the most fields per unit of work (retención, recargo, `invoice_class` /
`rectifies_invoice_number`, `iva_category` all land in one move). Then D1's
writer half (accept a supplied line set), also cascade-independent. D1's reader
half last, where a structured-source per-rate breakdown gives the new writer path
a real multi-line producer to test against rather than a hand-built fixture.

Sequencing accepted by the coordinator. The D2/D3 orthogonality above is the
coordinator's adjudication, ruling against this document's original framing.

### Close-out

**Confidence.** Every `path:line` was read at HEAD `0b1e3f040b`; nothing rests on
reasoning alone. The two cross-agent contributions (G3b; the `InvoiceDraft` field
list in Lane 1) were re-read here before being written down.

**Downgrade on reflection — T3** (purchase evidence confirmable as `ISSUED`). It
is ranked third among tangles and belongs lower. The reverse gate is hard and
tested, `kind` is a required explicit argument whose docstring states extraction
cannot infer it, and the resulting record must still satisfy every `ISSUED`
construction invariant. It is a missing symmetric check, not a live path to a
wrong number — nearer the ergonomic end than its placement implies.

**Retract — nothing.** One framing call was overturned (D2/D3, above); no finding
was withdrawn.

**Act on G1 and G2 first**, in that order. G1 is the only finding where a filed
number can be wrong without the operator having done anything wrong; G2 is the
one that makes the "robustly implemented" issued lane unreachable from its
primary verb.

**Open, not pursued.** G1's M303 screen has no M390 equivalent, and M390 is
reconciled against the summed M303 quarters by a blocking rule. Whether an
invoice-only bucket can reach a filed M390 through that gap is one targeted
question against the M390 binding set — not an investigation. If it cannot, the
thread closes; if it can, it outranks everything in this document. Left for the
coordinator to schedule.

## Sources

Direct source reads and targeted searches across the invoice domain, the invoice application
layer, the ledger application layer, the aggregation layer and the CLI entrypoints, plus
commit history for the change that put the slim store into the calculation mesh. Measured at
`0b1e3f040b`; re-verified in part at `daa9876ed3` by the honesty review and at `246d9a11f4`
during the plan rewrite.

Instrument caveat, recorded because several claims here are absence claims: the semantic code
index reported itself shrunken during this work, so **absence is not evidence**. Every
negative claim carried forward from this sweep was re-confirmed by targeted search at HEAD
before it was allowed to ground a decision.
