import { Icon, type IconName } from "@/components/ui/icon";

export type PaneControl = {
  id: string;
  icon: IconName;
  label: string;
  pressed?: boolean;
  run: () => void;
};

type Props = {
  title: string;
  /** Session phase dot and exit note, for terminal areas. */
  status?: { phase: string; note?: string };
  controls: PaneControl[];
  onToggleMaximize: () => void;
};

// Slim header for a workspace area; double-click toggles maximize.
export function PaneHeader({
  title,
  status,
  controls,
  onToggleMaximize,
}: Props) {
  return (
    <div
      className="pane-head"
      onDoubleClick={(event) => {
        if (!(event.target as HTMLElement).closest("button"))
          onToggleMaximize();
      }}
    >
      {status && (
        <span className={`dot phase-${status.phase}`} aria-hidden="true" />
      )}
      <span className="pane-title">{title}</span>
      {status?.note && <span className="exit-note">{status.note}</span>}
      <span className="tools-spacer" />
      {controls.map((control) => (
        <IconButton key={control.id} {...control} />
      ))}
    </div>
  );
}

export function IconButton({
  icon,
  label,
  pressed,
  run,
}: Omit<PaneControl, "id">) {
  return (
    <button
      className="icon-button"
      title={label}
      aria-label={label}
      aria-pressed={pressed}
      onClick={run}
    >
      <Icon name={icon} size="sm" />
    </button>
  );
}
