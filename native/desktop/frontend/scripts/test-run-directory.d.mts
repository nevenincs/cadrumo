/** This run's own results directory below `results`, created on first use. */
export function testRunDirectory(results: string): string;

/** This run's own scenario bundle directory below `results`, or null outside a
 * run. */
export function testRunScenariosBuild(results: string): string | null;

/** This run's product bundle directory below `results`, or null outside a run. */
export function testRunProductBuild(results: string): string | null;
