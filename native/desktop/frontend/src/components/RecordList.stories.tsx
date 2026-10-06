import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import {
  AVAILABLE,
  FIXTURE_RECORDS,
  MISSING,
  UNREADABLE,
  generatedBatches,
} from "@/dev/fixtures/logs";
import type { LogRecord, LogSourceState } from "../ipc/contract";
import { useStrings } from "../shell/strings";
import { ContextMenu } from "./ContextMenu";
import { DEFAULT_FILTERS, type RecordFilters } from "../shell/records";
import { RecordList } from "./RecordList";

// The log view over fixed records, in every state its source can be in.
type Args = {
  records: LogRecord[] | null;
  sourceState: LogSourceState | "unavailable" | null;
  dropped: number;
  filters: RecordFilters;
};

function View({ records, sourceState, dropped, filters: initial }: Args) {
  const [filters, setFilters] = useState(initial);
  return (
    <div className="flex h-dvh flex-col">
      <RecordList
        records={records}
        sourceState={sourceState}
        dropped={dropped}
        filters={filters}
        setFilters={setFilters}
        onMenu={() => undefined}
        shown
      />
    </div>
  );
}

const meta = {
  title: "Shell/Log view",
  parameters: { fill: true },
  args: {
    records: [...FIXTURE_RECORDS],
    sourceState: AVAILABLE,
    dropped: 0,
    filters: { ...DEFAULT_FILTERS, minLevel: 0 },
  },
  render: (args: Args) => <View {...args} />,
} satisfies Meta<Args>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Records: Story = {};

export const RecordsLost: Story = {
  name: "Records lost to overflow",
  args: { dropped: 3 },
};

export const Filtered: Story = {
  args: {
    filters: {
      text: "",
      minLevel: 2,
      hiddenSources: ["host"],
      logger: FIXTURE_RECORDS.find((record) => record.logger)?.logger ?? null,
    },
  },
};

export const NothingMatches: Story = {
  args: { filters: { ...DEFAULT_FILTERS, text: "no such record" } },
};

export const Empty: Story = { args: { records: [] } };

export const Waiting: Story = {
  name: "Before the host answers",
  args: { records: null, sourceState: null },
};

export const FileMissing: Story = {
  args: { records: [], sourceState: MISSING },
};

export const FileUnreadable: Story = {
  args: { records: [], sourceState: UNREADABLE },
};

export const HostUnavailable: Story = {
  args: { records: [], sourceState: "unavailable" },
};

export const TenThousand: Story = {
  name: "Ten thousand records",
  args: {
    records: generatedBatches(10_000).flatMap((batch) => batch.records),
  },
};

function WithMenu(args: Args) {
  const t = useStrings();
  return (
    <>
      <View {...args} />
      <ContextMenu
        label={t("desktop.palette.actions")}
        at={{ x: 320, y: 120 }}
        choose={() => undefined}
        items={[
          {
            id: "copy",
            label: t("desktop.menu.copy_line"),
            enabled: true,
            shortcut: "Ctrl+C",
          },
          {
            id: "visible",
            label: t("desktop.menu.copy_visible"),
            enabled: true,
          },
          { separator: true },
          {
            id: "level",
            label: t("desktop.menu.only_level", { level: "WARNING" }),
            enabled: true,
          },
          {
            id: "logger",
            label: t("desktop.menu.only_logger", { logger: "tui.app" }),
            enabled: false,
          },
        ]}
      />
    </>
  );
}

export const Menu: Story = {
  name: "Record menu",
  render: (args) => <WithMenu {...args} />,
};
