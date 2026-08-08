---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:8a9342518070ca06bfb25b1f9309cd5db6afc4398ccf4241ca33f6821a07000c'
step_id: 'S38'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Measure the tabular mapping baseline over the six csv_dialect descriptors, nine CSV exports and the libro registro header

## Scope

- `dev`

## Description

- Re-derive every tabular denominator from the pinned corpus key rather than from
  the Step row's prose.
- Measure deterministic shape recovery over the six `csv_dialect` descriptors
  through `cadrumo.core.tabular.normalize_tabular_bytes`.
- Measure header-row location over all nine CSV exports through the same entry
  point.
- Measure the exact-header deterministic floor over all 71 columns through
  `resolve_bulk_import_columns` with no mapper, establishing the residue the
  semantic mapping lane must actually carry.
- Prove every scoring axis capable of failing before quoting a perfect score.
- Record the model-dependent arm as BLOCKED rather than reporting a figure for it.

## Outcome

**This Step is CLOSED NARROWER THAN ITS TITLE, deliberately and on the record.**
It delivers the deterministic tabular baseline — shape recovery, header location
and the exact-header floor — each measured and each control-proved. It delivers
**no mapping-quality figure at all**, and the row's title names one.

**What the standing goal still asks that this close excludes.** The row is titled
a *mapping* baseline. Arms A, B and C measure dialect shape, header location and
deterministic exact-header resolution; not one of them measures how often the
semantic column-role mapping is RIGHT. That question is not deferred for
convenience — it has no key-grounded answer available, because the corpus authors
no column-role truth for any of the nine documents. It is carried forward as
`S280`, opened in the same action as this narrowing so the excluded half has an
owner and a row rather than disappearing into a checked box.

A reader comparing this record against its title should read it as *delivered
narrower*, never as *delivered as specified*.

All figures below are quoted against corpus key sha256
`e2db6a499f6f0ffafa4cf44084f433962dd3f8a0f6f0a65facaf7df07bb38593`
(890052 bytes, verified equal to the pinned value) and tree `d6f28f5394`. The
measured surfaces are byte-identical between `493abf6dd1` and `d6f28f5394`, so
the HEAD move during the run did not touch them.

### Denominators, derived from the key

The corpus carries 9 `csv_spreadsheet` documents. Their `truth_kind` splits
6 / 1 / 2: six carry a `csv_dialect` descriptor, one carries `bank_statement`
movement truth, and two carry `truth_kind = none`. The two carrying no shape
truth are the two libro registro books, issued and received.

**The Step row says "the libro registro header", singular. There are two**, and
neither carries any authored truth at all — not a dialect descriptor, not a
column mapping, not a ground-truth object.

### Arm A — deterministic shape recovery, six descriptors, no model

Engine route deterministic, so no tier judgement applies. Per axis, over all six
descriptors: delimiter 6/6, decimal separator 6/6, preamble lines 6/6, line
ending 6/6, data-row count 6/6. Every one of the six descriptors recovered every
one of the five scorable axes: 30/30 field-level.

Per descriptor, all five axes matched for the point-of-sale Z report (pipe
delimited, two-line preamble, TOTALES footer), the BBVA web export (five-line
preamble with blank lines inside it, every field quoted), the spreadsheet-exported
bank statement (ragged trailing semicolon, appended TOTAL row), the neobank export,
the expense-tracker export (embedded newline inside a quoted field), and the legacy
ERP tab-separated export.

**The `encoding` axis is UNSCORABLE and is excluded, not scored as a failure.**
Eight of the nine CSV files contain no byte above 0x7F, and the ninth's only such
bytes are its UTF-8 BOM. `cp1252`, `latin-1` and `utf-8` decode pure ASCII
byte-identically, so the key's encoding claim — `cp1252` twice, `latin-1` once,
`utf-8` three times — is not discriminable from the artefact. The product reports
`utf-8` for all six. Scoring that as 3/6 would blame the reader for a distinction
the corpus does not physically contain; the honest figure is that no scorable
descriptor exists on this axis.

