// "Ask Dialectic Here" and "Note Dialectic Here": the iPad/iPhone stand-in for the Mac's ⌃⌥D over other apps.
// A two-step shortcut (Take Screenshot → this action), run by Back Tap or AssistiveTouch, reads the page you're on
// (Vision, on the device), finds it in a course reading, and shows the answer as a card over that app.
// The screenshot never leaves the device: only recognised text is sent. Setup: SetupView / app/ios/README.md.
import AppIntents
import DialecticKit
import SwiftUI
import UIKit

let CARD_MAX_PEERS = 3
let CARD_MAX_SOURCES = 3

enum IntentFailure: LocalizedError {
    case noUser, badImage
    var errorDescription: String? {
        switch self {
        case .noUser: return "Open Dialectic and pick who you are first."
        case .badImage: return "Couldn't read the screenshot. In the shortcut, pass Take Screenshot's result to this action."
        }
    }
}

func screenQuotes(_ file: IntentFile) throws -> [String] {
    guard let image = UIImage(data: file.data)?.cgImage else { throw IntentFailure.badImage }
    let quotes = candidateQuotes(try recognizeLines(image))
    print("Screen: \(quotes.count) candidate quotes")
    return quotes
}

/// Classmates' notes on the located page: the shortcut's stand-in for the Mac's highlights switch.
func notesOnPage(readingId: Int, page: Int) async -> (visible: [Annotation], locked: Int) {
    guard let all = try? await annotations(readingId: readingId) else { return ([], 0) }
    let onPage = all.filter { $0.page == page && $0.parent_id == nil }
    return (onPage.filter { !$0.isLocked && $0.kind != "question" }, onPage.filter(\.isLocked).count)
}

struct AskHereIntent: AppIntent {
    static var title: LocalizedStringResource = "Ask Dialectic Here"
    static var description = IntentDescription("Ask about the passage on your screen. Pass it a screenshot (Take Screenshot).")
    static var openAppWhenRun = false

    @Parameter(title: "Screenshot")
    var screenshot: IntentFile

    @Parameter(title: "Question", requestValueDialog: "What's your question about this passage?")
    var question: String

    static var parameterSummary: some ParameterSummary { Summary("Ask Dialectic about \(\.$screenshot)") }

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog & ShowsSnippetView {
        guard currentUserId() != nil else { throw IntentFailure.noUser }
        let quotes = try screenQuotes(screenshot)
        let (quote, response) = try await firstInReading(quotes) { try await ask(quote: $0, question: question, sourceApp: SOURCE_APP + " shortcut") }
        var notes: [Annotation] = []
        if let located = response.located { notes = await notesOnPage(readingId: located.reading_id, page: located.page).visible }
        let peers = response.peer.filter { !$0.isLocked }
        let dialog: IntentDialog = peers.isEmpty
            ? "Saved your question. \(response.sources.isEmpty ? "No class answers yet." : "Here are the sources.")"
            : "\(peers.count) classmate\(peers.count == 1 ? "" : "s") answered."
        return .result(dialog: dialog, view: AnswerCard(quote: quote, question: question, response: response, pageNotes: notes.count))
    }
}

struct NoteHereIntent: AppIntent {
    static var title: LocalizedStringResource = "Note Dialectic Here"
    static var description = IntentDescription("Add a note on the passage on your screen. Pass it a screenshot (Take Screenshot).")
    static var openAppWhenRun = false

    @Parameter(title: "Screenshot")
    var screenshot: IntentFile

    @Parameter(title: "Note", requestValueDialog: "What do you notice here?")
    var note: String

    @Parameter(title: "Share with future classes", default: true)
    var share: Bool

    static var parameterSummary: some ParameterSummary { Summary("Note \(\.$note) on \(\.$screenshot)") }

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog & ShowsSnippetView {
        guard currentUserId() != nil else { throw IntentFailure.noUser }
        let quotes = try screenQuotes(screenshot)
        let (quote, saved) = try await firstInReading(quotes) { try await saveNote(quote: $0, body: note, share: share, sourceApp: SOURCE_APP + " shortcut") }
        return .result(dialog: "Saved your note\(saved.page.map { " on p. \($0)" } ?? "").",
                       view: NoteCard(quote: quote, note: note, saved: saved))
    }
}

