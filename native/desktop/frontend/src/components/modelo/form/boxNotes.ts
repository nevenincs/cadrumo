import type {
  ModeloFormIssueLine,
  PublicModeloFormField,
} from "../../../shell/modeloContract/modeloWorkForm";
import { addressKey, fieldKey } from "./session";

/** What the latest calculation noted about each box the form shows, by the
 * box's key, in the order the read model lists its lines: most urgent first.
 * A line the read model leads to no box, or to the records of a table, has
 * no box to stand beside; the check's lines list it. */
export type BoxNotes = ReadonlyMap<string, readonly ModeloFormIssueLine[]>;

export function boxNotes(lines: readonly ModeloFormIssueLine[]): BoxNotes {
  const notes = new Map<string, ModeloFormIssueLine[]>();
  for (const line of lines) {
    if (!line.from_calculation || line.in_records || !line.address) continue;
    const key = addressKey(line.address);
    const held = notes.get(key);
    if (held) held.push(line);
    else notes.set(key, [line]);
  }
  return notes;
}

const NONE: readonly ModeloFormIssueLine[] = [];

/** The notes beside one box, none when the calculation noted nothing there. */
export const notesOf = (
  notes: BoxNotes,
  field: PublicModeloFormField,
): readonly ModeloFormIssueLine[] => notes.get(fieldKey(field)) ?? NONE;
