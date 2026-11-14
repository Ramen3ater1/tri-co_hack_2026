// Apple Pencil highlighting in the reader (iPad): drag the Pencil across a passage like a highlighter and the
// text under the stroke is selected; lift it and the Ask | Note panel opens on that passage.
// Like Notability: the Pencil only ever highlights and fingers only ever scroll. Every other gesture in the web
// view (scrolling, zoom, iPad's own text selection) is set to fingers only, so Pencil touches reach nothing but
// the stroke recognizer below.
import UIKit
import WebKit

let PENCIL_STROKE_COLOR = UIColor(red: 1, green: 0.86, blue: 0.2, alpha: 0.35)  // highlighter yellow while drawing
let PENCIL_STROKE_WIDTH: CGFloat = 18
let PENCIL_MIN_CHARS = 2   // shorter selections are taps, not highlights
let FINGERS_ONLY_RECHECK: TimeInterval = 0.5  // the page makes new inner scroll views as it loads; re-check this often

/// Selects the text between two points in the page (WebKit's caretRangeFromPoint), returns it.
let PENCIL_SELECT_JS = """
(function(x0, y0, x1, y1) {
  // Points arrive in document coordinates; caretRangeFromPoint wants the viewport's.
  x0 -= window.scrollX; x1 -= window.scrollX; y0 -= window.scrollY; y1 -= window.scrollY;
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

private let PENCIL = [NSNumber(value: UITouch.TouchType.pencil.rawValue)]
private let FINGERS = [NSNumber(value: UITouch.TouchType.direct.rawValue)]

/// Starts on the Pencil's first touch (no movement threshold, unlike a pan), and keeps those touches from
/// the page underneath.
final class PencilStrokeRecognizer: UIGestureRecognizer {
    override func touchesBegan(_ touches: Set<UITouch>, with event: UIEvent) { state = .began }
    override func touchesMoved(_ touches: Set<UITouch>, with event: UIEvent) { state = .changed }
    override func touchesEnded(_ touches: Set<UITouch>, with event: UIEvent) { state = .ended }
    override func touchesCancelled(_ touches: Set<UITouch>, with event: UIEvent) { state = .cancelled }
}

@MainActor
final class PencilHighlighter: NSObject, UIGestureRecognizerDelegate {
    private weak var webView: WKWebView?
    private let recognizer: PencilStrokeRecognizer
    private let stroke = CAShapeLayer()
    private let path = UIBezierPath()
    private var start: CGPoint = .zero
    private var lastText = ""
    private var timer: Timer?
    var onHighlight: (String) -> Void = { _ in }

    init(webView: WKWebView) {
        self.webView = webView
        recognizer = PencilStrokeRecognizer()
        super.init()
        recognizer.addTarget(self, action: #selector(stroke(_:)))
        recognizer.allowedTouchTypes = PENCIL
        recognizer.delaysTouchesBegan = true   // the page never sees a Pencil touch
        recognizer.cancelsTouchesInView = true
        recognizer.delegate = self
        webView.addGestureRecognizer(recognizer)
        stroke.strokeColor = PENCIL_STROKE_COLOR.cgColor
        stroke.fillColor = nil
        stroke.lineWidth = PENCIL_STROKE_WIDTH
        stroke.lineCap = .round
        stroke.lineJoin = .round
        webView.layer.addSublayer(stroke)
        fingersOnlyEverywhere()
        timer = Timer.scheduledTimer(withTimeInterval: FINGERS_ONLY_RECHECK, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated { self?.fingersOnlyEverywhere() }
        }
    }

    /// Every gesture recognizer in the web view except ours ignores the Pencil.
    private func fingersOnlyEverywhere() {
        guard let webView else { return }
        var views: [UIView] = [webView]
        while let view = views.popLast() {
            for g in view.gestureRecognizers ?? [] where g !== recognizer && g.allowedTouchTypes != FINGERS {
                g.allowedTouchTypes = FINGERS
            }
            views.append(contentsOf: view.subviews)
        }
        stroke.zPosition = 1000
    }

    func gestureRecognizer(_ g: UIGestureRecognizer, shouldRecognizeSimultaneouslyWith other: UIGestureRecognizer) -> Bool { false }

    @objc private func stroke(_ g: PencilStrokeRecognizer) {
        guard let webView else { return }
        let point = g.location(in: webView)
        switch g.state {
        case .began:
            start = documentPoint(g)
            lastText = ""
            path.removeAllPoints()
            path.move(to: point)
        case .changed:
            path.addLine(to: point)
            stroke.path = path.cgPath
            let end = documentPoint(g)
            Task { await select(to: end) }
        case .ended:
            stroke.path = nil
            let end = documentPoint(g)
            Task {
                let text = await select(to: end).trimmingCharacters(in: .whitespacesAndNewlines)
                if text.count >= PENCIL_MIN_CHARS { onHighlight(text) }
            }
        default:
            stroke.path = nil
        }
    }

    /// The touch in the page's CSS pixels, from the top of the document. The page's content view carries the
    /// zoom as its transform, so a location in it is already unzoomed, and insets don't apply.
    private func documentPoint(_ g: UIGestureRecognizer) -> CGPoint {
        guard let webView, let content = webView.scrollView.subviews.first(where: { String(describing: type(of: $0)) == "WKContentView" })
        else { return .zero }
        return g.location(in: content)
    }

    @discardableResult
    private func select(to end: CGPoint) async -> String {
        guard let webView else { return "" }
        let js = "\(PENCIL_SELECT_JS)(\(start.x), \(start.y), \(end.x), \(end.y))"
        let text = (try? await webView.evaluateJavaScript(js)) as? String ?? lastText
        lastText = text
        return text
    }
}
