import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { Specimen } from "@/dev/catalogue/Frame";
import { useStrings } from "../shell/strings";
import {
  PaneHeader,
  SessionDot,
  type PaneControl,
  type SessionPhase,
} from "./PaneHeader";
import { Rail, type RailItem } from "./Rail";
import { Split } from "./Split";

// The pieces the window is laid out from: the rail, a pane's header and the
// split between two panes.
const noop = () => undefined;

const meta = { title: "Shell/Workspace" } satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

/** What the Messages button has to say: a count, or why there is none. */
type Messages = number | "never" | "failed" | "unknown";

function useRailItems(chosen: string, errors = 0, messages?: Messages) {
  const t = useStrings();
  const item = (
    id: string,
    icon: RailItem["icon"],
    key: string,
    shortcut?: string,
  ): RailItem => ({
    id,
    icon,
    label: t(key),
    shortcut,
    pressed: id === "search" ? undefined : id === chosen,
    onClick: noop,
  });
  const top: RailItem[] = [
    item("search", "search", "desktop.rail.search", "Ctrl+K"),
    item("docs", "book", "desktop.rail.docs_home", "Alt+Home"),
    item("tui", "tui", "desktop.rail.tui", "Ctrl+Shift+T"),
    // The profile's views, where the host offers them, lead the shortcuts.
    ...(messages === undefined
      ? []
      : [
          {
            ...item("calendar", "calendar", "desktop.calendar.title"),
            divided: true,
          },
          {
            ...item("messages", "mail", "desktop.rail.messages"),
            ...(typeof messages === "number"
              ? messages > 0
                ? {
                    badge: messages,
                    badgeLabel: t("desktop.messages.unread", {
                      count: messages,
                    }),
                  }
                : { hint: t("desktop.messages.none_unread") }
              : messages === "never"
                ? { hint: t("desktop.messages.never"), pin: "unknown" as const }
                : messages === "failed"
                  ? {
                      hint: t("desktop.messages.failed", {
                        code: "timed_out",
                      }),
                      pin: "failed" as const,
                    }
                  : // Not read: the account's own reason stands in.
                    {
                      pin: "unknown" as const,
                      hint: t("desktop.account.signed_out"),
                    }),
          },
        ]),
    {
      ...item("aeat", "office", "desktop.rail.aeat"),
      divided: messages === undefined,
    },
    {
      ...item("console", "console", "desktop.rail.console", "Ctrl+Shift+1"),
      divided: true,
    },
    item("python", "python", "desktop.rail.python", "Ctrl+Shift+2"),
    {
      ...item("logs", "logs", "desktop.rail.logs", "Ctrl+Shift+3"),
      badge: errors || undefined,
      badgeLabel: errors
        ? t("desktop.logs.errors", { count: errors })
        : undefined,
    },
  ];
  const bottom = [item("settings", "settings", "desktop.rail.settings")];
  return { label: t("desktop.rail.label"), top, bottom };
}

function RailSpecimen({
  chosen,
  errors,
  messages,
}: {
  chosen: string;
  errors?: number;
  messages?: Messages;
}) {
  return (
    <div className="flex h-120 border bg-chrome">
      <Rail {...useRailItems(chosen, errors, messages)} />
    </div>
  );
}

export const RailStates: Story = {
  name: "Rail",
  parameters: { surface: "chrome" },
  render: () => (
    <Specimen
      title="Rail"
      note="One tab stop; the arrow keys, Home and End move within it. Search, the window's toggles, shortcuts, then the panel's toggles. A chosen item carries a bar as well as its surface, and a count is said in its name."
      className="items-start gap-8"
    >
      <RailSpecimen chosen="tui" />
      <RailSpecimen chosen="console" errors={3} />
      <RailSpecimen chosen="logs" errors={128} />
    </Specimen>
  ),
};

