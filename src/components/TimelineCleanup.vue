<template>
  <div class="cleanup-page">
    <div class="cleanup-header">
      <h2>Timeline Cleanup</h2>
      <button class="pull-btn" :disabled="loading" @click="pull">
        {{ loading ? 'Pulling…' : 'Pull from d3' }}
      </button>
    </div>

    <p class="cleanup-intro">
      Pull every note and cue from all tracks in the session, tick the ones to
      remove, then delete. TC (timecode) tags are shown for context but can't be
      deleted. Pulled cues are never sent back to d3 — this page only deletes.
    </p>

    <!-- Search + selection controls (only meaningful once data is pulled) -->
    <div v-if="tracks.length" class="cleanup-toolbar">
      <input
        type="text"
        v-model="searchQuery"
        placeholder="Search tracks, notes, tags…"
        class="cleanup-search"
      />
      <span class="cleanup-spacer"></span>
      <button class="link-btn" @click="selectAllVisible">Select all</button>
      <button class="link-btn" @click="clearSelection">Clear</button>
    </div>

    <div v-if="statusMsg" class="cleanup-status">{{ statusMsg }}</div>
    <div v-if="error" class="cleanup-error">{{ error }}</div>

    <!-- Empty / pre-pull states -->
    <div v-if="!tracks.length && !loading" class="cleanup-empty">
      {{ pulled ? 'No notes or cues found on any track.' : 'Click "Pull from d3" to load notes and cues.' }}
    </div>
    <div v-else-if="tracks.length && !filteredTracks.length" class="cleanup-empty">
      No notes or cues match "{{ searchQuery }}".
    </div>

    <!-- Results, grouped by track -->
    <div
      v-for="track in filteredTracks"
      :key="track.uid"
      class="cleanup-track"
    >
      <div class="cleanup-track-header">
        <span class="cleanup-track-name">{{ track.name || '(unnamed track)' }}</span>
        <span class="cleanup-track-count">{{ track.cues.length }} cue(s)</span>
      </div>

      <ul class="cleanup-cue-list">
        <li v-for="cue in track.cues" :key="cue.beat" class="cleanup-cue">
          <div class="cleanup-cue-time">
            <span v-if="cue.tc" class="cleanup-tc">{{ cue.tc }}</span>
            <span class="cleanup-beat">beat {{ formatBeat(cue.beat) }}</span>
            <span v-if="cue.secs != null" class="cleanup-secs">{{ formatSecs(cue.secs) }}</span>
          </div>

          <div class="cleanup-elements">
            <!-- Tags first (cue/TC/MIDI), so a cue sits above the note at the
                 same beat, matching how d3 stacks them on the timeline. -->
            <template v-for="tag in cue.tags" :key="tag.type">
              <!-- TC tags are locked: shown for context, never deletable -->
              <div v-if="tag.type === TC_TYPE" class="cleanup-element locked">
                <span class="cleanup-lock" title="TC tags can't be deleted">🔒</span>
                <span class="cleanup-badge badge-tc">TC</span>
                <span class="cleanup-text">{{ tag.text }}</span>
              </div>
              <label v-else class="cleanup-element">
                <input
                  type="checkbox"
                  :checked="isSelected(tagKey(track.uid, cue.beat, tag.type))"
                  @change="toggle(tagKey(track.uid, cue.beat, tag.type))"
                />
                <!-- CUE tags use a d3-style beveled chip; MIDI keeps a badge -->
                <span v-if="tag.type === CUE_TYPE" class="cue-chip">CUE {{ tag.text }}</span>
                <template v-else>
                  <span class="cleanup-badge badge-midi">{{ tagTypeLabel(tag.type) }}</span>
                  <span class="cleanup-text">{{ tag.text }}</span>
                </template>
              </label>
            </template>

            <!-- Note below the tags -->
            <label v-if="cue.note" class="cleanup-element">
              <input
                type="checkbox"
                :checked="isSelected(noteKey(track.uid, cue.beat))"
                @change="toggle(noteKey(track.uid, cue.beat))"
              />
              <span class="cleanup-badge badge-note">NOTE</span>
              <span class="cleanup-text">{{ cue.note }}</span>
            </label>
          </div>
        </li>
      </ul>
    </div>

    <!-- Delete bar -->
    <div v-if="tracks.length" class="cleanup-delete-bar">
      <template v-if="!confirming">
        <button
          class="delete-btn"
          :disabled="selectedCount === 0 || loading"
          @click="requestDelete"
        >
          Delete selected ({{ selectedCount }})
        </button>
      </template>
      <template v-else>
        <span class="confirm-text">Delete {{ selectedCount }} item(s) from d3? This can't be undone.</span>
        <button class="delete-btn" :disabled="loading" @click="confirmDelete">Confirm delete</button>
        <button class="cancel-btn" :disabled="loading" @click="confirming = false">Cancel</button>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { apiBase } from '../d3Api.js'

