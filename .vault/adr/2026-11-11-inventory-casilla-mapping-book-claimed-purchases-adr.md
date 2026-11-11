---
tags:
  - '#adr'
  - '#inventory-casilla-mapping'
date: '2026-11-11'
modified: '2026-11-11'
body_schema: 'body-v2'
body_hash: 'sha256:e37bb23ceb6ff9160893a95c1ba70be9e5a178292c5addd88c775baab2e24631'
related:
  - "[[2026-08-23-inventory-casilla-mapping-adr]]"
  - "[[2026-10-30-inventory-casilla-mapping-corrections-adr]]"
  - "[[2026-08-23-inventory-casilla-grounding-research]]"
  - "[[2026-08-23-amortization-casilla-mapping-adr]]"
  - "[[2026-11-11-recargo-equivalencia-source-of-truth-derived-cuota-adr]]"
---

# `inventory-casilla-mapping` adr: `Merchandise purchases reach casilla 0181 through book-claimed ledger rows` | (**status:** `accepted`)

Accepted 2026-11-11 by PRIME under the operator's delegation of ADR acceptance, confirmed by the operator that day. PRIME read the record in full and accepted it on four conditions: a single claim mechanism, a persisted link with additive defaults, a cited route from the IRPF rules to the accounting rule for acquisition cost, and unchanged trade-persona figures. It added the constraint on unlinked purchases under Constraints.

This record amends `2026-08-23-inventory-casilla-mapping-adr` and `2026-10-30-inventory-casilla-mapping-corrections-adr`. Both now carry the amendment texts from Reconciliation.

## Problem Statement

Modelo 100 casilla 0181, "Compra de existencias (mercaderías y materias primas)", carries current purchases of goods held for sale. Under the accepted mapping the encrypted inventory book is the only source of 0177, 0181 and 0182. Merchandise purchases are booked in the transaction ledger, and the first-slice expense routing map sends their category to casilla 0183, "Otros consumos de explotación" (`src/cadrumo/_data/registry/aeat/facts/2025/mapping/0090-2025-modelo-100-first-slice-expense-routing-mapping.toml:228`). The minorista-recargo persona's four wholesaler purchases, 31171.40 including IVA and recargo (`dev/fixtures/personas/minorista-recargo/expectations.toml:229`), therefore land in 0183, and its 0181 is zero.

Moving the amount is not enough. If an operator books the same purchase as an inventory movement and the ledger row still routes to 0183, the purchase is deducted twice. A purchase needs one owner. The acquisition cost the book stores must also be the cost the law states, and today it has no field for recargo de equivalencia.

## Considerations

- Placement: the manual places "adquisiciones corrientes de bienes ... integrantes del activo corriente" in 0181 and "elementos y conjuntos incorporables ... materiales diversos" in 0183, defined as goods "adquiridos por esta para incorporarlos a su producción sin someterlos a transformación". Manual Renta part 1, `part1/source.pdf.extracted.md` under each year of `src/cadrumo/_data/corpus/manuals/renta/`: 0181 / 0183 / incorporables at 2022 lines 14543 / 14581 / 14586, 2023 16728 / 16767 / 16786, 2024 17348 / 17387 / 17411, 2025 17591 / 17630 / 17654. The 2020 and 2021 manuals carry the same three passages (2020 13999 / 14033 / 14038, 2021 14193 / 14227 / 14232). No 2026 manual is bundled; 2026 projects from the 2025 edition.
- Valuation route, IRPF to accounting rule:
  - LIRPF art. 28.1: the rendimiento neto of an activity follows the Impuesto sobre Sociedades rules (`src/cadrumo/_data/corpus/normatives/html/ley-35-2006.html.extracted.md:478`).
  - LIS art. 10.3: in estimación directa the base starts from the accounting result under the Código de Comercio and its implementing rules (`src/cadrumo/_data/corpus/normatives/html/ley-27-2014.html.extracted.md:103`).
  - PGC (RD 1514/2007), segunda parte, norma de registro y valoración 10ª, apartado 1: "Los impuestos indirectos que gravan las existencias sólo se incluirán en el precio de adquisición o coste de producción cuando no sean recuperables directamente de la Hacienda Pública". Apartado 1.1 defines the precio de adquisición as the amount the seller invoiced plus the additional costs until the goods are ready for sale. The PGC is not bundled. Source: `https://www.boe.es/buscar/act.php?id=BOE-A-2007-19884#A10`, BOE-A-2007-19884, verified 2026-11-11.
  - The manual states the same rule for 0181 and cites norma 10ª: "así como los impuestos que recaigan sobre las mismas excepto el IVA soportado deducible. Por tanto, el IVA soportado no deducible formará parte del precio de adquisición" (2025 lines 17601-17604, NRV 10ª citation at 17626 and 17645; 2024 17360-17361; 2023 16735-16736; 2022 14550-14551).
