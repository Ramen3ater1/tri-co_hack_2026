// Session highlights (josue, Sat 09:14): while a session is on, highlighter marks you make in your own
// PDF app are noticed on screen, and at the end you can save each one as a note.
//
// Every SESSION_TICK_S: capture the reading window (on this Mac, in memory only) → Vision text with
// word boxes → sample the pixels behind each word for a highlighter colour → runs of highlighted
// words on a line become one quote. Marks already there when the session started don't count.
// Only the text leaves the Mac. Handwriting isn't captured.
import AppKit
import SwiftUI
import Vision

let SESSION_TICK_S = 2.0
/// A pixel counts as highlighter if it's this saturated and this bright (page white has ~0 saturation,
/// text is dark). Tune here if a viewer's highlight colours are paler.
let HIGHLIGHT_MIN_SATURATION = 0.22
let HIGHLIGHT_MIN_BRIGHTNESS = 0.55
/// Of a word box's light pixels (the background between glyphs), at least this share must be highlighter.
let HIGHLIGHT_MIN_SHARE = 0.5
let HIGHLIGHT_SAMPLES = 8               // sample grid per word box: SAMPLES × SAMPLES/2
let SESSION_MIN_QUOTE_CHARS = 8         // ignore stray one-word marks shorter than this

// ---------- detection (pure, tested in the render check) ----------

/// The image's pixels as RGBA bytes, for sampling.
struct PixelBuffer {
    let width: Int
    let height: Int
    let bytes: [UInt8]

    init(_ image: CGImage) {
        width = image.width
        height = image.height
        var data = [UInt8](repeating: 0, count: width * height * 4)
        let context = CGContext(data: &data, width: width, height: height, bitsPerComponent: 8, bytesPerRow: width * 4,
                                space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
        context.draw(image, in: CGRect(x: 0, y: 0, width: width, height: height))
        bytes = data
    }

    /// (saturation, brightness) at a pixel, top-left origin.
    func hsb(x: Int, y: Int) -> (Double, Double) {
        let i = (min(max(y, 0), height - 1) * width + min(max(x, 0), width - 1)) * 4
        let r = Double(bytes[i]) / 255, g = Double(bytes[i + 1]) / 255, b = Double(bytes[i + 2]) / 255
        let maxC = max(r, g, b), minC = min(r, g, b)
        return (maxC == 0 ? 0 : (maxC - minC) / maxC, maxC)
    }

    /// Is the background of this box (normalised, top-left origin) highlighter-coloured?
    func isHighlighted(_ box: CGRect) -> Bool {
        var light = 0, marked = 0
        let rows = max(HIGHLIGHT_SAMPLES / 2, 2)
        for i in 0..<HIGHLIGHT_SAMPLES {
            for j in 0..<rows {
                let x = Int((box.minX + box.width * (Double(i) + 0.5) / Double(HIGHLIGHT_SAMPLES)) * Double(width))
                let y = Int((box.minY + box.height * (Double(j) + 0.5) / Double(rows)) * Double(height))
                let (saturation, brightness) = hsb(x: x, y: y)
                guard brightness >= HIGHLIGHT_MIN_BRIGHTNESS else { continue }  // a glyph, not background
                light += 1
                if saturation >= HIGHLIGHT_MIN_SATURATION { marked += 1 }
            }
        }
        return light >= 4 && Double(marked) / Double(light) >= HIGHLIGHT_MIN_SHARE
    }
}

/// Every run of highlighted words on a line, as text. Runs of one line each (a mark across two lines
/// gives two quotes; TODO(edge): join runs that continue onto the next line).
func highlightedQuotes(in image: CGImage) throws -> [String] {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false
    try VNImageRequestHandler(cgImage: image).perform([request])
    let pixels = PixelBuffer(image)
    var quotes: [String] = []
    for observation in request.results ?? [] {
        guard let candidate = observation.topCandidates(1).first else { continue }
        let text = candidate.string
        var run: Range<String.Index>?   // from the first highlighted word to the last, punctuation kept
        func flush() {
            if let run {
                let quote = String(text[run])
                if quote.count >= SESSION_MIN_QUOTE_CHARS { quotes.append(quote) }
            }
            run = nil
        }
        text.enumerateSubstrings(in: text.startIndex..., options: .byWords) { _, range, _, _ in
            guard let box = try? candidate.boundingBox(for: range)?.boundingBox else { return }
            // Vision boxes are normalised with a bottom-left origin.
            let topLeft = CGRect(x: box.minX, y: 1 - box.maxY, width: box.width, height: box.height)
            if pixels.isHighlighted(topLeft) {
                run = (run?.lowerBound ?? range.lowerBound)..<range.upperBound
            } else {
                flush()
            }
        }
        flush()
    }
    return quotes
}

// ---------- state ----------

struct SessionHighlight: Identifiable {
    let id = UUID()
    let quote: String
    let page: Int?
    var note = ""
    var saved = false
    var error: String?
}

@MainActor
final class SessionModel: ObservableObject {
    @Published var active = false
    @Published var highlights: [SessionHighlight] = []
    @Published var notInReading = 0
    @Published var status: String?
    @Published var saving = false
    var baseline: Set<String> = []      // squashed quotes already marked when the session started
    var seen: Set<String> = []          // squashed quotes handled already (kept or dropped)
    var started = false

