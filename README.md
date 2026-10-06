# Marker Madness

A Disguise Designer plugin for capturing playhead positions as named markers and
jumping back to them on demand. Each marker remembers its transport and track, so
you can recall a precise time — even in a different track — with a single click, a
number-key shortcut, or the `` ` `` hotkey. Markers can be labelled, reordered, and
imported/exported as YAML.

## Install the plugin (no coding needed)

Follow these steps to install the latest ready-to-use version in Disguise
Designer. You don't need to build anything or know how to use GitHub.

1. **Download it.** Go to the
   [latest release page](https://github.com/macswg/d3plg_marker_madness/releases/latest).
   Under the **Assets** heading, click the file that ends in `.zip`
   (for example `marker_madness-v1.0.0.zip`) to download it.
2. **Unzip it.** Find the downloaded `.zip` file (usually in your Downloads
   folder), right-click it, and choose **Extract All…** (Windows) or
   double-click it (Mac). You'll get a folder named `marker_madness`.
3. **Drop it into the d3 plugins folder.** Copy that whole `marker_madness`
   folder into your Disguise project's **plugins** folder.
4. **Load it in Designer.** Open (or restart) Disguise Designer and open the
   plugin from the plugin launcher. Look for **Marker Madness** with its
   playhead icon.

To update later, just delete the old `marker_madness` folder and repeat the
steps with the newest release.

## Features

The plugin has two pages: **Markers** for capturing playhead positions and
writing them to the timeline, and **Timeline Cleanup** for tidying up the cues
and notes already in the session.

### Markers

- **Capture markers** at the current playhead position, each tagged with its
  transport and track. The playhead reads out in d3's own timecode, and each
  marker stores its timecode, seconds, and beat.
- **Jump to a marker** with the *Go To* button — it seeks to the right track and
  time even if it lives in a different track.
- **Label markers** with free-text notes, and give each one an optional **cue
  number** (digits and dots, e.g. `1` or `1.1`).
- **Send to d3** writes the markers onto the timeline — labels become timeline
  notes and cue numbers become `CUE` tags, both at the captured beat. Markers
  are grouped by the track they came from.
- **Note prefix** — an optional prefix (e.g. `@`) is prepended with an
  underscore to every note sent to d3 (`@_cue1`), so plugin-added notes can be
  told apart from hand-placed ones.
- **Show Existing** interleaves the cues, notes, and section breaks already on
  the active track with your captured markers, sorted by time, with click-to-seek
  and a refresh button.
- **Number-key shortcuts** (1–9) to recall markers and a `` ` `` hotkey to
  capture one, each armed by its own toggle so they can't fire by accident.
- **Reorder** markers by drag and drop.
- **Markers persist** across reloads, along with the note prefix.
- **Import / export** the full marker list (position, timecode, beat, transport,
  track, notes, and cue numbers) as YAML. Export copies to the clipboard and
  import takes a pasted document — d3's plugin webview blocks file downloads and
  uploads, so both work through overlays instead.

### Timeline Cleanup

- **Pull from d3** reads every note and cue from all tracks in the session.
- **Rename notes and cue numbers in place** — edits are saved back at the same
  beat, so cue timing never moves. Tab / Shift+Tab steps between items.
- **Delete** the items you don't want, ticked individually. Deletion is
  per-element, so a `CUE` tag can be removed while a `TC` tag on the same cue
  survives.
- **Search** live across track names, note text, and tag text.
- **Protected by default** — `TC` tags and item times can't be touched until you
  unlock them: *Unlock TC* allows editing and deleting timecode tags, and
  *Unlock time* reveals each item's timecode so a single note or tag can be
  moved. Section breaks are shown for context and are never editable.
- Nothing is rewritten except the items you actually change.

## Disguise API reference

See [`docs/disguise-api-reference.md`](docs/disguise-api-reference.md) for a map of the
relevant Disguise developer docs and the specific REST endpoints / live-update keys
this plugin uses to read the playhead and control transports.

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
