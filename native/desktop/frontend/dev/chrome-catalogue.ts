/** Bundle encoding only: the generated catalogue remains the authority. */
const record = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);

const literal = (value: unknown) =>
  JSON.stringify(value)
    .replace(/</g, "\\u003c")
    .replace(/\u2028/g, "\\u2028")
    .replace(/\u2029/g, "\\u2029");

/** Share the repeated key vector without changing the synchronous map API.
 * Refuse catalogue drift rather than omit keys or invent fallback values. */
export function chromeCatalogueModule(catalogue: unknown): string {
  if (!record(catalogue))
    throw new TypeError("Desktop chrome must be a locale map");
  const languages = Object.keys(catalogue);
  let keys: string[] | undefined;
  const values: string[][] = [];
  for (const language of languages) {
    const entries = catalogue[language];
    if (!record(entries))
      throw new TypeError(
        `Desktop chrome locale ${language} must be a string map`,
      );
    const ownKeys = Object.keys(entries);
    keys ??= ownKeys;
    const sharedKeys = keys;
    if (
      ownKeys.length !== sharedKeys.length ||
      ownKeys.some((key, index) => key !== sharedKeys[index])
    )
      throw new TypeError(
        `Desktop chrome locale ${language} has different ordered keys`,
      );
    values.push(
      keys.map((key) => {
        const value = entries[key];
        if (typeof value !== "string")
          throw new TypeError(
            `Desktop chrome value ${language}.${key} must be text`,
          );
        return value;
      }),
    );
  }
  return `const keys=${literal(keys ?? [])};
const languages=${literal(languages)};
const values=${literal(values)};
export default Object.fromEntries(languages.map((language,index)=>[
  language,Object.fromEntries(keys.map((key,column)=>[key,values[index][column]]))
]));`;
}