### Arm B — header location, nine exports

Headers located 9/9. Total columns the mapping lane must label: 71. Header rows
sit at 1-based lines 1, 3, 4, 6, 1, 9, 1, 1, 1 — so five of the nine require
locating a header below a preamble, and the deepest is nine lines down.

### Arm C — exact-header deterministic floor, 71 columns

Exact-header resolution establishes **2 of 71 columns** across the nine exports,
consulting no mapping lane. The two are `currency` in the neobank export and
`notes` in the expense-tracker export — both English tokens that happen to
coincide with canonical importer column names.

Per export, exact-resolved: issued libro 0/10, Z report 0/8, BBVA 0/8, caixa 0/5,
neobank 1/8, bank statement 0/5, expenses app 1/10, ERP 0/7, received libro 0/10.

**Both libro registro books resolve 0 of 10.** The residue the semantic mapping
lane must carry is **69 of 71 columns**. This is the number that makes the lane
load-bearing rather than a convenience, and it is measured rather than asserted.

### The model-dependent arm — BLOCKED, no figure reported

**The credential blocker is resolved; one blocker remains.** With the Anthropic
credential exported into the process environment, the mapping call resolves the
design-proxy runtime correctly — the provenance stamp reads
`llm:anthropic-column-role-map:claude-haiku-4-5` — and then fails at the profile-bound
response cache: *no active bucket session*. The credential is present, the tier is
right, and the transport is never reached.

Opening that session needs the operator's passphrase. The one profile reports
`setup_incomplete` and the configured secret passphrase resolves unset, so there is
no provisioned route to a session on this machine. **No passphrase was guessed, and
the profile-bound store was not bypassed** — injecting a null cache would dodge the
audit trail the session exists to create, which is worse than the blockage.

Local inference was not attempted: headroom read 1.83 then 10.34 GiB inside twenty
minutes, and it is that volatility rather than either reading that bars it.

No mapping accuracy is reported. A ratio over zero recorded calls is the exact
shape this campaign has already mistaken for a clean result once.

### The scoring arm cannot score this lane at all

The harness scoring arm now exists and is correct. It is nevertheless unusable
here, and the reason is the corpus rather than the scorer: `score_emission`
refuses a document that authors no truth, and **all nine tabular documents author
none**. Probed directly, the refusal rate is **9 of 9**.

So the tabular path does not carry the same missing-scorer hole as the vision
path. It carries a different and more fundamental one: there is nothing for a
scorer to score. **No mapping-quality figure over this corpus can ever be
key-grounded**, however the transport is resolved. Any such figure must be scored
against an operator-authored expected mapping and labelled as the weaker claim —
which also means an acceptance floor derived from it is a floor against an
operator's judgement, not against the corpus.

## Verification

Corpus key pinning, re-derived denominators and Arm A:

    uv run --no-sync python <scratch driver>
    key sha256   e2db6a499f6f0ffafa4cf44084f433962dd3f8a0f6f0a65facaf7df07bb38593
    key bytes    890052
      csv_spreadsheet documents        9
      truth_kind == csv_dialect        6
      delimiter        6/6 descriptors recovered
      decimal          6/6 descriptors recovered
      preamble_lines   6/6 descriptors recovered
      line_ending      6/6 descriptors recovered
      data_rows        6/6 descriptors recovered
      encoding         NO SCORABLE DESCRIPTOR - no figure exists   [6 descriptor(s) UNSCORABLE, excluded]
      headers located: 9/9 exports
      total columns the mapping lane must label: 71

Arm C:

      exact-header resolved: 2/71 columns across 9 exports
      RESIDUE the semantic mapping lane must label: 69/71 columns