export const RailViews: Story = {
  name: "Rail with profile views",
  parameters: { surface: "chrome" },
  render: () => (
    <Specimen
      title="Rail with profile views"
      note="Where the host offers the profile's views, the calendar and Messages lead the shortcuts. Messages shows what was unread at the last sync; none unread shows nothing more, while never synced and a failed read carry a hollow pin, not a zero, and say which in the tooltip and the name. Withheld by the account, it carries the same pin and the account's own reason."
      className="items-start gap-8"
    >
      <RailSpecimen chosen="calendar" messages={3} />
      <RailSpecimen chosen="tui" messages={128} errors={3} />
      <RailSpecimen chosen="tui" messages={0} />
      <RailSpecimen chosen="tui" messages="never" />
      <RailSpecimen chosen="tui" messages="failed" />
      <RailSpecimen chosen="tui" messages="unknown" />
    </Specimen>
  ),
};

function usePaneControls(maximized = false): PaneControl[] {
  const t = useStrings();
  return [
    {
      id: "maximize",
      icon: maximized ? "restore" : "maximize",
      label: t(
        maximized ? "desktop.pane.restore" : "desktop.pane.maximize_tui",
      ),
      pressed: maximized,
      run: noop,
    },
    {
      id: "orientation",
      icon: "splitColumn",
      label: t("desktop.split.stack"),
      run: noop,
    },
    { id: "swap", icon: "swap", label: t("desktop.split.swap"), run: noop },
  ];
}

const PHASES: readonly SessionPhase[] = [
  "starting",
  "running",
  "exited",
  "failed",
  "unavailable",
];

function Headers() {
  const t = useStrings();
  const controls = usePaneControls();
  const maximized = usePaneControls(true);
  return (
    <div>
      <Specimen
        title="Pane header"
        note="Title, a session's state where it has one, and the pane's controls. Double-clicking the bar toggles maximize."
        className="grid max-w-3xl gap-3"
      >
        <div className="border">
          <PaneHeader
            title={t("desktop.pane.docs")}
            controls={controls}
            onToggleMaximize={noop}
          />
        </div>
        <div className="border">
          <PaneHeader
            title={t("desktop.pane.tui")}
            status={{ phase: "running" }}
            controls={maximized}
            onToggleMaximize={noop}
          />
        </div>
        <div className="border">
          <PaneHeader
            title={t("desktop.pane.tui")}
            status={{
              phase: "exited",
              note: t("desktop.session.exited", { code: 0 }),
            }}
            controls={controls}
            onToggleMaximize={noop}
          />
        </div>
        <div className="w-56 border">
          <PaneHeader
            title={t("desktop.pane.tui")}
            status={{
              phase: "failed",
              note: t("desktop.session.failed", { code: 1 }),
            }}
            controls={controls}
            onToggleMaximize={noop}
          />
        </div>
      </Specimen>
      <Specimen
        title="Session state"
        note="Filled while a session runs, hollow once it has ended; the note beside it says which."
      >
        {PHASES.map((phase) => (
          <span
            key={phase}
            className="flex items-center gap-2 text-sm text-muted-foreground"
          >
            <SessionDot phase={phase} />
            {phase}
          </span>
        ))}
      </Specimen>
    </div>
  );
}

export const PaneHeaders: Story = {
  name: "Pane header",
  render: () => <Headers />,
};

function Panes({
  orientation,
  reversed = false,
}: {
  orientation: "row" | "column";
  reversed?: boolean;
}) {
  const t = useStrings();
  const [ratio, setRatio] = useState(0.56);
  const controls = usePaneControls();
  const pane = (title: string, phase?: SessionPhase) => (
    <div className="flex min-w-0 flex-1 flex-col bg-background">
      <PaneHeader
        title={title}
        status={phase && { phase }}
        controls={controls}
        onToggleMaximize={noop}
      />
      <div className="flex-1" />
    </div>
  );
  return (
    <div className="flex h-dvh bg-chrome">
      <Split
        orientation={orientation}
        reversed={reversed}
        ratio={ratio}
        onRatio={setRatio}
        minA={240}
        minB={240}
        a={pane(t("desktop.pane.docs"))}
        b={pane(t("desktop.pane.tui"), "running")}
        aShown
        bShown
        label={t("desktop.split.resize")}
      />
    </div>
  );
}

export const SideBySide: Story = {
  parameters: { fill: true },
  render: () => <Panes orientation="row" />,
};

export const Stacked: Story = {
  parameters: { fill: true },
  render: () => <Panes orientation="column" />,
};

export const Swapped: Story = {
  parameters: { fill: true },
  render: () => <Panes orientation="row" reversed />,
};
