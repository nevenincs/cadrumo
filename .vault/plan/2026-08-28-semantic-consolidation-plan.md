---
tags:
  - '#plan'
  - '#semantic-consolidation'
date: '2026-08-28'
tier: L2
related:
  - '[[2026-08-28-semantic-consolidation-research]]'
  - '[[2026-08-28-semantic-consolidation-cli-payload-projection-adr]]'
modified: '2026-08-30'
body_schema: body-v2
body_hash: 'sha256:9e9caebf60f3370cee8afa9ff322c5bc84405e4295d898f4d232c3e73511b34b'
---

# `semantic-consolidation` plan

## Description

## Steps

### Phase `P01` - Retire the duplicated lazy re-export resolvers

Six package namespaces carry a PEP 562 __getattr__ resolver, four of them byte-identical in behaviour. This is duplication and an independent rules breach: package namespaces must be inert and export maps are prohibited. Closed first because it removes code rather than reconciling it, and because every later phase reads imports that these resolvers currently obscure.

- [ ] `P01.S06` - Retire the domain/modelos lazy export map, repointing every consumer at the owning defining module; `src/cadrumo/domain/modelos/__init__.py`.
- [ ] `P01.S07` - Retire the storage lazy export map last of its subtree, repointing its core, custody and crypto facing entries; `src/cadrumo/adapters/persistence/storage/__init__.py`.
- [ ] `P01.S08` - Retire the core lazy export map in full, the largest slice, on the measured finding that the facade saves a real consumer nothing; `src/cadrumo/core/__init__.py`.
- [ ] `P01.S09` - Census and rule on the second population of namespace export maps the mechanism-name search missed, under different identifiers; `src/cadrumo/`.
- [x] `P01.S41` - Repoint the one consumer the crypto retirement missed, which reached encrypt_record through the now-inert namespace and broke every profile passphrase encryption; `src/cadrumo/adapters/persistence/storage/_profile_custody.py`.
- [x] `P01.S42` - Gate the retirement blind spot: refuse an attribute read through a package namespace that does not expose it, so a retirement cannot half-land; `src/cadrumo/tests/test_namespace_attribute_reachability.py`.
- [ ] `P01.S80` - Hold the domain/modelos retirement uncommitted while a peer session lands an overlapping application/modelo relocation, because sixty files carry both diffs and neither can commit atomically without capturing the other; `src/cadrumo/domain/modelos/`.

### Phase `P02` - Reconcile the CLI payload models against the models they restate

116 payload classes under entrypoints/cli duplicate a model in application, domain or adapters, restating at least 715 annotated fields. The ruling this phase needs is whether a CLI payload is a legitimate wire contract or a copy; that ruling is an ADR, and the reconciliation itself is model work requiring judgement about constraint shape rather than mechanical rehoming.

