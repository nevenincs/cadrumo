import { invoke } from "@tauri-apps/api/core";
import type {
  HostCommand,
  HostCommands,
  HostResult,
  ShellToken,
} from "../ipc/contract";

/** A JSON-argument host command, typed end to end by the published contract. */
export type HostCall = <C extends HostCommand>(
  command: C,
  args: Omit<HostCommands[C]["args"], "token">,
) => Promise<HostResult<C>>;

/** Every JSON command goes through this call, which adds the launch token.
 * Typing the arguments by `HostCommands` makes a misnamed argument a compile
 * error instead of a refusal at run time. */
export function hostCall(token: ShellToken | null): HostCall {
  return (command, args) =>
    token
      ? invoke(command, { ...args, token })
      : Promise.reject(
          new Error("The desktop host did not provide a launch token."),
        );
}
