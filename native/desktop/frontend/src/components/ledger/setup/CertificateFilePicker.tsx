import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
} from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import type { LedgerPort, PickedFile } from "../../../shell/ledger";
import { useStrings } from "../../../shell/strings";

/**
 * The certificate file a person chooses with the system's file dialog. The
 * backend reads it when the record is sent and keeps its bytes in the
 * profile's encrypted custody; the window holds the host's token for the
 * pick and the file's name, never the file or its path.
 */
export function CertificateFilePicker({
  port,
  file,
  onFile,
  disabled = false,
}: {
  port: LedgerPort;
  file: PickedFile | null;
  /** The file now chosen, or `null` once it is set aside. */
  onFile(next: PickedFile | null): void;
  disabled?: boolean;
}) {
  const t = useStrings();
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const forget = (held: PickedFile) =>
    port.forgetFiles([held.token]).catch(() => undefined);
  const choose = async () => {
    if (busy) return;
    setBusy(true);
    setFailed(false);
    try {
      const picks = await port.pickFiles(
        "documents",
        "file",
        t("desktop.ledger.import.filter.documents"),
      );
      const picked = picks.files[0];
      if (!picked) return;
      if (file) void forget(file);
      onFile(picked);
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };
  const word = file
    ? t("desktop.ledger.withholding.file_change")
    : t("desktop.ledger.withholding.file_choose");
  return (
    <Field
      data-invalid={failed ? true : undefined}
      className="ledger-withholding-file"
    >
      <FieldLabel>{t("desktop.ledger.withholding.file")}</FieldLabel>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="ledger-withholding-file-choose"
          aria-label={`${t("desktop.ledger.withholding.file")}: ${word}`}
          aria-disabled={busy || disabled || undefined}
          onClick={() => {
            if (!disabled) void choose();
          }}
        >
          <Icon name="attach" size="sm" />
          {word}
        </Button>
        {file && (
          <>
            <span className="ledger-withholding-file-name flex items-center gap-1 text-sm text-muted-foreground">
              <Icon name="check" size="sm" />
              {file.name}
            </span>
            <Button
              type="button"
              size="xs"
              variant="ghost"
              className="ledger-withholding-file-clear"
              aria-disabled={disabled || undefined}
              onClick={() => {
                if (disabled) return;
                void forget(file);
                onFile(null);
              }}
            >
              {t("desktop.ledger.withholding.file_clear")}
            </Button>
          </>
        )}
      </div>
      <FieldDescription>
        {t("desktop.ledger.withholding.file_hint")}
      </FieldDescription>
      <FieldError>
        {failed ? t("desktop.ledger.withholding.file_failed") : null}
      </FieldError>
    </Field>
  );
}