/// Opens the app's reader at a path (the card's "Open in Dialectic").
struct OpenReaderIntent: AppIntent {
    static var title: LocalizedStringResource = "Open in Dialectic"
    static var openAppWhenRun = true
    static var isDiscoverable = false

    @Parameter(title: "Path") var path: String
    init() {}
    init(path: String) { self.path = path }

    @MainActor
    func perform() async throws -> some IntentResult {
        AppState.shared.pendingPath = path
        return .result()
    }
}

struct DialecticShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(intent: AskHereIntent(), phrases: ["Ask \(.applicationName) here", "Ask \(.applicationName) about this"],
                    shortTitle: "Ask Dialectic Here", systemImageName: "text.quote")
        AppShortcut(intent: NoteHereIntent(), phrases: ["Note in \(.applicationName)"],
                    shortTitle: "Note Dialectic Here", systemImageName: "square.and.pencil")
    }
}

// ---------- the cards shown over the other app ----------

struct AnswerCard: View {
    let quote: String
    let question: String
    let response: AskResponse
    let pageNotes: Int

    var peers: [Peer] { response.peer.filter { !$0.isLocked } }
    var locked: Int { response.peer.filter(\.isLocked).count }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            if let located = response.located {
                Text(contextTitle("Ask", section: located.section, page: located.page))
                    .font(.system(size: 12.5)).foregroundColor(Theme.muted).lineLimit(1)
            }
            QuoteChip(text: quote, lineLimit: 2)
            Text(question).font(.system(size: 14, weight: .semibold)).foregroundColor(Theme.ink)
            if !peers.isEmpty {
                SectionLabel("From your class")
                ForEach(peers.prefix(CARD_MAX_PEERS)) { peer in
                    RoleCard(role: .classmate) {
                        AuthorLine(name: peer.author ?? "Classmate", role: .classmate, badge: nil, detail: peer.page.map { "p. \($0)" })
                        Text(peer.body ?? "").font(.system(size: 13)).lineLimit(4)
                    }
                }
            }
            if locked > 0 {
                Text("\(lockedTitle(locked)). \(LOCKED_HINT)").font(.system(size: 12)).foregroundColor(Theme.muted)
            }
            if !response.sources.isEmpty {
                SectionLabel("Sources")
                ForEach(response.sources.prefix(CARD_MAX_SOURCES)) { source in
                    Text("\(source.title) · \(source.domain)").font(.system(size: 13)).foregroundColor(Theme.you).lineLimit(1)
                }
            }
            if response.ai_answer != nil {
                // AI stays behind a click, as on the Mac: it opens in the app, not on this card.
                Text("\(AI_BUTTON): open in Dialectic.").font(.system(size: 12)).foregroundColor(Theme.muted)
            }
            if pageNotes > 0 {
                Text("\(pageNotes) note\(pageNotes == 1 ? "" : "s") from your class on this page.").font(.system(size: 12)).foregroundColor(Theme.muted)
            }
            if let located = response.located {
                Button(intent: OpenReaderIntent(path: located.reader_url)) {
                    Text("Open in Dialectic").font(.system(size: 14, weight: .semibold)).frame(maxWidth: .infinity, minHeight: 40)
                }
                .tint(Theme.ink)
            }
        }
        .padding(14)
        .environment(\.colorScheme, .light)
    }
}

struct NoteCard: View {
    let quote: String
    let note: String
    let saved: SavedNote

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(contextTitle("Note", section: saved.section, page: saved.page)).font(.system(size: 12.5)).foregroundColor(Theme.muted)
            QuoteChip(text: quote, lineLimit: 2)
            RoleCard(role: .you) { Text(note).font(.system(size: 13)).lineLimit(5) }
            Button(intent: OpenReaderIntent(path: saved.reader_url)) {
                Text("Open in Dialectic").font(.system(size: 14, weight: .semibold)).frame(maxWidth: .infinity, minHeight: 40)
            }
            .tint(Theme.ink)
        }
        .padding(14)
        .environment(\.colorScheme, .light)
    }
}
