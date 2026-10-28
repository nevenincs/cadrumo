export const PORT_KEYS: readonly [
  "devPort",
  "previewPort",
  "docsPort",
  "cataloguePort",
  "scenariosPort",
  "scenariosDocsPort",
  "hotPort",
];
export function developmentServer(): {
  host: string;
  devPort: number;
  previewPort: number;
  docsPort: number;
  cataloguePort: number;
  scenariosPort: number;
  scenariosDocsPort: number;
  hotPort: number;
};
