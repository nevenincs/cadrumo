import {
  createContext,
  useContext,
  useEffect,
  useRef,
  type RefObject,
} from "react";
import type { FocusRegister } from "./focus";
import type { Guard, GuardRegister, GuardState } from "./guards";
import type { ViewParams } from "./register";
import type { RevealRegister, ViewParamsHandler } from "./reveal";

/** The window's one guard, focus and reveal register, for the components
 * that own work a navigation could destroy, a target it should focus or
 * the parameters it carries. */
export type NavigationRuntime = {
  readonly guards: GuardRegister;
  readonly focus: FocusRegister;
  readonly reveal: RevealRegister;
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
 * Registers `target` as the keyboard's target for register element `id`
 * while the calling component is mounted: an element's ref, or a function
 * that finds the element when focus is asked of it. Mounting is the signal:
 * a navigation to `id` waiting for its element focuses it then.
 */
export function useFocusTarget(
  id: string,
  target: RefObject<HTMLElement | null> | (() => HTMLElement | null),
): void {
  const runtime = useContext(NavigationContext);
  const latest = useRef(target);
  latest.current = target;
  useEffect(() => {
    if (!runtime) return;
    return runtime.focus.register(id, () => {
      const held = latest.current;
      return typeof held === "function" ? held() : held.current;
    });
  }, [runtime, id]);
}

/**
 * Hands the parameters of every navigation to register element `id` (such
 * as `select`) to `handler`, while the calling component is mounted. A
 * navigation that applied before the component mounted is handed over on
 * mount. The handler is read when it runs, so the current render's is used.
 */
export function useViewParams(
  id: string,
  handler: (params: ViewParams) => void,
): void {
  const runtime = useContext(NavigationContext);
  const latest = useRef(handler);
  latest.current = handler;
  useEffect(() => {
    if (!runtime) return;
    const handle: ViewParamsHandler = (params) => latest.current(params);
    return runtime.reveal.register(id, handle);
  }, [runtime, id]);
}
