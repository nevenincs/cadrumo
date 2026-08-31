---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:9d2bddb2a779f6c42454064a4c642db7268d61120fc678bff08ee0b83a588c76'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

# `registry-temporal-coverage` audit: `Modelo 200 legal grounding and the ejercicio-2024 revision rename`

## Scope

Modelo 200's casilla-level legal grounding, the legal catalogue entries that grounding needs, and the revision-identity defect that surfaced while doing it. Every count below was measured this session against the loaded tree or the bundled corpus, never inferred. Where an earlier figure of mine was wrong, the correction is stated in the same finding rather than silently replaced.

## Findings

### blocker-named-the-wrong-authority | high | The recorded blocker cited an instrument that cannot carry the evidence it was blocking on

The standing position was that Modelo 200 grounding could not proceed without reading the 2024 orden. The orden is bundled and was read: `orden-hac-657-2025` (BOE-A-2025-12818, 21 June 2025), 2,308 bytes, a self-declared excerpt of articles 1, 3 and 6 plus the final disposition. Article 1 approves the model, remitting its content to anexo I, which the excerpt does not carry; article 6 sets the filing window. It states nothing about any individual casilla, and no approving orden ever does. Reading it therefore could not have unblocked anything. The per-box authority is the AEAT Manual practico de Sociedades 2024, which was already bundled and text-extracted, carrying 150 explicit `Regulacion:` anchors. The lesson generalises: before treating a blocker as unfinished work, confirm the document it names could in principle hold the evidence claimed.

### consolidated-corpus-was-already-bundled | high | Three full consolidated texts were present while the campaign treated their provisions as unavailable

`ley-27-2014.html` (1,470,202 bytes, 212 extracted units), `ley-19-1994.html` (913 KB, Canarias) and `ley-31-2022.html` (3.07 MB, 317 units) are all bundled with per-provision anchors. Resolving `#a130` through the production resolver returns exactly one unit titled "Articulo 130. Derecho a la conversion de activos por impuesto diferido en credito exigible frente a la Administracion Tributaria", matching the section tag that names it. No acquisition was required for any LIS article grounded in this pass. Two normatives assumed absent were bundled under different filename stems, so absence must be established by content search, never by guessing a stem.

### anchor-canonicalisation-collision | high | Twenty-five provisions cannot be cited from the consolidated corpora because their BOE anchors collapse onto other provisions

`_canonical_anchor` strips non-alphanumerics, so the hyphenated anchor BOE gives a *bis* or *ter* article, or a high-ordinal disposicion, folds onto a plain low-numbered one: the anchor for article 15 bis normalises onto article 12's, article 30 bis onto article 33's, article 38 bis onto article 32's, DA 17th onto DA second's, DT 43rd onto DT fifth's. Measured collisions: ten in the LIS, twelve in Ley 19/1994, three in the RIS, none in Ley 31/2022. The resolver refuses a colliding anchor rather than returning the wrong provision, so no mis-citation can occur and the guard is working correctly; the consequence is that the shadowed provision is simply unreachable. This blocks provisions the manual itself cites, including article 30 bis on tributacion minima at three separate anchors, RIS article 59 bis, DA 17th and DA 18th on libertad de amortizacion, and DT 43rd. CORRECTION, same session: the claim that these provisions cannot be cited is WRONG, and the error was testing the artefact rather than the resolver that reads it. `resolve_anchored_extracted_unit` carries a structural-title fallback beyond exact-anchor matching, so the COMPACT canonical form reaches the provision even where BOE's own hyphenated anchor collides. Verified through the production resolver: `#a15bis` reaches article 15 bis, `#a30bis` reaches article 30 bis on tributacion minima, `#a38bis` and `#a38ter` reach theirs, `#dadecimoseptima` and `#dadecimoctava` reach the libertad de amortizacion disposiciones, and `#dtcuadragesimatercera` reaches DT 43rd. Only a PREFIX form such as `#dtcuadragesima` fails, and correctly, because it is ambiguous against the other cuadragesima ordinals and needs the full one. No per-provision excerpt file is required for any of them. The collision measurement itself stands and remains worth knowing -- BOE's hyphenated anchors genuinely do fold onto other provisions and the resolver genuinely does refuse them -- but the consequence drawn from it did not, and an entry citing one of these must simply use the compact form and prove it with a probe planting the COLLIDING article's own phrase.

### misleading-revision-name-hid-a-wrong-citation | high | A revision id contradicting its own declared span concealed a legal reference that does not apply

Modelo 200's revision was named to claim an open-ended span while declaring a bounded one, and registry validation refused the whole tree on that single contradiction. The span was correct and the name was wrong: a separate successor revision already covers the following ejercicio, and the approving orden covers periods initiated in 2024 only. Renaming the revision to the years it covers removed the refusal, and the registry then loaded and validated. The renaming immediately exposed a defect the false name had been hiding: LIS DT 44th, whose own declared effective date falls in the following ejercicio, was cited ten times inside the ejercicio-2024 revision, across its completeness manifest, constructs, formulas, parameters and revision declaration. The effective-window validator had been satisfied only because the revision claimed coverage of years it does not compute. All ten citations were removed; for this ejercicio the rate authority is the general article plus the reduced-rate article already cited. A misleading identifier is therefore not cosmetic: it suppressed a real grounding error and two tests asserting the wrong year.

### rename-scope-is-not-tree-wide | medium | Most occurrences of the old revision id belong to other modelos and a global replace would corrupt them

