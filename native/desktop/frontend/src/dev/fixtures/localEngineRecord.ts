import type {
  AgentLocalEngineToken,
  AgentLocalPlacement,
} from "../../ipc/contract";

// The made-up service's local engine record, which its catalogue, its
// provider settings and its local model lists all read, as the service reads
// one stored record for all three. The service, not the window, decides which
// engine's keyless lane is served: a lane named for a local engine is served
// only while that engine is the selected one, and every other lane whatever
// the engine.

/** The local engines, as the service names them. */
export const FIXTURE_ENGINES = [
  "llamacpp",
  "ollama",
] as const satisfies readonly AgentLocalEngineToken[];

/** The engine a scenario starts with unless it names another. */
export const FIXTURE_DEFAULT_ENGINE: AgentLocalEngineToken = "llamacpp";

export type FixtureEngineChoice = {
  engine: AgentLocalEngineToken;
  placement: AgentLocalPlacement;
};

/** The one record the made-up service's surfaces read the engine from. */
export type FixtureEngineRecord = {
  read(): FixtureEngineChoice;
  write(choice: FixtureEngineChoice): void;
};

export function fixtureEngineRecord(
  engine: AgentLocalEngineToken = FIXTURE_DEFAULT_ENGINE,
): FixtureEngineRecord {
  let held: FixtureEngineChoice = { engine, placement: "auto" };
  return {
    read: () => ({ ...held }),
    write(choice) {
      held = { ...choice };
    },
  };
}

/** Whether the service serves the lane of `provider` while `engine` is
 * selected. */
export function servesEngineLane(
  provider: string,
  engine: AgentLocalEngineToken,
): boolean {
  return (
    !(FIXTURE_ENGINES as readonly string[]).includes(provider) ||
    provider === engine
  );
}