- [x] `P02.S01` - Gate the CLI payload boundary: refuse a payload declaring a constraint or validator its canonical model does not own, per module, property-based, six arms mutation-proved; `src/cadrumo/entrypoints/cli/tests/test_cli_payload_constraint_authority.py`.
- [x] `P02.S02` - Promote the canonical evidence-reference and amendment-reason aliases to public defining modules and dedupe the twice-declared discard-reason alias; `src/cadrumo/domain/modelos/`.
- [ ] `P02.S03` - Reconcile the modelo payload modules onto canonical aliases and move the imported-evidence match invariant to the filing-record model; `src/cadrumo/entrypoints/cli/_modelo_payloads.py`.
- [ ] `P02.S04` - Reconcile the ledger payload modules onto canonical transaction, invoice, counterparty and rule aliases; `src/cadrumo/entrypoints/cli/`.
- [ ] `P02.S05` - Reconcile the config, diagnostics, overview and registry payload modules onto their canonical aliases; `src/cadrumo/entrypoints/cli/`.
- [x] `P02.S18` - Source the business-pct bound from the domain constraint the CLI helper restates, keeping only the operator-facing percent formatting in the CLI; `src/cadrumo/entrypoints/cli/_ledger_support.py`.
- [x] `P02.S43` - Judge a payload validator by its body rather than its presence, so the two sanctioned shapes stop reading as violations, and teach the detector that a threshold literal is usually wrapped in a constructor call; `src/cadrumo/entrypoints/cli/tests/test_cli_payload_constraint_authority.py`.
- [x] `P02.S44` - Type the counterparty key as the canonical content digest on both sides: the key is a SHA-256 hex value, and the CLI had dropped its bound to a single character; `src/cadrumo/application/ledger/counterparty_establishment.py`.
- [ ] `P02.S45` - Tax-review whether an invoice total may be negative before pushing a non-negative bound onto the canonical invoice, since a factura rectificativa under LIVA art. 89 may correct downward; `src/cadrumo/domain/invoices/_models.py`.
- [ ] `P02.S46` - Rule on the currency pattern once for both the invoice and export-row payloads, given the canonical already normalises to uppercase at the parse boundary; `src/cadrumo/`.
- [x] `P02.S47` - Reject the advice to delete the two reconstruction validators: both are the sanctioned shape, one calling three canonical identity validators and encoding the simplificada carve-out with its legal citation, the other rebuilding the rule so its regex-compilability check reruns; `src/cadrumo/entrypoints/cli/`.
- [ ] `P02.S48` - Migrate the export-row date and non-negative-amount checks the CLI enforces onto the canonical export row, which declares no validators at all; `src/cadrumo/application/ledger/models.py`.
- [x] `P02.S52` - Hard-move the classification rule contract to a public defining module and give it named aliases, so the CLI can project the rule's bounds instead of respelling them; `src/cadrumo/domain/transactions/classification_rule.py`.
- [x] `P02.S53` - Name the recurring text and count shapes once and adopt them across the CLI payloads, keeping the positive count local because the pydantic type would move the published schema; `src/cadrumo/core/text_bounds.py`.
- [x] `P02.S54` - Project the grounding refs, filing text, bucket object id and profile label the canonical models already declare; `src/cadrumo/entrypoints/cli/`.
- [x] `P02.S55` - Hard-move the bucket event and help-document contracts to public homes so the payloads mirroring them can project instead; `src/cadrumo/`.
- [x] `P02.S56` - Name the ledger wire shapes and settle the canonical currency length, which disagreed with itself between the transaction payload and the manual command; `src/cadrumo/application/ledger/models.py`.
- [x] `P02.S57` - Repair the payload-bounding gate whose allowlist named a formatter an earlier consolidation had already renamed away; `src/cadrumo/domain/buckets/tests/test_payload_value_bounding.py`.
- [x] `P02.S58` - Hard-move the review package, apoderamiento catalogue, borrador and notification contracts to public homes and project their named shapes, taking the CLI from three hundred and forty-six declarations to thirty; `src/cadrumo/`.
- [ ] `P02.S59` - Rule on the four free-text note bounds, which carry five hundred, two thousand and four thousand characters for the same operator commentary with no canonical among them; `src/cadrumo/entrypoints/cli/`.
- [ ] `P02.S60` - Reconcile the actor concept, declared at sixty-four on the filing label and a hundred and twenty-eight on the review package while both are fed by the same operator resolver; `src/cadrumo/`.
- [ ] `P02.S61` - Publicise the preflight issue detail, whose canonical alias elides at five hundred and twelve where the payload rejects, so the two disagree about what an over-long detail should do; `src/cadrumo/application/ledger/preflight.py`.
- [x] `P02.S102` - Declare the evidence-bundle notes bound once and adopt the canonical unit fraction on the manifest model, which restated both by hand beside the CLI payload that projects it; `src/cadrumo/application/evidence/`.
- [x] `P02.S103` - Declare the compensation expiry year once beside the balance model, and adopt the canonical bucket event id where the M036 payload had invented a looser one; `src/cadrumo/domain/iva_compensation/, src/cadrumo/entrypoints/cli/`.
- [x] `P02.S105` - Keep ModeloCode on the review-package manifest and its CLI projection, both of which discarded the validated three-digit type for a hand-rolled one-to-eight string bound; `src/cadrumo/application/modelo/review_package.py, src/cadrumo/entrypoints/cli/`.
- [x] `P02.S109` - Collapse the confidence bound onto the canonical unit-proportion predicate at both the transaction validator and the CLI gate, which restated the same zero-to-one range a third and fourth time; `src/cadrumo/domain/transactions/model_validation.py, src/cadrumo/entrypoints/cli/_review.py`.
- [x] `P02.S111` - Give the Spanish postcode format a domain-level home, since it is enforced only by the setup wizard and no other write path to address_postcode refuses a malformed value; `src/cadrumo/core/setup_answers.py`.
- [ ] `P02.S112` - Rehome the ledger folder-import aggregation and the Drive remote-object label derivation, both of which the CLI computes with no application or adapter counterpart; `src/cadrumo/entrypoints/cli/`.
- [x] `P02.S113` - Rehome the ledger folder-import fold beside the function that produces the per-file results, asserting the invocation-wide fields agree rather than silently taking the first file's; `src/cadrumo/application/ledger/actions_import.py`.
- [ ] `P02.S115` - Widen the folder-import fold so a directory import reports every file's validation and verification report, not only the first; `src/cadrumo/application/ledger/models.py`.
- [x] `P02.S117` - Rehome the Drive object-label derivation beside the hmac half of the same naming scheme, keeping it distinct from the manifest label whose policy differs; `src/cadrumo/adapters/outbound/storage/, src/cadrumo/entrypoints/cli/_config/`.
- [x] `P02.S119` - Adopt ModeloCode on the aggregation contract and result payloads, leaving the operator-input command untyped so its registry-driven refusal can still name the supported set; `src/cadrumo/application/aggregation/_service.py, src/cadrumo/entrypoints/cli/_modelo_payloads.py`.

