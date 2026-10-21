// Source-only browser scenarios: never compile the product or native package.
import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

const servers = Array.isArray(base.webServer) ? base.webServer : [];
export default defineConfig({
  ...base,
  projects: base.projects?.filter((project) => project.name === "scenarios"),
  webServer: servers.filter((server) => server.command === "npm run dev"),
});
