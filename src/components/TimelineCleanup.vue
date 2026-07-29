<template>
  <div class="cleanup-page">
    <div class="cleanup-header">
      <h2>Timeline Cleanup</h2>
      <button class="pull-btn" :disabled="loading" @click="pull">
        {{ loading ? 'Pulling…' : 'Pull from d3' }}
      </button>
    </div>

    <p class="cleanup-intro">
      Pull every note and cue from all tracks in the session. Click a note or
      cue number to rename it in place, then use Tab / Shift+Tab to step to the
      next or previous one — edits are saved back at the same beat, so cue
      timing never moves. Tick items and delete the ones you don't want. Section
      breaks are shown for context and can't be edited here. TC tags and marker
      times are protected until you unlock them — <em>Unlock TC</em> allows
      editing and deleting timecode tags, and <em>Unlock time</em> shows each
      item's timecode — click it to move just that note or tag. Nothing is
      rewritten except the items you change.
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
      <button
        :class="['lock-btn', { unlocked: tcUnlocked }]"
        :title="tcUnlocked
          ? 'TC tags can now be edited and deleted — click to protect them again'
          : 'Allow editing and deleting TC (timecode) tags'"
        @click="toggleTcUnlock"
      >
        {{ tcUnlocked ? '🔓 TC unlocked' : '🔒 Unlock TC' }}
      </button>
      <button
        :class="['lock-btn', { unlocked: timeUnlocked }]"
        :title="timeUnlocked
          ? 'Marker times can now be changed — click to protect them again'
          : 'Allow moving markers to a different timecode'"
        @click="toggleTimeUnlock"
      >
        {{ timeUnlocked ? '🔓 Time unlocked' : '🔒 Unlock time' }}
      </button>
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
            <!-- Section break marker: read-only context, shown above the tags
                 because it's a property of the track, not of the cue. -->
            <div v-if="cue.section != null" class="cleanup-element locked section-break">
              <span class="cleanup-lock" title="Section breaks can't be deleted here">🔒</span>
              <span class="cleanup-badge badge-section">SECTION</span>
              <span class="cleanup-text">Section {{ cue.section + 1 }} starts here</span>
            </div>

            <!-- Tags first (cue/TC/MIDI), so a cue sits above the note at the
                 same beat, matching how d3 stacks them on the timeline. -->
            <template v-for="tag in cue.tags" :key="tag.type">
              <!-- TC tags are shown for context and protected until unlocked,
                   because changing one shifts every timecode after it. -->
              <div v-if="tag.type === TC_TYPE && !tcUnlocked" class="cleanup-element locked">
                <span class="cleanup-lock" title="TC tags are protected — use “Unlock TC” to edit or delete them">🔒</span>
                <span class="cleanup-badge badge-tc">TC</span>
                <span class="cleanup-text">{{ tag.text }}</span>
              </div>
              <div v-else class="cleanup-element">
                <input
                  type="checkbox"
                  :checked="isSelected(tagKey(track.uid, cue.beat, tag.type))"
                  @change="toggle(tagKey(track.uid, cue.beat, tag.type))"
                />
                <!-- CUE tags use a d3-style beveled chip and can be renumbered;
                     MIDI keeps a read-only badge. -->
                <template v-if="tag.type === CUE_TYPE">
                  <template v-if="editingKey === tagKey(track.uid, cue.beat, CUE_TYPE)">
                    <input
                      v-focus
                      class="cleanup-edit-input cue-edit"
                      :value="editValue"
                      @input="editValue = sanitizeCueNumber($event.target.value)"
                      @keyup.enter="!isSaveDisabled && saveRename(track, cue, tag)"
                      @keyup.esc="cancelEdit"
                      @keydown.tab.exact.prevent="moveEdit(1)"
                      @keydown.tab.shift.prevent="moveEdit(-1)"
                      inputmode="decimal"
                      placeholder="Cue #"
                    />
                    <button class="edit-action" :disabled="isSaveDisabled || saving" @click="saveRename(track, cue, tag)">Save</button>
                    <button class="edit-action cancel" :disabled="saving" @click="cancelEdit">Cancel</button>
                  </template>
                  <template v-else>
                    <span
                      class="cue-chip editable"
                      title="Click to renumber this cue"
                      @click="startEdit(tagKey(track.uid, cue.beat, CUE_TYPE), tag.text)"
                    >CUE {{ tag.text }}</span>
                  </template>
                </template>
                <!-- Unlocked TC: editable like a note, but validated as a
                     timecode so a typo can't corrupt the track's mapping. -->
                <template v-else-if="tag.type === TC_TYPE">
                  <span class="cleanup-badge badge-tc">TC</span>
                  <template v-if="editingKey === tagKey(track.uid, cue.beat, TC_TYPE)">
                    <input
                      v-focus
                      :class="['cleanup-edit-input', 'tc-edit', { invalid: editValue && isSaveDisabled }]"
                      v-model="editValue"
                      @keyup.enter="!isSaveDisabled && saveRename(track, cue, tag)"
                      @keyup.esc="cancelEdit"
                      @keydown.tab.exact.prevent="moveEdit(1)"
                      @keydown.tab.shift.prevent="moveEdit(-1)"
                      placeholder="h:mm:ss:ff"
                    />
                    <button class="edit-action" :disabled="isSaveDisabled || saving" @click="saveRename(track, cue, tag)">Save</button>
                    <button class="edit-action cancel" :disabled="saving" @click="cancelEdit">Cancel</button>
                  </template>
                  <template v-else>
                    <span
                      class="cleanup-text editable"
                      title="Click to edit this timecode tag"
                      @click="startEdit(tagKey(track.uid, cue.beat, TC_TYPE), tag.text)"
                    >{{ tag.text }}</span>
                  </template>
                </template>
                <template v-else>
                  <span class="cleanup-badge badge-midi">{{ tagTypeLabel(tag.type) }}</span>
                  <span class="cleanup-text">{{ tag.text }}</span>
                </template>

                <!-- Move this tag (and only this tag) to another timecode -->
                <template v-if="timeUnlocked">
                  <template v-if="movingKey === moveKey(track.uid, cue.beat, tag.type)">
                    <input
                      v-focus
                      :class="['cleanup-edit-input', 'tc-edit', { invalid: moveValue && isMoveDisabled }]"
                      v-model="moveValue"
                      @keyup.enter="!isMoveDisabled && saveMove(track, cue, tag)"
                      @keyup.esc="cancelMove"
                      placeholder="h:mm:ss:ff"
                    />
                    <button class="edit-action" :disabled="isMoveDisabled || saving" @click="saveMove(track, cue, tag)">Move</button>
                    <button class="edit-action cancel" :disabled="saving" @click="cancelMove">Cancel</button>
                  </template>
                  <span
                    v-else
                    class="move-time editable"
                    title="Click to move this to a different timecode"
                    @click="startMove(moveKey(track.uid, cue.beat, tag.type), cue.tc)"
                  >{{ cue.tc || '—' }}</span>
                </template>
              </div>
            </template>

            <!-- Note below the tags -->
            <div v-if="cue.note" class="cleanup-element">
              <input
                type="checkbox"
                :checked="isSelected(noteKey(track.uid, cue.beat))"
                @change="toggle(noteKey(track.uid, cue.beat))"
              />
              <span class="cleanup-badge badge-note">NOTE</span>
              <template v-if="editingKey === noteKey(track.uid, cue.beat)">
                <input
                  v-focus
                  class="cleanup-edit-input"
                  v-model="editValue"
                  @keyup.enter="!isSaveDisabled && saveRename(track, cue, null)"
                  @keyup.esc="cancelEdit"
                  @keydown.tab.exact.prevent="moveEdit(1)"
                  @keydown.tab.shift.prevent="moveEdit(-1)"
                  placeholder="Note text"
                />
                <button class="edit-action" :disabled="isSaveDisabled || saving" @click="saveRename(track, cue, null)">Save</button>
                <button class="edit-action cancel" :disabled="saving" @click="cancelEdit">Cancel</button>
              </template>
              <template v-else>
                <span
                  class="cleanup-text editable"
                  title="Click to rename this note"
                  @click="startEdit(noteKey(track.uid, cue.beat), cue.note)"
                >{{ cue.note }}</span>
              </template>

              <!-- Move this note (and only this note) to another timecode -->
              <template v-if="timeUnlocked">
                <template v-if="movingKey === moveKey(track.uid, cue.beat, null)">
                  <input
                    v-focus
                    :class="['cleanup-edit-input', 'tc-edit', { invalid: moveValue && isMoveDisabled }]"
                    v-model="moveValue"
                    @keyup.enter="!isMoveDisabled && saveMove(track, cue, null)"
                    @keyup.esc="cancelMove"
                    placeholder="h:mm:ss:ff"
                  />
                  <button class="edit-action" :disabled="isMoveDisabled || saving" @click="saveMove(track, cue, null)">Move</button>
                  <button class="edit-action cancel" :disabled="saving" @click="cancelMove">Cancel</button>
                </template>
                <span
                  v-else
                  class="move-time editable"
                  title="Click to move this to a different timecode"
                  @click="startMove(moveKey(track.uid, cue.beat, null), cue.tc)"
                >{{ cue.tc || '—' }}</span>
              </template>
            </div>
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