### Phase `P03` - Consolidate the repeated secure-repository configuration shape

Eleven repository classes declare the identical namespace, payload_type, schema_version and sensitivity quartet. The question this phase answers is whether they are eleven restatements of one configuration shape or eleven legitimately distinct repositories that share four field names, and the answer decides whether a shared base is a consolidation or a false merge.

### Phase `P04` - Close the confirmed single-function duplicates

Behaviour-fingerprint matches that are small, self-contained and mechanically rehomable once a canonical home is ruled: the uppercase-alphanumeric code validator across domain auth and the CLI payloads, the passphrase strength renderer across two TUI screens, the projection row selector across M200 and M296, the snapshot lister across borrador and justificante, and three identical secure-persistence constructors.

### Phase `P05` - Adjudicate the enum-subset rebuilt groupings

Fifty-two enum-subset clusters at two to six sites, each a candidate partition of a closed axis stated more than once. Every one needs the substitutability pre-filter before collapse, because two modules naming the same members for genuinely different rules must stay apart. The home-office family grouping closed earlier is the worked precedent for both the fix and the gate.

### Phase `P06` - Collapse the filing-year axis onto one declared bound

The same filing_year field carries six contradictory windows across the tree -- ge=2000/le=2099 at 64 sites, ge=2000/le=2100 at 23, ge=1980/le=2200 and ge=1990/le=2200 elsewhere -- so core/_period.py accepts a filing year the aggregation repository refuses. Restating the bound per site is what let one axis mean six things; the fix is one alias every carrier imports, with the birth-year and accrual-year fields that legitimately reach 1900 adjudicated out rather than swept in.

- [x] `P06.S10` - Declare the filing-year window once in core and record why the floor is the registry's first authored revision; `src/cadrumo/core/filing_year.py`.
- [x] `P06.S11` - Adjudicate every year-bounded field: separate the filing-year axis from the birth, accrual and catastral revision years that legitimately reach 1900; `src/cadrumo/`.
- [x] `P06.S12` - Sweep the confirmed filing-year carriers onto the canonical alias across domain, application, adapters and the CLI payloads; `src/cadrumo/`.
- [x] `P06.S13` - Gate the axis: refuse a restated year window on a field the adjudication named a filing year, mutation-proved; `src/cadrumo/core/tests/`.
- [x] `P06.S122` - Extract the self-verifying custody digest base into a leaf module so every custody record can reach it, the two capsule records having been unable to subclass it where it lived; `src/cadrumo/adapters/persistence/storage/custody/`.
- [ ] `P06.S123` - Extend the custody digest base with the digest field validator, the mismatch check and the canonical payload, then subclass the five records that hand-roll them; `src/cadrumo/adapters/persistence/storage/custody/`.

### Phase `P07` - Rule on the second population of non-inert package namespaces

