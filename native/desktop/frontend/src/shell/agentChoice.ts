import { useCallback, useEffect, useState } from "react";
import type { AgentSelection } from "@/components/agent/types";

// The last provider, way into it, model and effort the person chose for the
// agent, kept for each profile in the shell's browser storage, so a new
// conversation starts with it after a restart or a new sign-in. It holds only
// the catalog's ids, never a message or a credential, and it is a starting
// point only: whoever reads it checks it against the catalog the agent serves
// now, so a choice the catalog no longer offers is never run.
//
// The storage key is a digest of the profile's name, so the storage names no
// profile. Storage may be missing, cleared, read-only or written by an older
// shell; the column then starts where the catalog says it does.

const STORE = "cadrumo-agent-choice";
const VERSION = 1;
// The longest id kept: a model id the agent accepts (agent/spec.py
// `MAX_MODEL_ID_CHARS`) is the longest of them.
const ID_MAX = 512;

async function storeKey(reader: string): Promise<string> {
  const bytes = new TextEncoder().encode(`${STORE}\u0000${reader}`);
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  const hex = [...digest]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
  return `${STORE}:${hex}`;
}

const isId = (value: unknown, empty = false): value is string =>
  typeof value === "string" &&
  value.length <= ID_MAX &&
  (empty || value.length > 0);

function readChoice(key: string): AgentSelection | null {
  let raw: unknown;
  try {
    raw = JSON.parse(localStorage.getItem(key) ?? "null");
  } catch {
    return null;
  }
  if (!raw || typeof raw !== "object") return null;
  const held = raw as Record<string, unknown>;
  if (
    held.version !== VERSION ||
    !isId(held.providerId) ||
    !isId(held.wayId) ||
    !isId(held.modelId, true) ||
    (held.effort !== undefined && !isId(held.effort))
  )
    return null;
  return {
    providerId: held.providerId,
    wayId: held.wayId,
    modelId: held.modelId,
    ...(held.effort !== undefined ? { effort: held.effort } : {}),
  };
}

function writeChoice(key: string, choice: AgentSelection): void {
  try {
    localStorage.setItem(
      key,
      JSON.stringify({
        version: VERSION,
        providerId: choice.providerId,
        wayId: choice.wayId,
        modelId: choice.modelId,
        ...(choice.effort !== undefined ? { effort: choice.effort } : {}),
      }),
    );
  } catch {
    // Not kept: the next start begins where the catalog says.
  }
}

/**
 * The choice `reader` last made, and the way to keep a new one. Null while
 * nobody is signed in, while the profile's key is being worked out, and
 * where nothing was kept.
 */
export function useRememberedChoice(reader: string | null): {
  remembered: AgentSelection | null;
  remember: (choice: AgentSelection) => void;
} {
  const [held, setHeld] = useState<{
    reader: string;
    key: string;
    choice: AgentSelection | null;
  } | null>(null);
  useEffect(() => {
    if (reader === null) return;
    let current = true;
    storeKey(reader).then(
      (key) => {
        if (current) setHeld({ reader, key, choice: readChoice(key) });
      },
      () => {
        // No digest, no key: nothing is kept for this profile.
      },
    );
    return () => {
      current = false;
    };
  }, [reader]);
  const owned = held !== null && held.reader === reader ? held : null;
  const remember = useCallback(
    (choice: AgentSelection) => {
      if (!owned) return;
      writeChoice(owned.key, choice);
      setHeld({ ...owned, choice });
    },
    [owned],
  );
  return { remembered: owned?.choice ?? null, remember };
}
