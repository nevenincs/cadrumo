// The requests that create an element, correct it and change its baja, built
// from what a form states. A request carries a whole revision of the
// register, so each form field names the path in the revision it states, and
// the revision is put together from those paths. Nothing here judges a fact:
// the backend validates the revision, and a refusal comes back with its
// reason.

import type {
  AcquisitionCandidate,
  ActivityAssetCorrectRequest,
  ActivityAssetCreateRequest,
  ActivityAssetRevision,
  DescriptorFacts,
  DisposalFacts,
  FormOptions,
} from "../../../shell/ledgerSetup";
import {
  factsOf,
  OUTSIDE,
  revisionPathOf,
  VEHICLE_DECLARED,
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
  /** What the registry admits, which says the facts each method takes. */
  options?: FormOptions | null;
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

/** Takes a fact out of the revision, and any group it leaves empty. */
function remove(target: Tree, path: readonly string[]): void {
  const parent = path
    .slice(0, -1)
    .reduce<Tree | null>(
      (at, step) =>
        at !== null && typeof at[step] === "object" && at[step] !== null
          ? (at[step] as Tree)
          : null,
      target,
    );
  if (parent === null) return;
  delete parent[path[path.length - 1]!];
  if (path.length > 2 && Object.keys(parent).length === 0)
    remove(target, path.slice(0, -1));
}

/** Puts each stated fact at the path of its field. A fact left unstated is not
 * put; given `clearing`, a fact stated as null is taken out. */
function state(target: Tree, values: FormValues, clearing: boolean): void {
  for (const [key, found] of Object.entries(values)) {
    const path = revisionPathOf(key);
    if (path === null) continue;
    if (found !== null) put(target, path, found);
    else if (clearing) remove(target, path);
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

/** The basis flag that says the element is a property follows its stage. */
function tidyBasis(revision: Tree): void {
  const basis = revision.basis as Tree | undefined;
  if (basis === undefined) return;
  basis.is_property = basis.stage === "whole_property";
  if (basis.stage !== "taxpayer_owned") delete basis.business_use_share;
  if (basis.stage !== "business_allocated")
    delete basis.prior_allocation_provenance;
  if (basis.stage !== "whole_property") {
    for (const name of [
      "construction_cost",
      "land_cost",
      "ownership_mode",
      "ownership_share",
      "office_area",
      "total_area",
    ])
      delete basis[name];
    delete revision.building_construction_date;
  }
}

/** The opening history without the facts a missing history cannot carry. */
function tidyOpening(revision: Tree): void {
  const opening = revision.opening_history as Tree | undefined;
  if (opening !== undefined && opening.status === "missing") {
    delete opening.accumulated_amount;
    delete opening.amortization_method;
    delete opening.covered_through_tax_year;
  }
}

/**
 * The request that creates an element: its first revision and its descriptor.
 * An element bought through a purchase of the ledger names that purchase and
 * its invoice; one bought outside the ledger names the document it holds,
 * the day it was bought and its activity. Null while the registry's modality
 * is unread, the acquisition is not stated, or the name is not stated.
 */
export function createRequest(
  values: FormValues,
  context: RevisionContext,
): ActivityAssetCreateRequest | null {
  const { candidate, regime } = context;
  const descriptor = descriptorOf(values);
  if (regime === null || descriptor === null) return null;
  const outside = values.acquisition_shape === OUTSIDE;
  if (outside && textOf(values.acquisition_reference) === null) return null;
  if (
    !outside &&
    (candidate === null ||
      candidate.invoice_evidence_id === null ||
      candidate.evidence_fingerprint === null)
  )
    return null;
  const revision: Tree = {
    asset_id: context.assetId,
    revision_number: 1,
    acquisition:
      outside || candidate === null
        ? {
            observed_transaction_id: null,
            observed_lineage_event_id: null,
            invoice_evidence_id: "",
            evidence_fingerprint: null,
          }
        : {
            observed_transaction_id: candidate.transaction_id,
            invoice_evidence_id: candidate.invoice_evidence_id,
            evidence_fingerprint: candidate.evidence_fingerprint,
          },
    ...(outside ? { further_acquisitions: [] } : {}),
    amortization: { regime },
  };
  state(revision, values, false);
  tidyBasis(revision);
  return {
    revision: revision as unknown as ActivityAssetRevision,
    descriptor,
  };
}

/** The election after a correction: the one the revision had, or else a new
 * one on the method the correction states, which keeps only the facts of the
 * old election that the new method takes as well. */
function electionAfter(
  base: Tree,
  values: FormValues,
  options: FormOptions | null,
): Tree {
  const before = (base.amortization ?? {}) as Tree;
  const method = textOf(values.method);
  if (method === null || method === before.method)
    return structuredClone(before);
  const taken = new Set(factsOf(options, method).map((fact) => fact.path[0]));
  const next: Tree = { regime: before.regime, method };
  for (const [name, found] of Object.entries(before)) {
    if (
      name !== "regime" &&
      name !== "method" &&
      taken.has(name) &&
      found !== null &&
      found !== undefined
    )
      next[name] = structuredClone(found);
  }
  return next;
}

/**
 * The request that corrects an element: the revision it supersedes, carried
 * whole, with the facts the form changed, and the claims recorded again in
 * the same write. A fact the form emptied is taken out. The baja the revision
 * records travels with it unchanged. Null while the revision it supersedes is
 * unread.
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
    amortization: electionAfter(before, values, context.options ?? null),
  };
  state(revision, values, true);
  if (values[VEHICLE_DECLARED] === false) delete revision.vehicle_affectation;
  tidyBasis(revision);
  tidyOpening(revision);
  return {
    revision: revision as unknown as ActivityAssetRevision,
    superseding_claims: supersede.map((claim) => ({
      supersedes_claim_id: claim,
      requested_free_amount: null,
    })),
  };
}

/**
 * The request that changes the baja an element records, or removes it. It is
 * a correction that carries the revision it supersedes whole, with only the
 * baja replaced by `disposal`, or taken out when that is null. The backend
 * works out the claims the baja moves.
 */
export function bajaRequest(
  base: RevisionBase | null,
  disposal: DisposalFacts | null,
): ActivityAssetCorrectRequest | null {
  if (base === null) return null;
  const before = structuredClone(base.revision) as unknown as Tree;
  const revision: Tree = {
    ...before,
    revision_number: Number(before.revision_number) + 1,
    supersedes_revision_id: base.revision_id,
    disposal,
  };
  return {
    revision: revision as unknown as ActivityAssetRevision,
    superseding_claims: [],
  };
}
