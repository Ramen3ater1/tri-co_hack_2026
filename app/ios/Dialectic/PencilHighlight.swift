// Apple Pencil highlighting in the reader (iPad): drag the Pencil across a passage like a highlighter and the
// text under the stroke is selected; lift it and the Ask | Note panel opens on that passage. Fingers still scroll.
import UIKit
import WebKit

let PENCIL_STROKE_COLOR = UIColor(red: 1, green: 0.86, blue: 0.2, alpha: 0.35)  // highlighter yellow while drawing
let PENCIL_STROKE_WIDTH: CGFloat = 18
let PENCIL_MIN_CHARS = 2   // shorter selections are taps, not highlights

/// Selects the text between two points in the page (WebKit's caretRangeFromPoint), returns it.
let PENCIL_SELECT_JS = """
(function(x0, y0, x1, y1) {
  const a = document.caretRangeFromPoint(x0, y0), b = document.caretRangeFromPoint(x1, y1);
  if (!a || !b) return "";
  const range = document.createRange();
  const forward = a.compareBoundaryPoints(Range.START_TO_START, b) <= 0;
  const s = forward ? a : b, e = forward ? b : a;
  range.setStart(s.startContainer, s.startOffset);
  range.setEnd(e.startContainer, e.startOffset);
  const sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(range);
  return sel.toString();
})
"""

/// A clear layer over the reader that only Apple Pencil touches land on (fingers fall through to the page).
/// The web view's own Pencil gestures sit on its inner views and won the stroke on some drags, so the
/// Pencil's touches never reach them now.
final class PencilOnlyView: UIView {
    override func point(inside point: CGPoint, with event: UIEvent?) -> Bool {
        guard bounds.contains(point), let touches = event?.allTouches, !touches.isEmpty else { return false }
        return touches.allSatisfy { $0.type == .pencil }
    }
}

@MainActor
final class PencilHighlighter: NSObject, UIGestureRecognizerDelegate {
    private weak var webView: WKWebView?
    private let stroke = CAShapeLayer()
    private let path = UIBezierPath()
    private var start: CGPoint = .zero
    private var lastText = ""
    var onHighlight: (String) -> Void = { _ in }

    init(webView: WKWebView) {
        self.webView = webView
        super.init()
        let pan = UIPanGestureRecognizer(target: self, action: #selector(pan(_:)))
        pan.allowedTouchTypes = [NSNumber(value: UITouch.TouchType.pencil.rawValue)]
        pan.delegate = self
        let catcher = PencilOnlyView(frame: webView.bounds)
        catcher.backgroundColor = .clear
        catcher.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        catcher.addGestureRecognizer(pan)
        webView.addSubview(catcher)
        // The Pencil highlights; only fingers scroll the page.
        webView.scrollView.panGestureRecognizer.allowedTouchTypes = [NSNumber(value: UITouch.TouchType.direct.rawValue)]
        stroke.strokeColor = PENCIL_STROKE_COLOR.cgColor
        stroke.fillColor = nil
        stroke.lineWidth = PENCIL_STROKE_WIDTH
        stroke.lineCap = .round
        stroke.lineJoin = .round
        catcher.layer.addSublayer(stroke)
    }

    func gestureRecognizer(_ g: UIGestureRecognizer, shouldRecognizeSimultaneouslyWith other: UIGestureRecognizer) -> Bool { false }

    @objc private func pan(_ g: UIPanGestureRecognizer) {
        guard let webView else { return }
        let point = g.location(in: webView)
        switch g.state {
        case .began:
            start = point
            lastText = ""
            path.removeAllPoints()
            path.move(to: point)
        case .changed:
            path.addLine(to: point)
            stroke.path = path.cgPath
            select(to: point)
        case .ended:
            stroke.path = nil
            Task {
                let text = await select(to: point).trimmingCharacters(in: .whitespacesAndNewlines)
                if text.count >= PENCIL_MIN_CHARS { onHighlight(text) }
            }
        default:
            stroke.path = nil
        }
    }

    /// Points are in the web view; the page's coordinates are the same in CSS pixels at zoom 1.
    @discardableResult
    private func select(to point: CGPoint) async -> String {
        guard let webView else { return "" }
        let scale = webView.scrollView.zoomScale
        let js = "\(PENCIL_SELECT_JS)(\(start.x / scale), \(start.y / scale), \(point.x / scale), \(point.y / scale))"
        let text = (try? await webView.evaluateJavaScript(js)) as? String ?? lastText
        lastText = text
        return text
    }

    private func select(to point: CGPoint) { Task { await select(to: point) } }
}
