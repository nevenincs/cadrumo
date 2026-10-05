import js from "@eslint/js";
import tseslint from "typescript-eslint";
import hooks from "eslint-plugin-react-hooks";
import globals from "globals";

// Import boundaries. One rule holds one list per file, so each group of files
// below gets the whole list that applies to it.
const development = {
  group: ["**/dev/**", "@/dev/**", "**/*.stories", "virtual:docs-fixture"],
  message: "Development tooling must not be imported by the product.",
};
const host = {
  group: ["@tauri-apps/**"],
  message: "Host access goes through the Host port.",
};
const aboveAPrimitive = [
  {
    group: ["@/shell/**", "@/ipc/**", "@/App", "**/shell/**", "**/ipc/**"],
    message: "A primitive stays generic: no shell or IPC import.",
  },
  {
    regex: "^@/components/(?!ui/)",
    message: "A primitive imports no product component.",
  },
];
const restricted = (...patterns) => ({
  "no-restricted-imports": ["error", { patterns }],
});

const tooling = ["src/dev/**", "src/**/*.stories.tsx"];
const primitives = ["src/components/ui/**"];
// The Tauri adapter, the entry that selects it and the contract's types.
const adapter = [
  "src/shell/tauriHost.ts",
  "src/shell/tauriTerminal.ts",
  "src/shell/hostCall.ts",
  "src/main.tsx",
  "src/ipc/contract.ts",
];

export default tseslint.config(
  { ignores: ["node_modules/**"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{js,mjs,ts,tsx}"],
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
  },
  {
    files: ["src/**/*.{ts,tsx}"],
    plugins: { "react-hooks": hooks },
    rules: {
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "error",
    },
  },
  {
    // The product never imports development tooling, and only the adapter
    // reaches the host API.
    files: ["src/**/*.{ts,tsx}"],
    ignores: [...tooling, ...primitives, ...adapter],
    rules: restricted(development, host),
  },
  {
    files: adapter,
    rules: restricted(development),
  },
  {
    // Layers point downward: a primitive imports nothing above it.
    files: ["src/components/ui/**/*.{ts,tsx}"],
    ignores: tooling,
    rules: restricted(development, host, ...aboveAPrimitive),
  },
);
