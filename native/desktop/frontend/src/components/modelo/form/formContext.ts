import { createContext, useContext } from "react";
import type { CommitKey } from "@/components/ui/dataGridModel";
import type { SourceSurface } from "../../../shell/modeloContract/modeloWork";
import type {
  ModeloWorkbenchFormProjectionV1,
  PublicModeloFormField,
} from "../../../shell/modeloContract/modeloWorkForm";
import type { BoxNotes } from "./boxNotes";
import type { FormSession } from "./session";
import type { EditRequest } from "./ValueCell";

/** What every block of the form draws from: the read, its working state,
 * and which box's editor is open. */
export type FormContextValue = {
  envelope: ModeloWorkbenchFormProjectionV1;
  session: FormSession;
  /** `fieldKey` of the box whose editor is open, and how it opened. */
  editing: { key: string; request: EditRequest } | null;
  setEditing: (key: string | null, request?: EditRequest) => void;
  /** A box's editor closed; the form moves on to match. */
  onDone: (field: PublicModeloFormField, how: CommitKey | "cancel") => void;
  onOpenSurface?: (surface: SourceSurface) => void;
  /** Whether the window can open an area; a box links only to one it can. */
  canOpenSurface: (surface: OpenableSurface) => boolean;
  /** What the latest calculation noted beside each box, as the read model
   * lists it. */
  notes: BoxNotes;
  /** Whether the reader sees the form in another language than its own, so
   * a label still in Spanish says so. */
  translated: boolean;
};

/** An area a source-fed value is kept and corrected in. */
export type OpenableSurface = Exclude<SourceSurface, "none">;

export const FormContext = createContext<FormContextValue | null>(null);

export function useForm(): FormContextValue {
  const value = useContext(FormContext);
  if (!value) throw new Error("A form block is drawn outside its form.");
  return value;
}

/** The area a box's source is corrected in, where the form can open it;
 * null where its source names none or the window has no page for it. */
export function openableSurface(
  form: FormContextValue,
  field: PublicModeloFormField,
): OpenableSurface | null {
  const surface = field.bindings[0]?.policy.surface;
  return surface && surface !== "none" && form.onOpenSurface
    ? form.canOpenSurface(surface)
      ? surface
      : null
    : null;
}
