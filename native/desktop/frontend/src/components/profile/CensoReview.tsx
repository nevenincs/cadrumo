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
import type { CensoDecision, CensoSnapshot } from "../../shell/profileCenso";
import { useStrings } from "../../shell/strings";

type Field = CensoSnapshot["fields"][number];

/** What saving the review does to one detail, as the host decided it. */
function outcomeKey(field: Field) {
  if (field.incoming === null) return "desktop.profile.censo.absent" as const;
  if (field.preserve) return "desktop.profile.censo.preserve" as const;
  return "desktop.profile.censo.adopt" as const;
}

/**
 * Every value a Censo read proposes, beside what the profile holds now and
 * what saving will do with it. The review is answered here as a whole.
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
  onAnswer(decision: Extract<CensoDecision, "apply" | "reject">): void;
}) {
  const t = useStrings();
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
                <th scope="col" className="py-1 font-medium">
                  {t("desktop.profile.censo.review_outcome")}
                </th>
              </tr>
            </thead>
            <tbody>
              {fields.map((field) => {
                const adopting = !field.preserve && field.incoming !== null;
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
                      className="py-1.5 text-muted-foreground italic"
                    >
                      {t(outcomeKey(field))}
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
          <Button disabled={busy} onClick={() => onAnswer("apply")}>
            {busy && <Spinner />}
            {t("desktop.profile.censo.apply")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
