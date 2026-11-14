# S1: live PDF, text selection → page-fraction boxes

**Tests:** can we select text in the real seed PDF (`app/backend/seed/souls-of-black-folk-ch1.pdf`) with pdf.js's text layer, store each selection as `page` + `quote` + `rects` (fractions of the page, SPEC §3.3), and redraw those boxes correctly at any zoom?

**Result: yes.** Real mouse selections give tight per-line boxes (e.g. "double-consciousness" → `{x: 0.595, y: 0.5605, w: 0.1713, h: 0.017}` on p. 2), and they stay on the right words from 130% to 170% with nothing recomputed. Seed notes anchor by searching their quote (letters and digits only, like `locate.py`) and become rects the same way.

Run it (from the repo root), then open http://localhost:8765/spikes/0306-pdf-selection/:

```bash
python3 -m http.server 8765 --bind 127.0.0.1
```

What carries over to `app/frontend` (react-pdf wraps the same pdf.js):
- Highlight layer **under** the text layer, `mix-blend-mode: multiply` on the layer (not the boxes), boxes positioned in `%`.
- `rangeToRects()`: `range.getClientRects()` → page fractions, merged one box per line.
- Build text layers before painting canvases: the page is selectable sooner, and a background tab doesn't block on canvas paint.

Plain HTML + pdf.js 3.11.174 from cdnjs, not react-pdf; the Ask button only shows the `/ask` payload (no backend call). `TODO(edge)`: selections across two pages keep only the first page.
