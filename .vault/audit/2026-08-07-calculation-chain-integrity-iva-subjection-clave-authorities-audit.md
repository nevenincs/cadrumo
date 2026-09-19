---
tags:
  - '#audit'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:65b23c07e337abdb4f1eec407a59685b1151978d3459ec00113ec116e27bbb3b'
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

### recc-oss-refusal-is-correct | medium | The OSS check gating the subjection fix resolves in favour of the fix: every rule emitting the omitted member produces an operation outside the TAI

The first finding declined to recommend admitting `DOMESTIC_NOT_SUBJECT` to the cash-accounting exclusion set because doing so would newly refuse the three OSS-Union rules for a taxpayer also on the cash-criterion regime. That question is now answered against the law rather than against current behaviour, and the refusal is correct.

The cash-criterion regime is scoped by LIVA article 163 duodecies apartado Uno to operations understood as carried out in the territory of application of the tax. The OSS Union scheme, under article 163 unvicies apartado Uno, covers suppliers established in the Community but not in the Member State of consumption, for services deemed supplied in that other Member State and for intra-community distance sales and interface-facilitated supplies. Those operations are by construction located in the Member State of consumption rather than in the Spanish territory, so they fall outside the cash-criterion regime by the same scope clause that already justifies the presence of the other non-subjection member.

Two further provisions confirm rather than merely permit that reading. Article 163 duovicies apartado Uno letter c requires a separate quarterly declaracion-liquidacion for the special regime, so an operation under it never reaches the ordinary Spanish declaracion-liquidacion. Article 163 tervicies apartado Uno bars deduction of input tax within that declaration, routing it to refund procedures instead. The cash-criterion regime is a devengo and deduction timing rule operating on the ordinary declaracion-liquidacion; applied to an operation that never enters it, there is nothing for the timing rule to act on.

The conclusion generalises beyond the OSS rules to the whole group. All six rules emitting `DOMESTIC_NOT_SUBJECT` produce operations outside the territory: outbound EU B2B services located at the customer under article 69 apartado uno number 1, B2C distance sales, the three OSS-Union rules, and issuers outside the territory. A row carrying the member through an explicit operator override rather than through a classification rule reaches the same result by a slightly different route, since a non-subject operation has no devengo for the regime to defer. The fix is therefore safe, and the gate this finding was raised to close is discharged.

### m349-clave-fallback-splits-three-safe-two-unsafe | high | The clave fallback gap is not uniform: three missing letters are unreachable by construction, two are reachable and silently mis-filed as a different clave

The second finding left one narrow question open: whether an invoice carrying no operation type can legitimately require clave C, D, H, M or R. Read against the bundled Modelo 349 diseno de registro, the answer splits, and the expectation that the five would prove to be rectification and triangulation variants was wrong. Triangulation is clave T, which the fallback already produces, and rectifications are a separate record type rather than a clave.

Claves R, D and C are the three call-off stock claves: transfers of goods under a consignment sales arrangement, returns of such goods from another Member State, and substitution of the intended acquirer. LIVA article 9 bis apartado Dos places the entrega, and its article 25 exemption, at the moment the acquirer takes the power of disposal, which is later than and separate from the movement these three claves report. The movement itself transfers no ownership and carries no invoice; apartado Uno letter d makes the vendor declare the despatch through the record book and the recapitulative declaration precisely because there is no supply yet to invoice. These three are therefore unreachable from an invoice-sourced path by construction, and the codebase carries no call-off stock modelling of any kind. For them the fallback is correct within its scope.

Claves M and H are not. Both cover intra-community supplies of goods following an exempt importation under LIVA article 27 number 12, H being the variant effected by a fiscal representative under article 86 apartado Tres. Article 27 number 12 exempts the importation precisely on condition that the subsequent supply is exempt under article 25, so that subsequent supply is an ordinary exempt intra-community supply: it is invoiced, and it carries the intra-community supply category. The fallback maps that category unconditionally to clave E. The diseno defines E as intra-community exempt supplies expressly excluding supplies following an exempt importation, which it directs to M or H as applicable. The fallback therefore emits the one clave the official table carves these operations out of, and does so silently.

The reachable half of this gap is a mis-filing against VIES rather than a scope limitation, which is why this finding carries a higher severity than the one that raised it.

## Recommendations

Distinguish the two mechanisms inside the cash-accounting exclusion set rather than simply adding the missing member. The durable form separates the apartado Dos carve-outs, each of which can name its letter, from the apartado Uno territorial scope case, which is a property of non-subjection rather than an enumerated exclusion. Deriving the scope arm from the subjection property would make the omission of a twin member unrepresentable, in the same way that a single proportion decision makes an income and withholding asymmetry unrepresentable.

The OSS precondition on that change is now discharged and the change is safe to make. The refusal it introduces for OSS rows is the correct outcome, established against the scope clause and against the separate-declaration and deduction provisions of the special regime rather than against current behaviour. The change still needs its own mutation proof, because a set-membership edit that reddens nothing has not been shown to bite.

Treat the clave fallback as two separate problems, because its gap is not uniform. For claves R, D and C the fallback is correct within its scope, and that scope should be stated in the code so a later reader is not left to infer it from a subset relation and file the same finding again. For claves M and H it mis-files against VIES today and must be corrected, either by collapsing the derivation onto the owning enum or by refusing rather than guessing when an intra-community supply carries no operation type. Refusing is the safer default, because the fallback cannot distinguish an ordinary article 25 supply from one following an exempt importation: the distinction is simply not present in the category it reads.

An architecturally significant decision underlies both findings and is not recorded here: whether a closed domain token whose value differs from its member name may be re-derived as a literal anywhere, or whether such tokens must be produced only by their owning enum. A follow-on decision record should make that call, because the invisibility pattern described in the second finding will otherwise recur wherever short codes are used.
