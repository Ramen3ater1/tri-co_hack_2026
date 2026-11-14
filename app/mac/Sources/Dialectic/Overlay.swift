// Classmates' highlights (the panel's switch or the menu) drawn over whatever PDF viewer is in front (design.md §3; boards 1, 4, 5).
//
// Capture the front window (on this Mac) → Vision text lines with boxes → POST /api/locate with the
// recognised text only → fit the page's line boxes (page fractions) to the lines on screen →
// that one fit places every annotation's rects on screen, locked ones included.
import AppKit
import ScreenCaptureKit
import SwiftUI
import Vision

let OVERLAY_REFRESH_S = 1.0      // re-capture + re-fit, so boxes follow scrolling
let POLL_S = 5.0                 // refetch annotations, like the web reader (SPEC §3.3)
let LOCATE_RETRY_S = 3.0         // at most one locate call this often
let LOCATE_SAMPLE_LINES = 8      // send only the longest recognised lines (design.md §3.1)
let NEAR_DISTANCE = 0.08         // same as db.py: a locked cluster is annotations this close together
let MIN_MATCH_CHARS = 12         // OCR lines shorter than this aren't used for the fit
let MAX_FIT_ERROR_PT = 8.0       // fits worse than this are thrown away
let MARGIN_WIDTH: CGFloat = 376
// SPEC §3.3 wording: a count of notes, not people (locked annotations carry no author).
let LOCKED_HINT = "Add a note or ask a question to see them."
func lockedTitle(_ n: Int) -> String { "\(n) note\(n == 1 ? "" : "s") near here" }
let PRIVACY_FOOTER = "Read on your Mac: only the recognised text is sent to find the page. The screenshot never leaves this Mac."

// ---------- page fitting ----------

struct OCRLine {
    let text: String
    let rect: CGRect   // window points, top-left origin
}

/// page fraction → window points: x' = a·x + b, y' = c·y + d.
struct Fit {
    let a, b, c, d: Double
    func map(_ r: Rect) -> CGRect {
        CGRect(x: a * r.x + b, y: c * r.y + d, width: a * r.w, height: c * r.h)
    }
}

func leastSquares(_ points: [(Double, Double)]) -> (Double, Double)? {
    let n = Double(points.count)
    guard n >= 2 else { return nil }
    let mu = points.map(\.0).reduce(0, +) / n
    let mv = points.map(\.1).reduce(0, +) / n
    let cov = points.map { ($0.0 - mu) * ($0.1 - mv) }.reduce(0, +)
    let varU = points.map { ($0.0 - mu) * ($0.0 - mu) }.reduce(0, +)
    guard varU > 1e-9 else { return nil }
    let slope = cov / varU
    return (slope, mv - slope * mu)
}

func editDistance(_ s: [Unicode.Scalar], _ t: [Unicode.Scalar]) -> Int {
    var prev = Array(0...t.count)
    for i in 1...max(s.count, 1) where !s.isEmpty {
        var cur = [i] + Array(repeating: 0, count: t.count)
        for j in 1...max(t.count, 1) where !t.isEmpty {
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (s[i - 1] == t[j - 1] ? 0 : 1))
        }
        prev = cur
    }
    return prev[t.count]
}

/// Same line, allowing a few OCR mistakes.
func similarLines(_ a: String, _ b: String) -> Bool {
    if a == b { return true }
    let longer = Double(max(a.count, b.count))
    guard Double(min(a.count, b.count)) / longer > 0.9 else { return false }
    return Double(editDistance(Array(a.unicodeScalars), Array(b.unicodeScalars))) <= max(2, longer * 0.08)
}