**Anti-tautology controls. 30/30 is only a measurement because each axis was
proved capable of reding.** Each mutation is applied to an in-memory copy; the
corpus tree is read-only and is not a git repository, so nothing was written to it.

      delimiter: ';' rewritten to ','       -> delimiter=',' vs key ';'      RED (control works)
      line_ending: CRLF collapsed to LF     -> line_ending='LF' vs key 'CRLF'  RED (control works)
      preamble_lines: two lines injected    -> preamble_lines=7 vs key 5     RED (control works)
      data_rows: last data row deleted      -> rows=11 vs key 12             RED (control works)
      decimal: dot-decimal file vs comma key-> decimal='.' vs key ','        RED (control works)

Positive control for the encoding-unscorable guard, so "unscorable" is a finding
and not a silent skip:

      pure-ASCII bytes           -> discriminable=False  (expected False)
      same bytes + one 0xF3 byte -> discriminable=True   (expected True)
      same bytes + UTF-8 BOM     -> discriminable=True   (expected True)
      issued libro (real BOM)    -> discriminable=True   (expected True)

Controls for Arm C, so 2/71 is a measurement and not a broken instrument:

      canonical importer headers -> exact-resolved 10/10
      nonsense headers           -> exact-resolved 0/3

The credentialed attempt, showing the credential is no longer the blocker and
naming the gate that is. The key itself is never echoed:

    credential present: True
    provider: ANTHROPIC model: claude-haiku-4-5
    decided_by: llm:anthropic-column-role-map:claude-haiku-4-5
    FAILED at: StorageValidationError
      storage runtime is not ready for profile-bound storage: no active bucket
      session; run `aeat config login NAME` to unlock a profile before invoking
      profile-bound storage.

The scoring arm probed against every tabular document, all nine refusing:

    Can score_emission score ANY of the nine tabular documents?
      OP-ISS-libro_facturas_expedidas_2025_2026      REFUSED
      OP-ISS-pos_zreport_20260514                    REFUSED
      OP-PUR-bank_bbva_2026Q1                        REFUSED
      OP-PUR-bank_caixa_excel_export_2026Q1          REFUSED
      OP-PUR-bank_neobank_2026Q1                     REFUSED
      OP-PUR-bank_statement_2026Q1_Q2                REFUSED
      OP-PUR-expenses_app_export_2026                REFUSED
      OP-REC-ledger_erp_export_2026Q1                REFUSED
      OP-REC-libro_facturas_recibidas_2025_2026      REFUSED

## Notes

- **The extra-refusal confound is cleared.** The guard landed on the mapper
  refuses without the llm extra, and a refusal would be indistinguishable from a
  low score in an aggregate. The extra probes PRESENT in this environment, so no
  Arm C or Arm A figure is a disguised refusal.
- **The key authors dialect truth, not mapping truth.** No corpus document carries
  an authored column-role mapping. The `csv_dialect` `source_record` carries
  delimiter, quoting, decimal, thousands, encoding, line ending, date format,
  preamble line count, quirks, row count and net sum — a parsing truth. Any
  mapping-quality figure over this corpus must therefore be scored against an
  operator-authored expectation, which is a weaker claim than a key-grounded one
  and must be labelled as such wherever it is eventually reported.
- **A reachability finding, recorded rather than worked around.**
  `resolve_bulk_import_columns` is not exported from its owning package's public
  facade, so Arm C reached it through the private module. Production code must not
  do this; the measurement did, and the promotion is a decision for the owning
  lane rather than something this Step should have taken unilaterally.
- The scoring drivers live in the session scratchpad and are ephemeral. Every
  figure above is reproducible from the public entry points named in this record
  against the pinned key.
- **An expected mapping for all 71 columns already exists and its provenance is
  clean.** It was derived from the `FieldRole` member semantics and the observed
  header text BEFORE any model output existed, so it cannot have been fitted to a
  result. `S280` should consume it rather than authoring a second one, and should
  carry forward the ambiguous slots it records — a value-date column beside a
  booked-date column, and a debit/credit pair, each of which has more than one
  defensible answer under a one-column-per-role constraint.
- **No acceptance floor may be set on the encoding axis**, on this corpus or a
  successor built the same way, until a file carries a byte that distinguishes the
  codecs. The axis reports unscorable rather than passing, so a floor set here
  would be a floor on an unobservable.
