import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import { useEffect, useState } from "react";
import type { CensoDecision, CensoSnapshot } from "../../shell/profileCenso";
import { useStrings } from "../../shell/strings";

type Field = CensoSnapshot["fields"][number];

/** What saving the review does to one detail, given the operator's choice. */
function outcomeKey(field: Field, accepted: boolean) {
  if (field.incoming === null) return "desktop.profile.censo.absent" as const;
  if (!accepted) return "desktop.profile.censo.preserve" as const;
  return "desktop.profile.censo.adopt" as const;
}
/** The host's own proposal for a value: adopt it unless it keeps the answer. */
const proposed = (field: Field) => !field.preserve && field.incoming !== null;

/**
 * Every value a Censo read proposes, beside what the profile holds now and
 * what saving will do with it. Each value the read states is accepted or
 * rejected on its own, starting from the host's proposal; the review is then
 * saved with the accepted ones or discarded as a whole.
 */
export function CensoReview({
  open,
  onOpenChange,
  fields,
  label,
  busy,
  onAnswer,
}: {
  open: boolean;
  onOpenChange(open: boolean): void;
  fields: Field[];
  /** The profile's own name for a detail's path. */
  label(path: string): string;
  busy: boolean;
  onAnswer(
    decision: Extract<CensoDecision, "apply" | "reject">,
    accepted?: string[],
  ): void;
}) {
  const t = useStrings();
  const [choices, setChoices] = useState<Record<string, boolean>>({});
  // Each time the review opens, or another one arrives, the choices start
  // from what the host proposes.
  useEffect(() => {
    setChoices(Object.fromEntries(fields.map((f) => [f.path, proposed(f)])));
  }, [open, fields]);
  const accepts = (field: Field) =>
    field.incoming !== null && (choices[field.path] ?? proposed(field));
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        data-censo-review
        className="grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden sm:max-w-3xl"
        closeLabel={t("desktop.profile.close_dialog")}
      >
        <DialogHeader>
          <DialogTitle>{t("desktop.profile.censo.review_title")}</DialogTitle>
          <DialogDescription>
            {t("desktop.profile.censo.review_description")}
          </DialogDescription>
        </DialogHeader>
        <div className="min-h-0 overflow-y-auto">
          <table className="w-full border-collapse text-sm">
            <thead className="sticky top-0 bg-background text-left text-muted-foreground">
              <tr>
                <th scope="col" className="py-1 pr-3 font-medium">
                  {t("desktop.profile.censo.review_field")}
                </th>
                <th scope="col" className="py-1 pr-3 font-medium">
                  {t("desktop.profile.censo.review_current")}
                </th>
                <th scope="col" className="py-1 pr-3 font-medium">
                  {t("desktop.profile.censo.incoming")}
                </th>
                <th scope="col" className="py-1 pr-3 font-medium">
                  {t("desktop.profile.censo.review_outcome")}
                </th>
                <td className="py-1" aria-hidden />
              </tr>
            </thead>
            <tbody>
              {fields.map((field) => {
                const adopting = accepts(field);
                return (
                  <tr
                    key={field.path}
                    data-censo-field={field.path}
                    className="border-t align-top"
                  >
                    <th
                      scope="row"
                      className="py-1.5 pr-3 text-left font-normal text-muted-foreground"
                    >
                      {label(field.path)}
                    </th>
                    <td
                      data-part="current"
                      className={cn(
                        "py-1.5 pr-3 break-words",
                        adopting &&
                          field.current !== null &&
                          "line-through decoration-1",
                        field.current === null && "text-muted-foreground",
                      )}
                    >
                      {field.current ?? t("desktop.profile.not_set")}
                    </td>
                    <td
                      data-part="incoming"
                      className={cn(
                        "py-1.5 pr-3 break-words",
                        field.incoming === null
                          ? "text-muted-foreground"
                          : "font-medium text-foreground",
                      )}
                    >
                      {field.incoming ?? "–"}
                    </td>
                    <td
                      data-part="outcome"
                      className="py-1.5 pr-3 text-muted-foreground italic"
                    >
                      {t(outcomeKey(field, adopting))}
                    </td>
                    <td data-part="choice" className="py-1">
                      {field.incoming !== null && (
                        <div
                          role="group"
                          aria-label={label(field.path)}
                          className="flex gap-1"
                        >
                          {(["accept", "reject"] as const).map((choice) => (
                            <Button
                              key={choice}
                              size="xs"
                              variant={
                                (choice === "accept") === adopting
                                  ? "primary"
                                  : "outline"
                              }
                              data-choice={choice}
                              aria-pressed={(choice === "accept") === adopting}
                              disabled={busy}
                              onClick={() =>
                                setChoices((now) => ({
                                  ...now,
                                  [field.path]: choice === "accept",
                                }))
                              }
                            >
                              {t(
                                choice === "accept"
                                  ? "desktop.profile.censo.choice_accept"
                                  : "desktop.profile.censo.choice_reject",
                              )}
                            </Button>
                          ))}
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            disabled={busy}
            onClick={() => onAnswer("reject")}
          >
            {t("desktop.profile.censo.reject")}
          </Button>
          <Button
            variant="outline"
            disabled={busy}
            onClick={() =>
              setChoices(
                Object.fromEntries(
                  fields.map((f) => [f.path, f.incoming !== null]),
                ),
              )
            }
          >
            {t("desktop.profile.censo.accept_all")}
          </Button>
          <Button
            disabled={busy}
            onClick={() =>
              onAnswer(
                "apply",
                fields.filter(accepts).map((field) => field.path),
              )
            }
          >
            {busy && <Spinner />}
            {t("desktop.profile.censo.apply")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
