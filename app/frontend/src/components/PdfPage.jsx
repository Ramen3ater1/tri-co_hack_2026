import { Page } from 'react-pdf';
import HighlightLayer from './HighlightLayer.jsx';

// One page of the reading: react-pdf's canvas and text layer, our highlights under the
// text layer (styles.css says why), and any popover or answer card anchored on this page
// (`children`). The reader finds the page from a selection by `data-page`.
export default function PdfPage({ pageNumber, scale, annotations, activeId, pendingRects, pageRef, onRendered, children }) {
  return (
    <div className="pdf-page" data-page={pageNumber} ref={pageRef}>
      <span className="page-number">p. {pageNumber}</span>
      <Page pageNumber={pageNumber} scale={scale} renderAnnotationLayer={false} loading="" onRenderSuccess={onRendered}>
        <HighlightLayer annotations={annotations} activeId={activeId} pendingRects={pendingRects} />
        {children}
      </Page>
    </div>
  );
}

// A DOM range over a page's text layer → boxes as fractions of the page, merged so each
// line of the selection is one box (from spike S1, spikes/0306-pdf-selection).
export function rangeToRects(range, pageEl) {
  const page = pageEl.querySelector('.react-pdf__Page').getBoundingClientRect();
  const raw = [...range.getClientRects()]
    .filter((r) => r.width > 0.5 && r.height > 0.5)
    .map((r) => ({
      x: (r.left - page.left) / page.width,
      y: (r.top - page.top) / page.height,
      w: r.width / page.width,
      h: r.height / page.height,
    }))
    // TODO(edge): a selection across two pages keeps only the first page's boxes.
    .filter((r) => r.x < 1 && r.y < 1 && r.x + r.w > 0 && r.y + r.h > 0);

  raw.sort((a, b) => a.y - b.y || a.x - b.x);
  const lines = [];
  for (const r of raw) {
    const line = lines.find((l) => Math.abs((l.y + l.h / 2) - (r.y + r.h / 2)) < l.h * 0.5);
    if (!line) {
      lines.push({ ...r });
      continue;
    }
    const right = Math.max(line.x + line.w, r.x + r.w);
    const bottom = Math.max(line.y + line.h, r.y + r.h);
    line.x = Math.min(line.x, r.x);
    line.y = Math.min(line.y, r.y);
    line.w = right - line.x;
    line.h = bottom - line.y;
  }
  const round = (v) => Math.round(v * 10000) / 10000;
  return lines.map((r) => ({ x: round(r.x), y: round(r.y), w: round(r.w), h: round(r.h) }));
}

// Where to put a popover or card under a passage: just below its last box, lined up with
// its first, kept inside the page. Returns inline style for a .page-overlay.
export function overlayStyle(rects, width) {
  const bottom = Math.max(...rects.map((r) => r.y + r.h));
  const left = Math.min(...rects.map((r) => r.x));
  return {
    top: `calc(${bottom * 100}% + 10px)`,
    left: `max(8px, min(calc(${left * 100}% - 40px), calc(100% - ${width + 8}px)))`,
  };
}

// Is a click (page fractions) inside one of these boxes?
export function hits(rects, x, y) {
  return (rects || []).some((r) => x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h);
}
