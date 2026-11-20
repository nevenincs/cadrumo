// How the scenario agent is set up: the choices a scenario makes about its
// stream, what it asks, what it stores and what the made-up computer holds.

/** How the fixture stream behaves: in order, with one frame sent twice, as a
 * resumed stream does; or with the stream lost once, as one the host could not
 * resume is, which the column recovers by reading the history and what is
 * pending again and watching anew. */
export type FixtureStream = "steady" | "gap";

/** What every fixture reply stops to wait on, if anything: questions, or a
 * tool the agent wants to use. */
export type FixtureAsks = "questions" | "approval";

/** What the conversations have stored: the fixture documents, nothing at
 * all, storage the host does not serve, or storage that cannot be read. */
export type FixtureDocuments = "stored" | "none" | "unavailable" | "failed";
/** Which of the local lane's models the made-up computer holds: none, as
 * before any setup, or all, as after every download. */
export type FixtureLocalModels = "none" | "all";

/** What the made-up service offers to choose among for the local engine and
 * its placement, where not every engine and placement it knows: each list is
 * served as written. */
export type FixtureEngineChoices = {
  engines?: readonly string[];
  placements?: readonly string[];
};
