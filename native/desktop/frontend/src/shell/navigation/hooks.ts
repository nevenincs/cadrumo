import {
  createContext,
  useContext,
  useEffect,
  useRef,
  type RefObject,
} from "react";
import type { FocusRegister } from "./focus";
import type { Guard, GuardRegister, GuardState } from "./guards";

/** The window's one guard register and focus register, for the components
 * that own work a navigation could destroy or a target it should focus. */
export type NavigationRuntime = {
  readonly guards: GuardRegister;
  readonly focus: FocusRegister;
};

export const NavigationContext = createContext<NavigationRuntime | null>(null);

/**
 * Registers the calling component as an owner of work a navigation could
 * destroy, for as long as it is mounted. `owner` is the element it belongs
 * to (see `Guard.owner`); `state` is read when a navigation is weighed, so
 * passing the current render's state is enough. `ask` and `discard` are as
 * on `Guard`; whether `ask` is given is fixed at mount.
 */
export function useNavigationGuard(
  owner: string,
  state: GuardState,
  handlers: Pick<Guard, "ask" | "discard"> = {},
): void {
  const runtime = useContext(NavigationContext);
  const latest = useRef({ state, handlers });
  latest.current = { state, handlers };
  const asks = handlers.ask !== undefined;
  useEffect(() => {
    if (!runtime) return;
    const guard: Guard = {
      owner,
      state: () => latest.current.state,
      ...(asks
        ? {
            ask: (proceed: () => void, stay: () => void) =>
              latest.current.handlers.ask?.(proceed, stay) ?? false,
          }
        : {}),
      discard: () => latest.current.handlers.discard?.(),
    };
    return runtime.guards.register(guard);
  }, [runtime, owner, asks]);
}

/**
 * Registers `ref` as the keyboard's target for register element `id` while
 * the calling component is mounted. Mounting is the signal: a navigation to
 * `id` waiting for its element focuses it then.
 */
export function useFocusTarget(
  id: string,
  ref: RefObject<HTMLElement | null>,
): void {
  const runtime = useContext(NavigationContext);
  useEffect(() => {
    if (!runtime) return;
    return runtime.focus.register(id, () => ref.current);
  }, [runtime, id, ref]);
}
