# Disguise API Reference (for this plugin)

A working map of the Disguise developer docs we rely on, plus the specific
endpoints/objects this plugin uses. Keep this updated as we learn more.

## Docs map

| Topic | URL |
| --- | --- |
| Plugins — introduction | https://developer.disguise.one/plugins/introduction/ |
| Plugins — getting started | https://developer.disguise.one/plugins/getting-started/ |
| Designer REST API — introduction | https://developer.disguise.one/api/introduction/ |
| Transport REST API (gototime, tracks, etc.) | https://developer.disguise.one/api/session/transport/ |
| Locator object (how resources are identified) | https://developer.disguise.one/api/locator/ |
| Python API — introduction | https://developer.disguise.one/python-api/introduction/ |
| Python API — Transports guide | https://developer.disguise.one/python-api/guides/transports/ |
| `vue-liveupdate` composable (the one this app uses) | https://github.com/disguise-one/vue-liveupdate |
| Sample components | https://github.com/disguise-one/Designer_Plugin-Components-Sample |
| Live Update sample plugin | https://github.com/disguise-one/Designer_Plugin-Live_Update |

## How this plugin talks to Designer

- Plugins are HTML/JS frontends rendered in Designer via Chromium Embedded
  Framework (CEF). The director endpoint is passed in the URL query string
  (`?director=...`), defaulting to `localhost`.
- **REST API base:** port **80** by default (`/api/...`). Configurable in
  d3Manager → Machine Settings → Advanced Network Configuration.
- **Service** endpoints (`/api/service/...`) are available whenever Disguise is
  installed; **Session** endpoints (`/api/session/...`) need Designer running.

## Read vs write (matters for the read-only "show notes" build — see issue #1)

The live-update channel (`/api/session/liveupdate`, used by `vue-liveupdate`) is
**read AND write** — it is not inherently safe. Safety for a show-notes build
must come from *omitting* write code paths at build time, not from the transport.

**Read-only surface (safe):**
- live-update **subscribe** to `object.player.tRender` (current playhead seconds)
- `GET /api/session/transport/activetransport`
- `GET /api/session/transport/tracks` / `transports` / `setlists` / `annotations`

**Write surface (unsafe during a show):**
- any `POST /api/session/transport/*` — `gototime`, `gototrack`, `gotosection`,
  `play`, `stop`, `engaged`, `volume`, `brightness`, …
- any *write* via the live-update composable

## Key endpoints this plugin uses / will use

### Read current transport + track
`GET /api/session/transport/activetransport`
```json
{
  "result": [{
    "uid": "", "name": "",
    "engaged": false, "playmode": "",
    "currentTrack": { "uid": "", "name": "" },
    "setList": { "uid": "", "name": "",
      "tracks": [{ "uid": "", "name": "", "length": 0, "crossfade": "" }] }
  }]
}
```

### Jump to a time (current command path)
`POST /api/session/transport/gototime`
```json
{
  "transports": [
    { "transport": { "uid": "", "name": "" }, "time": 0, "playmode": "" }
  ]
}
```

### Other transport jumps
- `POST /gototrack` — `{ transport, track: {uid,name}, playmode }` (jumps to track start)
- `POST /gotosection` — `{ transport, section, playmode }`
- `POST /gototimecode`, `POST /gotoframe`
- `POST /gotonexttrack` / `gotoprevtrack` / `gotonextsection` / `gotoprevsection`

## Locator object

Every resource (Transport, Track, Section, Prop, Screen) is identified by the
same shape — at least one field required:
```json
{ "uid": "123456789", "name": "act 1" }
```
- `uid` never changes → **prefer it as the source of truth**.
- `name` matches the *first* occurrence only.
- If both are given, **only `uid` is checked**.

So store both on each marker but key on `uid`, and treat `name` as the label.

## Open questions

- **Is `gototime`'s `time` track-relative or transport-global?** Decides whether
  jumping into a different track is one call or two (`gototrack` → `gototime`).
  Tracked in the spike issue.
