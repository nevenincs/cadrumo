export type ProductIdentity = {
  name: string;
  application_id: string;
  version: string;
};
export function identity(): ProductIdentity;
export function server(): {
  host: string;
  devPort: number;
  previewPort: number;
};
export function profile(configuration?: string): {
  directory: string;
  debug: boolean;
  environment: Record<string, string>;
};
export function artifactFile(): string;
export function executable(): string;
export function frontendDirectory(
  configDirectory: string,
  frontend: string,
): string;
export function tauriConfig(
  template: Record<string, unknown>,
  product: ProductIdentity,
  locations: { configDirectory: string; frontend: string; icons: string },
  platform?: string,
): Record<string, unknown>;
export function docsOrigin(
  window: { useHttpsScheme?: boolean },
  platform?: string,
): string;
