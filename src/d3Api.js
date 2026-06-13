// Shared helpers for talking to the d3 director REST API. Used by both the
// Markers page (App.vue) and the Timeline Cleanup page so the URL handling and
// Python-execute plumbing live in one place.

// Build a normalized http(s) base URL for the director REST API from the
// endpoint extracted from the plugin's URL query (e.g. "host:80").
export const apiBase = (directorEndpoint) => {
  return directorEndpoint.startsWith('http://') || directorEndpoint.startsWith('https://')
    ? directorEndpoint
    : `http://${directorEndpoint}`
}

// POST a block of Python to the director and verify it ran. The execute API
// returns { status, d3Log, pythonLog, returnValue }; a non-zero status.code
// means the script raised. NOTE: scripts run as Python 2.7 on the server.
export const executePython = async (directorEndpoint, script) => {
  const response = await fetch(`${apiBase(directorEndpoint)}/api/session/python/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ script })
  })

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }

  const result = await response.json()
  if (result.status && result.status.code !== 0) {
    throw new Error(`Python execute failed: ${result.status.message || JSON.stringify(result.status)}`)
  }
  return result
}
