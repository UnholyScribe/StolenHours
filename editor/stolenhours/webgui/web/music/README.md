# Dashboard music

Tracks listed in `playlist.json` play in a loop while Stolen Hours is open.
Drop new `.ogg` (or `.wav` / `.mp3`) files here, then add a row to `playlist.json`:

```json
{ "file": "your_track.ogg", "title": "Display name" }
```

Order in the JSON is play order; after the last track it wraps to the first.
Volume is `playlist.json` → `"volume"` (0–1). Mute is remembered in the browser.