The lazy-export ADR assembled its population by searching for one identifier, _LAZY_EXPORTS, and a mechanism census cannot see the same construct spelled differently. Ten further package namespaces carry it under other names -- _EXPORT_MODULES in operator_surface, _LAZY_NAMES in portals, _LAZY_REPOSITORY_NAMES in transactions, and bespoke __getattr__ bodies in llm, llm/_providers, entrypoints, entrypoints/cli, overview, core/errors and contribuyente. Four of those define production code directly and need relocation rather than map deletion. A companion gate, tests/test_lazy_facade_static_bindings.py, still describes the mechanism as deliberate in its own docstring, so the ADR ruling is not self-executing and that prose must be swept in the same campaign.

- [x] `P07.S14` - Re-census the non-inert namespaces by construct rather than identifier, and count consumers through relative imports as well as absolute ones; `src/cadrumo/`.
- [ ] `P07.S15` - Reconcile the lazy-facade static-binding gate with the retirement ruling so its docstring stops describing the mechanism as deliberate; `src/cadrumo/tests/test_lazy_facade_static_bindings.py`.
- [ ] `P07.S16` - Retire the small differently-named export maps in portals, transactions, llm, llm providers, entrypoints and operator_surface, one package per commit; `src/cadrumo/`.
- [ ] `P07.S17` - Relocate the production code out of the four namespaces that are modules in disguise before their namespaces can be made inert; `src/cadrumo/`.
- [x] `P07.S64` - Retire the portals namespace: publicise its seven owning modules, repoint every consumer, and leave the package inert; `src/cadrumo/domain/portals/`.
- [x] `P07.S65` - Retire the entrypoints namespace, which hid two exports below an unconditional raise so a censo transport import of the censal review resolved to nothing at runtime; `src/cadrumo/entrypoints/`.
- [ ] `P07.S66` - Retire the transactions, llm and operator_surface namespaces, the last of the low-risk export maps; `src/cadrumo/`.
- [ ] `P07.S67` - Relocate the production code out of the overview, contribuyente and core errors namespaces, which define it directly and cannot be made inert by deleting a map; `src/cadrumo/`.
- [x] `P07.S68` - Retire the operator_surface export map, publicising its eight modules and repointing twenty-three consumers; `src/cadrumo/application/operator_surface/`.
- [x] `P07.S69` - Scan every namespace for a name promised in its export surface that cannot resolve, confirming the entrypoints break was the last of its kind; `src/cadrumo/`.
- [x] `P07.S70` - Retire the overview namespace, moving the four status-report builders it defined into their own module and retiring a lazy guard whose circular-import justification had gone stale; `src/cadrumo/application/overview/`.
- [x] `P07.S73` - Retire the llm namespace, publicising its sixteen modules, and record that a rename swept by identifier rather than by path broke core for the second time in this campaign; `src/cadrumo/llm/`.
- [x] `P07.S74` - Scope every future module rename to the package directory and verify with compileall before repointing consumers, since the identifier sweep has now cost two recoveries; `src/cadrumo/`.
- [x] `P07.S75` - Retire the contribuyente namespace, moving the tax-residence models it defined into their own module and repointing a dynamic string import that no static tool could see; `src/cadrumo/domain/contribuyente/`.
- [x] `P07.S76` - Extend the reachability gate to dynamic string imports, which resolve no import statement and so pass every static check the campaign relies on; `src/cadrumo/tests/test_namespace_attribute_reachability.py`.
- [x] `P07.S77` - Retire the transactions namespace, the largest at two hundred and eighty-three import statements, and give the validation module the docstrings becoming public requires; `src/cadrumo/domain/transactions/`.
- [x] `P07.S78` - Retire the llm providers facade, whose lazy AnthropicAdapter arm had no caller because the client already imported that adapter from its own module, and publicise the ProviderAdapter contract four packages depend on; `src/cadrumo/llm/providers/`.
- [x] `P07.S79` - Repoint the core-struct anchor map at the portals and transactions modules the earlier retirements made public, which still named the private paths and left the staleness check red; `src/cadrumo/tests/test_docstring_core_struct_links.py`.
- [x] `P07.S81` - Widen the phase population from the ten namespaces the mechanism census found to the 108 the construct census found, recording what the standing goal still asks for beyond any narrower scope; `src/cadrumo/`.
- [ ] `P07.S82` - Retire the twelve heaviest eager re-export facades, one package per commit, beginning with domain/iva at 179 names and application/aggregation at 160; `src/cadrumo/`.
- [ ] `P07.S83` - Relocate the production code out of the twenty-three namespaces that define it directly, seven of which were absent from the phase population entirely; `src/cadrumo/`.
- [ ] `P07.S84` - Rule on the three module-scope registration side effects, whose dependency inversion is sound but whose siting in a package namespace makes touching that package cost 613 modules; `src/cadrumo/`.
- [x] `P07.S85` - Remove the orphan docstring describing the retired lazy map in application/registry and correct the module docstring that still claimed 87 lazy re-exports; `src/cadrumo/application/registry/__init__.py`.
- [x] `P07.S86` - Retire the core observability facade: sixty-one names across eleven modules, with the replay canonicity gate's pinned module literal moved in the same change; `src/cadrumo/core/observability/`.
- [x] `P07.S87` - Retire the currency, manuals and fincas facades, one package per commit; `src/cadrumo/domain/`.
- [x] `P07.S91` - Retire the censo, attachments, categories, invoices and buckets facades, dissolving the invoices-iva import cycle the invoices namespace made spellable; `src/cadrumo/domain/`.
- [x] `P07.S95` - Retire the deadlines, Google outbound and AEAT sede facades, repointing module-object imports and their body uses together; `src/cadrumo/`.
- [x] `P07.S99` - Retire the three largest domain facades: iva at 179 names across 26 modules, filing at 43 and iva_compensation at 36; `src/cadrumo/domain/`.
- [x] `P07.S104` - Sequence the core errors hierarchy split with whoever owns git rather than applying it incrementally, since a commit landing on a half-applied state produced a HEAD that could not import; `src/cadrumo/core/errors/`.
- [x] `P07.S106` - Finish the errors hierarchy split the concurrent session left half-landed, repointing the five stragglers still reaching the namespace; `src/cadrumo/core/errors/`.
- [x] `P07.S107` - Publicise the censo parser and repoint the portals service tests, the last names reached through namespaces already made inert; `src/cadrumo/adapters/inbound/censo/, src/cadrumo/application/portals/`.
- [ ] `P07.S110` - Rule on which CIF leader-class policy is authoritative, after grounding it against the official norm, and collapse the two identity validators that currently answer the same input differently; `src/cadrumo/core/identity/`.
- [x] `P07.S114` - Publicise the secret store's defining module, which the inert namespace left unreachable for its blob-store and storage consumers; `src/cadrumo/adapters/persistence/storage/secret_store/`.
- [ ] `P07.S118` - Publicise the mirror-manifest module so its remote-naming contracts are reachable without going through the storage namespace; `src/cadrumo/adapters/outbound/storage/`.

