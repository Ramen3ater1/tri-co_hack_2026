// The floating panels: the one ⌃⌥D panel (Ask | Note tabs, boards 2 and 3), plus short messages.
import AppKit
import SwiftUI

let COMPOSER_WIDTH: CGFloat = 500        // the one Ask | Note panel
let PANEL_MODE_KEY = "panelMode"         // UserDefaults: the last tab used, "ask" or "note"
let MESSAGE_PANEL_WIDTH: CGFloat = 420
let ANSWER_HEIGHT: CGFloat = 430          // the answer scrolls inside this
let ASK_HINT = "Visible to the class. Classmates answer first."
let NOTE_HINT = "Shared with the class."
let AI_BUTTON = "Still stuck? Show the AI explanation"
let AI_PRIVACY = "Sent to the AI: your question, the highlighted passage, the charter and the source excerpts. No names."
let ASK_WAITING = "Asking your class, then the sources…"

/// Where a passage is, when the overlay already knows (from the located page's lines).
struct PassageContext {
    let readingId: Int
    let section: String?
    let page: Int
    let nearLockedCount: Int   // locked classmates' annotations near this passage
}

func contextTitle(_ verb: String, section: String?, page: Int?) -> String {
    let place = [section, page.map { "p. \($0)" }].compactMap { $0 }.joined(separator: ", ")
    return place.isEmpty ? verb : "\(verb) · \(place)"
}

// ---------- Ask ----------

@MainActor
final class AskModel: ObservableObject {
    @Published var quote = ""
    @Published var question = ""
    @Published var error: String?
    @Published var loading = false
    @Published var response: AskResponse?
    @Published var showAI = false
    var context: PassageContext?
    var onSaved: () -> Void = {}

    var section: String? { response?.located?.section ?? context?.section }
    var page: Int? { response?.located?.page ?? context?.page }

    func ask() {
        let q = question.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !q.isEmpty, !quote.isEmpty, !loading else { return }
        guard currentUserId() != nil else {
            error = NO_USER_MESSAGE
            return
        }
        loading = true
        error = nil
        response = nil
        showAI = false
        Task {
            do {
                response = try await post("/api/ask", AskRequest(quote: quote, question: q), as: AskResponse.self, timeout: ASK_TIMEOUT_SECONDS)
                onSaved()
            } catch {
                print("POST /api/ask failed: \(error)")
                self.error = error.localizedDescription
            }
            loading = false
        }
    }
}

/// The Ask tab: question box, then the three-layer answer (board 2).
struct AskTab: View {
    @ObservedObject var model: AskModel
    let users: [User]
    @FocusState private var focused: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            TextField("Ask a question about this passage", text: $model.question)
                .textFieldStyle(.plain)
                .font(.system(size: 13))
                .padding(.horizontal, 10)
                .frame(minHeight: Theme.minHit)
                .background(RoundedRectangle(cornerRadius: 10).fill(Theme.panel))
                .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.hairline, lineWidth: 1))
                .focused($focused)
                .onSubmit { model.ask() }
                .disabled(model.loading)
            Text(ASK_HINT).font(.system(size: 11.5)).foregroundColor(Theme.muted)

            if let error = model.error {
                Text(error).font(.system(size: 12.5)).foregroundColor(.red).textSelection(.enabled)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if model.loading {
                HStack(spacing: 8) { ProgressView().controlSize(.small); Text(ASK_WAITING).foregroundColor(Theme.muted) }
            }
            if let response = model.response {
                Divider().overlay(Theme.hairline)
                ScrollView {
                    AnswerView(response: response, users: users, showAI: $model.showAI)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .frame(height: ANSWER_HEIGHT)
                if let located = response.located {
                    HStack {
                        Text("Saved as a question on p. \(located.page)").font(.system(size: 12)).foregroundColor(Theme.muted)
                        Spacer()
                        Button("Open in reader") { openInReader(located.reader_url) }
                            .buttonStyle(PrimaryButtonStyle(color: Theme.ink))
                    }
                }
            }
        }
        .onAppear { focused = true }
    }
}

struct AnswerView: View {
    let response: AskResponse
    let users: [User]
    @Binding var showAI: Bool

