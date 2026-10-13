import type { Meta, StoryObj } from "@storybook/react-vite";
import type { ComponentProps } from "react";
import { APPEARANCE_NOTE, NOOP } from "./Composer.stories";
import { QuestionsPrompt, type Question } from "./QuestionsPrompt";

// Appearance only: the questions a reply waits on. Answering and declining
// do nothing here.

type Args = ComponentProps<typeof QuestionsPrompt>;

export const QUESTIONS: Question[] = [
  {
    id: "q-trimestre",
    prompt: "¿Qué trimestre preparo?",
    kind: "choice",
    options: ["Primer trimestre", "Segundo trimestre", "Tercer trimestre"],
    required: true,
  },
  {
    id: "q-prorrata",
    prompt: "¿Aplicas la prorrata del IVA?",
    kind: "choice",
    options: ["Sí", "No", "No lo sé"],
    required: true,
  },
  {
    id: "q-notas",
    prompt: "¿Algo más que deba saber?",
    kind: "text",
    required: false,
  },
];

const meta = {
  title: "Shell/Agent/Questions prompt",
  parameters: {
    surface: "chrome",
    docs: { description: { component: APPEARANCE_NOTE } },
  },
  args: { questions: QUESTIONS, onAnswer: NOOP, onDecline: NOOP },
  render: (args: Args) => (
    <div className="grid w-(--agent-w) gap-2">
      <QuestionsPrompt {...args} />
    </div>
  ),
} satisfies Meta<Args>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Asked: Story = {};

export const OneQuestion: Story = {
  args: { questions: [QUESTIONS[0]!] },
};

export const FourQuestions: Story = {
  name: "Four questions, the most asked at once",
  args: {
    questions: [
      ...QUESTIONS,
      {
        id: "q-nif",
        prompt: "¿Cuál es el NIF del cliente de la factura 2026-031?",
        kind: "text",
        required: true,
      },
    ],
  },
};

export const Unavailable: Story = {
  name: "Answer and decline unavailable",
  args: { onAnswer: undefined, onDecline: undefined },
};