// Like executePython, but reads and returns the response body even on a non-2xx
// status so the real Python error (in status.message) can be surfaced instead
// of a bare "HTTP 500". Returns the parsed { status, returnValue, pythonLog }.
const executePythonVerbose = async (directorEndpoint, script) => {
  const response = await fetch(`${apiBase(directorEndpoint)}/api/session/python/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ script })
  })
  let body = {}
  try {
    body = await response.json()
  } catch (e) {
    body = {}
  }
  const status = body.status || {}
  if (!response.ok || (status.code !== undefined && status.code !== 0)) {
    const detail = status.message || body.pythonLog || `HTTP ${response.status}`
    throw new Error(detail.trim() || `HTTP ${response.status}`)
  }
  return body
}

const props = defineProps({
  directorEndpoint: { type: String, required: true }
})

// d3 Tag type ints (see Tag python API): TC=0, CUE=1, MIDI=2.
const TC_TYPE = 0
const CUE_TYPE = 1
const MIDI_TYPE = 2

// Pulled data: [{ uid, name, cues: [{ beat, secs, note, tags: [{type, text}] }] }]
const tracks = ref([])
const selected = ref(new Set())
const loading = ref(false)
const pulled = ref(false)
const statusMsg = ref('')
const error = ref('')
const confirming = ref(false)
const searchQuery = ref('')

const tagTypeLabel = (type) => (type === CUE_TYPE ? 'CUE' : type === MIDI_TYPE ? 'MIDI' : 'TC')

const formatBeat = (beat) => Number(beat).toFixed(2)
const formatSecs = (secs) => {
  const s = Number(secs)
  const m = Math.floor(s / 60)
  const rem = (s - m * 60).toFixed(1).padStart(4, '0')
  return `${m}:${rem}`
}

// Stable keys identifying each deletable element.
const noteKey = (uid, beat) => `${uid}|${beat}|note`
const tagKey = (uid, beat, type) => `${uid}|${beat}|tag:${type}`

const isSelected = (key) => selected.value.has(key)
const toggle = (key) => {
  const next = new Set(selected.value)
  if (next.has(key)) {
    next.delete(key)
  } else {
    next.add(key)
  }
  selected.value = next
}

// Live, display-only filter over the pulled data. A track whose name matches
// shows all its cues; otherwise only cues with a matching note or tag show.
const filteredTracks = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) {
    return tracks.value
  }
  const out = []
  for (const t of tracks.value) {
    if ((t.name || '').toLowerCase().includes(q)) {
      out.push(t)
      continue
    }
    const cues = t.cues.filter(c => {
      const noteMatch = (c.note || '').toLowerCase().includes(q)
      const tagMatch = c.tags.some(tag => (tag.text || '').toLowerCase().includes(q))
      return noteMatch || tagMatch
    })
    if (cues.length) {
      out.push({ ...t, cues })
    }
  }
  return out
})

// All selectable (non-TC) element keys in the current filtered view.
const visibleSelectableKeys = computed(() => {
  const keys = []
  for (const t of filteredTracks.value) {
    for (const c of t.cues) {
      if (c.note) {
        keys.push(noteKey(t.uid, c.beat))
      }
      for (const tag of c.tags) {
        if (tag.type !== TC_TYPE) {
          keys.push(tagKey(t.uid, c.beat, tag.type))
        }
      }
    }
  }
  return keys
})

const selectedCount = computed(() => selected.value.size)

const selectAllVisible = () => {
  const next = new Set(selected.value)
  for (const k of visibleSelectableKeys.value) {
    next.add(k)
  }
  selected.value = next
}

const clearSelection = () => {
  selected.value = new Set()
}

// Pull every note and cue from all tracks in the session.
const pull = async () => {
  loading.value = true
  error.value = ''
  statusMsg.value = ''
  confirming.value = false
  // Notes on the d3 execute environment:
  //  - The runner's return value is serialised to JSON by d3, so we return a
  //    raw object (no json.dumps, which would double-encode).
  //  - d3 attribute access raises a C++ PythonException that does NOT inherit
  //    from Python's Exception, so guards use a bare `except:` to catch it.
  //  - A track's display name is `description` (not `name`).
  //  - The `Track` type symbol may not be bound in the restricted scope, so we
  //    resolve the Track class from a live track instance, falling back to the
  //    global name only if needed.
  const script = [
    'try:',
    '    TrackType = None',
    '    try:',
    '        cur = state.localOrDirectorState().track',
    '        if cur is not None:',
    '            TrackType = type(cur)',
    '    except:',
    '        TrackType = None',
    '    if TrackType is None:',
    '        try:',
    '            TrackType = Track',
    '        except:',
    '            TrackType = None',
    '    if TrackType is None:',
    '        return {"ok": False, "error": "Could not resolve the Track type (no track loaded)."}',
    '    out = []',
    '    for t in resourceManager.allResources(TrackType):',
    '        try:',
    '            uid = str(t.uid)',
    '        except:',
    '            uid = ""',
    '        try:',
    '            name = str(t.description)',
    '        except:',
    '            name = ""',
    '        cues = []',
    '        for beat in t.cueBeats():',
    '            note = t.noteAtBeat(beat)',
    '            tags = []',
    '            for tag in t.tagsAtBeat(beat):',
    '                tags.append({"type": tag.type, "text": tag.text})',
    '            if note or tags:',
    '                try:',
    '                    secs = t.beatToTime(beat)',
    '                except:',
    '                    secs = None',
    '                tc = ""',
    '                try:',
    '                    tc = str(Timecode(t.beatToGlobalTime(beat, 0, False)))',
    '                except:',
    '                    tc = ""',
    '                if not tc:',
    '                    try:',
    '                        tc = str(Timecode(t.beatToTime(beat)))',
    '                    except:',
    '                        tc = ""',
    '                cues.append({"beat": beat, "secs": secs, "tc": tc, "note": note, "tags": tags})',
    '        if cues:',
    '            out.append({"uid": uid, "name": name, "cues": cues})',
    '    return {"ok": True, "tracks": out}',
    'except Exception as e:',
    '    return {"ok": False, "error": str(e)}'
  ].join('\n')

  try {
    const result = await executePythonVerbose(props.directorEndpoint, script)
    // returnValue is JSON text (d3 serialises the return). Parse once; tolerate
    // an already-parsed value just in case.
    const raw = result.returnValue
    let data = raw
    if (typeof raw === 'string') {
      data = raw.trim() === '' ? {} : JSON.parse(raw)
    }
    data = data || {}
    if (data.ok === false) {
      throw new Error(data.error || 'Unknown error in d3 script')
    }
    const list = Array.isArray(data.tracks) ? data.tracks : []
    tracks.value = list
    selected.value = new Set()
    pulled.value = true
    const total = list.reduce((n, t) => n + t.cues.length, 0)
    statusMsg.value = `Pulled ${total} cue(s) across ${list.length} track(s).`
  } catch (err) {
    console.error('Error pulling cues from d3:', err)
    error.value = `Could not pull from d3: ${err.message}`
  } finally {
    loading.value = false
  }
}

const requestDelete = () => {
  if (selectedCount.value > 0) {
    confirming.value = true
  }
}

// Build the delete list straight from the selection state, then remove each
// element by beat. TC tags are never selectable, so they can't appear here.
const confirmDelete = async () => {
  const items = []
  for (const t of tracks.value) {
    for (const c of t.cues) {
      if (c.note && isSelected(noteKey(t.uid, c.beat))) {
        items.push({ uid: t.uid, beat: c.beat, kind: 'note' })
      }
      for (const tag of c.tags) {
        if (tag.type !== TC_TYPE && isSelected(tagKey(t.uid, c.beat, tag.type))) {
          items.push({ uid: t.uid, beat: c.beat, kind: 'tag', tagType: tag.type })
        }
      }
    }
  }

  if (items.length === 0) {
    confirming.value = false
    return
  }

  loading.value = true
  error.value = ''
  statusMsg.value = ''
  // Resolve each track by uid and remove the chosen note/tag by beat. Per-item
  // bare `except:` so a single failure (or a d3 PythonException, which doesn't
  // derive from Exception) doesn't abort the whole batch.
  const script = [
    'import json',
    `items = json.loads(${JSON.stringify(JSON.stringify(items))})`,
    'uidMgr = UidManager.get()',
    'removed = 0',
    'errors = []',
    'for it in items:',
    '    try:',
    "        track = uidMgr.getResource(int(it['uid']))",
    '        if track is None:',
    "            errors.append('track ' + str(it['uid']) + ' not found')",
    '            continue',
    "        if it['kind'] == 'note':",
    "            track.removeNoteAtBeat(float(it['beat']))",
    '        else:',
    "            track.removeTagAtBeat(float(it['beat']), int(it['tagType']))",
    '        removed += 1',
    '    except:',
    "        errors.append('failed to remove at beat ' + str(it.get('beat')))",
    'return {"ok": True, "removed": removed, "errors": errors}'
  ].join('\n')

  try {
    const result = await executePythonVerbose(props.directorEndpoint, script)
    let data = result.returnValue
    if (typeof data === 'string') {
      data = data.trim() === '' ? {} : JSON.parse(data)
    }
    data = data || {}
    confirming.value = false
    selected.value = new Set()
    // Re-pull so the list reflects ground truth after deletion.
    await pull()
    const removed = data.removed != null ? data.removed : 0
    const failed = Array.isArray(data.errors) ? data.errors.length : 0
    statusMsg.value = failed
      ? `Deleted ${removed} item(s); ${failed} failed. List refreshed.`
      : `Deleted ${removed} item(s). List refreshed.`
  } catch (err) {
    console.error('Error deleting from d3:', err)
    error.value = `Could not delete from d3: ${err.message}`
    confirming.value = false
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.cleanup-page {
  margin: 0.3rem 0.5rem;
  padding: 0.6rem 1rem;
  border: 1px solid #424242;
  border-radius: 4px;
  background-color: #1e1e1e;
  color: #e0e0e0;
}

.cleanup-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.cleanup-header h2 {
  margin: 0;
  font-size: 1.1rem;
  color: #ffffff;
}

.cleanup-intro {
  font-size: 0.8rem;
  color: #9e9e9e;
  margin: 0.4rem 0 0.6rem;
  line-height: 1.4;
}

.pull-btn {
  padding: 0.45rem 1rem;
  background-color: #1976d2;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-family: inherit;
  transition: background-color 0.2s ease;
}
.pull-btn:hover:not(:disabled) { background-color: #1565c0; }
.pull-btn:disabled { background-color: #37474f; cursor: default; }

.cleanup-toolbar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.cleanup-search {
  flex: 1 1 auto;
  padding: 0.45rem 0.6rem;
  border: 2px solid #424242;
  border-radius: 4px;
  background-color: #121212;
  color: #e0e0e0;
  font-family: inherit;
  font-size: 0.9rem;
}
.cleanup-search:focus { outline: none; border-color: #64b5f6; }

.cleanup-spacer { flex: 0 0 0.5rem; }

.link-btn {
  background: none;
  border: none;
  color: #64b5f6;
  cursor: pointer;
  font-family: inherit;
  font-size: 0.85rem;
  padding: 0.25rem 0.4rem;
}
.link-btn:hover { text-decoration: underline; }

.cleanup-status { color: #81c784; font-size: 0.85rem; margin-bottom: 0.4rem; }
.cleanup-error { color: #e57373; font-size: 0.85rem; margin-bottom: 0.4rem; }
.cleanup-empty { color: #9e9e9e; font-style: italic; padding: 0.8rem 0; }

.cleanup-track {
  border: 1px solid #333;
  border-radius: 4px;
  margin-bottom: 0.6rem;
  overflow: hidden;
}

.cleanup-track-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #2a2a2a;
  padding: 0.4rem 0.7rem;
}
.cleanup-track-name { font-weight: 600; color: #fff; }
.cleanup-track-count { font-size: 0.78rem; color: #9e9e9e; }

.cleanup-cue-list { list-style: none; margin: 0; padding: 0; }

.cleanup-cue {
  display: flex;
  gap: 0.75rem;
  padding: 0.4rem 0.7rem;
  border-top: 1px solid #2a2a2a;
}

.cleanup-cue-time {
  flex: 0 0 8.5rem;
  display: flex;
  flex-direction: column;
  font-variant-numeric: tabular-nums;
}
.cleanup-tc { color: #ffffff; font-size: 0.85rem; font-weight: 600; }
.cleanup-beat { color: #9e9e9e; font-size: 0.75rem; }
.cleanup-secs { color: #757575; font-size: 0.75rem; }

.cleanup-elements { flex: 1 1 auto; display: flex; flex-direction: column; gap: 0.25rem; }

.cleanup-element {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  font-size: 0.88rem;
}
.cleanup-element.locked { cursor: default; opacity: 0.6; }
.cleanup-element input[type="checkbox"] { cursor: pointer; }

.cleanup-lock { font-size: 0.8rem; width: 1rem; text-align: center; }

.cleanup-badge {
  flex: 0 0 auto;
  font-size: 0.68rem;
  font-weight: 700;
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
  letter-spacing: 0.03em;
}
.badge-note { background-color: #37474f; color: #b0bec5; }
.badge-midi { background-color: #6a1b9a; color: #fff; }
.badge-tc { background-color: #424242; color: #bdbdbd; }

/* d3-style cue chip: dark pennant with a left-pointing wedge marking the beat,
   matching how cues are drawn on the timeline. Flat fill, no bevel/shadow. */
.cue-chip {
  display: inline-block;
  padding: 0.12rem 0.5rem 0.12rem 1rem;
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: #f5f5f5;
  background: #3a3a3a;
  clip-path: polygon(0 50%, 0.6rem 0, 100% 0, 100% 100%, 0.6rem 100%);
  white-space: nowrap;
}

.cleanup-text { color: #e0e0e0; word-break: break-word; }

.cleanup-delete-bar {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-top: 0.6rem;
  padding-top: 0.6rem;
  border-top: 1px solid #333;
}

.confirm-text { color: #ffb74d; font-size: 0.85rem; }

.delete-btn {
  padding: 0.45rem 1rem;
  background-color: #c62828;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-family: inherit;
  transition: background-color 0.2s ease;
}
.delete-btn:hover:not(:disabled) { background-color: #b71c1c; }
.delete-btn:disabled { background-color: #4e342e; cursor: default; opacity: 0.7; }

.cancel-btn {
  padding: 0.45rem 1rem;
  background-color: #424242;
  color: #e0e0e0;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-family: inherit;
}
.cancel-btn:hover:not(:disabled) { background-color: #525252; }
</style>
