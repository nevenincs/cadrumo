import { useState } from "react";
import type { MovementDraft, ProofDraft } from "./stockDraft";
import type { StockField } from "./stockFieldDefinitions";
import type { ProofSlotKey } from "./stockVocabulary";

/** The document a change of a proof is for: a slot of the purchase, or the
 * extra cost with the key it was minted. */
type ProofTarget = { slot: ProofSlotKey } | { extra: string };

/** What a movement form holds: what is typed, the extra costs and the files
 * kept. */
export function useMovementDraft(initial: MovementDraft) {
  const [draft, setDraft] = useState<MovementDraft>(initial);
  const setValue = (field: StockField, value: string) =>
    setDraft((current) => ({
      ...current,
      values: { ...current.values, [field.key]: value },
    }));
  const setExtra = (key: string, field: string, value: string) =>
    setDraft((current) => ({
      ...current,
      extras: current.extras.map((extra) =>
        extra.key === key ? { ...extra, [field]: value } : extra,
      ),
    }));
  const setProof = (
    target: ProofTarget,
    change: (current: ProofDraft) => ProofDraft,
  ) => {
    setDraft((current) =>
      "slot" in target
        ? {
            ...current,
            proofs: {
              ...current.proofs,
              [target.slot]: change(current.proofs[target.slot]),
            },
          }
        : {
            ...current,
            extras: current.extras.map((extra) =>
              extra.key === target.extra
                ? { ...extra, proof: change(extra.proof) }
                : extra,
            ),
          },
    );
  };
  return { draft, setDraft, setValue, setExtra, setProof };
}

export type MovementDraftState = ReturnType<typeof useMovementDraft>;

/** A reference for a draft the window sends and never shows. */
export const mint = () => crypto.randomUUID();
