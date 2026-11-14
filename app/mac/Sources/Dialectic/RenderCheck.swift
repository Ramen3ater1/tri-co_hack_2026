// `Dialectic --render <dir>`: a quick check without permissions or a server. Draws every screen with
// stub data to PNGs, and runs the real Vision + fit code on a rendered copy of page 2 to check the
// boxes land where they should. Not used by the app itself.
import AppKit
import SwiftUI

let RENDER_PAGE_SCALE = 1.3   // page drawn at 612×792 pt × this

@MainActor private func savePNG<V: View>(_ view: V, _ path: String) {
    let renderer = ImageRenderer(content: view.environment(\.colorScheme, .light))
    renderer.scale = 2
    guard let image = renderer.cgImage else { fatalError("Couldn't render \(path)") }
    let rep = NSBitmapImageRep(cgImage: image)
    try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: path))
    print("wrote \(path)")
}

private func sample<T: Decodable>(_ json: String, as type: T.Type) -> T {
    try! JSONDecoder().decode(type, from: json.data(using: .utf8)!)
}

/// The stub page's lines drawn as text, each stretched to its PDF line box.
private struct FakePage: View {
    let lines: [PageLine]
    let size: CGSize
    var marks: [Rect] = []   // drawn as yellow highlighter under the text
    var body: some View {
        ZStack(alignment: .topLeading) {
            Rectangle().fill(Color.white)
            ForEach(Array(marks.enumerated()), id: \.offset) { _, r in
                Rectangle().fill(Color(hex: 0xFFE45C))
                    .frame(width: r.w * size.width, height: r.h * size.height)
                    .offset(x: r.x * size.width, y: r.y * size.height)
            }
            ForEach(Array(lines.enumerated()), id: \.offset) { _, line in
                let box = CGRect(x: line.rect.x * size.width, y: line.rect.y * size.height,
                                 width: line.rect.w * size.width, height: line.rect.h * size.height)
                let font = NSFont(name: "Georgia", size: box.height * 0.8)!
                let natural = (line.text as NSString).size(withAttributes: [.font: font]).width
                Text(line.text).font(Font(font)).fixedSize()
                    .scaleEffect(x: box.width / natural, y: 1, anchor: .topLeading)
                    .offset(x: box.minX, y: box.minY)
            }
        }
        .frame(width: size.width, height: size.height)
        .foregroundColor(.black)
    }
}

private let OPENED_JSON = """
[{"id": 3, "page": 2, "kind": "note", "via": "web", "quote": "a sort of seventh son, born with a veil, and gifted with second-sight",
  "rects": [{"x": 0.1275, "y": 0.5149, "w": 0.5334, "h": 0.0168}], "body": "Folklore: a seventh son born with a caul was said to have second sight.",
  "created_at": "2026-11-14T01:00:00", "author": {"id": 1, "name": "Prof. Rivera", "role": "professor", "cohort": "Fall 2026"},
  "badge": "Professor", "locked": false,
  "replies": [
    {"id": 20, "page": 2, "kind": "note", "body": "So the veil is a gift and a barrier at once?", "created_at": "2026-11-14T02:00:00",
     "author": {"id": 2, "name": "Ana", "role": "student", "cohort": "Fall 2026"}, "locked": false},
    {"id": 21, "page": 2, "kind": "note", "body": "Yes, and watch how 'second-sight' returns two lines down.", "created_at": "2026-11-14T02:10:00",
     "author": {"id": 1, "name": "Prof. Rivera", "role": "professor", "cohort": "Fall 2026"}, "badge": "Professor", "locked": false}]},
 {"id": 4, "page": 2, "kind": "note", "via": "web", "quote": "this double-consciousness, this sense of always looking at one’s self through the eyes of others",
  "rects": [{"x": 0.5614, "y": 0.5604, "w": 0.3112, "h": 0.0168}, {"x": 0.1275, "y": 0.5831, "w": 0.4316, "h": 0.0168}],
  "body": "Our seminar read this as both a wound and a kind of insight.", "created_at": "2026-11-13T20:00:00",
  "author": {"id": 4, "name": "Sam", "role": "student", "cohort": "Spring 2026"}, "badge": "Spring 2026", "locked": false},
 {"id": 6, "page": 2, "kind": "note", "via": "web", "quote": "two warring ideals in one dark body",
  "rects": [{"x": 0.6268, "y": 0.6285, "w": 0.2457, "h": 0.0168}, {"x": 0.1275, "y": 0.6513, "w": 0.0386, "h": 0.0168}],
  "body": "Two souls, but one body holding them together.", "created_at": "2026-11-14T03:00:00",
  "author": {"id": 2, "name": "Ana", "role": "student", "cohort": "Fall 2026"}, "locked": false},
 {"id": 30, "page": 2, "kind": "note", "via": "hotkey", "quote": "It is a peculiar sensation, this double-consciousness",
  "rects": [{"x": 0.2900, "y": 0.5604, "w": 0.2700, "h": 0.0168}], "body": "It feels like being split, and seeing more because of it.",
  "created_at": "NOW", "author": {"id": 3, "name": "Ben", "role": "student", "cohort": "Fall 2026"}, "locked": false}]
"""