- Recargo de equivalencia is an indirect tax on the goods and is never recoverable. LIVA art. 154.Uno makes the recargo the means by which the minorista's IVA is exacted (`src/cadrumo/_data/corpus/normatives/html/ley-37-1992.html.extracted.md:3116`). Art. 154.Dos denies the minorista any deduction of IVA soportado on goods used in the regime's activities (`:3119`). Art. 156.1º charges the recargo on supplies of goods to minoristas (`:3134`). LIVA arts. 154 to 163 (`:3114` to `:3177`) contain no route by which the recargo is deducted or refunded. Under norma 10ª, both the IVA and the recargo charged on a purchase are part of its precio de adquisición.
- The recargo soportado on a purchase keeps its stored figure, because the buyer's cost is what the supplier charged (`2026-11-11-recargo-equivalencia-source-of-truth-derived-cuota-adr`, Constraints).
- The transaction substrate already carries `recargo_amount` inside the gross identity (`src/cadrumo/domain/transactions/models.py:568`, `:936`). The book's acquisition cost has no recargo field (`src/cadrumo/domain/contribuyente/inventory/records.py:186-199`).
- The register-claim mechanism already withholds ledger rows that another register owns:
  - `RentaDeductibilityContext.register_owned_transaction_ids` (`src/cadrumo/domain/renta/ledger_expenses.py:128`) keeps owned rows out of statutory-cap groups (`:958`).
  - `classify_ledger_expenses_against_asset_register` (`src/cadrumo/application/aggregation/activity_asset_expense_reconciliation.py:115`) builds the withheld set from the owner pairs of `_current_acquisition_owners` (`:368`).
  - `register_acquisition_transaction_ids` (`:387`) derives the frozenset.
  - `_split_register_owned` (`src/cadrumo/application/aggregation/modelo_bindings_renta_expenses.py:151`) removes the excluded rows from the observations.
  - `register_owned_acquisition_diagnostics` (`activity_asset_expense_reconciliation.py:316`) reports each withheld row.
  - The annual resolver wires these at `modelo_bindings_renta_expenses.py:249` and `:420-460`. The pago-fraccionado resolver (`:724`) wires them at `:910` and `:917`.
- Modelo 130 has no inventory-variation contributor. Its gastos keep purchases as cost (`dev/fixtures/personas/minorista-recargo/expectations.toml:107-108`).
- The 2026-10-30 corrections freeze stock facts once a closing authority is recorded, and keep descriptive facts editable.

## Considered options

- Route a merchandise ledger category to 0181 in the routing map. Rejected. 0181 then has two sources, the book and the ledger. A category cannot tell merchandise from incorporable materials, because the electricista, fontanero and minorista rows share `suministros_cliente_directos`. Variation would also be computed from a book that does not hold the purchases.
- Keep the book as the sole 0181 source, and add no link. Rejected. Booking a purchase in the book deducts it twice, once in 0181 and once in 0183.
- Keep the book as the sole 0181 source, and let each purchase movement claim its ledger row through the existing register-claim mechanism. Chosen.
- Add a separate inventory exclusion filter beside the asset claim. Rejected. Two withholding paths could disagree on which rows are excluded, and the statutory-cap groups would need a second input.

## Constraints

- The inventory book remains the sole source of 0177, 0181 and 0182 under `2026-08-23-inventory-casilla-mapping-adr`. The expense routing map gains no route to 0181.
- One claim mechanism:
  - An inventory purchase movement enrolls in the existing register-claim mechanism. The owner pairs that `classify_ledger_expenses_against_asset_register` consumes become typed claims. Each claim names the claiming register: an activity asset by `asset_id`, or an inventory purchase by activity, year and `movement_id`.
  - `register_owned_transaction_ids` becomes the union of both registers' claims.
  - Withheld rows carry a register-specific diagnostic.
  - No second filter, set or exclusion path exists.
- Population per resolver:
  - The Modelo 100 estimación directa resolver enrolls asset claims and inventory claims. A claimed row reaches no ledger expense casilla, 0183 included, and counts against no statutory cap.
  - The pago-fraccionado resolver enrolls asset claims only, so Modelo 130 casilla 02 keeps purchases as gastos.