The old revision id appears 1,137 times across the source tree, of which 1,039 belong to other modelos' identically-named revisions and nine are unrelated filename fragments; only eighty-nine denote this modelo. Two files carry both kinds, so even a per-file replace breaks them. The rename was therefore applied at classified line positions with a token-presence guard, so a stale line number cannot rewrite unrelated text. Registry-side the change was 4,813 key occurrences across 1,054 fragment files, plus 27,704 locale leaves carried by the locale CLI's revision-move verb with nothing overwritten, skipped or left undistributed.

### proximity-join-rejected | medium | Matching section tags to manual anchors by text proximity produces confident wrong groundings

A full join was built between casilla section tags and the manual's `Regulacion:` anchors, emitting every candidate with its supporting evidence and deliberately no ranking. Measured against the real population it reaches only 86 of 707 section paths, leaving 621 sections and 2,662 casilla entries untouched. More decisively, its strongest candidates are wrong: two unrelated sections both matched the disposicion on libertad de amortizacion at identical distance, and both the dominant-entity and dependent-entity grupo fiscal sections matched the reserva de capitalizacion article. Each was checked against the provision's own bundled title. Page proximity measures proximity, not meaning, and a coverage score of one at short distance can still be nonsense. The approach is recorded as rejected so it is not rebuilt; it retains value only as a candidate generator whose every proposal needs independent adjudication.

### grounding-progress-and-its-true-cost | medium | Six hundred casilla entries were re-grounded, and the remainder has no mechanical shortcut

Modelo 200 declares 3,462 casilla entries per revision, of which 3,375 carried one byte-identical eighteen-article blanket list; the two revisions are structural twins with the same 707 section paths. Nine legal entries were authored and verified through the production grounding path, each anchor resolved before any required text was written, each proven against cross-planted phrases from a sibling provision so the anchor is shown to scope the check. Six hundred entries were then re-grounded across both revisions, every mapping adjudicated against the provision's own text rather than its section tag, which matters because tags truncate at roughly fifty characters and because two mappings that read like one article are correctly grounded on a transitional disposition instead. Two provisions were deliberately not authored because they already existed in a sibling catalogue file. The remaining blanket entries cause no test failure; they are a grounding-quality defect, not a source of redness, and closing them requires per-section tax review across roughly 638 sections.

### unrouted-not-dormant | low | Two registry bindings that look orphaned are the registry face of a live feature

Two profile bindings carrying the sociedades laborales reserve are referenced by no casilla, construct or formula, and were initially classified as dormant and proposed for deletion. Tracing the concept to the entrypoint showed the feature is live: a domain calculation module, two rate constants, a calculate-input parameter and a real command-line option all exist. The bindings are unrouted rather than dead, and under the aggregation contract an unrouted source earns an advisory, never a deletion. Two symbolic casillas for the same concept sit outside the construct membership and form one coherent cluster with them.

## Recommendations

### per-provision-extraction-for-shadowed-anchors | Emit excerpt files for the twenty-five collision-shadowed provisions

Follow the existing provision-suffixed filename convention rather than widening the anchor canonicaliser, which would weaken a guard that is currently correct. Sequence this ahead of any further grounding of *bis* and *ter* articles, because those provisions cannot be cited at all until it lands.

### treat-revision-identity-as-load-bearing | Give revision ids the same scrutiny as revision data

The single validation refusal blocking the tree was a name, and it concealed a wrong legal citation plus two tests asserting the wrong year. A follow-on decision should rule on whether bare-year identity becomes the convention for bounded revisions across the registry, since several modelos already use it while others carry open-ended names over bounded spans.

### close-the-export-withdrawal | The withdrawn export tree leaves dependent gates red by construction

The generated export tree for this modelo has been withdrawn, so every gate reading its export layouts now fails, including the live filing proof and two schema regressions. The authoring inputs for the correct design exist. Publication belongs to the export campaign's own step and must run through the canonical publisher with its pre-cutover proof; it must not be reconstructed by hand.

### modelo-165-layout-contract-conflict | high | An era with no AEAT design cannot satisfy a gate that requires layout authority unconditionally

Modelo 165's `2023-2025` revision is reported by the model-law coverage audit as a `layout_authority` coverage gap, and every route to satisfying it was checked and is genuinely absent. The gate accepts any of three things: a cited source tiered `layout_authority`, a workbook parity reference of kind `record_design_layout`, `unsupported_binary_xls` or `static_layout`, or a live cross-reference tiered `layout_authority`. That revision has none of the three; its directory holds only application links, casillas, deadline windows and the revision declaration, and its two cited sources are both `official_source_guidance` pointing at the same orden HTML. It declares no reasoned disposition for the absence either, only a continuity one, so the audit is reporting an UNDECLARED absence, which is correct behaviour.

The absence is nevertheless deliberate. That modelo's own historical-layout regression states AEAT published no record design for the era, and the third bundled design's own heading reads `Ejercicio 2026` despite a filename suggesting 2023, so it cannot be backdated to cover it. The era is declared applicability-only for exactly this reason.

Exempting applicability-grade revisions from the layout tier was attempted and REVERTED: the gate's own mutation proof, which builds a synthetic corpus whose revision is itself applicability-grade with no layout authority, failed immediately. That proof encodes the gate's contract - an applicability revision lacking layout authority IS a reportable gap - so no grade or export-layout discriminator can separate the synthetic case from this one. The conflict is therefore genuine rather than a false positive: the coverage contract requires layout authority from every revision, and the era design deliberately includes a period that has none. Both positions are internally coherent and they contradict, so resolving it is a decision about which contract yields, not a patch.

### do-not-conflate-the-two-backlogs | Keep extraction, acquisition and adjudication separate in reporting

Three distinct causes currently block grounding: provisions unreachable through an anchor grammar though bundled, provisions genuinely absent from the corpus, and provisions present and reachable but needing tax review. Reporting them as one number would misstate the remaining work in both directions.
