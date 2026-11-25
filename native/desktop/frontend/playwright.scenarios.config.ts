// Browser scenarios alone: builds the scenario bundle and serves it, never the
// product bundle or the native package.
import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

const servers = Array.isArray(base.webServer) ? base.webServer : [];
export default defineConfig({
  ...base,
  projects: base.projects?.filter((project) => project.name === "scenarios"),
  webServer: servers.filter((server) => server.name === "scenarios"),
});
