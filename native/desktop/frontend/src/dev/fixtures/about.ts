import type { AboutInfo } from "../../ipc/contract";

/** A made-up installation, as the About dialog shows it. */
export const ABOUT_FIXTURE: AboutInfo = {
  product: "Cadrumo",
  display_version: "9.8.7+2031010203.debug",
  version: "9.8.7",
  build_id: "2031010203",
  build_type: "debug",
  build_date: "2031-01-02T03:04:05Z",
  channel: "stable",
  target: "windows-x86-64",
  python: "3.13.11",
  desktop: { version: "9.8.7", build_id: "2031010203", build_type: "debug" },
  components: [
    {
      name: "cadrumo",
      role: "desktop",
      path: "bin/cadrumo.exe",
      version: "9.8.7",
      build_id: "2031010203",
      build_type: "debug",
    },
    {
      name: "cadrumo-manager",
      role: "manager",
      path: "bin/cadrumo-manager.exe",
      version: "9.8.7",
      build_id: "2031010203",
      build_type: "debug",
    },
    {
      name: "cadrumo_python",
      role: "interpreter",
      path: "bin/cadrumo_python.exe",
      version: "9.8.7",
      build_id: "2031010203",
      build_type: "debug",
    },
  ],
  agent: {
    version: "4.5.6",
    dependencies: [
      { name: "anyio", version: "4.0.1" },
      { name: "langgraph", version: "1.2.3" },
    ],
  },
  tools: { node: "22.1.0" },
  distributions: [
    { name: "alpha-package", version: "1.0.0" },
    { name: "beta-package", version: "2.0.0" },
  ],
};
