import { cn } from "@/components/ui/cn";
import { Icon, type IconName } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";

export type PaneControl = {
  id: string;
  icon: IconName;
  label: string;
  shortcut?: string;
  pressed?: boolean;
  run: () => void;
};

/** A terminal session's phase, as the header and tabs show it. */
export type SessionPhase =
  "starting" | "running" | "exited" | "failed" | "unavailable";

const PHASES: Record<SessionPhase, string> = {
  starting: "bg-faint",
  running: "bg-success",
  exited: "ring-1 ring-faint ring-inset",
  failed: "ring-1 ring-destructive ring-inset",
  unavailable: "ring-1 ring-faint ring-inset",
};

/** A session's state as a dot: filled while it runs, hollow once it has ended. */
export function SessionDot({ phase }: { phase: SessionPhase }) {
  return (
    <span
      data-phase={phase}
      aria-hidden="true"
      className={cn("size-1.5 shrink-0 rounded-full", PHASES[phase])}
    />
  );
}

/**
 * The slim header of a workspace area: its title, a session's state where it
 * has one, and its controls. Double-clicking the bar toggles maximize.
 */
export function PaneHeader({
  title,
  status,
  controls,
  onToggleMaximize,
}: {
  title: string;
  status?: { phase: SessionPhase; note?: string };
  controls: PaneControl[];
  onToggleMaximize: () => void;
}) {
  return (
    <div
      className="pane-head flex h-control-lg shrink-0 items-center gap-2 border-b bg-chrome pr-1.5 pl-3 text-muted-foreground select-none"
      onDoubleClick={(event) => {
        if (!(event.target as HTMLElement).closest("button"))
          onToggleMaximize();
      }}
    >
      {status && <SessionDot phase={status.phase} />}
      {/* The note gives way first: the title is cut only once the note has
          gone. */}
      <span className="pane-title min-w-0 truncate font-semibold text-foreground">
        {title}
      </span>
      {status?.note && (
        <span
          className={cn(
            "min-w-0 shrink-[9999] truncate text-xs",
            status.phase === "failed" ? "text-destructive" : "text-faint",
          )}
        >
          {status.note}
        </span>
      )}
      <span className="flex-1" />
      {controls.map((control) => (
        <IconButton
          key={control.id}
          label={control.label}
          shortcut={control.shortcut}
          aria-pressed={control.pressed}
          onClick={control.run}
        >
          <Icon name={control.icon} />
        </IconButton>
      ))}
    </div>
  );
}