    var visiblePeers: [Peer] { response.peer.filter { !$0.isLocked } }
    var lockedCount: Int { response.peer.filter { $0.isLocked }.count }
    func blocks(_ layer: String) -> [Blocked] { response.blocked.filter { $0.layer == layer } }
    var myCohort: String? { users.first(where: { $0.id == currentUserId() })?.cohort }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // 1. From your class (hidden when empty).
            if !visiblePeers.isEmpty || lockedCount > 0 {
                VStack(alignment: .leading, spacing: 8) {
                    SectionLabel("From your class")
                    ForEach(visiblePeers) { peer in peerCard(peer) }
                    if lockedCount > 0 {
                        RoleCard(role: .classmate, dashed: true) {
                            Text(lockedTitle(lockedCount))
                                .font(.system(size: 13, weight: .semibold))
                            Text(LOCKED_HINT).font(.system(size: 12)).foregroundColor(Theme.muted)
                        }
                    }
                }
            }

            // 2. Sources, with this layer's charter notices in its place.
            if !response.sources.isEmpty || !blocks("sources_ai").isEmpty || !response.skipped_sources.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    SectionLabel("Sources")
                    ForEach(response.sources) { source in
                        VStack(alignment: .leading, spacing: 2) {
                            LinkButton(title: source.title, url: source.url)
                            Text("\(source.domain) · opens at the answering sentence")
                                .font(.system(size: 11.5)).foregroundColor(Theme.muted)
                        }
                        .frame(minHeight: 36, alignment: .leading)
                    }
                    ForEach(blocks("sources_ai")) { notice($0) }
                    if !response.skipped_sources.isEmpty { skippedLine }
                }
            }

            // 3. AI explanation, collapsed behind a button.
            if response.ai_answer != nil || !blocks("ai_answer").isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    if let ai = response.ai_answer {
                        if showAI {
                            SectionLabel("AI explanation")
                            RoleCard(role: .ai) {
                                AuthorLine(name: "Dialectic AI", role: .ai, badge: "AI")
                                Text(ai.body).font(.system(size: 13)).fixedSize(horizontal: false, vertical: true).textSelection(.enabled)
                            }
                        } else {
                            Button(AI_BUTTON) { showAI = true }.buttonStyle(QuietButtonStyle())
                        }
                    } else {
                        SectionLabel("AI explanation")
                    }
                    ForEach(blocks("ai_answer")) { notice($0) }
                    Text(AI_PRIVACY).font(.system(size: 11)).foregroundColor(Theme.muted).fixedSize(horizontal: false, vertical: true)
                }
            }
        }
    }

    func peerCard(_ peer: Peer) -> some View {
        let user = users.first(where: { $0.name == peer.author })
        let role = Role.of(authorId: user?.id, role: user?.role)
        let badge = role == .professor ? "Professor" : (peer.cohort != myCohort ? peer.cohort : nil)
        return RoleCard(role: role) {
            AuthorLine(name: peer.author ?? "Classmate", role: role, badge: badge, detail: peer.page.map { "p. \($0)" })
            Text(peer.body ?? "").font(.system(size: 13)).fixedSize(horizontal: false, vertical: true).textSelection(.enabled)
        }
    }

    var skippedLine: some View {
        let skipped = response.skipped_sources
        let reasons = Array(Set(skipped.map(\.reason))).sorted().joined(separator: "; ")
        return VStack(alignment: .leading, spacing: 2) {
            Text("\(skipped.count) result\(skipped.count == 1 ? "" : "s") skipped: \(reasons)")
                .font(.system(size: 11.5)).foregroundColor(Theme.muted).fixedSize(horizontal: false, vertical: true)
            // Permitted but unread ones are linked so the student can read them themselves (SPEC §6).
            ForEach(skipped.filter(\.linkable)) { s in
                LinkButton(title: s.title ?? s.url, url: s.url, size: 11.5)
            }
        }
    }

    func notice(_ blocked: Blocked) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(blocked.by == "no_sources" ? blocked.label : "Your class charter doesn't allow this (\(blocked.label)).")
                .font(.system(size: 12.5)).foregroundColor(Theme.warning)
            if let reason = blocked.reason, !reason.isEmpty {
                Text(reason).font(.system(size: 11.5)).foregroundColor(Theme.muted)
            }
        }
    }
}

// ---------- Note ----------

@MainActor
final class NoteModel: ObservableObject {
    @Published var quote = ""
    @Published var body = ""
    @Published var share = true
    @Published var saving = false
    @Published var error: String?
    @Published var saved: SavedNote?
    var context: PassageContext?
    var onSaved: () -> Void = {}

