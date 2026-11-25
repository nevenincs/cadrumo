import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
} from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { NativeSelect } from "@/components/ui/native-select";
import type { LedgerPort } from "../../../shell/ledger";
import { useStrings } from "../../../shell/strings";
import { setupCall } from "../setup/setupModel";
import type { ProofDraft } from "./stockDraft";
import { evidenceRequest, proofFromKept } from "./stockModel";
import { refusalWords } from "./stockWords";

const FILL_IN = "desktop.ledger.assets.write.fill_in";

/** A document the person chooses with the system's file dialog. The backend
 * reads and keeps it, and answers what it keeps it as; the window holds
 * neither the file nor a mark of its own making, and shows the file's name. */
export function StockProofPicker({
  port,
  label,
  hint,
  kinds,
  proof,
  onProof,
  fillIn,
  disabled = false,
}: {
  port: LedgerPort;
  label: string;
  hint?: string;
  /** The kinds the document can be; one kind asks for no choice. */
  kinds: readonly { value: string; label: string }[];
  proof: ProofDraft;
  onProof(change: (current: ProofDraft) => ProofDraft): void;
  fillIn: boolean;
  disabled?: boolean;
}) {
  const t = useStrings();
  const [failed, setFailed] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const choose = async () => {
    if (busy) return;
    setBusy(true);
    setFailed(null);
    try {
      const picks = await port.pickFiles(
        "documents",
        "file",
        t("desktop.ledger.import.filter.documents"),
      );
      const file = picks.files[0];
      if (!file) return;
      const kept = await setupCall(
        port,
        "ledger.inventory.evidence.add",
        evidenceRequest(file.token),
        true,
      );
      await port.forgetFiles([file.token]).catch(() => undefined);
      const proofKept =
        kept.kind === "done" ? proofFromKept(kept.result, file.name) : null;
      if (proofKept !== null)
        onProof((current) => ({
          ...current,
          reference: proofKept.reference,
          digest: proofKept.digest,
          fileName: proofKept.fileName,
        }));
      // A file the book did not keep says why in the book's own sentence,
      // and what is held already stays.
      else
        setFailed(refusalWords(t, kept)() ?? t("desktop.ledger.stock.refused"));
    } catch {
      setFailed(t("desktop.ledger.stock.refused"));
    } finally {
      setBusy(false);
    }
  };
  const shown = failed ?? (fillIn ? t(FILL_IN) : null);
  const word =
    proof.digest === ""
      ? t("desktop.ledger.stock.proof.choose_file")
      : t("desktop.ledger.stock.proof.change_file");
  return (
    <Field data-invalid={shown ? true : undefined}>
      <FieldLabel>{label}</FieldLabel>
      <div className="flex flex-wrap items-center gap-2">
        {kinds.length > 1 && (
          <NativeSelect
            controlSize="sm"
            aria-label={t("desktop.ledger.stock.proof.kind")}
            value={proof.kind}
            onChange={(event) =>
              onProof((current) => ({
                ...current,
                kind: event.target.value,
              }))
            }
          >
            <option value="" disabled>
              {t("desktop.ledger.form.choose")}
            </option>
            {kinds.map((kind) => (
              <option key={kind.value} value={kind.value}>
                {kind.label}
              </option>
            ))}
          </NativeSelect>
        )}
        <Button
          type="button"
          size="sm"
          variant="outline"
          aria-label={`${label}: ${word}`}
          aria-disabled={busy || disabled || undefined}
          onClick={() => {
            if (!disabled) void choose();
          }}
        >
          <Icon name="attach" size="sm" />
          {busy ? t("desktop.ledger.stock.proof.keeping") : word}
        </Button>
        {proof.digest !== "" && (
          <span className="flex items-center gap-1 text-sm text-muted-foreground">
            <Icon name="check" size="sm" />
            {proof.fileName ?? t("desktop.ledger.stock.proof.kept")}
          </span>
        )}
      </div>
      {hint && <FieldDescription>{hint}</FieldDescription>}
      <FieldError>{shown}</FieldError>
    </Field>
  );
}