/// Fit the server's page lines to the lines Vision found. nil if fewer than 2 lines match or the fit is poor.
func fitPage(ocr: [OCRLine], page: [PageLine]) -> Fit? {
    let pageKeys = page.map { squash($0.text) }
    var xs: [(Double, Double)] = []
    var ys: [(Double, Double)] = []
    for line in ocr {
        let key = squash(line.text)
        guard key.count >= MIN_MATCH_CHARS, let i = pageKeys.firstIndex(where: { similarLines($0, key) }) else { continue }
        let r = page[i].rect
        xs.append((r.x, line.rect.minX))
        xs.append((r.x + r.w, line.rect.maxX))
        ys.append((r.y + r.h / 2, line.rect.midY))
    }
    guard ys.count >= 2, let (a, b) = leastSquares(xs), let (c, d) = leastSquares(ys), a > 0, c > 0 else { return nil }
    let error = ys.map { abs(c * $0.0 + d - $0.1) }.reduce(0, +) / Double(ys.count)
    guard error <= MAX_FIT_ERROR_PT else {
        print("Overlay: fit too rough (\(Int(error)) pt off), ignoring")
        return nil
    }
    return Fit(a: a, b: b, c: c, d: d)
}

// ---------- capture + Vision (all on this Mac) ----------

/// The frontmost normal window of `pid`: its id and frame in global top-left coordinates.
func frontWindow(of pid: pid_t) -> (CGWindowID, CGRect)? {
    let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] ?? []
    for info in list {
        guard (info[kCGWindowOwnerPID as String] as? pid_t) == pid, (info[kCGWindowLayer as String] as? Int) == 0,
              let id = info[kCGWindowNumber as String] as? CGWindowID,
              let boundsDict = info[kCGWindowBounds as String], let bounds = CGRect(dictionaryRepresentation: boundsDict as! CFDictionary),
              bounds.width > 200, bounds.height > 200 else { continue }
        return (id, bounds)
    }
    return nil
}

func captureWindow(_ id: CGWindowID) async throws -> CGImage {
    let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true)
    guard let window = content.windows.first(where: { $0.windowID == id }) else {
        throw APIError(status: 0, message: "The reading window isn't on screen")
    }
    let filter = SCContentFilter(desktopIndependentWindow: window)
    let config = SCStreamConfiguration()
    let scale = CGFloat(filter.pointPixelScale)
    config.width = Int(window.frame.width * scale)
    config.height = Int(window.frame.height * scale)
    config.showsCursor = false
    return try await SCScreenshotManager.captureImage(contentFilter: filter, configuration: config)
}

func recognizeLines(_ image: CGImage, windowSize: CGSize) throws -> [OCRLine] {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false
    try VNImageRequestHandler(cgImage: image).perform([request])
    return (request.results ?? []).compactMap { observation in
        guard let text = observation.topCandidates(1).first?.string else { return nil }
        let box = observation.boundingBox  // normalised, bottom-left origin
        return OCRLine(text: text, rect: CGRect(x: box.minX * windowSize.width, y: (1 - box.maxY) * windowSize.height,
                                                width: box.width * windowSize.width, height: box.height * windowSize.height))
    }
}

/// All the text in an image, in reading order (top to bottom, then left to right), lines joined by spaces.
func recognizedText(_ image: CGImage) throws -> String {
    let lines = try recognizeLines(image, windowSize: CGSize(width: image.width, height: image.height))
    return lines.sorted { abs($0.rect.midY - $1.rect.midY) < $0.rect.height / 2 ? $0.rect.minX < $1.rect.minX : $0.rect.midY < $1.rect.midY }
        .map(\.text).joined(separator: " ").trimmingCharacters(in: .whitespacesAndNewlines)
}

/// Global top-left (CoreGraphics) rect → Cocoa screen rect.
func cocoaRect(_ r: CGRect) -> NSRect {
    let primaryHeight = NSScreen.screens.first?.frame.height ?? 0
    return NSRect(x: r.minX, y: primaryHeight - r.maxY, width: r.width, height: r.height)
}

// ---------- what's on the page ----------

