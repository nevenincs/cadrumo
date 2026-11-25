/**
 * A glob's matches by file name without its extension.
 *
 * The fixtures a glob reads are generated into the build tree and reached through an alias, and
 * how a glob spells the key of a file reached that way is the bundler's business. A story or
 * scenario names a fixture by what the generator named it.
 */
export function byName<T>(found: Record<string, T>): Record<string, T> {
  return Object.fromEntries(
    Object.entries(found).map(([path, load]) => [
      path.slice(path.lastIndexOf("/") + 1, path.lastIndexOf(".")),
      load,
    ]),
  );
}
