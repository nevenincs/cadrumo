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
