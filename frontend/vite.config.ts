import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

const buildOutputDirectory = process.env.CADRUMO_FRONTEND_BUILD_OUTPUT ?? 'dist'

if (buildOutputDirectory !== 'dist' && buildOutputDirectory !== 'build') {
  throw new Error('CADRUMO_FRONTEND_BUILD_OUTPUT must be exactly "dist" or "build".')
}

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: buildOutputDirectory,
  },
  server: {
    host: '0.0.0.0',
    port: 4310,
    strictPort: true,
  },
  preview: {
    host: '0.0.0.0',
    port: 4311,
    strictPort: true,
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  },
})