// TC tags are protected by default: they define the timecode mapping for the
// whole track, so editing or deleting one shifts every timecode after it. The
// toggle makes that an explicit, deliberate act rather than a stray click.
const tcUnlocked = ref(false)

const toggleTcUnlock = () => {
  tcUnlocked.value = !tcUnlocked.value
  if (!tcUnlocked.value) {
    // Re-locking must not leave a TC tag armed for deletion or mid-edit.
    const next = new Set()
    for (const k of selected.value) {
      if (!k.endsWith(`tag:${TC_TYPE}`)) {
        next.add(k)
      }
    }
    selected.value = next
    if (editingKey.value && editingKey.value.endsWith(`tag:${TC_TYPE}`)) {
      cancelEdit()
    }
  }
}

// Inline rename state: the key of the single element being edited and its
// working value. `saving` blocks the buttons while a write is in flight.
const editingKey = ref(null)
const editValue = ref('')

// Clicking a note/cue swaps it for an input, so focus and select the text to
// let the user type straight over it without a second click.
const vFocus = {
  mounted: (el) => {
    el.focus()
    el.select()
  }
}
const saving = ref(false)

// Cue numbers follow d3's schema X, X.Y, X.Y.Z (digits in dot-separated groups).
const CUE_NUMBER_RE = /^\d+(\.\d+)*$/
const sanitizeCueNumber = (value) => (value || '').replace(/[^\d.]/g, '')

