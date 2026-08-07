---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:bc95eb6806cab7f60c41956f8bf25b736fe7ee5c28072439edef943f011ceab0'
step_id: 'S11'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W03.P05.S11

## Outcome

The axis is placed and persisted: `TipoActividad` in `core`, the ten Modelo 036 codes; `tipo_actividad` on `Transaction`; and a resolver in `domain/transactions` that reads the art. 95 correspondence from the registry parameters `S38` landed.

The row's own re-scoping named two remaining blockers, and this Step resolves one of them and deliberately does not touch the other.

## Why the code lives on the transaction

The alternative placement is the taxpayer profile, and for a single-activity filer the two are equivalent. They stop being equivalent for the case the axis exists to serve. `S13` needs Modelo 131 casilla 01 and casilla 08 fed from disjoint row sets, and a taxpayer with both an agrarian and a non-agrarian activity has rows of each kind under one profile. A profile-level code cannot split them; a per-row code can, and collapses to the profile answer when there is only one activity.

`None` therefore means undeclared, not "no activity" — an aggregation that needs the split has to treat it as unknown rather than assume either side.

## Grounded, not inferred

The resolver contains no code-to-partition map. It reads the `rirpf-art-95:selector-m036-*` parameters, each carrying its own `legal_refs`, and would be a second authority for the same fact if it restated them.

Two correspondences are only obvious after reading the article, and both are asserted with the apartado that fixes them:

- `A04 Artísticas y Deportivas` is professional because art. 95.2.a) counts Sección Tercera among rendimientos de actividades profesionales alongside Sección Segunda — not because artistic work resembles professional work.
- `A02 Ganadería independiente` partitions with the livestock codes across the table's own IAE split, because art. 95.4 says *Se entenderán incluidas entre las actividades agrícolas y ganaderas: a) La ganadería independiente*.

## The tests are structural on purpose

A test asserting `A04 -> profesional` against the loader passes just as well when both are wrong together, so the suite asserts the properties the mapping must have — partition-exclusive, drawn from the closed code set, complete over the four apartados — and reserves the literal assertions for the two legally-load-bearing correspondences.

The absent-parameter refusal is the positive control for the empty-set assertion. `GANADERA_ENGORDE_PORCINO_AVICULTURA` is legitimately empty, so a missing parameter must NOT also produce an empty set, or the assertion that the gap is *declared* would hold for a gap that was merely missing.

The anti-tautology proof deletes the persisted key rather than corrupting it. The field is optional, so a dropped value re-defaults to `None` instead of raising — which is exactly the save-drops-field shape a roundtrip test cannot see. The proof is that the deletion surfaces as strict inequality.

## What this deliberately does not settle

`IrpfActivityKind` already classifies a taxpayer as professional or sectorial for retención, two-membered on a stated argument: art. 95's seven provisions fix four distinct figures, six of them in rate-identical pairs, so a member per activity would spend names on splits selecting the same number.

`Art95ActivityPartition` is finer — four members — and is not a competing answer to that question. It classifies by which apartado FIXES the rate, which has to be finer, because art. 95.4.2.º and art. 95.5 both yield 2 % from different provisions and the registry carries them as separate parameters for that reason.

The bridge — deriving `IrpfActivityKind` from a declared code instead of asking the operator — is not built, and not for lack of grounding. It needs an input no profile field holds, and where that field lives is an open decision on the profile side that this Step should not pre-empt by building half of it. The module states the relationship where a reader meets it, so the next person does not have to rediscover that the two enums are one step apart rather than in conflict.

## Absorbed on the way

`5c6873b64c` collapsed the Modelo 347 threshold comparison onto a leaf module and left the centralisation gate red: its consumer list still required the two binding families to import a constant they deliberately no longer touch, so the gate was asking for the duplication the commit had just removed. Repointed to the collapsed home.
