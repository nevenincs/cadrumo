import { userEvent } from "storybook/test";
import type { Meta, StoryObj } from "@storybook/react-vite";
import type { ComponentProps } from "react";
import type { AgentQuestion } from "../../shell/agentSession";
import { APPEARANCE_NOTE, NOOP } from "./Composer.stories";
import { QuestionsPrompt } from "./QuestionsPrompt";

// Appearance only: the questions a reply waits on. Answering and declining
// do nothing here.

type Args = ComponentProps<typeof QuestionsPrompt>;

export const QUESTIONS: AgentQuestion[] = [
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
    required: false,
  },
  {
    id: "q-notas",
    prompt: "¿Algo más que deba saber?",
    kind: "text",
    options: null,
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
        id: "q.nif_2",
        prompt: "¿Cuál es el NIF del cliente de la factura 2026-031?",
        kind: "text",
        options: null,
        required: true,
      },
    ],
  },
};

export const LongestQuestion: Story = {
  name: "A prompt and options at their longest",
  args: {
    questions: [
      {
        id: "q-trimestre",
        prompt: "¿Para qué trimestre preparo la declaración? ".repeat(12),
        kind: "choice",
        options: [
          "Primer trimestre",
          "Segundo trimestre",
          "Tercer trimestre",
          "Cuarto trimestre, con el ajuste de fin de año incluido, y el resto de lo que haga falta para cerrar el ejercicio de este perfil",
        ],
        required: true,
      },
    ],
  },
};

export const TooLongAnswer: Story = {
  name: "A text answer too long to send",
  args: { questions: [QUESTIONS[2]!] },
  play: async ({ canvasElement }) => {
    const field = canvasElement.querySelector("textarea");
    if (field) await userEvent.click(field);
    if (field) await userEvent.paste("Una nota. ".repeat(210));
  },
};

export const Unavailable: Story = {
  name: "Answer and decline unavailable",
  args: { onAnswer: undefined, onDecline: undefined },
};