    func save() {
        let text = body.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !saving, saved == nil else { return }
        guard currentUserId() != nil else {
            error = NO_USER_MESSAGE
            return
        }
        saving = true
        error = nil
        Task {
            do {
                saved = try await post("/api/note", NoteRequest(quote: quote, body: text, share_with_future: share), as: SavedNote.self)
                onSaved()
            } catch {
                print("POST /api/note failed: \(error)")
                self.error = error.localizedDescription
            }
            saving = false
        }
    }
}

/// The Note tab: note box, share checkbox, Save (board 3).
struct NoteTab: View {
    @ObservedObject var model: NoteModel
    @FocusState private var focused: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionLabel("Your note")
            TextArea(placeholder: "What do you notice here?", text: $model.body, height: 96)
                .focused($focused)
                .disabled(model.saved != nil)
            Toggle("Share with future classes", isOn: $model.share)
                .toggleStyle(.checkbox).font(.system(size: 12.5))
                .disabled(model.saved != nil)
            if let error = model.error {
                Text(error).font(.system(size: 12.5)).foregroundColor(.red).textSelection(.enabled)
                    .fixedSize(horizontal: false, vertical: true)
            }
            HStack {
                if let saved = model.saved {
                    Text("Saved as a note\(saved.page.map { " on p. \($0)" } ?? "").").font(.system(size: 12)).foregroundColor(Theme.muted)
                    Spacer()
                    Button("Open in reader") { openInReader(saved.reader_url) }
                        .buttonStyle(PrimaryButtonStyle(color: Theme.ink))
                } else {
                    Text(NOTE_HINT).font(.system(size: 12)).foregroundColor(Theme.muted)
                    Spacer()
                    if model.saving { ProgressView().controlSize(.small) }
                    Button("Save") { model.save() }
                        .buttonStyle(PrimaryButtonStyle())
                        .keyboardShortcut(.return, modifiers: .command)
                        .disabled(model.saving)
                }
            }
        }
        .onAppear { focused = true }
    }
}

// ---------- the one panel: Ask | Note ----------

enum ComposerMode: String {
    case ask, note
}

@MainActor
final class ComposerModel: ObservableObject {
    @Published var mode: ComposerMode {
        didSet { UserDefaults.standard.set(mode.rawValue, forKey: PANEL_MODE_KEY) }  // remember the last choice
    }
    let ask = AskModel()
    let note = NoteModel()

    init(quote: String, context: PassageContext?, onSaved: @escaping () -> Void) {
        mode = ComposerMode(rawValue: UserDefaults.standard.string(forKey: PANEL_MODE_KEY) ?? "") ?? .ask
        ask.quote = quote
        ask.context = context
        ask.onSaved = onSaved
        note.quote = quote
        note.context = context
        note.onSaved = onSaved
    }

    var section: String? { ask.response?.located?.section ?? note.saved?.section ?? ask.context?.section }
    var page: Int? { ask.response?.located?.page ?? note.saved?.page ?? ask.context?.page }
}

/// ⌃⌥D's panel: header with Ask | Note and the highlights switch, the quote, then the chosen tab.
struct ComposerView: View {
    @ObservedObject var model: ComposerModel
    @ObservedObject var ask: AskModel      // observed too, so the header follows an answer arriving
    @ObservedObject var note: NoteModel
    @ObservedObject var overlay: OverlayModel
    let users: [User]

    var place: String {
        [model.section, model.page.map { "p. \($0)" }].compactMap { $0 }.joined(separator: ", ")
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                ModeSwitch(mode: $model.mode)
                Spacer(minLength: 4)
                Toggle("Highlights", isOn: Binding(get: { overlay.active }, set: { _ in AppDelegate.shared.toggleHighlights() }))
                    .toggleStyle(.switch).controlSize(.mini).font(.system(size: 11.5))
                    .help("Show classmates' highlights on the page you're reading")
                KeyCap(label: HOTKEY_LABEL)
            }
            if !place.isEmpty {
                Text(place).font(.system(size: 12.5)).foregroundColor(Theme.muted).lineLimit(1).truncationMode(.middle)
            }
            if model.mode == .note, let near = note.context?.nearLockedCount, near > 0, note.saved == nil {
                RoleCard(role: .classmate, dashed: true) {
                    Text("\(lockedTitle(near)). Your note opens them.")
                        .font(.system(size: 12.5)).foregroundColor(Theme.ink)
                }
            }
            QuoteChip(text: model.ask.quote)
            if model.mode == .ask {
                AskTab(model: ask, users: users)
            } else {
                NoteTab(model: note)
            }
        }
        .frame(width: COMPOSER_WIDTH - 32, alignment: .leading)
        .panelSurface()
    }
}

