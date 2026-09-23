---
tags:
  - '#adr'
  - '#assets-core'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:b1de4f96b753e56645de2e428db6bd136d2cbe4ccdae3be83cca0eefb5b7a39e'
related:
  - "[[2026-09-23-assets-core-vehicle-affectation-research]]"
  - "[[2026-09-21-assets-core-lifecycle-contract-adr]]"
  - "[[2026-09-23-assets-core-amortization-method-set-adr]]"
---

# `assets-core` adr: `Vehicles are amortized only on a typed affectation declaration` | (**status:** `accepted`)

## Problem Statement

The lifecycle decision `2026-09-21-assets-core-lifecycle-contract-adr` left
vehicles outside its scope, but the 2025 registry still admits the transport
table classes without any affectation test, so a passenger car also used
privately can be amortized. `2026-09-23-assets-core-vehicle-affectation-research`
shows such a car is not an affected asset at all. The product must either
refuse vehicles or decide which affectation facts admit them, and LIS DA 18a
free depreciation of new electric vehicles depends on the same facts.

## Considerations

- A vehicle is indivisible, so affectation is all or nothing; no business-use
  percentage exists in law (`2026-09-23-assets-core-vehicle-affectation-research`).
- Accessory private use on non-working time keeps most assets affected, but not
  passenger cars, mopeds, motorcycles, trailers, aircraft or leisure boats
  outside five listed uses (same research).
- An element absent from the activity's books is not affected, save proof to
  the contrary (same research).
- The product cannot observe use; it can only record a declaration with its
  evidence and refuse anything short of an admitted one.

## Considered options

- Keep every vehicle-capable class refused. Rejected: taxis, driving-school
  cars, hire vehicles and exclusively used cars are lawful affected assets.
- A business-use percentage on the revision. Rejected: it contradicts
  indivisibility and would produce a partial charge the law does not allow.
- A typed affectation declaration on the revision, tested before any class that
  can hold a restricted vehicle is charged. Chosen.

## Constraints

- The revision is the accepted immutable carrier of amortization facts
  (`2026-09-23-assets-core-amortization-method-set-adr`); the declaration joins
  it, so a change of affectation is an explicit correction.
- The DA 18a entry-into-service window for the 2025 IRPF period follows the
  AEAT 2025 manual (2024 and 2025) until the RDL 7/2026 effect-clause question
  in the proration research is settled.

## Implementation

A registry flag table marks, per statutory class and modality, whether the
class can hold a vehicle the regulation restricts: the LIS table's external
transport and ships-and-aircraft rows and the simplified table's transport
group. Every class carries an explicit flag, and an absent flag refuses.

The revision gains an optional vehicle affectation declaration: the vehicle
category, the private use (none, accessory on non-working time, or shared), the
listed use relied on for a restricted category, whether the vehicle is
recorded in the activity's books, and an evidence reference. A flagged class
without a declaration is incomplete. A vehicle not recorded in the books,
shared with private use, or used privately in a restricted category without a
listed use is refused with its provision. Exclusive use, or accessory use where
the regulation permits it, admits the vehicle to every method its class admits.

The DA 18a method joins the admitted set for new material vehicles whose
declaration admits them, whose propulsion is one of the five annex-II types,
and whose entry into service falls in the registry's window. It claims the
elected amount within the remaining base, like the other free methods.

## Rationale

The declaration encodes exactly the facts the regulation tests, so the product
refuses the unlawful cases the research identifies without refusing the lawful
ones, and it cannot produce a partial charge that indivisibility forbids.
Carrying it on the immutable revision reuses the accepted correction and
continuity contract rather than a new store.

## Consequences

- Vehicle-capable classes stop charging undeclared vehicles, a deliberate
  refusal for any existing revision that relied on the unchecked path.
- An exclusive-use declaration for a passenger car is the taxpayer's assertion;
  the evidence reference is its only support, and inspection risk stays with
  the taxpayer.
- The IVA treatment of vehicles (LIVA art. 95.Tres) stays with the IVA
  register; this decision does not link the two.
- Authorized by the operator's coordinator on 2026-09-23 as the ordered third
  follow-up of the method-set work, after the proration and workforce items.
