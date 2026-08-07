---
tags:
  - '#audit'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:76c93586c15966cd1c3d785b9cccab1d61ea2e5a03e1d3f7285f633a380d5b79'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` audit: `IVA subjection and M349 clave: two fragmented authorities`

## Scope

A semantic sweep of the IVA category and clave surfaces for a third encoding of subjection, of operation type, or of the mapping between them, under a name neither existing axis shares. Read-only; nothing was edited.

Subjection and operation type are separate axes by design. An outbound EU B2B service is not subject in Spain, yet reportable on Modelo 349 under clave S. `IvaCategory` carries the first fact and `IntracomOperationType` the second, and that separation is deliberate. The question asked here was therefore not whether a duplicate `IvaCategory` exists, but whether some other site encodes one of those axes, or their mapping, under an unrelated name.

Discovery was by meaning rather than by identifier: decide whether an operation is subject to Spanish VAT, decide which clave an operation reports under, map an operation's territorial facts to its declaration treatment. Neither finding below shares an identifier with its counterpart, and neither would have surfaced from a symbol search. Relations were then established by measurement against the loaded modules, not by reading tables.

## Findings

### iva-subjection-two-members | medium | Subjection has two interchangeable `IvaCategory` members that one gate treats differently, because the exclusion set mixes two distinct LIVA mechanisms

`IvaCategory` carries two members expressing non-subjection, `DOMESTIC_NOT_SUBJECT` and `OPERACION_NO_SUJETA`. Neither carries a docstring distinguishing it, while their neighbour `INTRA_COMMUNITY_SERVICE_SUPPLY` carries an explicit note stating why it is kept distinct from a sibling. That asymmetry prompted measurement rather than inspection.

Loading 1478 modules and comparing the two members at every `IvaCategory`-keyed mapping and set found them identical at nine surfaces: the cuota-less and evidence-exempt frozensets under each of their aliases, the non-derivable saturation reasons, and the component rows, which give both the same legal reference on both invoice sides. The cuota-zero-by-law predicate agrees for both invoice kinds. One mapping diverges, `_IVA_CATEGORY_HINTS` in `src/cadrumo/domain/transactions/_llm.py`, which carries prompt prose rather than treatment. Exactly one surface in the tree contains one member and not the other: `_CASH_ACCOUNTING_EXCLUDED_CATEGORIES` in `src/cadrumo/application/aggregation/_iva_ledger.py`, consumed by the cash-accounting gate in the same module, contains `OPERACION_NO_SUJETA` and omits `DOMESTIC_NOT_SUBJECT`.

Which member a row receives is decided by the classification rule that fires. Six rules emit `DOMESTIC_NOT_SUBJECT`, covering outbound EU B2B services, B2C distance sales, the three OSS-Union rules, and issuers outside the TAI. Three emit `OPERACION_NO_SUJETA`, covering external-scheme services, outbound third-country services, and IOSS low-value distance sales. No principle separating the two groups is discoverable: OSS-Union services take one member while third-country services take the other, and OSS goods and IOSS goods split the same way.

The legal grounding shows the set is mixing two mechanisms rather than merely missing an entry. LIVA article 163 duodecies apartado Uno scopes the cash-criterion regime to operations understood as carried out in the territory of application of the tax. An operation that is not subject is by definition not carried out in that territory, so it falls outside the regime by scope. Apartado Dos separately lists carve-outs for operations that are inside the territory: exempt supplies under articles 21 to 25 at letter b, intra-community acquisitions at letter c, reverse charge under article 84 apartado uno numbers 2, 3 and 4 at letter d, imports at letter e, and other special regimes at letter a. Checked member by member, six of the seven entries map to a specific letter of apartado Dos. `OPERACION_NO_SUJETA` matches no letter; its presence is justified only by the territorial scope clause of apartado Uno. On that same justification `DOMESTIC_NOT_SUBJECT` qualifies identically.

The set therefore holds six apartado Dos carve-outs alongside one apartado Uno scope case without distinguishing them, which is how the twin could be absent without anyone noticing.