- Persisted link:
  - `MovementRecord` (`src/cadrumo/domain/contribuyente/inventory/records.py:384`) gains `claimed_transaction_id: TransactionId | None`, default `None`. It is permitted only on `PURCHASE` movements.
  - The record lives in `InventoryLedger.period_movements`, persisted in the secure-object namespace `cadrumo.persistence.profile.inventory` (`PROFILE_INVENTORY_LEDGER_NAMESPACE`, `src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py:280`, schema `SECURE_OBJECT_SCHEMA_VERSION_V1`).
  - Superseded movements in `InventoryLedger.history` keep the link they had.
- Recargo in cost:
  - `InventoryAcquisitionCost` (`records.py:186`) gains `consideration_recargo_amount`, a cent amount of zero or more. It is non-recoverable by construction and is added to `nonrecoverable_iva_included` and `total_acquisition_cost` through `derive_inventory_acquisition_totals`.
  - `InventoryAcquisitionFacts` gains the same field.
  - A purchase with a non-zero recargo and a non-zero `consideration_deductible_iva_ratio` is refused, because LIVA art. 154.Dos denies the deduction.
- Migration and versioning:
  - Both fields are additive with absent defaults: no link, and zero recargo.
  - `INVENTORY_SCHEMA_VERSION` stays `"3"` and the namespace schema stays V1, as in the 2026-10-30 additive precedent. No stored book is rewritten.
  - An unlinked movement stays valid and claims nothing. A movement without recargo stays valid. If its linked row carries recargo, the amount check below refuses the link.
  - The movement and acquisition fingerprints (`src/cadrumo/domain/contribuyente/inventory/valuation.py:80`, `:471`) include each new key only when it is set. Existing projection fingerprints and drafts therefore do not drift.
- Link checks. Each check is a typed refusal with a catalogue key and facts, run at link write and again at Modelo 100 resolution.
  - Missing transaction: the named transaction is absent from the profile's ledger.
  - Double claim: a transaction claimed by movements of two different books (activity and year), or by a book and the asset register. Several purchase movements of one book may claim one transaction, which covers a multi-line invoice.
  - Amount mismatch: the summed consideration of the movements that claim one transaction (`consideration_excluding_iva`, `consideration_iva_amount`, `consideration_recargo_amount`) must equal the transaction's `taxable_base`, `iva_amount` and `recargo_amount` to the cent, each compared separately. Attributable cost components are not part of the comparison.
  - Missing substrate: a transaction without `taxable_base` and `iva_amount` cannot be compared and is refused.
- At resolution, any refusal leaves the activity's inventory cohort unresolved with an actionable finding. It never withholds silently and never falls back to 0183.
- The link is a claim fact, not a stock fact. It enters no valuation or projection fingerprint. Linking and unlinking are corrections with a `correction_id`, retained in history, and stay permitted after a closing authority. The claimed set enters the Modelo 100 calculation revision's recorded inputs, so a change makes an existing draft stale through the existing drift gate. Recargo is a stock fact and stays frozen under the 2026-10-30 rule.
- Unlinked purchases are never read as outside the ledger:
  - A `PURCHASE` movement with no `claimed_transaction_id`, in an activity and year that has ledger expense rows, raises a structured finding at Modelo 100 resolution. The finding blocks verification.
  - It clears only when the operator links the movement or states explicitly, on the movement, that the purchase has no ledger row. The statement is a persisted typed fact with three states: linked, stated without a ledger row, and unstated. A blank is never read as "not in the ledger".
  - Books without purchase movements are unaffected.
- The scope covers every year of the registry support envelope, following the year rule. A projected year keeps its grade limits.

## Implementation

We will keep the inventory book as the sole source of casilla 0181. A purchase movement will name the ledger transaction it books, and that transaction will be withheld from Modelo 100 ledger expense routing through the existing register-claim mechanism. The book's acquisition cost will include recargo de equivalencia alongside non-recoverable IVA.

The following outline is a hypothesis within the constraints:

- Generalize the owner pairs into a claim type, extend `register_acquisition_transaction_ids` into a union over both registers, and pass inventory claims from the annual resolver only.
- The annual expense resolver reads the inventory books through the inventory repository port that `InventorySourceResolver` (`src/cadrumo/application/aggregation/inventory.py:604`) already uses.
- Add the link operation beside `ledger.inventory.movement.correct` (`src/cadrumo/domain/contribuyente/inventory/corrections.py:207`). It reaches CLI, TUI and MCP as the other inventory operations do.
- The minorista-recargo persona books its four wholesaler purchases as linked movements. Expected 2025 result: 0181 = 31171.40, 0183 without them, 0177 = 0182 = 0 on its equal 7400.00 openings and closings, and an unchanged gastos total.

