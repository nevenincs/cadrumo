p = '.importlinter'
lines = open(p, encoding='utf-8').read().split('\n')


def find(anchor):
    hits = [i for i, l in enumerate(lines) if l == anchor]
    assert len(hits) == 1, (anchor, len(hits))
    return hits[0]


ins = []

# invoices catalogue: one more aggregation consumer
ins.append(("    cadrumo.application.review._adapters -> cadrumo.adapters.persistence.profile.invoices", [
    "    cadrumo.application.aggregation._modelo_bindings_invoice_iva -> cadrumo.adapters.persistence.profile.invoices",
]))

# modelos_calculation catalogue: the guarded edit executor and the calculation service
ins.append(("    cadrumo.application.modelo.verification_actions -> cadrumo.adapters.persistence.profile.modelos_calculation", [
    "    cadrumo.application.modelo._edit_execution -> cadrumo.adapters.persistence.profile.modelos_calculation",
    "    cadrumo.application.modelo.calculation -> cadrumo.adapters.persistence.profile.modelos_calculation",
]))

# modelos_work_units catalogue
ins.append(("    cadrumo.application.modelo.work_lifecycle -> cadrumo.adapters.persistence.profile.modelos_work_units", [
    "    cadrumo.application.modelo._edit_execution -> cadrumo.adapters.persistence.profile.modelos_work_units",
]))

# buckets event history
ins.append(("    cadrumo.application.modelo.work_lifecycle -> cadrumo.adapters.persistence.profile.buckets", [
    "    cadrumo.application.modelo._edit_execution -> cadrumo.adapters.persistence.profile.buckets",
]))

# prorrata-register: the remaining default-construction consumers
ins.append(("    cadrumo.application.modelo.revision_persistence -> cadrumo.adapters.persistence.profile.prorrata_register", [
    "    cadrumo.application.modelo._prorrata_regularizacion_advisory -> cadrumo.adapters.persistence.profile.prorrata_register",
    "    cadrumo.application.modelo.calculation_actions -> cadrumo.adapters.persistence.profile.prorrata_register",
    "    cadrumo.application.modelo.export -> cadrumo.adapters.persistence.profile.prorrata_register",
    "    cadrumo.application.prorrata_register.service -> cadrumo.adapters.persistence.profile.prorrata_register",
    "    # The same boundary-exception import the prorrata regularizacion above makes:",
    "    # the modelo-binding support helper classifies a storage failure by its",
    "    # exception class. Plain exceptions carry no behaviour, so there is nothing",
    "    # to invert behind a port -- naming the class IS consuming the contract.",
    "    cadrumo.application.aggregation._modelo_bindings_support -> cadrumo.adapters.persistence.storage.errors",
    "    # ── bienes-inversion IVA register repository ports-inversion: the concrete",
    "    #    BienesInversionIvaRegisterRepository sits in the persistence adapter",
    "    #    behind its register protocol, and these four modules retain only the",
    "    #    sanctioned default-construction edge (ADR sec. 538). The service is the",
    "    #    composition site; the regularizacion calculation, the advisory and the",
    "    #    export each resolve the register for the revision they are computing. ──",
    "    cadrumo.application.bienes_inversion.service -> cadrumo.adapters.persistence.profile.bienes_inversion",
    "    cadrumo.application.calculations.bienes_inversion_regularizacion -> cadrumo.adapters.persistence.profile.bienes_inversion",
    "    cadrumo.application.modelo._bienes_inversion_advisory -> cadrumo.adapters.persistence.profile.bienes_inversion",
    "    cadrumo.application.modelo.export -> cadrumo.adapters.persistence.profile.bienes_inversion",
    "    # ── The secure-object namespace integrity report is a DIAGNOSTIC read of the",
    "    #    SQL substrate's own invariant, not a data path: the report model names",
    "    #    the integrity type the substrate defines so the diagnostic can state",
    "    #    which namespaces it checked. Pinned at the exact sql module. ──",
    "    cadrumo.application.diagnostic_models -> cadrumo.adapters.persistence.storage.sql.secure_objects",
]))

# usage_ratios: the user_profile resolver alongside the ledger caller
ins.append(("    cadrumo.application.ledger.actions_common -> cadrumo.adapters.persistence.profile.usage_ratios", [
    "    cadrumo.application.user_profile.usage_ratio_resolution -> cadrumo.adapters.persistence.profile.usage_ratios",
]))

# justificante repository: the second application caller
ins.append(("    cadrumo.application.calculations.cross_period_clean_state -> cadrumo.adapters.persistence.profile.justificante", [
    "    cadrumo.application.calculations.cross_period_external_evidence -> cadrumo.adapters.persistence.profile.justificante",
]))

# application/live + auth outbound Sede and authentication edges
ins.append(("    cadrumo.application.live.errors -> cadrumo.adapters.outbound.aeat.sede.errors", [
    "    # The Clave Movil support surface is the same outbound-authentication class",
    "    # as the certificate edge pinned with the auth probes above: the failure-mode",
    "    # enum and the configuration/timeout errors are the integration's own",
    "    # vocabulary, and this layer translates them into user-facing refusals.",
    "    cadrumo.application.live.errors -> cadrumo.adapters.outbound.aeat.auth.clave_movil_support",
    "    cadrumo.application.auth.operator_probes -> cadrumo.adapters.outbound.aeat.auth.clave_movil_support",
    "    # Driving the Sede is this package's purpose: the censal-datos fetch, the",
    "    # declarations register and its expediente walker, and the filed-observation",
    "    # capture are each pinned at the named outbound module they call rather than",
    "    # at a wildcard over adapters.outbound.aeat.sede.",
    "    cadrumo.application.live.censo -> cadrumo.adapters.outbound.aeat.sede.censal_datos",
    "    cadrumo.application.live.filed_data_capture -> cadrumo.adapters.outbound.aeat.sede.declarations_capture",
    "    cadrumo.application.live.justificante -> cadrumo.adapters.outbound.aeat.sede.declarations",
    "    cadrumo.application.live.justificante -> cadrumo.adapters.outbound.aeat.sede.walker",
]))

# modelo edit receipts: no existing block; attach to the edit-executor family
ins.append(("    cadrumo.application.modelo._edit_execution -> cadrumo.adapters.persistence.profile.modelos_work_units", [
    "    # The guarded edit executor persists an encrypted receipt per mutation; the",
    "    # receipt repository is a relocated concrete like its three siblings above,",
    "    # and this module is its only application-layer construction site.",
    "    cadrumo.application.modelo._edit_execution -> cadrumo.adapters.persistence.profile.modelos_edit_receipts",
]))

resolved = [(find(a), ls) for a, ls in ins]
for idx, ls in sorted(resolved, key=lambda x: x[0], reverse=True):
    lines[idx + 1:idx + 1] = ls

open(p, 'w', encoding='utf-8', newline='').write('\n'.join(lines))
print("added", sum(len(ls) for _, ls in ins), "lines")
