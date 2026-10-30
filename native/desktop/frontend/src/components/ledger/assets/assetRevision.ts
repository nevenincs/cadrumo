// The requests that create an element and correct it, built from what a form
// states. A request carries a whole revision of the register, so each form
// field names the path in the revision it states, and the revision is put
// together from those paths. Nothing here judges a fact: the backend validates
// the revision, and a refusal comes back with its reason.

import type {
  AcquisitionCandidate,
  ActivityAssetCorrectRequest,
  ActivityAssetCreateRequest,
  ActivityAssetRevision,
  DescriptorFacts,
} from "../../../shell/ledgerSetup";
import {
  methodStated,
  methodTakes,
  REVISION_PATHS,
  type FormValue,
  type FormValues,
} from "./assetFields";

/** The revision a correction supersedes, with its identity. */
export type RevisionBase = {
  revision: ActivityAssetRevision;
  revision_id: string;
};

/** What the registry and the register add to what a form states. */
export type RevisionContext = {
  assetId: string;
  /** The modality the registry's options were read under; null until read. */
  regime: string | null;
  /** The purchase a new element names as its acquisition. */
  candidate: AcquisitionCandidate | null;
  /** The revision a correction supersedes; null when creating. */
  base: RevisionBase | null;
};

type Tree = { [key: string]: unknown };

function put(target: Tree, path: readonly string[], found: FormValue): void {
  let at = target;
  for (const step of path.slice(0, -1)) {
    const next = at[step];
    if (typeof next !== "object" || next === null) at[step] = {};
    at = at[step] as Tree;
  }
  at[path[path.length - 1]!] = found;
}

/** Puts each stated fact at the path of its field. A fact left unstated is not
 * put. */
function state(target: Tree, values: FormValues): void {
  for (const [key, found] of Object.entries(values)) {
    const path = Object.hasOwn(REVISION_PATHS, key)
      ? REVISION_PATHS[key]
      : undefined;
    if (path !== undefined && found !== null) put(target, path, found);
  }
}

const textOf = (found: FormValue | undefined): string | null =>
  typeof found === "string" && found !== "" ? found : null;

/** The descriptor a new element is created with: its name and serial number;
 * the rest of the description is added afterwards. */
function descriptorOf(values: FormValues): DescriptorFacts | null {
  const name = textOf(values.name);
  if (name === null) return null;
  return {
    name,
    serial_number: textOf(values.serial_number),
    description: null,
    document_kind: null,
    document_number: null,
    supplier_name: null,
    supplier_tax_id: null,
  };
}

/**
 * The request that creates an element: its first revision and its descriptor.
 * Null while the registry's modality is unread, the purchase is not chosen or
 * has no invoice evidence (which the register keeps with the acquisition), or
 * the name is not stated.
 */
export function createRequest(
  values: FormValues,
  context: RevisionContext,
): ActivityAssetCreateRequest | null {
  const { candidate, regime } = context;
  const descriptor = descriptorOf(values);
  if (
    regime === null ||
    candidate === null ||
    candidate.invoice_evidence_id === null ||
    candidate.evidence_fingerprint === null ||
    descriptor === null
  )
    return null;
  const revision: Tree = {
    asset_id: context.assetId,
    revision_number: 1,
    acquisition: {
      observed_transaction_id: candidate.transaction_id,
      invoice_evidence_id: candidate.invoice_evidence_id,
      evidence_fingerprint: candidate.evidence_fingerprint,
    },
    amortization: { regime },
  };
  state(revision, values);
  return {
    revision: revision as unknown as ActivityAssetRevision,
    descriptor,
  };
}

/** The election after a correction: the one the revision had, or else a new
 * one on the method the correction states, which keeps only the facts of the
 * old election that the new method takes as well. */
function electionAfter(base: Tree, values: FormValues): Tree {
  const before = (base.amortization ?? {}) as Tree;
  const method = textOf(values.method);
  if (method === null || method === before.method)
    return structuredClone(before);
  const next: Tree = { regime: before.regime, method };
  for (const [key, path] of Object.entries(REVISION_PATHS)) {
    const fact = path[1];
    if (
      path[0] === "amortization" &&
      path.length === 2 &&
      fact !== "method" &&
      methodTakes(method, key) &&
      before[fact!] !== undefined &&
      before[fact!] !== null
    )
      next[fact!] = structuredClone(before[fact!]);
  }
  return next;
}

/** The basis and opening history after a correction, without the facts the
 * stage or status typed no longer takes. */
function tidy(revision: Tree): void {
  const basis = revision.basis as Tree | undefined;
  if (basis !== undefined) {
    if (basis.stage !== "taxpayer_owned") delete basis.business_use_share;
    if (basis.stage !== "business_allocated")
      delete basis.prior_allocation_provenance;
  }
  const opening = revision.opening_history as Tree | undefined;
  if (opening !== undefined && opening.status === "missing") {
    delete opening.accumulated_amount;
    delete opening.amortization_method;
    delete opening.covered_through_tax_year;
  }
  const election = revision.amortization as Tree;
  // A method whose facts the form cannot state keeps those of the revision.
  if (!methodStated(String(election.method))) return;
  for (const key of Object.keys(REVISION_PATHS)) {
    const path = REVISION_PATHS[key]!;
    if (path[0] === "amortization" && path.length === 2) {
      const fact = path[1]!;
      if (
        election[fact] !== undefined &&
        fact !== "method" &&
        !methodTakes(String(election.method), key)
      )
        delete election[fact];
    }
  }
}

/**
 * The request that corrects an element: the revision it supersedes with the
 * facts the form changed, and the claims recorded again in the same write.
 * Null while the revision it supersedes is unread.
 */
export function correctRequest(
  values: FormValues,
  context: RevisionContext,
  supersede: readonly string[],
): ActivityAssetCorrectRequest | null {
  const { base } = context;
  if (base === null) return null;
  const before = structuredClone(base.revision) as unknown as Tree;
  const revision: Tree = {
    ...before,
    revision_number: Number(before.revision_number) + 1,
    supersedes_revision_id: base.revision_id,
    amortization: electionAfter(before, values),
  };
  state(revision, values);
  tidy(revision);
  return {
    revision: revision as unknown as ActivityAssetRevision,
    superseding_claims: supersede.map((claim) => ({
      supersedes_claim_id: claim,
      requested_free_amount: null,
    })),
  };
}
