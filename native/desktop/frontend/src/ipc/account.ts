// The sign-in, session and profile shapes the host's account commands and
// channels carry. Field names and casing follow the host's serde output
// exactly.

import type { HostFailure, HostOperation } from "./contract";

export type SignInRefusal = {
  code: string;
  retryAfterSeconds: number | null;
  /** Safe native failure context, without exception messages or paths. */
  operation?: HostOperation;
  ioKind?: string;
  osCode?: number;
};

/**
 * The session this window holds waits for a fresh proof after the profile's
 * worker was lost. It grants nothing until then, and the person is not signed
 * out. The window presents the saved sign-in by itself, once.
 */
export type Reconnecting = {
  /** The saved sign-in did not bring the session back: only the password can. */
  passwordRequired: boolean;
};

/** Runtime presence plus this desktop's usable person standing. Reading may
 * restore its own saved session, but never reports person activity. A refusal
 * with present presence keeps the profile selected and requires fresh proof. */
export type SignInStatus = {
  supported: boolean;
  state: "present" | "absent" | "unknown";
  active_profile: string | null;
  runtimeAvailable: boolean;
  refusal: SignInRefusal | null;
  /** Present only while the window's own session waits. */
  reconnecting?: Reconnecting;
};

/** Public presence and runtime/profile changes; never session authority. */
export type SignInSignal =
  | { kind: "sign-in-state"; revision: number; status: SignInStatus }
  | {
      kind: "sign-in-observation-failed";
      revision: number;
      error: HostFailure;
    };

/** Supervisor readiness is public availability, never profile authentication. */
export type ManagerStatus = {
  state:
    | "unsupported"
    | "starting"
    | "ready"
    | "recovering"
    | "waiting"
    | "stopping"
    | "stopped"
    | "failed";
  failure: HostFailure | null;
};

export type ManagerSignal =
  | { kind: "manager-state"; revision: number; status: ManagerStatus }
  | {
      kind: "manager-observation-failed";
      revision: number;
      error: HostFailure;
    };

/** sign_in_submit uses a raw UTF-8 password body and x-cadrumo-token header. */
export type SignInResult =
  | { kind: "signed-in"; status: SignInStatus }
  | ({ kind: "refused" } & SignInRefusal);

/** sign_out_with_password requires a raw UTF-8 password body and the exact
 * profile label/id in x-cadrumo-profile; sign_out carries no secret. Both
 * return the canonical logout result and preserve unknown cleanup outcomes. */
export type SignOutResult = {
  remainingAccess: {
    /** The person's saved automation setting. A sign-out keeps it; it is not
     * access. */
    automationEnabled: boolean | null;
    /** Whether a key issued for an external agent can still admit. Keys do
     * not follow the sign-in, so this is true while one can. Null when the
     * product could not say. */
    automationAccessRemains: boolean | null;
    automationRevoked: false;
  };
};

export type ProfileChoice = {
  /** The label the person gave it. It is also what a sign-in names: labels
   * are unique on a computer, and the product keeps a profile's identity
   * out of everything it prints. */
  name: string;
  /** The profile the product has selected. */
  active: boolean;
};

export type ProfileList = {
  profiles: ProfileChoice[];
  /** False when the product could not read its profiles coherently: an
   * empty list is then not proof that there are none. */
  complete: boolean;
};

export type ProfileDeleteReview = {
  name: string;
  profileId: string;
  digest: string;
};

/**
 * sign_in_submit and profile_create name a profile in the
 * `x-cadrumo-profile` header: its label as UTF-8, percent-encoded, since a
 * header carries no other text. sign_in_submit may leave it out, and then
 * signs in to the profile the product has selected. profile_create uses a
 * raw UTF-8 password body, as sign_in_submit does.
 */
export type ProfileCreateResult =
  { kind: "created"; name: string } | ({ kind: "refused" } & SignInRefusal);

/**
 * profile_password_change takes a raw UTF-8 body: one JSON object with
 * `current_passphrase`, `new_passphrase` and `new_passphrase_confirmation`,
 * which the host hands to the product's command line and keeps nowhere.
 * `unknown`: the change was submitted and its outcome was not observed, so
 * the old password may or may not still sign in.
 */
export type PasswordChangeResult =
  | { kind: "changed" }
  | ({ kind: "refused" } & SignInRefusal)
  | { kind: "unknown" };
