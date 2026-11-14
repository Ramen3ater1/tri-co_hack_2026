import { colorFor } from '../colors.js';

// The coloured boxes for one page's annotations. `rects` are fractions of the page
// (SPEC §3.3), so boxes are placed in % and stay on the right words at any zoom.
// Locked annotations are never passed in: their highlights aren't drawn (SPEC §3.3).
export default function HighlightLayer({ annotations, activeId, pendingRects }) {
  return (
    <div className="highlight-layer" aria-hidden="true">
      {annotations.map((annotation) =>
        (annotation.rects || []).map((rect, i) => (
          <div
            key={`${annotation.id}-${i}`}
            className={`highlight${annotation.id === activeId ? ' active' : ''}`}
            style={{ ...boxStyle(rect), background: colorFor(annotation.author).bg }}
          />
        )),
      )}
      {(pendingRects || []).map((rect, i) => (
        <div key={`pending-${i}`} className="highlight pending" style={boxStyle(rect)} />
      ))}
    </div>
  );
}

function boxStyle(rect) {
  return {
    left: `${rect.x * 100}%`,
    top: `${rect.y * 100}%`,
    width: `${rect.w * 100}%`,
    height: `${rect.h * 100}%`,
  };
}
