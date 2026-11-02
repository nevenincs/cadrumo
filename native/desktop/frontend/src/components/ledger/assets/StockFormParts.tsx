import type { ReactNode } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { useStrings } from "../../../shell/strings";
import { WriteHold } from "../WritePause";
import { Reading } from "../setup/SetupParts";
import type { OfferState } from "./stockReads";

/** What a form says while the choices it offers are not there. */
export function OffersNote({ state }: { state: OfferState["state"] }) {
  const t = useStrings();
  if (state === "done") return null;
  return state === "loading" ? (
    <Reading label={t("desktop.ledger.stock.options_loading")} />
  ) : (
    <Alert tone="warning" role="alert" icon={<Icon name="alert" />}>
      {t("desktop.ledger.stock.options_failed")}
    </Alert>
  );
}

export function FormButtons({
  busy,
  ready,
  submit,
  onClose,
}: {
  busy: boolean;
  ready: boolean;
  submit: string;
  onClose(): void;
}) {
  const t = useStrings();
  return (
    <div className="flex flex-wrap gap-2">
      <Button
        type="button"
        size="sm"
        variant="ghost"
        aria-disabled={busy || undefined}
        onClick={() => {
          if (!busy) onClose();
        }}
      >
        {t("desktop.ledger.form.cancel")}
      </Button>
      <WriteHold>
        <Button
          type="submit"
          size="sm"
          className="ledger-stock-submit"
          aria-disabled={!ready || busy || undefined}
        >
          {busy ? t("desktop.ledger.form.saving") : submit}
        </Button>
      </WriteHold>
      {!ready && !busy && (
        <span className="self-center text-xs text-muted-foreground">
          {t("desktop.ledger.form.fill_to_continue")}
        </span>
      )}
    </div>
  );
}

/** A group of fields under a heading, inside a form. */
export function Section({
  heading,
  children,
  actions,
}: {
  heading: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <h4 className="font-medium">{heading}</h4>
        <span className="flex-1" />
        {actions}
      </div>
      {children}
    </section>
  );
}
