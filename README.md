# Vue 3 + Vite

This template should help get you started developing with Vue 3 in Vite. The template uses Vue 3 `<script setup>` SFCs, check out the [script setup docs](https://v3.vuejs.org/api/sfc-script-setup.html#sfc-script-setup) to learn more.

Learn more about IDE Support for Vue in the [Vue Docs Scaling up Guide](https://vuejs.org/guide/scaling-up/tooling.html#ide-support).

## Docker development workflow

1. Install Docker Desktop and make sure the Docker daemon is running.
2. From the repo root, start the dev container:
   ```sh
   docker compose up
   ```
   The Vite dev server is exposed on http://localhost:5173. The working tree is bind-mounted so any edits on your host are immediately reflected in the container. `node_modules` lives in a named Docker volume so dependency installs stay fast between runs.
3. To run arbitrary commands inside the container, use:
   ```sh
   docker compose exec dev <command>
   ```
   For example, `docker compose exec dev npm run build`.

### Building to a plugin-specific directory

The build output location is controlled by the `.build-target` file at the repo root. Put either an absolute path or a path relative to the repo in that file. During `npm run build` the Vite config reads the file, ensures the directory exists, and writes the production assets there (without clearing it automatically). This allows each plugin to point to its own destination without changing source files.

Tips:

- Check the file into version control with a sensible default (the template uses `dist`).
- When targeting a host path outside the repository, make sure it is available inside Docker. You can add an extra bind mount in `docker-compose.override.yml`, for example:
  ```yaml
  services:
    dev:
      volumes:
        - /path/to/plugin:/plugin-output
  ```
  and then point `.build-target` to `/plugin-output`.

### Targeting a path outside the repo on Windows

1. Create `docker-compose.override.yml` (ignored by git) and mount the host folder that contains all plugin build outputs:
- Note: Use forward slashes or escape the back slashes if using windows paths (should look like the exmple below).
   ```yaml
   services:
     dev:
       volumes:
         - "C:/path/to/d3/plugins/folder:/host-plugins"
   ```
   Adjust the Windows path for your plugin directory; the right side (`/host-plugins`) is how the container sees it.
2. Edit `.build-target` so it points to a subfolder within that mount, e.g. `/host-plugins/<plugin-name>`.
3. Run `docker compose build` (or `--no-cache` if you changed the Dockerfile) followed by `docker compose up`.

4. Build the plugin from scratch without starting the dev server by running:
   ```
   docker compose run --rm dev npm run build
   ```
   This runs `npm run build` inside the dev container once and exits, writing the output straight into your host plugin folder.
