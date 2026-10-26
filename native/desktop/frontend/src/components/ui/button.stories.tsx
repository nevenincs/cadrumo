import type { Meta, StoryObj } from "@storybook/react-vite";
import { Specimen } from "@/dev/catalogue/Frame";
import { Button } from "./button";
import { Icon } from "./icon";
import { IconButton } from "./icon-button";

const meta = {
  title: "Primitives/Button",
  component: Button,
  args: { children: "Sign in", variant: "primary", size: "md" },
  argTypes: {
    variant: {
      control: "select",
      options: [
        "primary",
        "secondary",
        "outline",
        "ghost",
        "destructive",
        "link",
      ],
    },
    size: { control: "select", options: ["xs", "sm", "md", "lg"] },
    pending: { control: "boolean" },
    disabled: { control: "boolean" },
  },
} satisfies Meta<typeof Button>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Playground: Story = {};

const VARIANTS = [
  "primary",
  "secondary",
  "outline",
  "ghost",
  "destructive",
  "link",
] as const;

export const Variants: Story = {
  render: () => (
    <div>
      <Specimen
        title="Variants"
        note="One primary action per surface; hover and focus are live."
      >
        {VARIANTS.map((variant) => (
          <Button key={variant} variant={variant}>
            {variant}
          </Button>
        ))}
      </Specimen>
      <Specimen title="Disabled">
        {VARIANTS.map((variant) => (
          <Button key={variant} variant={variant} disabled>
            {variant}
          </Button>
        ))}
      </Specimen>
      <Specimen
        title="Pending"
        note="Work this button started is in flight: busy, and not activatable."
      >
        <Button pending>Signing in…</Button>
        <Button variant="outline" pending>
          Sign out
        </Button>
      </Specimen>
      <Specimen
        title="Pressed"
        note="A toggle says so with aria-pressed, which also styles it."
      >
        <Button variant="outline" size="xs" aria-pressed="true">
          Follow
        </Button>
        <Button variant="outline" size="xs" aria-pressed="false">
          Follow
        </Button>
        <Button variant="ghost" size="xs" aria-pressed="true">
          Python
        </Button>
        <Button variant="ghost" size="xs" aria-pressed="false">
          Host
        </Button>
      </Specimen>
    </div>
  ),
};

export const Sizes: Story = {
  render: () => (
    <div>
      <Specimen title="Text" note="Heights are the density tokens.">
        {(["xs", "sm", "md", "lg"] as const).map((size) => (
          <Button key={size} size={size}>
            {size}
          </Button>
        ))}
      </Specimen>
      <Specimen title="With an icon">
        <Button variant="outline" size="sm">
          <Icon name="signOut" />
          Sign out
        </Button>
        <Button>
          <Icon name="lock" />
          Sign in
        </Button>
      </Specimen>
      <Specimen
        title="Icon buttons"
        note="Always named: the label is the accessible name and the tooltip."
      >
        {(["xs", "sm", "md", "lg"] as const).map((size) => (
          <IconButton key={size} size={size} label={`Maximize (${size})`}>
            <Icon name="maximize" size={size === "lg" ? "lg" : "sm"} />
          </IconButton>
        ))}
        <IconButton label="Search" shortcut="Ctrl+K">
          <Icon name="search" />
        </IconButton>
        <IconButton label="Restore" aria-pressed="true">
          <Icon name="restore" />
        </IconButton>
        <IconButton label="Close" disabled>
          <Icon name="close" />
        </IconButton>
      </Specimen>
    </div>
  ),
};
