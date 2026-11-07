// The generated window projections are build output that `just fixtures-seed`
// writes; a tree that was never seeded makes every glob over them match
// nothing. A development page or story must not read that as "no data".

/** The projections a glob found, or an error naming the command that writes
 * them when it found none. */
export function requireServed<T>(
  family: string,
  found: Record<string, T>,
): Record<string, T> {
  if (Object.keys(found).length === 0)
    throw new Error(
      `No generated window fixture matches ${family}; run \`just fixtures-seed\` to produce it`,
    );
  return found;
}