/// One margin entry: an open annotation, or a cluster of locked ones.
struct PageThread: Identifiable {
    let number: Int
    let annotation: Annotation?
    let locked: [Annotation]
    var noteCount: Int { locked.first?.group_notes ?? locked.count }
    var id: Int { annotation?.id ?? -(locked.first?.id ?? 0) }
    var top: Double { (annotation?.rects ?? locked.first?.rects)?.map(\.y).min() ?? 1 }
    var role: Role { annotation.map { Role.of(authorId: $0.author?.id, role: $0.author?.role) } ?? .classmate }
}

func verticalGap(_ a: [Rect], _ b: [Rect]) -> Double {
    guard let aTop = a.map(\.y).min(), let aBottom = a.map({ $0.y + $0.h }).max(),
          let bTop = b.map(\.y).min(), let bBottom = b.map({ $0.y + $0.h }).max() else { return 1 }
    return max(0, max(aTop, bTop) - min(aBottom, bBottom))
}

/// Open annotations each get a thread; locked ones one per lock-card group (the server's `group`,
/// or by nearness if it doesn't send one). Numbered top to bottom.
func buildThreads(_ annotations: [Annotation]) -> [PageThread] {
    var groups: [(Annotation?, [Annotation])] = annotations.filter { !$0.isLocked }.map { ($0, []) }
    var clusters: [[Annotation]] = []
    for item in annotations.filter(\.isLocked).sorted(by: { ($0.rects?.first?.y ?? 1) < ($1.rects?.first?.y ?? 1) }) {
        if let group = item.group, let i = clusters.firstIndex(where: { $0.first?.group == group }) {
            clusters[i].append(item)
        } else if item.group == nil, let last = clusters.last?.last, last.group == nil,
                  verticalGap(last.rects ?? [], item.rects ?? []) <= NEAR_DISTANCE {
            clusters[clusters.count - 1].append(item)
        } else {
            clusters.append([item])
        }
    }
    groups += clusters.map { (nil, $0) }
    let sorted = groups.map { PageThread(number: 0, annotation: $0.0, locked: $0.1) }.sorted { $0.top < $1.top }
    return sorted.enumerated().map { PageThread(number: $0.offset + 1, annotation: $0.element.annotation, locked: $0.element.locked) }
}

// ---------- state ----------

@MainActor
final class OverlayModel: ObservableObject {
    @Published var active = false
    @Published var status: String?          // replaces the pill text while looking or on an error
    @Published var isStub = false
    @Published var located: Located?
    @Published var lines: [PageLine] = []
    @Published var annotations: [Annotation] = []
    @Published var fit: Fit?
    @Published var windowSize: CGSize = .zero
    @Published var selectedId: Int?
    @Published var justOpened: Set<Int> = []
    @Published var replyText = ""
    @Published var replyError: String?
    @Published var sending = false
    var everLocked: Set<Int> = []
    var stubAnnotations: [Annotation]?

    var threads: [PageThread] { buildThreads(annotations) }
    var selected: Annotation? { annotations.first(where: { $0.id == selectedId && !$0.isLocked }) }
    var place: String {
        guard let located else { return "" }
        return "\(located.section ?? located.reading_title), p. \(located.page)"
    }

    func setAnnotations(_ all: [Annotation]) {
        let onPage = all.filter { $0.page == located?.page }
        for item in onPage where !item.isLocked && everLocked.contains(item.id) { justOpened.insert(item.id) }
        everLocked.formUnion(onPage.filter(\.isLocked).map(\.id))
        annotations = onPage
    }

    /// Where `quote` sits on the located page, and how many locked classmates are near it.
    func context(for quote: String) -> PassageContext? {
        guard let located, !lines.isEmpty else { return nil }
        var text = ""
        var lineAt: [Int] = []   // line index of each squashed character
        for (i, line) in lines.enumerated() {
            let key = squash(line.text)
            text += key
            lineAt += Array(repeating: i, count: key.count)
        }
        let target = squash(quote)
        guard !target.isEmpty, let range = text.range(of: target) else {
            return PassageContext(readingId: located.reading_id, section: located.section, page: located.page, nearLockedCount: 0)
        }
        let start = text.distance(from: text.startIndex, to: range.lowerBound)
        let spanned = Set(lineAt[start..<(start + target.count)]).map { lines[$0].rect }
        let near = annotations.filter { $0.isLocked && verticalGap($0.rects ?? [], spanned) <= NEAR_DISTANCE }.count
        return PassageContext(readingId: located.reading_id, section: located.section, page: located.page, nearLockedCount: near)
    }

