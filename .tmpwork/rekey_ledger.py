import sys

p = '.importlinter'
lines = open(p, encoding='utf-8').read().split('\n')


def find(anchor):
    hits = [i for i, l in enumerate(lines) if l == anchor]
    assert len(hits) == 1, (anchor, len(hits))
    return hits[0]


ins = []

ins.append(("    # being a legal inner reach, and resolves through the ledger's public facade.", [
    "    # The pins are keyed at the promoted public module names and at the narrow",
    "    # llm target each one actually reaches, rather than at the bare package: the",
    "    # gated readers, the rasteriser and the proposer are separate decisions and a",
    "    # new reach into a different llm module should have to state itself.",
    "    cadrumo.application.ledger.invoice_draft_extraction -> cadrumo.llm.errors",
    "    cadrumo.application.ledger.invoice_draft_extraction -> cadrumo.llm.evidence_draft_text",
    "    cadrumo.application.ledger.invoice_draft_extraction -> cadrumo.llm.evidence_draft_vision",
    "    cadrumo.application.ledger.invoice_draft_extraction -> cadrumo.llm.providers.local",
    "    cadrumo.application.ledger.invoice_draft_extraction -> cadrumo.llm.supply_nature_proposal",
    "    cadrumo.application.ledger.llm_classification -> cadrumo.llm.errors",
    "    cadrumo.application.ledger.llm_classification -> cadrumo.llm.providers.local",
    "    cadrumo.application.ledger.llm_classification -> cadrumo.llm.text_classifier",
    "    cadrumo.application.ledger.llm_classification -> cadrumo.llm.vision_classifier",
]))

ins.append(("    # edge that is not a DTO consumer still fails loudly.", [
    "    cadrumo.application.ledger.invoice_draft_extraction -> cadrumo.llm.models",
    "    cadrumo.application.ledger.llm_classification -> cadrumo.llm.models",
    "    cadrumo.application.ledger.llm_classification -> cadrumo.llm.suggestions",
    "    cadrumo.application.ledger.llm_diagnostics -> cadrumo.llm.models",
    "    cadrumo.application.ledger.llm_review_workflow -> cadrumo.llm.suggestions",
]))

ins.append(("    # unreproducible figure in a rationale rots into folklore.", [
    "    #",
    "    # The family is now spelled at the modules that carry it. Confirmation moved",
    "    # into invoice_confirmation when evidence_draft was split along its seams,",
    "    # and the encrypted-store reach travelled with the behaviour, not with the",
    "    # filename: the namespace constant, the per-bucket store resolver and the",
    "    # attachment store are the same three imports the pre-split module made.",
    "    cadrumo.application.ledger.evidence -> cadrumo.adapters.persistence.profile.buckets",
    "    cadrumo.application.ledger.evidence -> cadrumo.adapters.persistence.storage.attachment",
    "    cadrumo.application.ledger.evidence -> cadrumo.adapters.persistence.storage.envelope.secure_bound_repository",
    "    cadrumo.application.ledger.evidence -> cadrumo.adapters.persistence.storage.runtime_repository",
    "    cadrumo.application.ledger.evidence -> cadrumo.adapters.persistence.storage.secure_object_namespaces",
    "    cadrumo.application.ledger.invoice_confirmation -> cadrumo.adapters.persistence.profile.invoices",
    "    cadrumo.application.ledger.invoice_confirmation -> cadrumo.adapters.persistence.storage.attachment",
    "    cadrumo.application.ledger.invoice_confirmation -> cadrumo.adapters.persistence.storage.runtime_repository",
]))

ins.append(("    # symbol rename can invalidate.", [
    "    cadrumo.application.ledger.counterparty_establishment -> cadrumo.adapters.persistence.storage.envelope.secure_bound_repository",
    "    cadrumo.application.ledger.counterparty_establishment -> cadrumo.adapters.persistence.storage.secure_object_namespaces",
]))

ins.append(("    # format is inbound-adapter work; the ledger consumes the answer.", [
    "    cadrumo.application.ledger.evidence_input -> cadrumo.adapters.inbound.einvoice.shape",
]))

ins.append(("    # otherwise have gone unnoticed.", [
    "    cadrumo.application.ledger.batch_ingest -> cadrumo.adapters.inbound.einvoice.shape",
]))

ins.append(("    # which means consuming the adapter's record type here.", [
    "    cadrumo.application.ledger.aeat_record_projection -> cadrumo.adapters.inbound.einvoice.record_batch",
]))