private let ASK_JSON = """
{"question_id": 41,
 "peer": [{"annotation_id": 3, "author": "Prof. Rivera", "cohort": "Fall 2026", "page": 2, "quote": "q",
           "body": "Folklore: a seventh son born with a caul (a 'veil') was said to have second sight."},
          {"annotation_id": 4, "author": "Sam", "cohort": "Spring 2026", "page": 2, "quote": "q",
           "body": "Compare the 'second-sight' line just above."}],
 "sources": [{"source_id": 2, "title": "Caul — Encyclopaedia Britannica", "url": "https://www.britannica.com/science/caul#:~:text=a", "quote": "A caul is..."},
             {"source_id": 3, "title": "Seventh son of a seventh son", "url": "https://en.wikipedia.org/wiki/Seventh_son#:~:text=b", "quote": "..."}],
 "ai_answer": {"annotation_id": 42, "body": "In European and African American folklore a child born with a caul [1] was thought to see spirits; the seventh son [2] carried similar powers."},
 "skipped_sources": [{"url": "https://www.sparknotes.com/x", "title": "SparkNotes", "why": "not_permitted", "reason": "study-guide sites aren't permitted"}],
 "blocked": [],
 "located": {"reading_id": 1, "reading_title": "The Souls of Black Folk, Ch. 1", "page": 2, "section": "Of Our Spiritual Strivings", "reader_url": "/readings/1?page=2&annotation=41"}}
"""