    func reply(to root: Annotation, then refresh: @escaping () -> Void) {
        let body = replyText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !body.isEmpty, let readingId = located?.reading_id, !sending else { return }
        sending = true
        replyError = nil
        Task {
            do {
                _ = try await post("/api/readings/\(readingId)/annotations", ReplyRequest(body: body, parent_id: root.id), as: Annotation.self)
                replyText = ""
                refresh()
            } catch {
                print("Reply failed: \(error)")
                replyError = error.localizedDescription
            }
            sending = false
        }
    }
}

// ---------- views ----------

/// The click-through layer over the reading window: boxes, dashed outlines, pins, the selected ring.
struct HighlightLayer: View {
    @ObservedObject var model: OverlayModel

    var body: some View {
        Canvas { ctx, _ in
            guard let fit = model.fit else { return }
            let textLeft = model.lines.map { fit.map($0.rect).minX }.min() ?? 0
            for thread in model.threads {
                let items = thread.annotation.map { [$0] } ?? thread.locked
                var first: CGRect?
                for item in items {
                    for rect in item.rects ?? [] {
                        let box = fit.map(rect).insetBy(dx: -2, dy: -1)
                        first = first ?? box
                        let path = Path(roundedRect: box, cornerRadius: 3)
                        if item.isLocked {
                            ctx.stroke(path, with: .color(Theme.classmate), style: StrokeStyle(lineWidth: 1.5, dash: [4, 3]))
                        } else {
                            var fill = ctx
                            fill.blendMode = .multiply  // the words stay readable through the box
                            fill.fill(path, with: .color(thread.role.color.opacity(Theme.highlightAlpha)))
                        }
                        if item.id == model.selectedId {
                            ctx.stroke(Path(roundedRect: box.insetBy(dx: -2, dy: -2), cornerRadius: 4), with: .color(Theme.you), lineWidth: 3)
                        }
                    }
                }
                if let first {
                    let center = CGPoint(x: max(min(first.minX, textLeft) - 16, 10), y: first.midY)  // in the page margin, level with the box
                    ctx.fill(Path(ellipseIn: CGRect(x: center.x - 9, y: center.y - 9, width: 18, height: 18)), with: .color(thread.role.pinColor))
                    ctx.draw(Text("\(thread.number)").font(.system(size: 10, weight: .bold)).foregroundColor(.white), at: center)
                }
            }
        }
        .frame(width: model.windowSize.width, height: model.windowSize.height)
        .allowsHitTesting(false)
    }
}

struct StatusPill: View {
    @ObservedObject var model: OverlayModel

    var body: some View {
        HStack(spacing: 8) {
            Circle().fill(model.status == nil ? Theme.classmate : Theme.muted).frame(width: 8, height: 8)
            if let status = model.status {
                Text(status).font(.system(size: 12.5)).foregroundColor(Theme.ink)
            } else {
                Text("Classmates' highlights").font(.system(size: 12.5, weight: .semibold)).foregroundColor(Theme.ink)
                Text("· \(model.place)").font(.system(size: 12.5)).foregroundColor(Theme.muted)
            }
            Text("·").foregroundColor(Theme.muted)
            Button { AppDelegate.shared.toggleHighlights() } label: {
                Text("Hide").font(.system(size: 12.5, weight: .medium)).foregroundColor(Theme.you)
            }
            .buttonStyle(.plain)
            if model.isStub {
                // STUB: POST /api/locate pending Owen's OK
                Text("stub data").font(.system(size: 10.5, weight: .semibold)).foregroundColor(Theme.warning)
                    .padding(.horizontal, 6).padding(.vertical, 1)
                    .background(Capsule().stroke(Theme.warning, lineWidth: 1))
            }
        }
        .padding(.horizontal, 14).padding(.vertical, 8)
        .background(Capsule().fill(Theme.panel))
        .overlay(Capsule().stroke(Theme.hairline, lineWidth: 1))
        .shadow(color: .black.opacity(0.12), radius: 6, y: 2)
        .fixedSize()
        .padding(10)
        .environment(\.colorScheme, .light)
    }
}

