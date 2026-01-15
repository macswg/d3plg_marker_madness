import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { designerPythonLoader } from '@disguise-one/designer-pythonapi/vite-loader'
import { existsSync, mkdirSync, readFileSync } from 'node:fs'
import path from 'node:path'

const BUILD_TARGET_FILE = process.env.BUILD_TARGET_FILE ?? '.build-target'
const FALLBACK_OUT_DIR = 'dist'

function resolveBuildOutputDir() {
  const configuredPath = (() => {
    const candidate = path.resolve(process.cwd(), BUILD_TARGET_FILE)
    if (!existsSync(candidate)) {
      return null
    }

    const contents = readFileSync(candidate, 'utf-8').trim()
    if (!contents) {
      return null
    }

    return path.isAbsolute(contents)
      ? contents
      : path.resolve(process.cwd(), contents)
  })()

  const outDir = configuredPath ?? path.resolve(process.cwd(), FALLBACK_OUT_DIR)

  try {
    mkdirSync(outDir, { recursive: true })
  } catch (err) {
    console.warn(
      `[vite.config.js] Failed to ensure build output directory "${outDir}". Falling back to "${FALLBACK_OUT_DIR}".`,
      err
    )
    return path.resolve(process.cwd(), FALLBACK_OUT_DIR)
  }

  return outDir
}

const buildOutDir = resolveBuildOutputDir()

// Detect if running in Docker via environment variable (set in docker-compose.yml)
// This allows native file watching on Mac/Linux when not in Docker, and polling when in Docker
const isDocker = process.env.DOCKER === 'true'

export default defineConfig({
  base: './', // Use relative paths for assets so the plugin works when served from any path
  plugins: [
    vue(),
    designerPythonLoader()
  ],
  server: {
    port: 5173,
    host: '0.0.0.0', // Allow external connections (needed for Docker and Tailscale)
    watch: {
      // Use polling for file watching (required on Windows, especially in Docker)
      usePolling: true,
      interval: 1000, // Polling interval in milliseconds
    },
    // No HMR config - let Vite auto-detect for remote connections
  },
  build: {
    outDir: buildOutDir,
    emptyOutDir: false,
  },
})
