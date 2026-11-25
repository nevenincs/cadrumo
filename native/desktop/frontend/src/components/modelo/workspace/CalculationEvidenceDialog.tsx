import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScopedWriteHoldNotice } from "../WriteScope";
import { useStrings } from "../../../shell/strings";
import type { CalculationEvidenceAnswer } from "./calculationEvidence";

export function CalculationEvidenceDialog({
  asksModelo390,
  busy,
  held,
  onCancel,
  onConfirm,
}: {
  asksModelo390: boolean;
  busy: boolean;
  held: boolean;
  onCancel(): void;
  onConfirm(answer: CalculationEvidenceAnswer): void;
}) {
  const t = useStrings();
  const [joint, setJoint] = useState<boolean | null>(null);
  const [observedAt, setObservedAt] = useState<string | null>(null);
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !busy) onCancel();
      }}
    >
      <DialogContent
        closeLabel={t("workspace.modelo.calculate.evidence.cancel")}
      >
        <DialogHeader>
          <DialogTitle>
            {t("workspace.modelo.calculate.evidence.title")}
          </DialogTitle>
          <DialogDescription>
            {t("workspace.modelo.calculate.evidence.description")}
          </DialogDescription>
        </DialogHeader>
        <fieldset disabled={busy || held} className="flex flex-col gap-3">
          <legend className="mb-3 text-sm font-medium">
            {t("workspace.modelo.calculate.evidence.joint_return")}
          </legend>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name="joint-return"
              checked={joint === true}
              onChange={() => setJoint(true)}
            />
            {t("workspace.modelo.calculate.evidence.yes")}
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name="joint-return"
              checked={joint === false}
              onChange={() => setJoint(false)}
            />
            {t("workspace.modelo.calculate.evidence.no")}
          </label>
          {asksModelo390 && (
            <>
              <p className="text-sm text-muted-foreground">
                {t("workspace.modelo.calculate.evidence.modelo_390_hint")}
              </p>
              <label className="flex items-start gap-2 text-sm">
                <Checkbox
                  checked={observedAt !== null}
                  onChange={(event) =>
                    setObservedAt(
                      event.target.checked ? new Date().toISOString() : null,
                    )
                  }
                />
                {t("workspace.modelo.calculate.evidence.modelo_390_confirm")}
              </label>
            </>
          )}
        </fieldset>
        <ScopedWriteHoldNotice />
        <DialogFooter>
          <Button variant="ghost" disabled={busy} onClick={onCancel}>
            {t("workspace.modelo.calculate.evidence.cancel")}
          </Button>
          <Button
            disabled={
              busy ||
              held ||
              joint === null ||
              (asksModelo390 && observedAt === null)
            }
            onClick={() => {
              if (joint !== null) onConfirm({ jointReturn: joint, observedAt });
            }}
          >
            {t("workspace.modelo.calculate.evidence.calculate")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
