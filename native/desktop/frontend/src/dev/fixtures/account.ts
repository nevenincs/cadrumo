import type { SignInRefusal, SignInStatus } from "../../ipc/contract";
import { targetOf } from "../../shell/profiles";
import {
  canSignIn,
  GATED,
  phaseOf,
  type SignInController,
} from "../../shell/signIn";

// An account controller in a fixed state, for stories. Its phase is derived
// from its status by the shell's own rule, so a story cannot show a state the
// application could not be in.

export const SIGNED_OUT: SignInStatus = {
  supported: true,
  state: "absent",
  active_profile: "Demo profile",
  runtimeAvailable: true,
  refusal: null,
};

export const refused = (
  code: string,
  retryAfterSeconds: number | null = null,
): SignInRefusal => ({ code, retryAfterSeconds });

export function accountFixture(
  rest: Partial<Omit<SignInController, "phase" | "gated" | "canSignIn">> = {},
): SignInController {
  const status = "status" in rest ? (rest.status ?? null) : SIGNED_OUT;
  const profiles = rest.profiles ?? null;
  const phase = phaseOf(true, status, profiles);
  const offering = phase === "signed-out" || phase === "no-profile";
  const target = offering ? targetOf(profiles, null) : null;
  const refusal = rest.refusal ?? status?.refusal ?? null;
  return {
    manager: null,
    recoveringServices: false,
    refusal,
    retrySeconds: 0,
    busy: false,
    startingServices: false,
    canStartServices: false,
    canInstallServices: false,
    startServices: async () => undefined,
    remaining: null,
    signOutFailure: null,
    createRefusal: null,
    createUnknown: null,
    creating: false,
    created: null,
    canCreate: profiles !== null,
    target,
    offering,
    mustChoose:
      offering &&
      profiles?.complete === true &&
      profiles.profiles.length > 0 &&
      !target,
    choose: () => undefined,
    create: async () => false,
    submit: async () => undefined,
    signOut: async () => undefined,
    settle: () => undefined,
    recheck: async () => undefined,
    tuiExited: () => undefined,
    ...rest,
    profiles,
    status,
    phase,
    gated: GATED.has(phase),
    canSignIn: canSignIn(phase),
  };
}