/// The strip docked beside the reading window: "On this page", or one thread (board 5).
struct MarginView: View {
    @ObservedObject var model: OverlayModel
    let refresh: () -> Void
    var scrolls = true   // false only in the render check: ImageRenderer draws ScrollViews blank

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            if let root = model.selected {
                ThreadView(model: model, root: root, number: model.threads.first(where: { $0.id == root.id })?.number, refresh: refresh, scrolls: scrolls)
            } else {
                list
            }
        }
        .padding(14)
        .frame(width: MARGIN_WIDTH, alignment: .topLeading)
        .frame(maxHeight: .infinity, alignment: .top)
        .background(RoundedRectangle(cornerRadius: Theme.panelRadius).fill(Theme.ground))
        .overlay(RoundedRectangle(cornerRadius: Theme.panelRadius).stroke(Theme.hairline, lineWidth: 1))
        .environment(\.colorScheme, .light)
    }

    var header: String {
        let n = model.threads.count
        var text = "· \(n) thread\(n == 1 ? "" : "s")"
        if !model.justOpened.isEmpty { text += " · \(model.justOpened.count) just opened" }
        return text
    }

    var list: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 6) {
                Text("On this page").font(.system(size: 14, weight: .semibold)).foregroundColor(Theme.ink)
                Text(header).font(.system(size: 13)).foregroundColor(Theme.muted)
                Spacer()
            }
            MaybeScroll(scrolls) {
                VStack(alignment: .leading, spacing: 10) {
                    ForEach(model.threads) { thread in
                        if let annotation = thread.annotation {
                            AnnotationCard(annotation: annotation, number: thread.number, justOpened: model.justOpened.contains(annotation.id))
                                .contentShape(Rectangle())
                                .onTapGesture { model.selectedId = annotation.id; model.replyText = "" }
                        } else {
                            LockedCard(count: thread.noteCount, number: thread.number)
                        }
                    }
                    if model.threads.isEmpty && model.fit != nil {
                        Text("No annotations on this page yet.").font(.system(size: 12.5)).foregroundColor(Theme.muted)
                    }
                }
            }
            Spacer(minLength: 0)
            Text(PRIVACY_FOOTER).font(.system(size: 11)).foregroundColor(Theme.muted).fixedSize(horizontal: false, vertical: true)
        }
    }
}

struct AnnotationCard: View {
    let annotation: Annotation
    var number: Int? = nil
    var justOpened = false
    var showQuote = true

    var role: Role { Role.of(authorId: annotation.author?.id, role: annotation.author?.role) }
    var detail: String? {
        let when = relativeTime(annotation.created_at)
        let mac = annotation.via == "hotkey" ? (role == .you ? "from your Mac" : "from a Mac") : nil
        let kind = annotation.kind == "question" ? "question" : nil
        let parts = [kind, when, mac].compactMap { $0 }
        return parts.isEmpty ? nil : parts.joined(separator: ", ")
    }