### m349-clave-second-authority | medium | The clave is derived twice, once from the enum whose value is the clave and once from a partial table of string literals

The function `_intracommunity_clave` in `src/cadrumo/application/invoices/_source_resolver.py` has two paths. When an invoice carries an operation type it delegates to `_m349_clave_for_operation_type`, which validates the type against the collectible or payable set and then returns the member's value directly. `IntracomOperationType` is therefore the clave authority: its value is the clave letter. When the operation type is absent it falls back to a chain of `IvaCategory` comparisons emitting clave letters as string literals. The field is optional and defaults to none, so the fallback path is live rather than vestigial.

Measured against the enum, the fallback emits the letters A, E, I, S and T. The canonical set is A, C, D, E, H, I, M, R, S and T. The fallback is an exact subset of the canonical set, missing exactly C, D, H, M and R.

The reason this pair went unnoticed is worth recording as a pattern rather than as an incident. The literal `I` in the fallback reproduces the value of the member named `ADQUISICION_SERVICIOS`. The member name and its clave letter differ, so a search for the literal does not reach the member and a search for the member name does not reach the literal. Generalised: when an enum's value is the domain token and its member name is not, any literal re-derivation of that token is invisible to a symbol search from both directions. Other instances of this shape should be expected wherever a domain token is a short code.

This is not classified as a defect. The five letters the fallback cannot produce are rectification and triangulation-variant claves that may have no `IvaCategory` expression at all, in which case the fallback is correct within its scope and the finding is a near-neighbour proven not to cover those cases, to be cited as precedent rather than retired.

### axis-separation-holds-in-code | low | The predicted leak from subjection fragmentation into clave selection does not exist, confirming the axis separation is real and not merely intended

The hazard expected from the first finding was that the two non-subjection members would diverge in Modelo 349 clave selection. That is where the subjection and operation-type axes meet, and a divergence there would mis-file an operation against VIES, which is the most consequential outcome available to this fragmentation.

Measured: neither `DOMESTIC_NOT_SUBJECT` nor `OPERACION_NO_SUJETA` appears anywhere in `_intracommunity_clave`, in `_m349_clave_for_operation_type`, or in either the collectible or payable operation-type set. The clave path reads only the intra-community categories and the operation type.

This is recorded with the same weight as the findings above because it is a load-bearing negative rather than a null result. The separation of the two axes is enforced in code and not only intended, so the subjection fragmentation cannot propagate into clave selection today. A later refactor that routed clave selection through a general category table would break that property silently, and this measurement is the baseline against which such a change would be detected.

## Recommendations

Distinguish the two mechanisms inside the cash-accounting exclusion set rather than simply adding the missing member. The durable form separates the apartado Dos carve-outs, each of which can name its letter, from the apartado Uno territorial scope case, which is a property of non-subjection rather than an enumerated exclusion. Deriving the scope arm from the subjection property would make the omission of a twin member unrepresentable, in the same way that a single proportion decision makes an income and withholding asymmetry unrepresentable.

Gate any change to that set behind a check of the OSS declaration path first. Admitting `DOMESTIC_NOT_SUBJECT` would newly refuse the three OSS-Union rules whenever a taxpayer on the cash-criterion regime also sells through OSS. That combination is live, the refusal may or may not be correct, and the grounding above does not settle it. The change is grounded but not free, and the OSS check is the precondition rather than a follow-up.

Answer one narrow question before touching the clave fallback: can an invoice with no operation type legitimately require clave C, D, H, M or R. If it cannot, the fallback is correct within its scope and should state that scope explicitly, so a later reader is not left to infer it from the subset relation. If it can, the fallback silently mis-files those operations and the two derivations must be collapsed onto the enum.

An architecturally significant decision underlies both findings and is not recorded here: whether a closed domain token whose value differs from its member name may be re-derived as a literal anywhere, or whether such tokens must be produced only by their owning enum. A follow-on decision record should make that call, because the invisibility pattern described in the second finding will otherwise recur wherever short codes are used.
