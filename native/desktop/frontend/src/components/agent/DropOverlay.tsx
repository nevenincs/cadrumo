import { Fragment } from "react";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { Kbd } from "@/components/ui/kbd";
import { useStrings } from "../../shell/strings";

/** The modifier that arms a drop, as the keycap shows it. */
const DROP_KEY = "Shift";

/** Puts a keycap where a sentence names the key. */
function withKeycap(sentence: string) {
  const parts = sentence.split("{key}");
  return parts.map((part, index) => (
    <Fragment key={index}>
      {part}
      {index < parts.length - 1 && <Kbd>{DROP_KEY}</Kbd>}
    </Fragment>
  ));
}

/**
 * What covers the agent column while files are dragged over it. Armed, the
 * drop would add them: the edge turns solid and says how many. It takes no
 * pointer events; whatever handles the drag owns the drop.
 */
export function DropOverlay({
  visible,
  armed = false,
  fileCount,
  acceptedTypes,
  locale,
}: {
  visible: boolean;
  armed?: boolean;
  /** The files being dragged, where the platform says. */
  fileCount?: number;
  /** The file types the conversation takes, by extension, e.g. "PDF". */
  acceptedTypes?: readonly string[];
  locale: string;
}) {
  const t = useStrings();
  if (!visible) return null;
  const release =
    fileCount === undefined || fileCount < 1
      ? t("desktop.agent.drop_release")
      : fileCount === 1
        ? t("desktop.agent.drop_release_single")
        : t("desktop.agent.drop_release_multiple", { count: fileCount });
  const types =
    acceptedTypes && acceptedTypes.length > 0
      ? new Intl.ListFormat(locale, { type: "unit" }).format(acceptedTypes)
      : null;
  return (
    <div
      data-armed={armed || undefined}
      className="pointer-events-none absolute inset-0 z-(--layer-pinned) flex p-2"
    >
      <div
        role="status"
        className={cn(
          "flex flex-1 flex-col items-center justify-center gap-2 rounded-xl border-2 bg-background/90 p-6 text-center text-balance transition-colors",
          armed
            ? "border-solid border-foreground"
            : "border-dashed border-border-strong",
        )}
      >
        <Icon name="plus" size="lg" className="text-muted-foreground" />
        <p className="font-serif text-lg text-foreground">
          {armed ? release : t("desktop.agent.drop_title")}
        </p>
        {!armed && (
          <p className="flex flex-wrap items-center justify-center gap-1 text-sm text-muted-foreground">
            {withKeycap(t("desktop.agent.drop_hint"))}
          </p>
        )}
        {types && (
          <p className="text-xs text-faint">
            {t("desktop.agent.drop_accepts", { types })}
          </p>
        )}
      </div>
    </div>
  );
}