    var body: some View {
        RoleCard(role: role) {
            AuthorLine(name: annotation.author?.name ?? "Classmate", role: role, badge: annotation.badge, detail: detail, pin: number)
            if showQuote, let quote = annotation.quote {
                Text("“\(quote.count > 60 ? String(quote.prefix(58)) + "…" : quote)”")
                    .font(Theme.serif(12.5)).foregroundColor(Theme.muted).lineLimit(2)
            }
            Text(annotation.body ?? "").font(.system(size: 13)).foregroundColor(Theme.ink)
                .fixedSize(horizontal: false, vertical: true).textSelection(.enabled)
            let replies = annotation.replies?.count ?? 0
            HStack {
                if replies > 0 { Text("\(replies) repl\(replies == 1 ? "y" : "ies")").font(.system(size: 11.5)).foregroundColor(Theme.you) }
                if justOpened { Text("just opened").font(.system(size: 11.5, weight: .medium)).foregroundColor(Theme.classmatePin) }
            }
        }
    }
}

struct LockedCard: View {
    let count: Int
    let number: Int

    var body: some View {
        RoleCard(role: .classmate, dashed: true) {
            HStack(spacing: 6) {
                Pin(number: number, color: Theme.classmatePin)
                Text(lockedTitle(count)).font(.system(size: 13, weight: .semibold))
            }
            Text(LOCKED_HINT).font(.system(size: 12.5)).foregroundColor(Theme.ink)
            HStack(spacing: 4) {
                Text("Select the passage, then").font(.system(size: 11.5)).foregroundColor(Theme.muted)
                KeyCap(label: HOTKEY_LABEL)
                Text("to note or ask").font(.system(size: 11.5)).foregroundColor(Theme.muted)
            }
        }
    }
}

struct ThreadView: View {
    @ObservedObject var model: OverlayModel
    let root: Annotation
    let number: Int?
    let refresh: () -> Void
    var scrolls = true

    var replies: [Annotation] { root.replies ?? [] }  // oldest first, from the server

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Button("← On this page") { model.selectedId = nil }
                    .buttonStyle(.plain).font(.system(size: 13, weight: .medium)).foregroundColor(Theme.you)
                    .frame(minHeight: Theme.minHit)
                Spacer()
                Text(root.page.map { "p. \($0)" } ?? "").font(.system(size: 12)).foregroundColor(Theme.muted)
            }
            MaybeScroll(scrolls) {
                VStack(alignment: .leading, spacing: 10) {
                    AnnotationCard(annotation: root, number: number)
                    if !replies.isEmpty {
                        SectionLabel("\(replies.count) repl\(replies.count == 1 ? "y" : "ies")")
                        HStack(alignment: .top, spacing: 10) {
                            Rectangle().fill(Theme.hairline).frame(width: 1)
                            VStack(alignment: .leading, spacing: 8) {
                                ForEach(replies) { AnnotationCard(annotation: $0, showQuote: false) }
                            }
                        }
                        .padding(.leading, 6)
                    }
                }
            }
            TextArea(placeholder: "Reply to \(root.author?.name ?? "this thread")", text: $model.replyText, height: 70)
            if let error = model.replyError {
                Text(error).font(.system(size: 12)).foregroundColor(.red).fixedSize(horizontal: false, vertical: true)
            }
            HStack {
                if let readingId = model.located?.reading_id {
                    Button { openInReader("/readings/\(readingId)?page=\(root.page ?? 1)&annotation=\(root.id)") } label: {
                        Text("Open in reader").font(.system(size: 12.5, weight: .medium)).foregroundColor(Theme.you)
                    }
                    .buttonStyle(.plain)
                }
                Spacer()
                if model.sending { ProgressView().controlSize(.small) }
                Button("Reply") { model.reply(to: root, then: refresh) }
                    .buttonStyle(PrimaryButtonStyle())
                    .disabled(model.sending)
            }
        }
    }
}

struct MaybeScroll<Content: View>: View {
    let scrolls: Bool
    @ViewBuilder let content: () -> Content
    init(_ scrolls: Bool, @ViewBuilder content: @escaping () -> Content) { self.scrolls = scrolls; self.content = content }
    var body: some View {
        if scrolls { ScrollView { content() } } else { content() }
    }
}

// ---------- controller ----------

