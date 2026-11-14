// The Ask | Note panel (boards 2 and 3), shared by the iPad/iPhone app. Adapted from app/mac Panels.swift:
// same wording, same three-layer answer (From your class → Sources → AI behind a button).
import SwiftUI

public let PANEL_MODE_KEY = "panelMode"         // UserDefaults: the last tab used, "ask" or "note"
public let ASK_HINT = "Visible to the class. Classmates answer first."
public let NOTE_HINT = "Shared with the class."
public let AI_BUTTON = "Still stuck? Show the AI explanation"
public let AI_PRIVACY = "Sent to the AI: your question, the highlighted passage, the charter and the source excerpts. No names."
public let ASK_WAITING = "Asking your class, then the sources…"

/// "Open in reader": each app opens a reader path (e.g. "/readings/2?page=3") its own way.
public struct OpenReaderKey: EnvironmentKey {
    public static let defaultValue: (String) -> Void = { path in print("No reader to open \(path) in") }
}
public extension EnvironmentValues {
    var openReader: (String) -> Void {
        get { self[OpenReaderKey.self] }
        set { self[OpenReaderKey.self] = newValue }
    }
}

// ---------- Ask ----------

@MainActor
public final class AskModel: ObservableObject {
    @Published public var quote = ""
    @Published public var question = ""
    @Published public var error: String?
    @Published public var loading = false
    @Published public var response: AskResponse?
    @Published public var showAI = false
    public var sourceApp: String?

    public init() {}

    public func ask() {
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
                response = try await DialecticKit.ask(quote: quote, question: q, sourceApp: sourceApp)
            } catch {
                print("POST /api/ask failed: \(error)")
                self.error = error.localizedDescription
            }
            loading = false
        }
    }
}

public struct AskTab: View {
    @ObservedObject var model: AskModel
    let users: [User]
    @FocusState private var focused: Bool
    @Environment(\.openReader) private var openReader

    public init(model: AskModel, users: [User]) { self.model = model; self.users = users }

    public var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            TextField("Ask a question about this passage", text: $model.question, axis: .vertical)
                .textFieldStyle(.plain)
                .font(.system(size: 15))
                .padding(.horizontal, 10).padding(.vertical, 8)
                .frame(minHeight: Theme.minHit)
                .background(RoundedRectangle(cornerRadius: 10).fill(Theme.panel))
                .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.hairline, lineWidth: 1))
                .focused($focused)
                .submitLabel(.send)
                .onSubmit { model.ask() }
                .disabled(model.loading)
            HStack {
                Text(ASK_HINT).font(.system(size: 12)).foregroundColor(Theme.muted)
                Spacer()
                if model.response == nil {
                    Button("Ask") { model.ask() }
                        .buttonStyle(PrimaryButtonStyle())
                        .disabled(model.loading || model.question.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }

            if let error = model.error {
                Text(error).font(.system(size: 13)).foregroundColor(.red).textSelection(.enabled)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if model.loading {
                HStack(spacing: 8) { ProgressView(); Text(ASK_WAITING).foregroundColor(Theme.muted) }
            }
            if let response = model.response {
                Divider().overlay(Theme.hairline)
                AnswerView(response: response, users: users, showAI: $model.showAI)
                    .frame(maxWidth: .infinity, alignment: .leading)
                if let located = response.located {
                    HStack {
                        Text("Saved as a question on p. \(located.page)").font(.system(size: 12)).foregroundColor(Theme.muted)
                        Spacer()
                        Button("Open in reader") { openReader(located.reader_url) }
                            .buttonStyle(PrimaryButtonStyle(color: Theme.ink))
                    }
                }
            }
        }
        .onAppear { focused = true }
    }
}

public struct AnswerView: View {
    let response: AskResponse
    let users: [User]
    @Binding var showAI: Bool

    public init(response: AskResponse, users: [User], showAI: Binding<Bool>) {
        self.response = response; self.users = users; self._showAI = showAI
    }

    var visiblePeers: [Peer] { response.peer.filter { !$0.isLocked } }
    var lockedCount: Int { response.peer.filter { $0.isLocked }.count }
    func blocks(_ layer: String) -> [Blocked] { response.blocked.filter { $0.layer == layer } }
    var myCohort: String? { users.first(where: { $0.id == currentUserId() })?.cohort }