/// Ask | Note as two pills (the canvas look; a native segmented control doesn't match it).
struct ModeSwitch: View {
    @Binding var mode: ComposerMode
    var body: some View {
        HStack(spacing: 2) {
            pill("Ask", .ask)
            pill("Note", .note)
        }
        .padding(2)
        .background(Capsule().fill(Theme.ground))
        .overlay(Capsule().stroke(Theme.hairline, lineWidth: 1))
    }

    func pill(_ title: String, _ value: ComposerMode) -> some View {
        Button { mode = value } label: {
            Text(title)
                .font(.system(size: 13, weight: mode == value ? .semibold : .regular))
                .foregroundColor(mode == value ? Theme.ink : Theme.muted)
                .padding(.horizontal, 14).frame(minHeight: 28)
                .background(Capsule().fill(mode == value ? Theme.panel : Color.clear))
                .contentShape(Capsule())
        }
        .buttonStyle(.plain)
    }
}

struct MessageView: View {
    let text: String
    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: "text.quote").foregroundColor(Theme.you)
            Text(text).font(.system(size: 13)).foregroundColor(Theme.ink).fixedSize(horizontal: false, vertical: true)
        }
        .frame(width: MESSAGE_PANEL_WIDTH - 32, alignment: .leading)
        .panelSurface()
    }
}

// ---------- the floating panel window ----------

/// Borderless and non-activating: it takes typing, but the reading app stays the front app.
final class FloatingPanel: NSPanel {
    init() {
        super.init(contentRect: NSRect(x: 0, y: 0, width: 400, height: 200),
                   styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
        isFloatingPanel = true
        level = .floating
        hidesOnDeactivate = false
        isReleasedWhenClosed = false
        isMovableByWindowBackground = true
        backgroundColor = .clear
        isOpaque = false
        hasShadow = true
        collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
    }
    override var canBecomeKey: Bool { true }
    override func cancelOperation(_ sender: Any?) { orderOut(nil) }  // Esc closes
}

@MainActor
final class PanelController {
    let panel = FloatingPanel()

    /// Show `view` in the panel. Near the mouse (a stand-in for the selection) when `nearMouse`.
    func show<V: View>(_ view: V, nearMouse: Bool = true) {
        let hosting = NSHostingView(rootView: AnyView(view))
        panel.contentView = hosting
        fit(hosting, anchorTopLeft: nearMouse ? mouseAnchor() : nil)
        panel.makeKeyAndOrderFront(nil)
    }

    /// Re-fit the panel to its content (after an answer arrives), keeping the top-left corner.
    func refit() {
        guard let hosting = panel.contentView as? NSHostingView<AnyView> else { return }
        fit(hosting, anchorTopLeft: NSPoint(x: panel.frame.minX, y: panel.frame.maxY))
    }

    private func fit(_ hosting: NSView, anchorTopLeft: NSPoint?) {
        let size = hosting.fittingSize
        let screen = NSScreen.screens.first(where: { $0.frame.contains(anchorTopLeft ?? .zero) }) ?? NSScreen.main!
        let visible = screen.visibleFrame
        var origin: NSPoint
        if let anchor = anchorTopLeft {
            origin = NSPoint(x: anchor.x, y: anchor.y - size.height)
        } else {
            origin = NSPoint(x: visible.midX - size.width / 2, y: visible.midY - size.height / 2)
        }
        origin.x = min(max(origin.x, visible.minX + 8), visible.maxX - size.width - 8)
        origin.y = min(max(origin.y, visible.minY + 8), visible.maxY - size.height - 8)
        panel.setFrame(NSRect(origin: origin, size: size), display: true)
    }

    private func mouseAnchor() -> NSPoint {
        let mouse = NSEvent.mouseLocation
        return NSPoint(x: mouse.x + 16, y: mouse.y - 16)
    }
}