/// Takes the first click even when its window isn't key (the pill's Hide).
final class FirstClickHostingView<Content: View>: NSHostingView<Content> {
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
}

/// A borderless window that never takes clicks.
func passThroughWindow() -> NSWindow {
    let window = NSWindow(contentRect: .zero, styleMask: [.borderless], backing: .buffered, defer: false)
    window.isOpaque = false
    window.backgroundColor = .clear
    window.hasShadow = false
    window.ignoresMouseEvents = true
    window.level = .floating
    window.isReleasedWhenClosed = false
    window.collectionBehavior = [.canJoinAllSpaces, .stationary, .ignoresCycle, .fullScreenAuxiliary]
    return window
}

@MainActor
final class OverlayController {
    let model = OverlayModel()
    private let highlightWindow = passThroughWindow()
    private let pillWindow = passThroughWindow()
    private let marginPanel = FloatingPanel()
    private var targetPid: pid_t?
    private var lastFrame: CGRect?
    private var loop: Task<Void, Never>?
    private var poll: Task<Void, Never>?
    private var lastLocate = Date.distantPast
    private var busy = false

    init() {
        highlightWindow.contentView = NSHostingView(rootView: HighlightLayer(model: model))
        pillWindow.contentView = FirstClickHostingView(rootView: StatusPill(model: model))
        pillWindow.ignoresMouseEvents = false  // the pill's Hide takes clicks; the box layer stays click-through
        marginPanel.isMovableByWindowBackground = false
        marginPanel.hasShadow = true
        marginPanel.contentView = NSHostingView(rootView: MarginView(model: model, refresh: { [weak self] in self?.refreshNow() }))
    }

    var isActive: Bool { model.active }

    func toggle() {
        if model.active { stop() } else { start() }
    }

