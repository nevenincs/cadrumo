import { createContext, useContext } from "react";
import type { CommitKey } from "@/components/ui/dataGridModel";
import type {
  ModeloWorkbenchFormProjectionV1,
  PublicModeloFormField,
  SourceSurface,
} from "../../../shell/modeloContract";
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
  /** Whether the reader sees the form in another language than its own, so
   * a label still in Spanish says so. */
  translated: boolean;
};

export const FormContext = createContext<FormContextValue | null>(null);

export function useForm(): FormContextValue {
  const value = useContext(FormContext);
  if (!value) throw new Error("A form block is drawn outside its form.");
  return value;
}