### Phase `P08` - Consolidate the repeated constrained scalar shapes

An AST census of every pydantic Field constraint in production code found the same constraint tuple restated at scale on concepts with no canonical alias, and in two cases restated beside a canonical alias that already existed. The inclusive zero-to-one share is declared at 22 further Field sites; the dotted namespaced-id grammar is redeclared byte-identically at four sites despite a public canonical constant; a zero-to-one-hundred percentage at 15 sites and a two-character country code at 32 have no alias at all. Three groups are deliberately NOT collapsed and the plan records why: an exclusive gt/lt rate bound is a different rule, a float-typed score is a different type, and the nine-character tax-id fields are not promotable onto the identity token because that token normalises without enforcing a length.

- [x] `P08.S19` - Declare the zero-to-one share once and retire the nine open-coded bound checks, keeping each caller's own refusal and the exclusive split-child rule intact; `src/cadrumo/core/unit_proportion.py`.
- [x] `P08.S20` - Adopt the share alias at the 22 remaining Field sites carrying the identical inclusive bound; `src/cadrumo/`.
- [x] `P08.S21` - Retire the four independent redeclarations of the dotted namespaced-id grammar in favour of the public canonical constant, and rule on whether its defining module should be public; `src/cadrumo/`.
- [x] `P08.S22` - Declare the zero-to-one-hundred percentage scale once, keeping it distinct from the share alias rather than conflating two scales; `src/cadrumo/`.
- [x] `P08.S23` - Declare the two-character country code once across the 32 sites that state only its length, and rule on whether a charset check belongs on it; `src/cadrumo/`.
- [ ] `P08.S24` - Adjudicate the nine-character tax-id fields against the identity token, which normalises without enforcing a length and so is not a safe promotion; `src/cadrumo/domain/calculations/registry/`.
- [ ] `P08.S25` - Rule on the float-typed zero-to-one scores and the exclusive gt/lt rate bound: whether each earns its own alias or stays open-coded as a distinct rule; `src/cadrumo/`.
- [ ] `P08.S26` - Settle the reported divergence between the SHA-256 hex length literals and the named constant that states the same length; `src/cadrumo/`.
- [x] `P08.S27` - Record that grouping by constraint shape conflates concepts: the two-character group mixed country codes with tipo-renta, subclave and provincia codes, and only about two thirds were countries; `src/cadrumo/`.
- [x] `P08.S28` - Adopt the content-digest aliases at the twenty sites that pin only a length, tightening a pattern onto fields that had none, and retire the two independent SHA-256 length constants; `src/cadrumo/`.
- [ ] `P08.S29` - Adjudicate the coefficient field declared with contradictory zero-inclusion rules in one file, and the gross-amount and taxable-base fields that disagree across sites; `src/cadrumo/domain/`.
- [ ] `P08.S30` - Rule on the six tax-id fields that pin a length while matching neither the checksum-validating nor the normalising canonical alias; `src/cadrumo/domain/calculations/registry/`.
- [x] `P08.S31` - Split the bare datetime fields in the domain into instants that owe UTC-awareness and calendar dates that must not be forced into it; `src/cadrumo/domain/`.
- [x] `P08.S32` - Record that the three coefficient declarations are two concepts, not one: the seasonal-day index is distinct from the modulo coefficient, so only the raw module and the calculation result actually disagree, and settling them is a tax review against the orden text rather than a code judgement; `src/cadrumo/domain/calculations/registry/_m303_orden_raw_models.py`.
- [x] `P08.S33` - Adopt the UTC instant alias on the domain timestamp fields whose own documentation promises timezone-aware UTC while enforcing nothing, closing a validation hole rather than a style gap; `src/cadrumo/domain/`.
- [ ] `P08.S34` - Declare the source-locator bound once: the same concept carries no bound, 512 and 1024 at different sites; `src/cadrumo/`.
- [x] `P08.S35` - Record that the transactions awareness helper delegates to the canonical validator and only translates the error type, so it is a wrapper to keep rather than a duplicate to retire; `src/cadrumo/domain/transactions/_model_validation.py`.
- [x] `P08.S36` - Record why the locator bounds resist a single alias: the thousand-character sites carry a source URL while the five-hundred-character ones carry a structured reference, so one alias would either refuse stored URLs or loosen the structured sites; `src/cadrumo/`.
- [x] `P08.S37` - Route the sancion money parse and its expected-amount check through the canonical half-up rounder, so neither falls back to the banker's rounding the money module forbids at the cent; `src/cadrumo/adapters/inbound/notificacion/_sancion.py`.
- [x] `P08.S38` - Record that both rules-breach checks came back clean: officiality is asked of the one authority everywhere, and every source-kind set is derived from the canonical mesh rather than hand-relisted; `src/cadrumo/application/`.
- [ ] `P08.S39` - Tax-review whether a zero base imponible is legitimate before collapsing the taxable-base bound, which two sites forbid and two allow; `src/cadrumo/domain/`.
- [ ] `P08.S40` - Migrate the secure-object revision id from its delimiter-joined hash convention to the canonical content-hash primitive; `src/cadrumo/adapters/persistence/storage/sql/_secure_object_crypto.py`.
- [x] `P08.S49` - Adopt the non-negative integer type pydantic already ships at the hundred-plus CLI count fields that retyped the bound, having first confirmed the emitted schema is byte-identical; `src/cadrumo/entrypoints/cli/`.
- [x] `P08.S50` - Record why the ge=1 count sites are not swept: the positive-integer type is an exclusive bound and emits a different schema, so the swap would move the published contract for no semantic gain; `src/cadrumo/`.
- [ ] `P08.S51` - Extend the non-negative count adoption to the remaining domain, application and adapter sites once the shared tree is quieter; `src/cadrumo/`.
- [x] `P08.S62` - Correct the justificante presented-at classification, which the UTC sweep typed as an instant although AEAT stamps a local wall-clock time the extractor reads naive, and keep the parse-completion timestamp as the counter-example; `src/cadrumo/domain/justificante/_schema.py`.
- [x] `P08.S63` - Gate the classification the UTC sweep got wrong: refuse a field promising an instant whose producer parses a printed local time and can only return a naive value, mutation-proved on both arms; `src/cadrumo/core/tests/test_utc_instant_sources_are_aware.py`.
- [x] `P08.S71` - Route the manual ledger command through the canonical business-pct coupling validator, publicising the module so application code can reach what it had been re-implementing byte for byte; `src/cadrumo/domain/transactions/model_validation.py`.
- [x] `P08.S72` - Record the attachment-id normaliser as a deliberate non-merge: it drops blank entries where the transaction identifier normaliser refuses them, so its shape is not a superset; `src/cadrumo/application/ledger/models.py`.
- [x] `P08.S88` - Repoint the thirty-eight gate path pins the campaign's renames left naming deleted files, which made those gates scan an empty set and pass while blind; `src/cadrumo/, dev/`.
- [x] `P08.S89` - Fix the violations the unblinded gates exposed: a CLI payload re-implementing ISO date parsing, two stale persisted-version exemptions, and one over-granted bool exemption; `src/cadrumo/`.
- [x] `P08.S90` - Add a tree-wide relative-import resolver as a standing check, so a repoint that emits the wrong dot depth is caught before it reaches a commit; `src/cadrumo/tests/`.
- [x] `P08.S92` - Sweep the second stale-pin class the path sweep could not see: gates naming their canonical module by bare basename, distinguishing those from assertions that a retired module is absent; `src/cadrumo/, dev/`.
- [x] `P08.S93` - Run both stale-pin sweeps after every namespace retirement rather than once, since each retirement creates new stale pins; `src/cadrumo/, dev/`.
- [ ] `P08.S94` - Rule on the two application/modelo edit-execution functions that compose a secure-object write without asserting a revision, a pre-existing finding the composing-write gate reports; `src/cadrumo/application/modelo/_edit_execution.py`.
- [x] `P08.S96` - Sweep the third stale-pin class: ruff per-file ignores in pyproject naming modules the retirements made public, deleting rather than repointing where a narrower inline suppression already covers the site; `pyproject.toml`.
- [x] `P08.S97` - Rehome the censal no-write-surface scan and its anti-tautology guard off the sede facade onto the censal module, so emptying a namespace cannot turn a guard green by emptiness; `src/cadrumo/adapters/outbound/aeat/sede/tests/`.
- [x] `P08.S98` - Repoint the setup-answers lazy module accessor at deadlines.models, and move the FiscalResidency reads to the renta-code module that actually defines them; `src/cadrumo/core/setup_answers.py`.
- [x] `P08.S100` - Promote the post-retirement checks into a single reusable sweep covering all five stale-reference classes, so each retirement runs a written-down pass rather than ad-hoc checks; `dev/quality/namespace_retirement_sweep.py`.
- [x] `P08.S101` - Repoint the two application/modelo files reading filing contracts off the package object, which the reachability gate caught as an AttributeError that only fires when the path runs; `src/cadrumo/application/modelo/`.
- [ ] `P08.S108` - Detect a name imported from a genuinely inert namespace, distinguishing it from one reached through a live lazy export map; `src/cadrumo/tests/`.
- [x] `P08.S116` - Refuse a name imported from a namespace that exports nothing, the failure that has landed three times and takes a package down at collection rather than at use; `src/cadrumo/tests/test_inert_namespace_imports_resolve.py`.
- [x] `P08.S120` - Stop the payload gate reading an empty-string presence check as a declared rule, which was flagging a validator that only delegates; `src/cadrumo/entrypoints/cli/tests/test_cli_payload_constraint_authority.py`.
- [x] `P08.S121` - Repoint the dotted module paths written inside string literals, a class every AST sweep is blind to and which had been failing four custody lock tests in a way that read as flakiness; `src/cadrumo/, dev/quality/namespace_retirement_sweep.py`.

## Parallelization

## Verification