@MainActor
func renderCheck(into dir: String) {
    try! FileManager.default.createDirectory(atPath: dir, withIntermediateDirectories: true)
    let savedUser = UserDefaults.standard.object(forKey: USER_DEFAULTS_KEY)
    UserDefaults.standard.set(3, forKey: USER_DEFAULTS_KEY)  // render as Ben
    defer { UserDefaults.standard.set(savedUser, forKey: USER_DEFAULTS_KEY) }
    let users = sample(#"[{"id":1,"name":"Prof. Rivera","role":"professor","cohort":"Fall 2026"},{"id":2,"name":"Ana","role":"student","cohort":"Fall 2026"},{"id":3,"name":"Ben","role":"student","cohort":"Fall 2026"},{"id":4,"name":"Sam","role":"student","cohort":"Spring 2026"}]"#, as: [User].self)

    // 1. Vision + fit on a rendered page 2, against the known answer.
    let stub = try! loadStub()
    let pageSize = CGSize(width: 612 * RENDER_PAGE_SCALE, height: 792 * RENDER_PAGE_SCALE)
    let renderer = ImageRenderer(content: FakePage(lines: stub.lines, size: pageSize))
    renderer.scale = 2
    let ocr = try! recognizeLines(renderer.cgImage!, windowSize: pageSize)
    guard let fit = fitPage(ocr: ocr, page: stub.lines) else { fatalError("FIT FAILED on the rendered page (\(ocr.count) OCR lines)") }
    print(String(format: "fit: %d OCR lines; a=%.1f (want %.1f) b=%.1f (want 0) c=%.1f (want %.1f) d=%.1f (want 0)",
                 ocr.count, fit.a, pageSize.width, fit.b, fit.c, pageSize.height, fit.d))

    // 1b. The ⌃⌥D box fallback reads a cropped box of that page back as the quote.
    let page = renderer.cgImage!
    let box = page.cropping(to: CGRect(x: 0, y: Int(0.555 * Double(page.height)), width: page.width, height: Int(0.06 * Double(page.height))))!
    let boxText = try! recognizedText(box)
    print("box text: \(boxText)")
    let wanted = squash("this double-consciousness, this sense of always looking at one’s self through the eyes of others")
    print(squash(boxText).contains(wanted) ? "box text contains the double-consciousness quote: OK" : "BOX TEXT MISSING THE QUOTE")

    // 2. The overlay on that page: locked (board 1), then opened (board 4) with a thread selected (board 5).
    let model = OverlayModel()
    model.located = stub.located
    model.lines = stub.lines
    model.fit = fit
    model.windowSize = pageSize
    model.isStub = true
    model.setAnnotations(stub.annotations ?? [])
    savePNG(ZStack(alignment: .topLeading) { FakePage(lines: stub.lines, size: pageSize); HighlightLayer(model: model) }, "\(dir)/1-overlay-locked.png")
    savePNG(MarginView(model: model, refresh: {}, scrolls: false).frame(height: 760), "\(dir)/1-margin-locked.png")
    savePNG(StatusPill(model: model), "\(dir)/1-pill.png")
    let ctx = model.context(for: "this double-consciousness, this sense of always looking")
    print("note context near the locked cluster: \(ctx.map { "p. \($0.page), \($0.nearLockedCount) locked near" } ?? "nil")")

    let now = { () -> String in let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"; return f.string(from: Date()) }()
    model.setAnnotations(sample(OPENED_JSON.replacingOccurrences(of: "NOW", with: now), as: [Annotation].self))
    savePNG(ZStack(alignment: .topLeading) { FakePage(lines: stub.lines, size: pageSize); HighlightLayer(model: model) }, "\(dir)/4-overlay-opened.png")
    savePNG(MarginView(model: model, refresh: {}, scrolls: false).frame(height: 900), "\(dir)/4-margin-opened.png")
    model.selectedId = 3
    savePNG(MarginView(model: model, refresh: {}, scrolls: false).frame(height: 760), "\(dir)/5-thread.png")

    // 3. The one ⌃⌥D panel, both tabs (the answer scrolls, so it's drawn on its own too).
    let savedMode = UserDefaults.standard.string(forKey: PANEL_MODE_KEY)
    defer { UserDefaults.standard.set(savedMode, forKey: PANEL_MODE_KEY) }
    let composer = ComposerModel(quote: "this double-consciousness, this sense of always looking at one’s self through the eyes of others",
                                 context: ctx, onSaved: {})
    composer.mode = .ask
    composer.ask.question = "Where does the idea of double-consciousness come from?"
    savePNG(ComposerView(model: composer, ask: composer.ask, note: composer.note, overlay: model, session: SessionModel(), users: users), "\(dir)/2-panel-ask.png")
    composer.mode = .note
    savePNG(ComposerView(model: composer, ask: composer.ask, note: composer.note, overlay: model, session: SessionModel(), users: users), "\(dir)/3-panel-note.png")
    let answer = sample(ASK_JSON, as: AskResponse.self)
    savePNG(AnswerView(response: answer, users: users, showAI: .constant(false)).frame(width: 468).padding(16).background(Color.white), "\(dir)/2-ask-answer.png")

    // 4. Session highlights: colour detection on a page with a yellow mark, and on one without.
    let markQuote = stub.annotations!.first { $0.id == 3 }!   // "a sort of seventh son, born with a veil, …"
    let marked = ImageRenderer(content: FakePage(lines: stub.lines, size: pageSize, marks: markQuote.rects!))
    marked.scale = 2
    let found = try! highlightedQuotes(in: marked.cgImage!)
    print("session, marked page: \(found)")
    print(found.contains(where: { squash($0).contains(squash("seventh son, born with a veil")) }) && found.count == 1
          ? "session colour detection on the marked page: OK" : "SESSION COLOUR DETECTION FAILED on the marked page")
    let plain = try! highlightedQuotes(in: renderer.cgImage!)
    print(plain.isEmpty ? "session colour detection on the plain page: OK (nothing found)" : "SESSION FALSE POSITIVES on the plain page: \(plain)")
    savePNG(FakePage(lines: stub.lines, size: pageSize, marks: markQuote.rects!), "\(dir)/6-session-marked-page.png")

    let session = SessionModel()
    session.active = true
    session.highlights = [SessionHighlight(quote: found.first ?? "a sort of seventh son, born with a veil", page: 2, note: "The veil as a gift, not only a barrier."),
                          SessionHighlight(quote: "two warring ideals in one dark body", page: 2)]
    session.notInReading = 1
    savePNG(SessionPill(model: session), "\(dir)/6-session-pill.png")
    savePNG(SessionReviewView(model: session, scrolls: false, done: {}), "\(dir)/6-session-review.png")
}