ins.append(("    #    unmatched_ignore_imports_alerting = error fails a pin that overshoots. ──", [
    "    # The catalogue repositories this package constructs -- transactions,",
    "    # invoices, buckets, work units, calculation revisions -- and the encrypted",
    "    # storage substrate they resolve through are pinned at the exact module each",
    "    # import names. Every one is a concrete relocated into the persistence",
    "    # adapter by the ports-inversion campaign, so the residual edge is the",
    "    # construction edge sec. 538 permits, not an un-inverted reach: the",
    "    # application layer names the concrete because it is the composition site.",
    "    cadrumo.application.ledger.actions_common -> cadrumo.adapters.persistence.profile.buckets",
    "    cadrumo.application.ledger.actions_common -> cadrumo.adapters.persistence.profile.invoices",
    "    cadrumo.application.ledger.actions_common -> cadrumo.adapters.persistence.profile.modelos_calculation",
    "    cadrumo.application.ledger.actions_common -> cadrumo.adapters.persistence.profile.modelos_work_units",
    "    cadrumo.application.ledger.actions_common -> cadrumo.adapters.persistence.profile.transactions",
    "    cadrumo.application.ledger.actions_common -> cadrumo.adapters.persistence.storage.attachment",
    "    cadrumo.application.ledger.actions_common -> cadrumo.adapters.persistence.storage.errors",
    "    cadrumo.application.ledger.actions_common -> cadrumo.adapters.persistence.storage.runtime_repository",
    "    cadrumo.application.ledger.actions_common -> cadrumo.adapters.persistence.storage.secure_object_namespaces",
    "    cadrumo.application.ledger.actions_import -> cadrumo.adapters.persistence.storage.secure_object_namespaces",
    "    cadrumo.application.ledger.llm_diagnostics -> cadrumo.adapters.persistence.profile.transactions",
    "    # The two extraction lanes persist what they read the same way the ledger",
    "    # stores above do: the invoice catalogue they confirm into, the attachment",
    "    # store holding the evidence bytes, and the per-bucket secure-object store.",
    "    # These were the pre-split module's own persistence imports; splitting it",
    "    # into five responsibilities moved them, it did not add them.",
    "    cadrumo.application.ledger.invoice_draft_extraction -> cadrumo.adapters.persistence.profile.invoices",
    "    cadrumo.application.ledger.invoice_draft_extraction -> cadrumo.adapters.persistence.storage.attachment",
    "    cadrumo.application.ledger.invoice_draft_extraction -> cadrumo.adapters.persistence.storage.runtime_repository",
    "    cadrumo.application.ledger.llm_classification -> cadrumo.adapters.persistence.profile.buckets",
    "    cadrumo.application.ledger.llm_classification -> cadrumo.adapters.persistence.storage.attachment",
    "    cadrumo.application.ledger.llm_classification -> cadrumo.adapters.persistence.storage.runtime_repository",
]))

ins.append(("    # sees and this pin therefore reviews.", [
    "    cadrumo.application.ledger.actions_import -> cadrumo.adapters.inbound.financial.providers.base",
    "    cadrumo.application.ledger.actions_import -> cadrumo.adapters.inbound.financial.providers.csv",
    "    cadrumo.application.ledger.actions_import -> cadrumo.adapters.inbound.financial.providers.detection",
    "    cadrumo.application.ledger.actions_import -> cadrumo.adapters.inbound.financial.providers.ofx",
    "    cadrumo.application.ledger.actions_import -> cadrumo.adapters.inbound.financial.providers.pdf_n26",
    "    cadrumo.application.ledger.actions_import -> cadrumo.adapters.inbound.financial.providers.xlsx",
]))

ins.append(("    # _aeat_record_projection, now stated rather than assumed.", [
    "    # Splitting evidence_draft turned that one consumer into three, each holding",
    "    # the part of the read it owns: the extraction lane calls the parser and",
    "    # catches its XML failure, and the two record-shaping modules consume the",
    "    # invoice class the parser returns. Same justification, three spellings.",
    "    cadrumo.application.ledger.confirmed_field_resolution -> cadrumo.adapters.inbound.einvoice.parsers",
    "    cadrumo.application.ledger.invoice_draft_extraction -> cadrumo.adapters.inbound.einvoice.parsers",
    "    cadrumo.application.ledger.invoice_draft_extraction -> cadrumo.adapters.inbound.einvoice.xml",
    "    cadrumo.application.ledger.invoice_draft_records -> cadrumo.adapters.inbound.einvoice.parsers",
]))

ins.append(("    # the extracted text means as evidence.", [
    "    cadrumo.application.ledger.evidence_textlayer -> cadrumo.adapters.inbound.pdf.page_text_extraction",
]))

ins.append(("    # outbound recorder; diagnostics folds that recorder's encrypted usage log.", [
    "    cadrumo.application.ledger.llm_classification -> cadrumo.adapters.outbound.llm.run_telemetry",
    "    cadrumo.application.ledger.llm_diagnostics -> cadrumo.adapters.outbound.llm.usage",
]))

ins.append(("    #    the adapter directly (narrow target keeps the source-module set flat) ──", [
    "    cadrumo.application.ledger.actions_common -> cadrumo.adapters.persistence.profile.usage_ratios",
]))

resolved = [(find(a), ls) for a, ls in ins]

stale = "    # Two ledger stores added by llm-package-split, same shape as the ledger"
d0 = find(stale)
assert lines[d0 + 3] == "    # behind the optional inference boundary.", lines[d0 + 3]

for idx, ls in sorted(resolved, key=lambda x: x[0], reverse=True):
    lines[idx + 1:idx + 1] = ls

d0 = [i for i, l in enumerate(lines) if l == stale]
assert len(d0) == 1
d0 = d0[0]
assert lines[d0 + 3] == "    # behind the optional inference boundary."
del lines[d0:d0 + 4]

open(p, 'w', encoding='utf-8', newline='').write('\n'.join(lines))
print("added", sum(len(ls) for _, ls in ins), "lines; removed 4 stale comment lines")