    var pillText: String {
        var text = "\(highlights.count) highlight\(highlights.count == 1 ? "" : "s")"
        if notInReading > 0 { text += " · \(notInReading) not in a course reading" }
        return text
    }

    func saveNotes(then done: @escaping () -> Void) {
        guard !saving else { return }
        saving = true
        Task {
            for index in highlights.indices where !highlights[index].saved {
                let note = highlights[index].note.trimmingCharacters(in: .whitespacesAndNewlines)
                guard !note.isEmpty else { continue }  // only highlights with a note are saved (no 'highlight' kind yet)
                do {
                    _ = try await post("/api/note", NoteRequest(quote: highlights[index].quote, body: note, share_with_future: true), as: SavedNote.self)
                    highlights[index].saved = true
                    highlights[index].error = nil
                } catch {
                    print("Session: saving a note failed: \(error)")
                    highlights[index].error = error.localizedDescription
                }
            }
            saving = false
            done()
        }
    }
}

// ---------- views ----------

struct SessionPill: View {
    @ObservedObject var model: SessionModel
    var body: some View {
        HStack(spacing: 8) {
            Circle().fill(Theme.you).frame(width: 8, height: 8)
            Text("Dialectic session").font(.system(size: 12.5, weight: .semibold)).foregroundColor(Theme.ink)
            Text("· \(model.status ?? model.pillText)").font(.system(size: 12.5)).foregroundColor(Theme.muted)
            Text("·").foregroundColor(Theme.muted)
            Button { AppDelegate.shared.toggleSession() } label: {
                Text("End").font(.system(size: 12.5, weight: .medium)).foregroundColor(Theme.you)
            }
            .buttonStyle(.plain)
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

/// After End: each highlight with an optional note; Save notes saves the ones with a note.
struct SessionReviewView: View {
    @ObservedObject var model: SessionModel
    var scrolls = true
    let done: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Session highlights").font(.system(size: 14, weight: .semibold)).foregroundColor(Theme.ink)
                Text("· \(model.pillText)").font(.system(size: 12.5)).foregroundColor(Theme.muted)
                Spacer()
            }
            if model.highlights.isEmpty {
                Text("No new highlights in this session.").font(.system(size: 13)).foregroundColor(Theme.muted)
            } else {
                Text("Add a note to the ones you want to keep. Only highlights with a note are saved, as notes shared with the class.")
                    .font(.system(size: 12)).foregroundColor(Theme.muted).fixedSize(horizontal: false, vertical: true)
                MaybeScroll(scrolls) {
                    VStack(alignment: .leading, spacing: 14) {
                        ForEach($model.highlights) { $item in
                            VStack(alignment: .leading, spacing: 6) {
                                HStack {
                                    if let page = item.page { Text("p. \(page)").font(.system(size: 11.5)).foregroundColor(Theme.muted) }
                                    Spacer()
                                    if item.saved { Text("Saved").font(.system(size: 11.5, weight: .medium)).foregroundColor(Theme.professor) }
                                }
                                QuoteChip(text: item.quote, lineLimit: 3)
                                TextArea(placeholder: "Note (optional)", text: $item.note, height: 54)
                                    .disabled(item.saved)
                                if let error = item.error {
                                    Text(error).font(.system(size: 12)).foregroundColor(.red).fixedSize(horizontal: false, vertical: true)
                                }
                            }
                        }
                    }
                }
                .frame(maxHeight: 420)
            }
            HStack {
                Button("Close") { done() }.buttonStyle(.plain).foregroundColor(Theme.muted).frame(minHeight: Theme.minHit)
                Spacer()
                if model.saving { ProgressView().controlSize(.small) }
                if !model.highlights.isEmpty {
                    Button("Save notes") { model.saveNotes(then: { AppDelegate.shared.overlay.refreshNow() }) }
                        .buttonStyle(PrimaryButtonStyle())
                        .disabled(model.saving)
                }
            }
        }
        .frame(width: COMPOSER_WIDTH - 32, alignment: .leading)
        .panelSurface()
    }
}

// ---------- controller ----------

@MainActor
final class SessionController {
    let model = SessionModel()
    private let pillWindow = passThroughWindow()
    private var targetPid: pid_t?
    private var loop: Task<Void, Never>?
    private var busy = false

