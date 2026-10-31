/** This run's own results directory below `results`, created on first use. */
export function testRunDirectory(results: string): string;

/** This run's own scenario bundle directory below `results`, or null outside a
 * run. */
export function testRunScenariosBuild(results: string): string | null;

/** This run's product bundle directory below `results`, or null outside a run. */
export function testRunProductBuild(results: string): string | null;

/** Test-run listeners, allocated once by the runner and read by its children. */
export function testRunPorts(results: string): {
  previewPort: number;
  scenariosPort: number;
  scenariosDocsPort: number;
  hotPort: number;
  controlPort: number;
  token: string;
} | null;

export function reserveTestRunPorts(
  results: string,
): Promise<NonNullable<ReturnType<typeof testRunPorts>>>;
export function releaseTestRunPorts(
  results: string,
  keys: string[],
): Promise<void>;
