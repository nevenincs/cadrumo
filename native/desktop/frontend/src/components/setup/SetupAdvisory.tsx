import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import { liveRun, type SetupControl } from "../../shell/setup";
import { useStrings } from "../../shell/strings";

/** The one line Settings carries while Cadrumo is not fully set up: what is
 * the matter, as a single control that opens the setup flow. Once setup is
 * complete, or before it has been read, it shows nothing. */
export function SetupAdvisory({
  control,
  onOpen,
}: {
  control: SetupControl;
  onOpen: () => void;
}) {
  const t = useStrings();
  const { snapshot } = control;
  if (snapshot === null) return null;
  const running = liveRun(snapshot) !== null;
  if (!running && snapshot.complete !== false) return null;
  return (
    <button
      type="button"
      data-setup-advisory={running ? "running" : "incomplete"}
      className="flex w-full items-center gap-2 rounded-lg border bg-card px-3 py-2 text-left text-sm text-foreground outline-none hover:bg-muted/40 focus-visible:ring-2 focus-visible:ring-ring"
      onClick={onOpen}
    >
      {running ? <Spinner /> : <Icon name="download" className="text-brand" />}
      <span className="min-w-0 flex-1">
        {running
          ? t("desktop.setup.advisory_running")
          : t("desktop.setup.advisory_incomplete")}
      </span>
      <Icon name="forward" className="text-faint" />
    </button>
  );
}