    init() {
        pillWindow.contentView = FirstClickHostingView(rootView: SessionPill(model: model))
        pillWindow.ignoresMouseEvents = false  // End takes clicks
    }

    func start() {
        guard CGPreflightScreenCaptureAccess() else {
            AppDelegate.shared.requestScreenRecordingOnce()
            AppDelegate.shared.showMessage(NO_SCREEN_RECORDING_MESSAGE)
            return
        }
        guard let front = NSWorkspace.shared.frontmostApplication, front.processIdentifier != getpid() else {
            AppDelegate.shared.showMessage("Click the window you're reading in, then start the session again.")
            return
        }
        targetPid = front.processIdentifier
        model.active = true
        model.started = false
        model.highlights = []
        model.notInReading = 0
        model.baseline = []
        model.seen = []
        model.status = "starting…"
        showPill()
        loop = Task { [weak self] in
            while !Task.isCancelled {
                await self?.tick()
                try? await Task.sleep(nanoseconds: UInt64(SESSION_TICK_S * 1e9))
            }
        }
        print("Session started on \(front.localizedName ?? "pid \(targetPid!)")")
    }

    /// End: stop capturing and open the review panel.
    func stop() {
        loop?.cancel()
        model.active = false
        pillWindow.orderOut(nil)
        print("Session ended: \(model.highlights.count) highlights, \(model.notInReading) not in a course reading")
        AppDelegate.shared.panels.show(SessionReviewView(model: model, done: { AppDelegate.shared.panels.panel.orderOut(nil) }), nearMouse: false)
    }

    private func showPill() {
        guard let screen = NSScreen.main else { return }
        let size = pillWindow.contentView?.fittingSize ?? NSSize(width: 360, height: 50)
        pillWindow.setFrame(NSRect(x: screen.visibleFrame.midX - size.width / 2, y: screen.visibleFrame.maxY - size.height - 4,
                                   width: size.width, height: size.height), display: true)
        pillWindow.orderFrontRegardless()
    }

    private func tick() async {
        guard model.active, !busy, let pid = targetPid else { return }
        showPill()  // the text changes width
        // Only look while the reading app is in front (not our own panels or another app).
        guard NSWorkspace.shared.frontmostApplication?.processIdentifier == pid, let (windowId, _) = frontWindow(of: pid) else { return }
        busy = true
        defer { busy = false }
        do {
            let image = try await captureWindow(windowId)  // in memory only, never written to disk
            let quotes = try await Task.detached { try highlightedQuotes(in: image) }.value
            if !model.started {
                // Marks already on the page when the session started aren't this session's.
                model.baseline = Set(quotes.map(squash))
                model.started = true
                model.status = nil
                print("Session baseline: \(quotes.count) existing highlights ignored")
                return
            }
            for quote in quotes {
                let key = squash(quote)
                guard !model.baseline.contains(key), !model.seen.contains(key) else { continue }
                model.seen.insert(key)
                await add(quote)
            }
        } catch {
            print("Session tick failed: \(error)")
            model.status = error.localizedDescription
        }
    }

    /// Keep the quote only if it's in a course reading.
    private func add(_ quote: String) async {
        do {
            let (response, isStub) = try await locate(text: quote)
            // STUB: the stub always answers page 2, so check the quote is really on it.
            if isStub && !squash(response.lines.map(\.text).joined()).contains(squash(quote)) {
                model.notInReading += 1
                return
            }
            model.highlights.append(SessionHighlight(quote: quote, page: response.located.page))
            print("Session: new highlight on p. \(response.located.page): \(quote.prefix(60))")
        } catch let error as APIError where error.status == 404 {
            model.notInReading += 1
        } catch {
            print("Session: locate failed: \(error)")
            model.status = error.localizedDescription
        }
    }
}
