/** The seeder's record of the window projections, in their directory. */
export const WINDOW_INDEX: string;

/**
 * Write a project file that extends the frontend's tsconfig.json with every
 * path alias spelled absolutely and @fixtures bound to this build's window
 * projections, and return its path.
 */
export function writeAliasProject(destination: string): string;