Trade personas are unchanged:

- The autonomo-electricista and autonomo-fontanero books state no stock at any time (`dev/fixtures/personas/autonomo-electricista/persona.toml:87`, `dev/fixtures/personas/autonomo-fontanero/persona.toml:123`). With no purchase movement, 0181 is a proven zero from a complete book, not a default.
- Their materials are elementos incorporables used in installation services, which the manual places in 0183. Their ledger rows are claimed by no book and keep routing there.
- 2025 values stay as follows:

  | Persona | 0181 | 0183 | 0218 |
  | --- | --- | --- | --- |
  | autonomo-electricista | 0.00 | 9800.00 | 14600.00 |
  | autonomo-fontanero | 0.00 | 8830.00 | 20158.00 |

- 0183 is the sum of the taxable bases of ELE-MAT-1 to 4 and FON-MAT-1 to 4 in each persona's `ledger.csv`.
- 0218 is the "suma de gastos previos" in `expectations.toml:355` and `expectations.toml:576`.

## Rationale

The claim keeps one owner per purchase, which rules out both double deduction and a second 0181 source. Reusing the asset-register claim means statutory caps, withheld-row diagnostics and observation filtering already apply to inventory claims, with no parallel path to keep in step. The amount check at link and at resolution is what makes the withheld row and the book's acquisition the same money. Without it, the claim could remove a different amount from 0183 than the book adds to 0181. Including recargo follows from the statutory route LIRPF art. 28.1, LIS art. 10.3 and NRV 10ª.1, with LIVA art. 154 establishing that neither tax is recoverable. The manual states the same result for 0181.

## Consequences

- Merchandise purchases reach 0181 once the operator books and links them. The total of gastos is unchanged; only the casilla changes.
- An unlinked book purchase in an activity and year with ledger expense rows blocks verification until it is linked or stated as having no ledger row, so the same purchase cannot be deducted twice unnoticed.
- Modelo 130 is unaffected.
- Existing books load unchanged and keep their fingerprints.
- The asset register's own writes are unchanged. A book claiming an asset-claimed row is refused at link time. An asset claim added later is refused at resolution.
- Reconsider this decision if official instructions place recargo-regime purchases anywhere other than 0181, or if a later Modelo 130 decision adds a variation of existencias.

## Reconciliation

Amendment to `2026-08-23-inventory-casilla-mapping-adr`, appended to that record on 2026-11-11:

"Casilla 0181 remains sourced only from the inventory book. A ledger row that a purchase movement of the book claims is withheld from every Modelo 100 ledger expense destination, including 0183, through the shared register claim, and refuses on a missing transaction, a double claim or an amount mismatch, as `2026-11-11-inventory-casilla-mapping-book-claimed-purchases-adr` states. In the constraint defining 0181, 'non-recoverable IVA' reads 'non-recoverable indirect taxes, namely non-recoverable IVA and recargo de equivalencia (PGC NRV 10ª.1, LIVA art. 154)'."

Amendment to `2026-10-30-inventory-casilla-mapping-corrections-adr`, appended to that record on 2026-11-11:

"A purchase movement's ledger link is a claim fact. It enters no valuation or fingerprint, and linking or unlinking remains permitted after a closing authority, as a correction with a `correction_id` retained in history. A change to the claimed set makes a Modelo 100 draft stale through the drift gate. A purchase's recargo de equivalencia is a stock fact."

No edit is needed to `2026-08-23-amortization-casilla-mapping-adr` or the assets-core records. The asset withholding wording ("if the register owns it, it is withheld") holds unchanged, and the cross-register refusal belongs to this record.

## Open questions

- A transaction in a currency other than EUR: its tax substrate is in the native currency. This decision refuses it as a link target until an FX rule for the comparison is decided.
- One purchase invoice split across two activities' books: refused here as a double claim. Whether a split claim with a summed amount check is lawful and needed is not grounded.
- Freight or similar attributable costs booked as their own ledger rows: they enter `total_acquisition_cost` and also route to a ledger casilla. Whether attributable components should carry their own claims is undecided. Until then, the operator states such costs in only one place.
- The NRV 10ª text was read from BOE online, not from a bundled corpus copy. Bundling RD 1514/2007 is not part of this decision.
- The questions above stay refusals as written.