    public var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // 1. From your class (hidden when empty).
            if !visiblePeers.isEmpty || lockedCount > 0 {
                VStack(alignment: .leading, spacing: 8) {
                    SectionLabel("From your class")
                    ForEach(visiblePeers) { peer in peerCard(peer) }
                    if lockedCount > 0 {
                        RoleCard(role: .classmate, dashed: true) {
                            Text(lockedTitle(lockedCount)).font(.system(size: 14, weight: .semibold))
                            Text(LOCKED_HINT).font(.system(size: 12.5)).foregroundColor(Theme.muted)
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
                            LinkButton(title: source.title, url: source.url, size: 14)
                            Text("\(source.domain) · opens at the answering sentence")
                                .font(.system(size: 12)).foregroundColor(Theme.muted)
                        }
                        .frame(minHeight: Theme.minHit, alignment: .leading)
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
                                Text(ai.body).font(.system(size: 14)).fixedSize(horizontal: false, vertical: true).textSelection(.enabled)
                            }
                        } else {
                            Button(AI_BUTTON) { showAI = true }.buttonStyle(QuietButtonStyle())
                        }
                    } else {
                        SectionLabel("AI explanation")
                    }
                    ForEach(blocks("ai_answer")) { notice($0) }
                    Text(AI_PRIVACY).font(.system(size: 11.5)).foregroundColor(Theme.muted).fixedSize(horizontal: false, vertical: true)
                }
            }

            if visiblePeers.isEmpty && lockedCount == 0 && response.sources.isEmpty && response.ai_answer == nil {
                Text("No answer yet. Your question is saved on the page, so classmates can answer it.")
                    .font(.system(size: 13)).foregroundColor(Theme.muted).fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    func peerCard(_ peer: Peer) -> some View {
        let user = users.first(where: { $0.name == peer.author })
        let role = Role.of(authorId: user?.id, role: user?.role)
        let badge = role == .professor ? "Professor" : (peer.cohort != myCohort ? peer.cohort : nil)
        return RoleCard(role: role) {
            AuthorLine(name: peer.author ?? "Classmate", role: role, badge: badge, detail: peer.page.map { "p. \($0)" })
            Text(peer.body ?? "").font(.system(size: 14)).fixedSize(horizontal: false, vertical: true).textSelection(.enabled)
        }
    }

    var skippedLine: some View {
        let skipped = response.skipped_sources
        let reasons = Array(Set(skipped.map(\.reason))).sorted().joined(separator: "; ")
        return VStack(alignment: .leading, spacing: 2) {
            Text("\(skipped.count) result\(skipped.count == 1 ? "" : "s") skipped: \(reasons)")
                .font(.system(size: 12)).foregroundColor(Theme.muted).fixedSize(horizontal: false, vertical: true)
            ForEach(skipped.filter(\.linkable)) { s in
                LinkButton(title: s.title ?? s.url, url: s.url, size: 12)
            }
        }
    }

    func notice(_ blocked: Blocked) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(blocked.by == "no_sources" ? blocked.label : "Your class charter doesn't allow this (\(blocked.label)).")
                .font(.system(size: 13)).foregroundColor(Theme.warning)
            if let reason = blocked.reason, !reason.isEmpty {
                Text(reason).font(.system(size: 12)).foregroundColor(Theme.muted)
            }
        }
    }
}

// ---------- Note ----------

@MainActor
public final class NoteModel: ObservableObject {
    @Published public var quote = ""
    @Published public var body = ""
    @Published public var share = true
    @Published public var saving = false
    @Published public var error: String?
    @Published public var saved: SavedNote?
    public var sourceApp: String?

    public init() {}

    public func save() {
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
                saved = try await saveNote(quote: quote, body: text, share: share, sourceApp: sourceApp)
            } catch {
                print("POST /api/note failed: \(error)")
                self.error = error.localizedDescription
            }
            saving = false
        }
    }
}

public struct NoteTab: View {
    @ObservedObject var model: NoteModel
    @FocusState private var focused: Bool
    @Environment(\.openReader) private var openReader

