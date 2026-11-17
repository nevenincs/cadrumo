// The window's names for the request and result of the ledger operations that
// change, check or trace one movement: edits, classification, manual entry,
// staged checks, splits, lifecycle, history and the model's suggestions. Each
// is the registered Python contract's own type, taken from the generated
// modules by definition id, so no field is written here. A request leaves out
// the profile, which the host fills.

import type { LedgerMovementCheckContracts } from "./ledgerMovementCheckContract";
import type { LedgerMovementContracts } from "./ledgerMovementContract";

type Contracts = LedgerMovementContracts & LedgerMovementCheckContracts;
type Definition = keyof Contracts;

/** What the window sends: the registered request without the profile. */
type Sent<D extends Definition> = Omit<Contracts[D]["request"], "profile_id">;

/** What the operation serves. */
type Served<D extends Definition> = Contracts[D]["result"];

export type LedgerUpdateRequest = Sent<"ledger.update">;
export type LedgerUpdateResult = Served<"ledger.update">;

export type LedgerTrackResult = Served<"ledger.track">;