    func start() {
        guard CGPreflightScreenCaptureAccess() else {
            CGRequestScreenCaptureAccess()  // macOS shows its prompt; the human grants it
            AppDelegate.shared.showMessage(NO_SCREEN_RECORDING_MESSAGE)
            return
        }
        guard let front = NSWorkspace.shared.frontmostApplication, front.processIdentifier != getpid() else {
            AppDelegate.shared.showMessage("Click the window you're reading in, then turn on Show highlights again.")
            return
        }
        targetPid = front.processIdentifier
        model.active = true
        model.status = "Looking for the page…"
        model.fit = nil
        model.located = nil
        model.selectedId = nil
        model.justOpened = []
        model.everLocked = []
        lastFrame = nil
        lastLocate = .distantPast
        loop = Task { [weak self] in
            while !Task.isCancelled {
                await self?.tick()
                try? await Task.sleep(nanoseconds: UInt64(OVERLAY_REFRESH_S * 1e9))
            }
        }
        poll = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: UInt64(POLL_S * 1e9))
                await self?.fetchAnnotations()
            }
        }
        print("Overlay on for \(front.localizedName ?? "pid \(targetPid!)")")
    }

    func stop() {
        loop?.cancel()
        poll?.cancel()
        model.active = false
        highlightWindow.orderOut(nil)
        pillWindow.orderOut(nil)
        marginPanel.orderOut(nil)
        print("Overlay off")
    }

    /// After a note, question or reply: refetch now so a lock that just opened fills in (board 4).
    func refreshNow() {
        guard model.active else { return }
        Task { await fetchAnnotations() }
    }

    private func tick() async {
        guard model.active, !busy, let pid = targetPid else { return }
        // Only over the reading app (or while you use our own panels).
        let frontPid = NSWorkspace.shared.frontmostApplication?.processIdentifier
        guard frontPid == pid || frontPid == getpid() else {
            highlightWindow.orderOut(nil); pillWindow.orderOut(nil); marginPanel.orderOut(nil)
            return
        }
        guard let (windowId, frame) = frontWindow(of: pid) else {
            model.status = "Can't find the reading window."
            return
        }
        busy = true
        defer { busy = false }
        if frame != lastFrame {
            model.fit = nil  // moving or resizing: hide the boxes rather than draw them in the wrong place
            lastFrame = frame
        }
        do {
            let image = try await captureWindow(windowId)
            let size = frame.size
            let ocr = try await Task.detached { try recognizeLines(image, windowSize: size) }.value
            var fit = model.lines.isEmpty ? nil : fitPage(ocr: ocr, page: model.lines)
            if fit == nil && Date().timeIntervalSince(lastLocate) > LOCATE_RETRY_S {
                // New page, or first look: find out which reading and page this is.
                lastLocate = Date()
                if try await locatePage(ocr) {
                    fit = fitPage(ocr: ocr, page: model.lines)
                }
            }
            guard model.active else { return }
            model.windowSize = size
            model.fit = fit
            if model.located != nil {
                model.status = fit == nil ? "Looking for \(model.place) on screen…" : nil
            }
            place(frame)
        } catch {
            print("Overlay tick failed: \(error)")
            model.status = error.localizedDescription
            place(frame)
        }
    }

    /// Returns true if the page was found (and annotations loaded).
    private func locatePage(_ ocr: [OCRLine]) async throws -> Bool {
        let sample = ocr.map(\.text).sorted { $0.count > $1.count }.prefix(LOCATE_SAMPLE_LINES).joined(separator: "\n")
        guard !sample.isEmpty else {
            model.status = "No text on screen to find the page from."
            return false
        }
        do {
            let (response, isStub) = try await locate(text: sample)
            let pageChanged = response.located.page != model.located?.page || response.located.reading_id != model.located?.reading_id
            model.isStub = isStub
            model.located = response.located
            model.lines = response.lines
            model.stubAnnotations = isStub ? response.annotations : nil
            if pageChanged { model.justOpened = []; model.everLocked = []; model.selectedId = nil }
            await fetchAnnotations()
            return true
        } catch let error as APIError where error.status == 404 {
            model.status = "This page isn't a course reading."
            model.located = nil
            model.lines = []
            return false
        }
    }

    private func fetchAnnotations() async {
        guard model.active, let located = model.located else { return }
        do {
            model.setAnnotations(try await get("/api/readings/\(located.reading_id)/annotations", as: [Annotation].self))
        } catch let error as URLError where model.stubAnnotations != nil {
            // STUB: no server to ask, so show the stub's demo annotations.
            print("Annotations: server unreachable (\(error.code.rawValue)), showing stub annotations")
            model.setAnnotations(model.stubAnnotations ?? [])
        } catch {
            print("GET annotations failed: \(error)")
            model.status = error.localizedDescription
        }
    }

    /// Lay the three windows over and beside the reading window.
    private func place(_ frame: CGRect) {
        let window = cocoaRect(frame)
        highlightWindow.setFrame(window, display: true)
        highlightWindow.orderFrontRegardless()

        let pillSize = pillWindow.contentView?.fittingSize ?? NSSize(width: 420, height: 50)
        pillWindow.setFrame(NSRect(x: window.midX - pillSize.width / 2, y: window.maxY - pillSize.height - 24,
                                   width: pillSize.width, height: pillSize.height), display: true)
        pillWindow.orderFrontRegardless()

        guard model.located != nil else {
            marginPanel.orderOut(nil)
            return
        }
        let screen = NSScreen.screens.first(where: { $0.frame.intersects(window) }) ?? NSScreen.main!
        let visible = screen.visibleFrame
        let height = min(window.height, visible.height)
        // Docked to the right of the reading window, or inside its right edge when there's no room.
        let x = window.maxX + 8 + MARGIN_WIDTH <= visible.maxX ? window.maxX + 8 : window.maxX - MARGIN_WIDTH - 8
        let y = max(visible.minY, window.maxY - height)
        marginPanel.setFrame(NSRect(x: x, y: y, width: MARGIN_WIDTH, height: height), display: true)
        marginPanel.orderFrontRegardless()
    }
}
