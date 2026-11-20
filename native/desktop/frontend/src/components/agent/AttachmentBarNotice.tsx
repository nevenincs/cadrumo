import { Button } from "@/components/ui/button";
import type { DisclosureRefusalCode } from "../../shell/attachmentAdminContract";
import { countWords, useStrings } from "../../shell/strings";

/** The refusals that come from where the window runs, not from this file or
 * this moment: no answer of the person's changes them. */
export type BarCode = Extract<
  DisclosureRefusalCode,
  "gestor_mode" | "cloud_upload_not_permitted" | "profile_not_eligible"
>;

/** A read the installation or profile keeps on this computer, as the service
 * refused it for the run `replyId`. */
export type BarredRead = {
  requestId: string;
  replyId: string;
  code: BarCode;
  name: string;
  provider: string;
};

export const isBar = (code: string): code is BarCode =>
  code === "gestor_mode" ||
  code === "cloud_upload_not_permitted" ||
  code === "profile_not_eligible";

/** Words for a bar: an installation that keeps documents here and one that
 * is in gestor mode say the same. */
export const barKey = (code: BarCode) =>
  code === "profile_not_eligible"
    ? "desktop.agent.attachment_refusal.profile_not_eligible"
    : "desktop.agent.attachment_refusal.cloud_upload_not_permitted";

const once = <Item,>(items: readonly Item[]) => [...new Set(items)];

/**
 * One notice for the files of a run that were not sent: which, why in words,
 * and where the way on is. A local model reads them on this computer, so the
 * button opens the model picker where the window offers one.
 */
export function AttachmentBarNotice({
  reads,
  onChooseModel,
}: {
  reads: readonly BarredRead[];
  /** Opens the column's model picker; absent where it offers none. */
  onChooseModel: (() => void) | undefined;
}) {
  const t = useStrings();
  if (reads.length === 0) return null;
  const names = once(reads.map((read) => read.name));
  const providers = once(reads.map((read) => read.provider)).join(", ");
  const reasons = once(reads.map((read) => t(barKey(read.code))));
  return (
    <section
      role="status"
      className="grid gap-2 rounded-xl bg-card p-3.5 text-sm shadow-raised"
    >
      <p className="font-medium text-foreground">
        {countWords(
          t,
          names.length,
          {
            one: "desktop.agent.attachment_kept_here_one",
            other: "desktop.agent.attachment_kept_here",
          },
          { count: names.length, provider: providers },
        )}
      </p>
      <ul className="list-disc pl-5 text-foreground">
        {names.map((name) => (
          <li key={name}>{name}</li>
        ))}
      </ul>
      <p className="text-muted-foreground">{reasons.join(" ")}</p>
      <p className="text-foreground">
        {countWords(t, names.length, {
          one: "desktop.agent.attachment_kept_here_way_one",
          other: "desktop.agent.attachment_kept_here_way",
        })}
      </p>
      {onChooseModel && (
        <div className="flex justify-end">
          <Button variant="outline" size="xs" onClick={onChooseModel}>
            {t("desktop.agent.attachment_kept_here_models")}
          </Button>
        </div>
      )}
    </section>
  );
}
