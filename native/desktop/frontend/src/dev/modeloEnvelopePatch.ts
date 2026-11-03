// A Modelo 100 form is over three megabytes, and the filers and languages
// read of it differ in a few hundred words, so scripts/modelo-fixtures.mjs
// stores all but one of them as a patch of the envelope it differs from:
// `{ patch_of: <name>, changes }`. `changes` mirrors the envelope. An object
// holds the changes by key, or by position where the envelope holds a list,
// and a one-element array is the value that replaces what stood there. The
// whole envelope is what applying the changes to the one it names makes; no
// envelope is read in a way that tells it from one stored whole.

/** Every envelope by name, each read on first use. */
export type StoredEnvelopes = Record<string, () => Promise<unknown>>;

type Patch = { patch_of: string; changes: unknown };

function isPatch(value: unknown): value is Patch {
  if (typeof value !== "object" || value === null || Array.isArray(value))
    return false;
  const keys = Object.keys(value);
  return (
    keys.length === 2 && keys.includes("patch_of") && keys.includes("changes")
  );
}

/** `base` with `changes` applied; `base` itself is left as it is. */
export function patched(base: unknown, changes: unknown): unknown {
  if (Array.isArray(changes)) return changes[0];
  const copy = (
    Array.isArray(base) ? [...(base as unknown[])] : { ...(base as object) }
  ) as Record<string, unknown>;
  for (const [key, change] of Object.entries(
    changes as Record<string, unknown>,
  ))
    copy[key] = patched(copy[key], change);
  return copy;
}

/** The same envelopes, each whole whether it is stored whole or as a patch. */
export function wholeEnvelopes(stored: StoredEnvelopes): StoredEnvelopes {
  const whole: StoredEnvelopes = {};
  for (const [name, load] of Object.entries(stored))
    whole[name] = async () => {
      const read = await load();
      if (!isPatch(read)) return read;
      const base = whole[read.patch_of];
      if (!base) throw new Error(`${name} is a patch of ${read.patch_of}`);
      return patched(await base(), read.changes);
    };
  return whole;
}
