import type { Meta, StoryObj } from "@storybook/react-vite";
import { AgentHeader } from "./AgentHeader";
import { AgentWelcome } from "./AgentWelcome";
import {
  APPEARANCE_NOTE,
  KEEP_DRAFT,
  MODELS,
  NOOP,
  PROVIDERS,
  READY_FILES,
  SELECTION,
  UPLOADING_FILES,
} from "./Composer.stories";
import { Composer } from "./Composer";
import { ConsentPrompt } from "./ConsentPrompt";
import { DOCUMENTS } from "./DocumentsPanel.stories";
import { DocumentsPanel } from "./DocumentsPanel";
import { DropOverlay } from "./DropOverlay";
import { ACTIVE_GROUPS } from "./HistoryList.stories";
import { HistoryList } from "./HistoryList";
import type { StagedAttachment } from "./types";

// Appearance only: the column's parts put together at the width the column
// opens at, in fixed states. No host, no model and no files: nothing here
// sends, uploads or answers.

type Body = "welcome" | "history" | "documents" | "consent";
type Args = {
  body: Body;
  attachments: StagedAttachment[];
  running: boolean;
  dragging: "none" | "idle" | "armed";
};

function Column({
  body,
  attachments,
  running,
  dragging,
  locale,
}: Args & { locale: string }) {
  return (
    <div className="grid h-dvh grid-cols-[auto_minmax(0,1fr)] bg-chrome">
      <aside className="relative flex h-dvh w-(--agent-w) flex-col border-r bg-background">
        <AgentHeader
          title={
            body === "welcome" ? "New conversation" : "IVA del tercer trimestre"
          }
          subtitle="Opus 5.5 · High"
          documentCount={
            body === "welcome" ? attachments.length : DOCUMENTS.length
          }
          historyOpen={body === "history"}
          documentsOpen={body === "documents"}
          onNewConversation={NOOP}
          onToggleHistory={NOOP}
          onToggleDocuments={NOOP}
        />
        {body === "history" ? (
          <HistoryList
            groups={ACTIVE_GROUPS}
            archivedCount={2}
            onToggleArchived={NOOP}
            onOpen={NOOP}
            onArchive={NOOP}
            onDelete={NOOP}
          />
        ) : body === "documents" ? (
          <DocumentsPanel
            documents={DOCUMENTS}
            locale={locale}
            onClose={NOOP}
            onRoleChange={NOOP}
            onRemove={NOOP}
          />
        ) : (
          <>
            {body === "consent" ? (
              <div className="flex min-h-0 flex-1 flex-col justify-end p-3">
                <ConsentPrompt
                  providerName="Anthropic"
                  modelName="Opus 5.5"
                  contentItems={[
                    { id: "message", label: "Your message" },
                    {
                      id: "documents",
                      label:
                        "3 documents: factura-2026-031.pdf, ticket-gasolinera.jpg, extracto-tercer-trimestre.xlsx",
                    },
                  ]}
                  onAllow={NOOP}
                  onDecline={NOOP}
                />
              </div>
            ) : (
              <AgentWelcome />
            )}
            <div className="shrink-0 p-3 pt-0">
              <Composer
                locale={locale}
                attachments={attachments}
                providers={PROVIDERS}
                models={MODELS}
                selection={SELECTION}
                running={running}
                onSend={KEEP_DRAFT}
                onStop={NOOP}
                onAddFiles={NOOP}
                onSelectionChange={NOOP}
                onRemoveAttachment={NOOP}
                onRemoveAllAttachments={NOOP}
                onShowAllAttachments={NOOP}
              />
            </div>
          </>
        )}
        <DropOverlay
          visible={dragging !== "none"}
          armed={dragging === "armed"}
          fileCount={2}
          acceptedTypes={["PDF", "JPG", "PNG", "XLSX", "CSV", "ZIP"]}
          locale={locale}
        />
      </aside>
      <p className="max-w-80 p-4 text-sm text-muted-foreground">
        {APPEARANCE_NOTE}
      </p>
    </div>
  );
}

const meta = {
  title: "Shell/Agent/Agent column",
  parameters: {
    fill: true,
    docs: { description: { component: APPEARANCE_NOTE } },
  },
  args: { body: "welcome", attachments: [], running: false, dragging: "none" },
  render: (args: Args, { globals }) => (
    <Column {...args} locale={String(globals.locale)} />
  ),
} satisfies Meta<Args>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Welcome: Story = {};

export const WithStagedFiles: Story = {
  args: { attachments: READY_FILES },
};

export const UploadingFiles: Story = {
  args: { attachments: UPLOADING_FILES },
};

export const Running: Story = {
  name: "Running: Stop",
  args: { running: true },
};

export const HistoryOpen: Story = { args: { body: "history" } };

export const DocumentsOpen: Story = { args: { body: "documents" } };

export const ConsentAsked: Story = {
  name: "Consent asked (needs owner review)",
  args: { body: "consent", attachments: READY_FILES },
};

export const FilesDraggedOver: Story = {
  args: { dragging: "idle" },
};

export const FilesDraggedOverArmed: Story = {
  name: "Files dragged over, armed",
  args: { dragging: "armed" },
};
