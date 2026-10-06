// The profiles on this computer, as the shell may know them: their names,
// which one the product has selected, and the two things a person does with
// them before signing in: choose one, or create one. A host that offers none
// of it leaves `Host.profiles` out, and the shell then signs in to the one
// profile the status names and sends everything else to the TUI.

import type {
  ProfileChoice,
  ProfileCreateResult,
  ProfileList,
} from "../ipc/contract";

export interface ProfileAccounts {
  list(): Promise<ProfileList>;
  /** Creates a profile and selects it. It does not sign in: the password
   * is consumed, and zeroed, by this one call. */
  create(name: string, password: Uint8Array): Promise<ProfileCreateResult>;
}

/** The product's own bounds, so that what it would refuse is said before
 * anything is sent. The product remains the judge. */
export const PROFILE_NAME_MAX = 160;
export const PASSWORD_MIN = 8;
// The product also bounds a password at 1024 bytes of UTF-8, which this many
// characters can reach and never pass.
export const PASSWORD_MAX = 256;

export type NameProblem = "missing" | "hyphen" | "long" | "taken";

export function nameProblem(
  name: string,
  list: ProfileList | null,
): NameProblem | null {
  const given = name.trim();
  if (!given) return "missing";
  // The product's command line reads a leading hyphen as an option, and
  // answers such a name with an internal error instead of a refusal.
  if (given.startsWith("-")) return "hyphen";
  if ([...given].length > PROFILE_NAME_MAX) return "long";
  const folded = given.toLocaleLowerCase();
  return list?.profiles.some((p) => p.name.toLocaleLowerCase() === folded)
    ? "taken"
    : null;
}

export type PasswordProblem = "short" | "long";

export function passwordProblem(password: string): PasswordProblem | null {
  const length = [...password].length;
  if (length < PASSWORD_MIN) return "short";
  return length > PASSWORD_MAX ? "long" : null;
}

/**
 * The profile a password would sign in to: the one the person chose while
 * it is still listed, else the one the product has selected, else the only
 * one there is. Null where there are several and none is selected: the
 * person has to choose.
 */
export function targetOf(
  list: ProfileList | null,
  chosen: string | null,
): ProfileChoice | null {
  if (!list) return null;
  return (
    list.profiles.find((p) => p.name === chosen) ??
    list.profiles.find((p) => p.active) ??
    (list.profiles.length === 1 ? (list.profiles[0] ?? null) : null)
  );
}
