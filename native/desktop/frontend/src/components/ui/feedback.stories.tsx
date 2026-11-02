import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, within } from "storybook/test";
import { Specimen } from "@/dev/catalogue/Frame";
import { useStrings } from "@/shell/strings";
import { GlyphMark } from "../modelo/workspace/Marks";
import { Alert, AlertDescription, AlertTitle } from "./alert";
import { Badge } from "./badge";
import { Button } from "./button";
import { EmptyState } from "./empty";
import { Icon } from "./icon";
import { Kbd } from "./kbd";
import { Progress } from "./progress";
import { Separator } from "./separator";
import { Spinner } from "./spinner";

const meta = { title: "Primitives/Feedback" } satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

export const Alerts: Story = {
  parameters: { surface: "card" },
  render: () => (
    <div className="max-w-96">
      <Specimen
        title="Tones"
        note="A quiet surface; the icon and title carry the tone."
        className="grid"
      >
        <Alert icon={<Icon name="info" />}>
          <AlertTitle>Your sign-in expired.</AlertTitle>
          <AlertDescription>Sign in again to continue.</AlertDescription>
        </Alert>
        <Alert tone="success" icon={<Icon name="check" />}>
          <AlertTitle>Copied</AlertTitle>
        </Alert>
        <Alert tone="warning" icon={<Icon name="clock" />}>
          <AlertTitle>Too many attempts.</AlertTitle>
          <AlertDescription>You can try again in 30 s.</AlertDescription>
          <Progress className="mt-1" value={12} max={30} aria-hidden="true" />
        </Alert>
        <Alert tone="danger" role="alert" icon={<Icon name="alert" />}>
          <AlertTitle>Signing in didn't work (timed_out).</AlertTitle>
        </Alert>
      </Specimen>
      <Specimen title="Without an icon" className="grid">
        <Alert>
          <AlertDescription>
            Agent access you enabled stays on.
          </AlertDescription>
        </Alert>
      </Specimen>
    </div>
  ),
};

export const Status: Story = {
  render: () => (
    <div>
      <Specimen title="Badges">
        <Badge variant="count">2</Badge>
        <Badge variant="count">99+</Badge>
        <Badge>Neutral</Badge>
        <Badge variant="soft">Demo profile</Badge>
        <Badge variant="success">Signed in</Badge>
        <Badge variant="warning">3 warnings</Badge>
        <Badge variant="danger">2 errors</Badge>
        <Badge variant="inverse">Copied</Badge>
      </Specimen>
      <Specimen title="Key hints">
        <Kbd>Esc</Kbd>
        <Kbd>Ctrl+K</Kbd>
        <Kbd>Ctrl+Shift+T</Kbd>
      </Specimen>
      <Specimen title="Pending">
        <Spinner label="Loading" />
        <span className="flex items-center gap-2 text-muted-foreground">
          <Spinner />
          Checking your sign-in…
        </span>
      </Specimen>
      <Specimen title="Progress" className="grid max-w-80">
        <Progress value={0} aria-label="Wait" />
        <Progress value={40} aria-label="Wait" />
        <Progress value={100} aria-label="Wait" />
      </Specimen>
      <Specimen title="Separator" className="grid max-w-80">
        <Separator />
        <div className="flex h-control-sm items-center gap-2">
          Left <Separator orientation="vertical" /> Right
        </div>
      </Specimen>
    </div>
  ),
};

export const EmptyStates: Story = {
  parameters: { fill: true },
  render: () => (
    <div className="grid min-h-dvh grid-cols-1 divide-x @container sm:grid-cols-3">
      <EmptyState
        icon="logs"
        heading="No log records yet"
        description="Records appear here as Cadrumo writes them."
      />
      <EmptyState role="status" busy description="Checking your sign-in…" />
      <EmptyState
        icon="lock"
        heading="Not signed in"
        description="Sign in to open your workspace."
      >
        <Button>Sign in</Button>
      </EmptyState>
    </div>
  ),
};

function Glyphs() {
  const t = useStrings();
  return (
    <Specimen
      title="Glyph marks"
      note="One glyph that says one thing: the wrapper is the image and carries the words."
    >
      <GlyphMark
        icon="check"
        words={t("workspace.declarations.list.group.recorded")}
        className="text-success"
      />
      <GlyphMark
        icon="alert"
        words={t("workspace.modelo.level.missing")}
        className="text-destructive"
      />
      <GlyphMark
        icon="info"
        words={t("workspace.modelo.level.info")}
        className="text-faint"
      />
    </Specimen>
  );
}

export const Marks: Story = {
  render: () => <Glyphs />,
  play: async ({ canvasElement }) => {
    const marks = within(canvasElement).getAllByRole("img");
    await expect(marks).toHaveLength(3);
    for (const mark of marks)
      await expect(mark).toHaveAccessibleName(expect.stringMatching(/\S/));
  },
};