    public init(model: NoteModel) { self.model = model }

    public var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionLabel("Your note")
            TextArea(placeholder: "What do you notice here?", text: $model.body, height: 110)
                .focused($focused)
                .disabled(model.saved != nil)
            Toggle("Share with future classes", isOn: $model.share)
                .font(.system(size: 13))
                .tint(Theme.you)
                .disabled(model.saved != nil)
            if let error = model.error {
                Text(error).font(.system(size: 13)).foregroundColor(.red).textSelection(.enabled)
                    .fixedSize(horizontal: false, vertical: true)
            }
            HStack {
                if let saved = model.saved {
                    Text("Saved as a note\(saved.page.map { " on p. \($0)" } ?? "").").font(.system(size: 12)).foregroundColor(Theme.muted)
                    Spacer()
                    Button("Open in reader") { openReader(saved.reader_url) }
                        .buttonStyle(PrimaryButtonStyle(color: Theme.ink))
                } else {
                    Text(NOTE_HINT).font(.system(size: 12)).foregroundColor(Theme.muted)
                    Spacer()
                    if model.saving { ProgressView() }
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

public enum ComposerMode: String {
    case ask, note
}

@MainActor
public final class ComposerModel: ObservableObject {
    @Published public var mode: ComposerMode {
        didSet { UserDefaults.standard.set(mode.rawValue, forKey: PANEL_MODE_KEY) }  // remember the last choice
    }
    public let ask = AskModel()
    public let note = NoteModel()
    /// Where the passage is, when it's already known (e.g. from a screenshot).
    public var knownSection: String?
    public var knownPage: Int?

    public init(quote: String, sourceApp: String? = nil, mode: ComposerMode? = nil) {
        self.mode = mode ?? ComposerMode(rawValue: UserDefaults.standard.string(forKey: PANEL_MODE_KEY) ?? "") ?? .ask
        ask.quote = quote
        ask.sourceApp = sourceApp
        note.quote = quote
        note.sourceApp = sourceApp
    }

    public var section: String? { ask.response?.located?.section ?? note.saved?.section ?? knownSection }
    public var page: Int? { ask.response?.located?.page ?? note.saved?.page ?? knownPage }
}

/// The panel: Ask | Note, where the passage is, the quote, then the chosen tab. `accessory` goes top right.
public struct ComposerView<Accessory: View>: View {
    @ObservedObject var model: ComposerModel
    @ObservedObject var ask: AskModel      // observed too, so the header follows an answer arriving
    @ObservedObject var note: NoteModel
    let users: [User]
    let accessory: Accessory

    public init(model: ComposerModel, users: [User], @ViewBuilder accessory: () -> Accessory) {
        self.model = model; self.ask = model.ask; self.note = model.note; self.users = users; self.accessory = accessory()
    }

    var place: String {
        [model.section, model.page.map { "p. \($0)" }].compactMap { $0 }.joined(separator: ", ")
    }

    public var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                ModeSwitch(mode: $model.mode)
                Spacer(minLength: 4)
                accessory
            }
            if !place.isEmpty {
                Text(place).font(.system(size: 13)).foregroundColor(Theme.muted).lineLimit(1).truncationMode(.middle)
            }
            QuoteChip(text: model.ask.quote, lineLimit: 6)
            if model.mode == .ask {
                AskTab(model: ask, users: users)
            } else {
                NoteTab(model: note)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .environment(\.colorScheme, .light)
    }
}

/// Ask | Note as two pills (the canvas look; a native segmented control doesn't match it).
public struct ModeSwitch: View {
    @Binding var mode: ComposerMode
    public init(mode: Binding<ComposerMode>) { self._mode = mode }
    public var body: some View {
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
                .font(.system(size: 14, weight: mode == value ? .semibold : .regular))
                .foregroundColor(mode == value ? Theme.ink : Theme.muted)
                .padding(.horizontal, 18).frame(minHeight: 36)
                .background(Capsule().fill(mode == value ? Theme.panel : Color.clear))
                .contentShape(Capsule())
        }
        .buttonStyle(.plain)
    }
}