// TC tags read back from d3 as h:mm:ss:ff (e.g. "1:00:00:0"), and d3 also
// renders them with a dot before the frames, so accept either separator.
// Minutes and seconds take 1 OR 2 digits: typing "1:5:12:0" is the natural way
// to edit a field, and requiring "05" left the value silently invalid.
const TIMECODE_RE = /^(\d{1,3}):(\d{1,2}):(\d{1,2})[:.](\d{1,3})$/

// Parse a timecode into its parts, or null if it isn't one. Ranges are checked
// numerically rather than by digit pattern so "1:5:9:0" is accepted but
// "1:75:00:00" is not. Frames are bounded server-side, where the fps is known.
const parseTimecode = (value) => {
  const m = TIMECODE_RE.exec((value || '').trim())
  if (!m) {
    return null
  }
  const parts = { h: Number(m[1]), m: Number(m[2]), s: Number(m[3]), f: Number(m[4]) }
  if (parts.m > 59 || parts.s > 59) {
    return null
  }
  return parts
}

// Canonical h:mm:ss:ff, so what we send and echo back is consistent regardless
// of how it was typed.
const formatTimecode = (value) => {
  const p = parseTimecode(value)
  if (!p) {
    return null
  }
  const pad = (n, w) => String(n).padStart(w, '0')
  return `${pad(p.h, 2)}:${pad(p.m, 2)}:${pad(p.s, 2)}:${pad(p.f, 2)}`
}

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
      const sectionMatch = c.section != null && `section ${c.section + 1}`.includes(q)
      return noteMatch || tagMatch || sectionMatch
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
        if (tag.type !== TC_TYPE || tcUnlocked.value) {
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

// --- Inline rename (notes & cue numbers) ---------------------------------

// True when the current edit value can't be saved: empty for a note, or not a
// valid cue number for a cue (key ends with the CUE tag suffix).
const isSaveDisabled = computed(() => {
  const v = (editValue.value || '').trim()
  if (!editingKey.value) {
    return true
  }
  if (editingKey.value.endsWith(`tag:${CUE_TYPE}`)) {
    return !CUE_NUMBER_RE.test(v)
  }
  if (editingKey.value.endsWith(`tag:${TC_TYPE}`)) {
    return parseTimecode(v) === null
  }
  return v === ''
})

const startEdit = (key, currentValue) => {
  editingKey.value = key
  editValue.value = currentValue || ''
}

const cancelEdit = () => {
  editingKey.value = null
  editValue.value = ''
}

// Rename a note (tag === null) or a cue number in place. Writing at the same
// beat overrides that element and leaves the cue's position unchanged.
const saveRename = async (track, cue, tag) => {
  if (isSaveDisabled.value || saving.value) {
    return
  }
  const kind = tag ? 'tag' : 'note'
  const text = (editValue.value || '').trim()
  const payload = {
    uid: track.uid,
    beat: cue.beat,
    kind,
    text,
    // Write back the tag's own type so an unlocked TC edit stays a TC tag
    // instead of being rewritten as a cue.
    tagType: tag ? tag.type : CUE_TYPE
  }

  saving.value = true
  error.value = ''
  statusMsg.value = ''
  const script = [
    'import json',
    `p = json.loads(${JSON.stringify(JSON.stringify(payload))})`,
    'try:',
    "    track = UidManager.get().getResource(int(p['uid']))",
    '    if track is None:',
    '        out = {"ok": False, "error": "track not found"}',
    '    else:',
    "        if p['kind'] == 'note':",
    "            track.setNoteAtBeat(float(p['beat']), p['text'])",
    '        else:',
    "            track.setTagAtBeat(float(p['beat']), Tag(int(p['tagType']), p['text']))",
    '        out = {"ok": True}',
    'except Exception as e:',
    '    out = {"ok": False, "error": str(e)}',
    'return out'
  ].join('\n')

  try {
    const result = await executePythonVerbose(props.directorEndpoint, script)
    let data = result.returnValue
    if (typeof data === 'string') {
      data = data.trim() === '' ? {} : JSON.parse(data)
    }
    data = data || {}
    if (data.ok === false) {
      throw new Error(data.error || 'Rename failed')
    }
    // Update local state in place so the list reflects the change without a
    // re-pull (keeps selection and scroll position).
    if (kind === 'note') {
      cue.note = text
    } else {
      tag.text = text
    }
    statusMsg.value =
      kind === 'note'
        ? 'Note renamed.'
        : tag.type === TC_TYPE
          ? 'Timecode tag updated.'
          : 'Cue number updated.'
    editingKey.value = null
    editValue.value = ''
  } catch (err) {
    console.error('Error renaming in d3:', err)
    error.value = `Could not rename: ${err.message}`
  } finally {
    saving.value = false
  }
}

// Every editable element across the visible tracks, flattened in the order the
// list reads (per cue: the CUE tag, then the note). This is the path Tab walks.
const editableItems = computed(() => {
  const items = []
  for (const track of filteredTracks.value) {
    for (const cue of track.cues) {
      // Walk cue.tags in render order so Tab follows what's on screen; TC tags
      // only join the path once unlocked.
      for (const tag of cue.tags || []) {
        if (tag.type !== CUE_TYPE && !(tag.type === TC_TYPE && tcUnlocked.value)) {
          continue
        }
        items.push({
          key: tagKey(track.uid, cue.beat, tag.type),
          value: tag.text,
          track,
          cue,
          tag
        })
      }
      if (cue.note) {
        items.push({
          key: noteKey(track.uid, cue.beat),
          value: cue.note,
          track,
          cue,
          tag: null
        })
      }
    }
  }
  return items
})

// Tab / Shift+Tab commit the current rename and open the next (or previous)
// element for editing, so a track's cues can be walked from the keyboard.
// Tabbing past either end closes the editor, like tabbing out of a form.
const moveEdit = async (delta) => {
  if (saving.value) {
    return
  }
  const items = editableItems.value
  const current = items.findIndex((i) => i.key === editingKey.value)
  if (current === -1) {
    return
  }

  const item = items[current]
  // Only write when the value actually changed — an unchanged Tab is pure
  // navigation and shouldn't cost a round trip to d3.
  if ((editValue.value || '').trim() !== item.value) {
    if (isSaveDisabled.value) {
      return // invalid entry: keep the user on this field rather than losing it
    }
    await saveRename(item.track, item.cue, item.tag)
    if (error.value) {
      return // write failed — stay put so the edit isn't silently dropped
    }
  }

  const nextKey = items[current + delta]?.key
  // Re-read the list after the save so the value we load is the current one.
  const next = nextKey ? editableItems.value.find((i) => i.key === nextKey) : null
  if (!next) {
    cancelEdit()
    return
  }
  startEdit(next.key, next.value)
}

// --- Moving an element to a different timecode ----------------------------

// Marker positions are protected by default: moving one rewrites where it
// fires in the show, so it sits behind its own unlock.
const timeUnlocked = ref(false)

// Which element is having its time changed, and the timecode being typed.
// Kept separate from the rename state so the two can't tangle.
const movingKey = ref(null)
const moveValue = ref('')

const moveKey = (uid, beat, type) =>
  type == null ? `${uid}|${beat}|move:note` : `${uid}|${beat}|move:tag:${type}`

const isMoveDisabled = computed(() => parseTimecode(moveValue.value) === null)

const startMove = (key, currentTc) => {
  cancelEdit()
  movingKey.value = key
  moveValue.value = currentTc || ''
}

const cancelMove = () => {
  movingKey.value = null
  moveValue.value = ''
}

const toggleTimeUnlock = () => {
  timeUnlocked.value = !timeUnlocked.value
  if (!timeUnlocked.value) {
    cancelMove()
  }
}

// Move a single element (a note, or one tag) to a different timecode. Only the
// clicked element moves; anything else sharing that beat stays where it is.
//
// d3 has no timecodeToBeat, so the beat is derived here: each TC tag starts a
// timecode range, and within a range timecode advances with track time. The
// resolved beat is only written once it maps back to the requested timecode.
const saveMove = async (track, cue, tag) => {
  if (isMoveDisabled.value || saving.value) {
    return
  }
  const kind = tag ? 'tag' : 'note'
  const payload = {
    uid: track.uid,
    beat: cue.beat,
    kind,
    tagType: tag ? tag.type : TC_TYPE,
    tc: formatTimecode(moveValue.value)
  }

  saving.value = true
  error.value = ''
  statusMsg.value = ''
  const script = [
    'import json',
    `p = json.loads(${JSON.stringify(JSON.stringify(payload))})`,
    'tm = guisystem.currentTransportManager',
    'fps = float(tm.customTimelineFps)',
    'if fps <= 0:',
    '    fps = 30.0',
    'track = UidManager.get().getResource(int(p["uid"]))',
    'if track is None:',
    '    return {"ok": False, "error": "track not found"}',
    // Timecode counts whole frames, and at 29.97 a timecode second is NOT a real
    // second: d3 turns time into a frame count at the true fps, then formats it
    // using the nominal integer fps (30 for 29.97, non-drop-frame). Doing the
    // maths in seconds drifts ~0.1% — seconds off by the end of a long track —
    // so everything below works in frames and only converts to time at the edges.
    'nom = int(round(fps))',
    'if nom <= 0:',
    '    nom = 30',
    'def tcToFrames(s):',
    '    q = str(s).replace(".", ":").split(":")',
    '    while len(q) < 4:',
    '        q.append("0")',
    '    try:',
    '        return (int(q[0])*3600 + int(q[1])*60 + int(q[2]))*nom + int(q[3])',
    '    except:',
    '        return None',
    'def framesToTc(F):',
    '    F = int(round(F))',
    '    if F < 0:',
    '        F = 0',
    '    return "%02d:%02d:%02d:%02d" % (F//(nom*3600), (F//(nom*60))%60, (F//nom)%60, F%nom)',
    'target = tcToFrames(p["tc"])',
    'if target is None:',
    '    return {"ok": False, "error": "could not parse that timecode"}',
    // The frame field counts against the nominal fps, so 29 is valid at 29.97.
    'tcParts = str(p["tc"]).replace(".", ":").split(":")',
    'if len(tcParts) > 3 and int(tcParts[3]) >= nom:',
    '    return {"ok": False, "error": "frames must be less than " + str(nom) + " at this timeline fps"}',
    // Each TC tag opens a new timecode range; beat 0 is the implicit zero-based
    // range covering everything before the first tag. Values are frame counts.
    'regions = {0.0: 0}',
    'for b in track.cueBeats():',
    '    for tg in track.tagsAtBeat(b):',
    '        if tg.type == 0:',
    '            v = tcToFrames(tg.text)',
    '            if v is not None:',
    '                regions[float(b)] = v',
    'rb = sorted(regions.keys())',
    'def fwd(beat):',
    '    base = rb[0]',
    '    for x in rb:',
    '        if x <= beat + 1e-6:',
    '            base = x',
    '    return regions[base] + int(round((track.beatToTime(beat) - track.beatToTime(base)) * fps))',
    'newBeat = None',
    'for i in range(len(rb)):',
    '    base = rb[i]',
    '    nxt = rb[i+1] if i+1 < len(rb) else None',
    '    cand = track.timeToBeat(track.beatToTime(base) + (target - regions[base]) / fps)',
    '    if cand < base - 1e-6:',
    '        continue',
    '    if nxt is not None and cand >= nxt - 1e-6:',
    '        continue',
    '    newBeat = cand',
    '    break',
    // A TC tag restarts timecode partway through a track, so the track's
    // timecode is a set of spans with gaps between them. If the target lands in
    // a gap, no beat has that timecode — say which spans do exist rather than
    // just refusing.
    'if newBeat is None:',
    '    limit = float(track.lengthInBeats)',
    '    spans = []',
    '    for i in range(len(rb)):',
    '        s = rb[i]',
    '        e = rb[i+1] if i+1 < len(rb) else limit',
    '        if e > limit:',
    '            e = limit',
    '        if e <= s:',
    '            continue',
    '        endFrames = regions[s] + int(round((track.beatToTime(e) - track.beatToTime(s)) * fps))',
    '        if i + 1 < len(rb):',
    '            endFrames = endFrames - 1',
    '        spans.append(framesToTc(regions[s]) + "-" + framesToTc(endFrames))',
    '    return {"ok": False, "error": "no beat on this track has that timecode. A TC tag restarts timecode partway through, so this track only covers " + " and ".join(spans)}',
    // Never write a beat that cannot be confirmed to map back to what was asked
    // for. One frame of slack absorbs rounding at the time/beat boundary.
    'if abs(fwd(newBeat) - target) > 1:',
    '    return {"ok": False, "error": "could not confirm the new timecode (round-trip mismatch)"}',
    // beatToTimecode is transport-wide, so it is only a meaningful second
    // opinion on the track that is actually loaded.
    'try:',
    '    isCurrent = (state.localOrDirectorState().track.uid == track.uid)',
    'except:',
    '    isCurrent = False',
    'if isCurrent:',
    '    try:',
    '        rt = tcToFrames(str(tm.beatToTimecode(newBeat)))',
    '    except:',
    '        rt = None',
    '    if rt is None or abs(rt - target) > 1:',
    '        return {"ok": False, "error": "d3 reads that beat as " + str(tm.beatToTimecode(newBeat)) + ", not " + str(p["tc"]) + " — refusing to write it"}',
    'try:',
    '    maxBeat = float(track.lengthInBeats)',
    'except:',
    '    maxBeat = None',
    'if newBeat < -1e-6 or (maxBeat is not None and newBeat > maxBeat + 1e-6):',
    '    return {"ok": False, "error": "that timecode falls outside the track length"}',
    'oldBeat = float(p["beat"])',
    'if abs(newBeat - oldBeat) < 1e-6:',
    '    return {"ok": True, "moved": False}',
    'if p["kind"] == "note":',
    '    text = track.noteAtBeat(oldBeat)',
    '    if not text:',
    '        return {"ok": False, "error": "there is no note at that beat any more"}',
    '    overwrote = bool(track.noteAtBeat(newBeat))',
    '    track.removeNoteAtBeat(oldBeat)',
    '    track.setNoteAtBeat(newBeat, text)',
    'else:',
    '    tt = int(p["tagType"])',
    '    text = None',
    '    for tg in track.tagsAtBeat(oldBeat):',
    '        if tg.type == tt:',
    '            text = tg.text',
    '            break',
    '    if text is None:',
    '        return {"ok": False, "error": "that tag is no longer at that beat"}',
    '    overwrote = False',
    '    for tg in track.tagsAtBeat(newBeat):',
    '        if tg.type == tt:',
    '            overwrote = True',
    '            break',
    '    track.removeTagAtBeat(oldBeat, tt)',
    '    track.setTagAtBeat(newBeat, Tag(tt, text))',
    'return {"ok": True, "moved": True, "beat": newBeat, "overwrote": overwrote}'
  ].join('\n')

  const requested = payload.tc
  try {
    const result = await executePythonVerbose(props.directorEndpoint, script)
    let data = result.returnValue
    if (typeof data === 'string') {
      data = data.trim() === '' ? {} : JSON.parse(data)
    }
    data = data || {}
    if (data.ok === false) {
      throw new Error(data.error || 'Move failed')
    }
    cancelMove()
    if (data.moved === false) {
      statusMsg.value = 'Already at that timecode — nothing moved.'
    } else {
      // Positions changed, so re-pull for ground truth (and correct ordering).
      await pull()
      statusMsg.value = data.overwrote
        ? `Moved to ${requested}, replacing what was already at that beat.`
        : `Moved to ${requested}.`
    }
  } catch (err) {
    console.error('Error moving in d3:', err)
    error.value = `Could not move: ${err.message}`
  } finally {
    saving.value = false
  }
}

// Pull every note and cue from all tracks in the session.
const pull = async () => {
  loading.value = true
  error.value = ''
  statusMsg.value = ''
  confirming.value = false
  editingKey.value = null
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
    '    tm = None',
    '    try:',
    '        tm = guisystem.currentTransportManager',
    '    except:',
    '        tm = None',
    '    out = []',
    '    for t in resourceManager.allResources(TrackType):',
    // Deleted tracks stay in the resource list, distinguished only by living
    // under trash/ (e.g. "trash/objects/track/foo.apx"). Skip them, otherwise a
    // deleted track shows up alongside the live one with the same name. If the
    // path can't be read, keep the track rather than hide it silently.
    '        try:',
    '            tpath = str(t.path).replace("\\\\", "/").lower()',
    '        except:',
    '            tpath = ""',
    '        if tpath.startswith("trash/") or "/trash/" in tpath:',
    '            continue',
    '        try:',
    '            uid = str(t.uid)',
    '        except:',
    '            uid = ""',
    '        try:',
    '            name = str(t.description)',
    '        except:',
    '            name = ""',
    '        cues = []',
    // Section breaks live outside the cue/note system: a track exposes them as
    // nSections() boundaries. Section 0 starts at beat 0 (the track start, not
    // a break) so it is skipped. Beats are rounded to a common key because a
    // section boundary and a cue at the "same" beat can differ in the last bits.
    '        secBeats = {}',
    '        try:',
    '            nSec = t.nSections()',
    '        except:',
    '            nSec = 0',
    '        for i in range(1, nSec):',
    '            try:',
    '                secBeats[round(t.sectionToBeat(i), 6)] = i',
    '            except:',
    '                pass',
    '        beats = []',
    '        seen = {}',
    '        for b in t.cueBeats():',
    '            k = round(b, 6)',
    '            if k not in seen:',
    '                seen[k] = True',
    '                beats.append(b)',
    '        for k in secBeats:',
    '            if k not in seen:',
    '                seen[k] = True',
    '                beats.append(k)',
    '        beats.sort()',
    '        for beat in beats:',
    '            note = t.noteAtBeat(beat)',
    '            tags = []',
    '            for tag in t.tagsAtBeat(beat):',
    '                tags.append({"type": tag.type, "text": tag.text})',
    '            section = secBeats.get(round(beat, 6))',
    '            if note or tags or section is not None:',
    '                try:',
    '                    secs = t.beatToTime(beat)',
    '                except:',
    '                    secs = None',
    '                tc = ""',
    '                if tm is not None:',
    '                    try:',
    '                        tc = str(tm.beatToTimecode(beat))',
    '                    except:',
    '                        tc = ""',
    '                cues.append({"beat": beat, "secs": secs, "tc": tc, "note": note, "tags": tags, "section": section})',
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
    const sections = list.reduce(
      (n, t) => n + t.cues.filter(c => c.section != null).length,
      0
    )
    statusMsg.value = sections
      ? `Pulled ${total} cue(s) across ${list.length} track(s), including ${sections} section break(s).`
      : `Pulled ${total} cue(s) across ${list.length} track(s).`
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
        if ((tag.type !== TC_TYPE || tcUnlocked.value) && isSelected(tagKey(t.uid, c.beat, tag.type))) {
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
.badge-section { background-color: #00695c; color: #e0f2f1; }

/* Section breaks read as a divider in the track, so give them a rule above. */
.section-break {
  border-top: 1px dashed #00695c;
  padding-top: 0.3rem;
  margin-top: 0.15rem;
}

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

/* Inline rename: the note text / cue chip is itself the click target, so give
   it a hover cue instead of a separate pencil button. */
.editable { cursor: pointer; }
.cleanup-text.editable:hover {
  color: #64b5f6;
  text-decoration: underline;
  text-underline-offset: 2px;
}
.cue-chip.editable:hover { background: #4a4a4a; }

.cleanup-edit-input {
  padding: 0.2rem 0.4rem;
  border: 2px solid #424242;
  border-radius: 4px;
  background-color: #121212;
  color: #e0e0e0;
  font-family: inherit;
  font-size: 0.85rem;
  min-width: 12rem;
}
.cleanup-edit-input.cue-edit { min-width: 5rem; width: 5rem; text-align: center; }
.cleanup-edit-input.tc-edit { min-width: 8rem; width: 8rem; font-variant-numeric: tabular-nums; }

/* Unlock toggles: muted while protecting, amber once the guard is off so the
   unlocked state is obvious at a glance. */
.lock-btn {
  background: none;
  border: 1px solid #424242;
  border-radius: 4px;
  color: #9e9e9e;
  cursor: pointer;
  font-size: 0.78rem;
  padding: 0.2rem 0.5rem;
  white-space: nowrap;
}
.lock-btn:hover { border-color: #616161; color: #e0e0e0; }
.lock-btn.unlocked {
  border-color: #ef6c00;
  color: #ffb74d;
  background-color: rgba(239, 108, 0, 0.12);
}

/* Per-element timecode, shown only while time is unlocked. Clicking it opens
   the move editor for that one element. */
.move-time {
  color: #ffb74d;
  font-size: 0.75rem;
  font-variant-numeric: tabular-nums;
  margin-left: auto;
  padding-left: 0.5rem;
  white-space: nowrap;
}
.move-time:hover {
  color: #ffe0b2;
  text-decoration: underline;
  text-underline-offset: 2px;
}
.cleanup-edit-input:focus { outline: none; border-color: #64b5f6; }
/* Typed something that won't validate: say so rather than just disabling Save. */
.cleanup-edit-input.invalid,
.cleanup-edit-input.invalid:focus { border-color: #c62828; }

.edit-action {
  padding: 0.2rem 0.6rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-family: inherit;
  font-size: 0.8rem;
  background-color: #1976d2;
  color: #fff;
}
.edit-action:hover:not(:disabled) { background-color: #1565c0; }
.edit-action:disabled { background-color: #37474f; cursor: default; opacity: 0.7; }
.edit-action.cancel { background-color: #424242; }
.edit-action.cancel:hover:not(:disabled) { background-color: #525252; }

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
