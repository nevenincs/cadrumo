"""Reasons for calculation source diagnostics."""

from typing import Literal

CalculationSourceDiagnosticReason = Literal[
    "duplicate_binding_owner",
    "duplicate_bound_casilla_owner",
    "duplicate_relation_owner",
    "source_issue",
    "iva_selected_scope_evidence_failure",
    "iva_compensation_annual_source_evidence_failure",
    "unresolved_binding",
    "storage_degraded",
    "source_domain_not_ready",
    "unhandled_binding_source",
    # The binding's provider kind is registered with disposition ``deferred``:
    # the declaration is legal and enrolled, but no executable route owns it yet.
    # Distinct from "unhandled_binding_source", which is drift between the
    # registration and the route table, not an authored deferral.
    "deferred_binding_source",
    "unresolved_derived_binding",
    # An operator-supplied override whose key names nothing the active revision
    # declares: no binding carries it, so the value is folded into a channel
    # nothing ever reads. Distinct from "unresolved_binding", which says a
    # binding the revision DOES declare received no value -- the inverse, and
    # the reason the two must not be collapsed: there the gap is visible on the
    # binding, here there is no binding to be visible on, so the override's
    # disappearance is indistinguishable from the operator never having entered
    # it. Retired relation ids are the concrete source: relations were absorbed
    # into binding providers, the override channel is keyed by binding id now,
    # and an override persisted under the pre-absorption vocabulary stops
    # applying without a word. Advisory rather than blocking, because the
    # figure it names may be genuinely obsolete -- but never silent, because an
    # operator who entered a figure and sees it absent from the result is owed
    # the reason.
    "orphaned_override",
    # The resolved provenance graph does not show the terminal origin the
    # binding's declaration -- authored, or derived from its provider
    # registration -- says the value must rest on: a class the declaration does
    # not admit, no terminal node at all where one is required, more than one
    # where the family carries a single fact, or a missing evidence fingerprint
    # on a class that must carry one. Distinct from "unresolved_binding", which
    # says no value arrived: here a value DID arrive, complete-looking, by a
    # route nobody declared, which is the failure a complete total hides best.
    "terminal_origin_mismatch",
    "unrouted_observation",
    # An independent QUANTITY consumed rows carry that no binding drawing that
    # quantity reaches -- the retención suffered on the renta side, a base
    # imponible or recargo on the IVA side. Distinct from "unrouted_observation"
    # on the axis that matters to a reader: there, no binding consumes the row
    # and every screen agrees it is unrouted; here the row IS consumed, so the
    # row-keyed screens are silent by construction and their silence must not
    # read as confirmation. Collapsing THOSE two would leave an operator unable
    # to tell "this row reaches nothing" from "this row reaches a casilla but
    # its withholding does not".
    #
    # Deliberately ONE member across every ledger family. Which family raised it
    # is already on the diagnostic as source_kind (and binding_source derived
    # from it), so a per-family member would carry nothing a consumer cannot
    # already read while growing this Literal once per family -- the opposite
    # gradient to the one the shared screen exists to produce. The consequence
    # differs by family (a vanishing retención credit is a settlement error, a
    # missing base imponible is a completeness error) and that belongs in the
    # message, not in a routing key nothing routes on.
    "unrouted_declarable_quantity",
    # A fourth axis beside the one above, and OBSERVATION-INDEPENDENT unlike
    # it: "unrouted_declarable_quantity" needs a real row whose fact is
    # uncovered by a binding that DOES exist; this fires when no binding on
    # the revision could EVER draw a present category's base, for any row of
    # that category, before this taxpayer's own row is even considered. True
    # or false from the registry alone. Advisory rather than blocking -- the
    # affected categories are typically cuota-less by law, so no tax is lost,
    # only the base itself has nowhere on this revision to land.
    "structurally_unroutable_base_category",
    # A row a binding DOES consume, but without the invoice substrate the
    # binding's fact assumes: its contribution rests on bank cash (or is
    # absent). Distinct from "unrouted_observation", which is a row no binding
    # consumes at all.
    "ungrounded_income_substrate",
    # A row whose LINKED sales invoice could not be trusted, so it declares
    # bank cash instead of the invoice base. Distinct from
    # "ungrounded_income_substrate", where no invoice was linked at all: here
    # the operator did the linking and the link itself is what needs repair.
    "unusable_sales_invoice_evidence",
    # An invoice folded into this period whose LIVA art. 75 devengo date was
    # not recorded, so its issue date stood in for it. The figures are the best
    # available, not a legal determination: an operation performed near a
    # quarter boundary and invoiced in the next one is declared in the wrong
    # period by exactly this substitution.
    "devengo_date_proxy_attribution",
    # A ledger row whose period rests on its bank date because no operation date
    # is recorded, and a row whose recorded operation date falls after the money.
    # Both are the operator's to judge: LIVA art. 75.Uno against 75.Dos.
    "iva_row_placed_on_movement_date",
    "iva_operation_date_after_movement",
    "oss_no_live_source",
    # The filer's comunidad of residence, or an unstated one, has no autonomic
    # deducción enrolled in the edition: its regional deducciones are not computed
    # and stay enterable by hand. Leaving one out can only raise the tax.
    "autonomic_deducciones_not_enrolled",
    # An annual withholding summary whose per-perceptor-clave detail store holds
    # NO observation for the year. The bound percepciones count is still
    # materialised as an explicit zero so the casilla gets its fact and the
    # calculate/pull surfaces stay identical, but the zero is a claim the store
    # cannot support: the filing obligation for these resúmenes anuales is
    # triggered by SATISFYING the declared rentas, so a declaration with no
    # type-2 record either omits percepciones that exist or is not owed at all.
    # Kept a reason of its own rather than folded into "source_issue" because a
    # verification gate has to route on it: this is the one absence that must
    # never reach filing grade unattended, and a shared advisory reason cannot
    # be told apart from the advisories that legitimately pass.
    "withholding_detail_absent",
    # A Spanish declarado's CÓDIGO PROVINCIA on a Modelo 347 record, which the
    # 2025 design fills from its domicilio fiscal and the invoices record only
    # inside free-text addresses. Its own reason, naming the counterparts and the
    # record field, because the filer must supply it: the generic "source_issue"
    # names neither and reads as the whole declaration missing something.
    "m347_declarado_provincia_unrecorded",
    # A record naming a party (a Modelo 347 declarado or arrendatario, a Modelo
    # 349 operador) whose name field the person's declared filing name cannot
    # fill: none is declared, the design gives no rule for it, or it is wider
    # than the field. Its own reason because only the filer can state the name
    # and the export refuses until they do.
    "declared_party_name_unresolved",
    # The cash amount above 6.000 EUR a Modelo 347 declarado record carries (RD
    # 1065/2007 art. 34.1.h), which no invoice records. Owed only where such cash
    # was received, so it is worth checking and never classes as missing.
    "m347_metalico_unrecorded",
    "missing_transaction_evidence",
    "administrador_retencion_rate_mismatch",
    # An ISSUED-side retención the ledger INFERRED from a cash shortfall whose
    # figure is no statutory rate product. The shortfall may be a bank fee, a
    # discount, or a disputed line rather than tax withheld, in which case the
    # credit is an over-claim. Screened on the rate rather than on the inference
    # marker so the correct domestic-B2B majority stays silent.
    "inferred_retencion_rate_unmatched",
    # The weaker sibling: the inferred figure DOES equal a statutory sectoral
    # rate, but 1 % and 2 % are small enough that a bank fee or discount reaches
    # them by accident. Kept a separate reason rather than a reworded message so
    # an automated operator routes on the field; the two carry different
    # epistemic weight and must not be collapsed.
    "inferred_retencion_sectoral_rate_unconfirmed",
    # An ISSUED-side retención the ledger INFERRED, kept OUT of the credit the
    # declaration claims. Distinct from the two rate reasons above, which judge
    # whether an inferred figure is plausible: this one reports that a figure was
    # excluded whatever its rate, because the credit takes only the retención a
    # linked invoice declares. The operator can convert each row by recording the
    # retención on its invoice, so the amount is reported alongside the count.
    "inferred_retencion_excluded_from_credit",
    # An ISSUED-side retención that is UNKNOWN rather than absent: no substrate
    # determines one, or the implied rate exceeded the maximum the registry
    # supports and the figure was refused. Reporting it as a zero would assert a
    # proven nothing-withheld, so it keeps a reason of its own.
    "unresolved_retencion_substrate",
    # A value produced by a binding whose declared grade cap stops it at
    # calculation. Raised once per capped binding and box by the canonical
    # resolution step for every resolver together, never by a resolver itself,
    # and carrying the resolver's stated outcome so a proven zero withholds
    # nothing while every other case withholds verify, export and filing.
    "advisory_binding_value",
    # A credit casilla whose declared value source and one of its declared
    # cross-check sources state different amounts, compared exactly at the cent.
    # Raised by the registry-declared credit reconciliation after the formulas
    # run, never by a resolver, and persisted with every source and amount.
    "credit_source_disagreement",
    # A declared cross-check source with nothing to compare. It reads "not
    # cross-checked", never agreement, and withholds nothing.
    "credit_cross_check_absent",
    # A figure the operator accepted is now disputed in another way than the one
    # accepted, so the resolution no longer covers it. Withholds nothing itself.
    "credit_resolution_stale",
    # An operator's acceptance covers a disagreement of this calculation. Raised when a
    # check or an export restates the calculation's notes, never by a resolver.
    "credit_resolution_applied",
    # A Modelo 349 clave the resolver INFERRED from the invoice's IVA category
    # because the record stated no operation type. Correct for an ordinary LIVA
    # art. 25 exempt supply, but a supply following an exempt importation (art.
    # 27.12) reports under clave "M" or "H", and the invoice carries no fact
    # separating the two. Raised only when the bucket also holds an importation,
    # so it cannot fire on a taxpayer for whom "E" is the only available clave.
    "m349_clave_inferred_from_category",
    # An invoice with a counterparty in another member state and no cuota, which
    # states neither an operation type nor an IVA category. Zero IVA towards an
    # EU party reads equally as an exempt supply of goods (clave E) and as a
    # service the recipient self-assesses (clave S), and on the received side as
    # an acquisition of goods or of services, so no clave can be read from the
    # record and none is guessed. The operation is withheld from the
    # recapitulativa, and this reason makes the withholding a gap the filer puts
    # right rather than a declaration that reads as one with no operators.
    "m349_operation_unclassified",
    # An invoice denominated in a foreign currency with no resolved euro rate,
    # withheld from an informativa because its euro value is unknown. Excluding
    # the AMOUNT is correct -- declaring the foreign face value as euro would
    # misstate it. What this reason exists for is the OPERATION: it is real and
    # declarable, only its euro figure is missing, so an informativa that simply
    # omits it leaves the operator filing an incomplete return. Kept distinct
    # from `unrouted_observation` because the remedy is different: that one
    # needs a binding, this one needs a conversion rate on the record.
    "unconverted_foreign_currency",
    # A Modelo 347 filer carries a declaring role (art. 31's claves C/D/E
    # population) whose clave depends on a transaction-level fact this
    # invoice leaves UNDECLARED (tri-state ``None``, not ``False``): whether
    # an acquisition is al margen de la actividad empresarial (clave D), or
    # whether a payment is a subvención/auxilio/ayuda (clave E). Neither a
    # silent ``False`` (under-declares the population the role exists to
    # cover) nor a silent ``True`` (over-declares) is acceptable, so an
    # undeclared fact surfaces here instead of picking a side.
    "unclassified_declarant_role_fact",
    # A declared figure that rests on a reading of the law the registry marks
    # as unsettled for the filing period: a grouping or floor the bundled
    # corpus does not decide, a category whose exclusion is arguable, or a
    # total whose sign the rule does not settle. The figure follows the
    # registry's reading and is declared, never dropped; this reason exists so
    # the reading is disclosed rather than presented as settled. Distinct from
    # "unclassified_declarant_role_fact", where the filer's record leaves a
    # fact undeclared: here the record is complete and the law is the open
    # question, so the remedy is a check against AEAT guidance, not an edit.
    "unsettled_legal_reading",
    # An invoice whose declared IVA treatment and whose counterparty contradict
    # each other: an intra-community supply to a third country, or an export to
    # a member state. Routing on the category alone would declare volume the
    # taxpayer never supplied that way, so the line is withheld -- and this
    # reason exists so the withholding is reported rather than silent. The
    # bank-transaction path returns a typed gate issue for the same shape; the
    # invoice projector returns observations, so it reports through here.
    "invoice_category_counterparty_mismatch",
    # A received reverse charge whose line carries no rated slot. The recipient
    # owes the self-assessed cuota (LIVA art. 84.Uno.2), the supplier charges
    # nothing, and the record states no rate to apply -- so the figure cannot be
    # derived without asserting which rate the supply bore. Refusing to invent it
    # is correct; refusing silently would file a quietly short return, which is
    # what this reason prevents.
    "invoice_reverse_charge_cuota_not_derivable",
    # The recorded recargo departs from the rate art. 161 publishes for that
    # slot. A cross-check beside the declared figure, never a replacement of it.
    "invoice_recargo_departs_from_published_rate",
    # One recorded recargo over lines at several IVA rates, left out of the
    # M303 recargo casillas. No longer emitted: the screen now places each
    # rate's art. 161 share or blocks the period. Kept because stored revisions
    # calculated before that carry it and must still load and explain it.
    "invoice_recargo_not_attributable_to_a_tier",
    "official_box_unpopulated",
    "prior_payment_not_deducted",
    "prior_payment_minoracion_not_captured",
    "settlement_not_computed",
    "prorrata_especial_obligatoria",
    "prorrata_especial_check_unavailable",
    "prorrata_volume_check_unavailable",
    "prorrata_volume_declaration_missing",
    "prorrata_volume_divergence",
    "dt12_regime_window_closed",
    "dt12_regime_window_unverified",
    "dt12_parcial_rescate_guidance",
    # A rate-keyed official box layer that accounts for LESS than the rate-blind
    # total it breaks down. Not an unrouted quantity: the money IS routed, into
    # the total, and the return declares it in full. What is missing is a rate
    # for it, so no box may claim one -- which makes this the one advisory whose
    # remedy is a ledger edit rather than a registry or resolver gap, and the one
    # the export gate later refuses on.
    "rate_boxes_underaccount_total",
    # A casilla whose aggregation resolved to ZERO over a NON-EMPTY income set,
    # because every contributing row was excluded by an activity narrowing the
    # operator has no channel to satisfy. The exclusion itself is correct and is
    # NOT what this reports -- admitting an undeclared row would route a
    # non-agrarian filer's income into an agrarian box, the over-declaration
    # error. What it reports is that the box is empty for a reason invisible from
    # the box: income exists in the period and no activity is declared for it.
    # Deliberately makes no claim ABOUT the income's activity, because nothing in
    # the ledger establishes one -- that absence is the finding.
    "aggregation_activity_undeclared",
    # An operator-supplied casilla value that REPLACED a value the resolvers
    # computed for the same casilla, where the two differ. Not an error: the
    # operator wins by design, because the facts behind a regularizacion may
    # live outside the ledger. What it discloses is that a derived figure was
    # discarded, which nothing else on this path says out loud. Distinct from
    # every unrouted reason: nothing here is missing from the return, one of two
    # available figures was chosen over the other.
    "operator_override_diverges_from_computed",
    # A higher precedence tier replaced a DIFFERENT value a lower tier held for
    # the same filed figure: borrador over the mesh or the profile, an
    # operator's value over a carried one, or an operator's box over a bound
    # value. The ladder still picks the higher tier, so calculation proceeds;
    # what this states is that a filed figure rests on a contested value, and
    # it withholds checking, exporting and recording until the sources agree.
    "precedence_tier_divergence",
    # The same contest on a figure that reaches no exported box. Worth checking
    # and never withholding anything, because no wrong figure can reach the
    # filing through it.
    "precedence_tier_divergence_advisory",
    # A ledger expense row withheld from a Renta expense total because the
    # activity-asset register declares that transaction as an asset's
    # acquisition. The purchase price is the amortizable base, deducted through
    # the register's amortization charge (RIS art. 3.2 under LIS art. 12.1),
    # never a current expense -- so nothing is missing from the return and this
    # is NOT a durable unrouted condition. It exists because the withholding is
    # invisible from the casilla: an operator who recorded a real business
    # purchase and sees it absent from the expense total is owed the reason, and
    # the amount it names is exactly the one the register replaced.
    "register_owned_capital_acquisition",
    # A ledger expense row withheld from every Modelo 100 expense total because a
    # purchase movement of an inventory book claims it: the book carries the same
    # money into casilla 0181 as its acquisition cost. Nothing is missing from the
    # return. It persists with the draft so a later change to the claimed rows is
    # seen as drift.
    "inventory_book_claimed_purchase",
    # A Modelo 193 payment-year record for income accrued in an earlier year,
    # whose base and withholding amounts no official source settles: the
    # withholding was declared in the accrual year's Modelo 123, and the record
    # design is silent on what the later record repeats. The amounts are kept,
    # so nothing is missing from the return; what is missing is the authority
    # for them, which must not read as settled.
    "m193_settled_row_amounts_unresolved_authority",
    # A ledger row in an amortization category that no registered element claims
    # as its acquisition. The register is the only route to the activity
    # amortization boxes, so the row deducts nothing, and leaving it at that would
    # silently drop a real element from the return. A finding, not a block, until
    # the element is registered or the row is reclassified.
    "ledger_amortization_row_unregistered",
    # A resident of a foral territory holding registered activity assets. Modelo
    # 100 and Modelo 130 of the AEAT do not apply there, so no figure from the
    # register may reach them, and Cadrumo cannot work the figure out under foral
    # rules. A finding, not a block, and distinct from a source that could not be
    # read: there is nothing to retry.
    "activity_asset_foral_territory",
    # A recorded tax residence that could not be read while the register holds
    # elements. It establishes neither territory, so no figure from the register
    # reaches the form until the profile states the residence. A finding, not a block.
    "activity_asset_residence_unresolved",
    # A residence is recorded, but none is in force in this period. The register
    # still counts, because nothing places the period in a foral territory; only
    # the filer can state where they lived then.
    "activity_asset_residence_period_unknown",
    # An element in service with lawful base remaining and no effective claim for
    # part of the year. The deduction is not invented and the return is not
    # refused, because a gap reduces a deduction without invalidating the return.
    "activity_asset_claim_gap",
    # What the register states for an element against what the ledger shows now:
    # the entries it names paid less than its cost, or the element explains only part of them.
    # Findings for the filer, who decides which side is wrong; neither withholds anything.
    "register_acquisition_exceeds_ledger",
    "register_acquisition_partly_accounted",
    # An element names a ledger entry the ledger no longer holds. A finding: the
    # element keeps its figures and the filer decides which side is wrong.
    "register_acquisition_row_missing",
    # A row deducted as a current expense whose own words, or its purchase invoice's,
    # describe an amortizable element. A question for the filer: the row keeps deducting.
    "ledger_expense_may_be_durable",
    # The schedule refused to work out what an element accrued, so the element
    # contributes nothing and the amount it may be owed is unknown, not zero.
    "activity_asset_accrual_unavailable",
    # What a baja's calculation tells the filer without stopping the return: a
    # missing claim, a minimum above the deduction, a year with no minimum, a gain
    # with no exemption computed, or an excess the instructions do not route.
    "activity_asset_disposal_finding",
    # An element of an agrarian activity left out of the Modelo 130 expense box
    # because that activity's instalment is a share of income (RIRPF art. 110.1.c).
    "activity_asset_agrarian_excluded",
    # An element whose acquisition row declares no activity, held by a taxpayer
    # another of whose elements is agrarian. It counts in the Modelo 130 expense
    # box, since silence does not mean agrarian, but only the filer can settle it.
    "activity_asset_activity_undeclared",
    # A household group (descendants, ascendants) whose stated count is larger than
    # the rows the profile records. The recorded rows are used and the declaration
    # is not stopped, but the group is not proven complete: the filer described
    # people the profile does not yet hold.
    "household_rows_incomplete",
    # A household row that omits a fact the official design requires of every row of its
    # group, such as an ascendant stored with no NIF. The declaration cannot be checked,
    # exported or filed until the filer states it; nothing stands in for it.
    "household_row_fact_unstated",
]
