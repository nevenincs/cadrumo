// The guard register: what a navigation would destroy. Every owner of
// unsaved or in-flight work registers here with the element it belongs to,
// and every navigation (a link, the palette, the rail, a page, sign-out, a
// profile switch, the window's close) is weighed against it before it
// applies. The register holds no navigation of its own; the navigator asks.

/** What an owner would lose if it were taken down now. */
export type GuardState =
  /** Nothing: let the navigation through. */
  | "clean"
  /** Staged or drafted values: ask once whether to discard them or stay. */
  | "dirty"
  /** An effect in flight whose outcome the owner must show: refuse. */
  | "busy"
  /** An open dialog or credential form: stand down and keep it. */
  | "modal";

export type Guard = {
  /** The element the owner belongs to, by the id the window mounts it
   * under: a register id such as `ledger` or `ledger/invoices`, or one of
   * the window's own pages. `window` belongs to no page and is never taken
   * down by a navigation, only by sign-out, a profile switch or the close. */
  readonly owner: string;
  state(): GuardState;
  /** Optional: the owner's own way of asking about dirty work. It returns
   * false when, on looking, there was nothing to ask about; otherwise it
   * calls exactly one of `proceed` (discarded) or `stay`. Without it, the
   * navigator asks with its shared discard-or-stay prompt and, on discard,
   * calls `discard`. */
  ask?(proceed: () => void, stay: () => void): boolean;
  /** Drops the owner's dirty work; called before a navigation the person
   * chose to let through the shared prompt. */
  discard?(): void;
};

/** Which navigations are being weighed: one that shows something, or one
 * that takes everything down. */
export type Leaving =
  | { readonly kind: "navigate"; readonly unmounted: ReadonlySet<string> }
  | { readonly kind: "sign_out" | "switch" | "close" };

export type Assessment = {
  readonly modal: readonly Guard[];
  readonly busy: readonly Guard[];
  readonly dirty: readonly Guard[];
};

/** What the navigator does about a navigation, given the guards' states. */
export type Decision =
  | { readonly kind: "proceed" }
  /** Refused with a toast; nothing is asked and nothing changes. */
  | { readonly kind: "refuse"; readonly reason: "modal" | "busy" }
  /** The close asks whether to close over work still in flight. */
  | { readonly kind: "ask_busy_close" }
  /** Ask the dirty owners once whether to discard. */
  | { readonly kind: "ask_dirty"; readonly owners: readonly Guard[] };

export class GuardRegister {
  private readonly guards = new Set<Guard>();

  /** Adds an owner; the returned function removes exactly this one. */
  register(guard: Guard): () => void {
    this.guards.add(guard);
    return () => {
      this.guards.delete(guard);
    };
  }

  /** The owners a navigation would take down, by state. A modal owner
   * counts wherever it is: a dialog anywhere holds every navigation. */
  assess(leaving: Leaving): Assessment {
    const modal: Guard[] = [];
    const busy: Guard[] = [];
    const dirty: Guard[] = [];
    for (const guard of this.guards) {
      const state = guard.state();
      if (state === "modal") {
        modal.push(guard);
        continue;
      }
      const takenDown =
        leaving.kind !== "navigate" || leaving.unmounted.has(guard.owner);
      if (!takenDown) continue;
      if (state === "busy") busy.push(guard);
      else if (state === "dirty") dirty.push(guard);
    }
    return { modal, busy, dirty };
  }
}

/** The navigator's answer to one assessment. A modal owner always stands
 * the navigation down. Work in flight refuses it without override, except
 * the window's close, which asks, because a second close still closes. */
export function decide(leaving: Leaving, assessed: Assessment): Decision {
  if (assessed.modal.length > 0) return { kind: "refuse", reason: "modal" };
  if (assessed.busy.length > 0)
    return leaving.kind === "close"
      ? { kind: "ask_busy_close" }
      : { kind: "refuse", reason: "busy" };
  if (assessed.dirty.length > 0)
    return { kind: "ask_dirty", owners: assessed.dirty };
  return { kind: "proceed" };
}
