// Dialectic Mac hotkey app (SPEC §3.9): select text anywhere, press ⌥⇧D, ask a question.
// Menu-bar only. Talks to the same server as the web app; keeps no data of its own.
import AppKit
import Carbon.HIToolbox
import SwiftUI

// ---------- tunables ----------

/// The Dialectic server. DEMO: set to the deployed site (SPEC §9) before the demo.
let SERVER_URL = "http://localhost:8000"
/// Hotkey: ⌥⇧D.
let HOTKEY_KEYCODE = UInt32(kVK_ANSI_D)
let HOTKEY_MODIFIERS = UInt32(optionKey | shiftKey)
let HOTKEY_LABEL = "⌥⇧D"
/// How long to wait for the front app to put the selection on the pasteboard after ⌘C.
let COPY_WAIT_SECONDS = 0.6
/// /api/ask searches the web and calls the LLM, so it can take a while.
let ASK_TIMEOUT_SECONDS: TimeInterval = 120
let USER_DEFAULTS_KEY = "userId"

let NO_SELECTION_MESSAGE = "Select some text first, then press \(HOTKEY_LABEL)."
let NO_USER_MESSAGE = "Pick who you are in the Dialectic menu-bar menu first."
let NO_ACCESSIBILITY_MESSAGE =
    "Dialectic needs Accessibility access to copy your selection. Turn it on in System Settings → Privacy & Security → Accessibility, then press \(HOTKEY_LABEL) again."

// ---------- API shapes (SPEC §6; checked against app/backend/ask.py and main.py) ----------

struct User: Decodable {
    let id: Int
    let name: String
    let role: String?
    let cohort: String?
}

struct AskRequest: Encodable {
    let quote: String
    let question: String
}

struct AskResponse: Decodable {
    let question_id: Int
    let peer: [Peer]
    let sources: [Source]
    let ai_answer: AIAnswer?
    let skipped_sources: [Skipped]
    let blocked: [Blocked]
    let located: Located?
}

/// A peer annotation, or a locked one (SPEC §3.4: `{id, page, rects, locked: true}`, no author or text).
struct Peer: Decodable, Identifiable {
    let annotation_id: Int?
    let id_: Int?
    let author: String?
    let cohort: String?
    let page: Int?
    let quote: String?
    let body: String?
    let locked: Bool?

    var id: Int { annotation_id ?? id_ ?? -1 }
    var isLocked: Bool { locked == true }

    enum CodingKeys: String, CodingKey {
        case annotation_id, author, cohort, page, quote, body, locked
        case id_ = "id"
    }
}

struct Source: Decodable, Identifiable {
    let source_id: Int?
    let title: String
    let url: String
    let quote: String?
    var id: String { url }
}

struct AIAnswer: Decodable {
    let annotation_id: Int
    let body: String
}

struct Skipped: Decodable, Identifiable {
    let url: String
    let title: String?
    let why: String
    let reason: String
    var id: String { url }
    /// not_permitted / not_covered are ruled out by the charter: show them, don't link them (SPEC §6).
    var linkable: Bool { why == "unreachable" || why == "no_answer" }
}

struct Blocked: Decodable, Identifiable {
    let layer: String  // "sources_ai" | "ai_answer"
    let by: String     // "toggle" | "rule" | "no_sources"
    let label: String
    let reason: String?
    var id: String { layer + by + label }
}

struct Located: Decodable {
    let reading_id: Int
    let reading_title: String
    let page: Int
    let section: String?
    let reader_url: String
}

/// FastAPI errors are `{"detail": "..."}` (or a list of problems for a 422).
struct APIError: LocalizedError {
    let message: String
    var errorDescription: String? { message }
}

// ---------- HTTP ----------

func request(_ path: String, method: String = "GET", body: Data? = nil, timeout: TimeInterval = 15) async throws -> Data {
    guard let url = URL(string: SERVER_URL + path) else { throw APIError(message: "Bad URL: \(SERVER_URL + path)") }
    var req = URLRequest(url: url, timeoutInterval: timeout)
    req.httpMethod = method
    if let userId = UserDefaults.standard.object(forKey: USER_DEFAULTS_KEY) as? Int {
        req.setValue(String(userId), forHTTPHeaderField: "X-User-Id")
    }
    if let body {
        req.httpBody = body
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
    }
    let (data, response) = try await URLSession.shared.data(for: req)
    let status = (response as? HTTPURLResponse)?.statusCode ?? 0
    if !(200..<300).contains(status) {
        throw APIError(message: "Server said \(status): \(errorDetail(data))")
    }
    return data
}

func errorDetail(_ data: Data) -> String {
    if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any], let detail = json["detail"] {
        if let text = detail as? String { return text }
        return String(describing: detail)
    }
    return String(data: data, encoding: .utf8) ?? "(no body)"
}

// ---------- panel state ----------

@MainActor
final class PanelModel: ObservableObject {
    @Published var quote = ""
    @Published var question = ""
    @Published var message: String?      // a notice instead of the ask form (no selection, no user…)
    @Published var error: String?
    @Published var loading = false
    @Published var response: AskResponse?
    @Published var showAI = false

    func reset(quote: String) {
        self.quote = quote
        question = ""
        message = nil
        error = nil
        loading = false
        response = nil
        showAI = false
    }

    func ask() {
        let q = question.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !q.isEmpty, !quote.isEmpty, !loading else { return }
        guard UserDefaults.standard.object(forKey: USER_DEFAULTS_KEY) != nil else {
            error = NO_USER_MESSAGE
            return
        }
        loading = true
        error = nil
        response = nil
        showAI = false
        let body = try! JSONEncoder().encode(AskRequest(quote: quote, question: q))
        Task {
            do {
                let data = try await request("/api/ask", method: "POST", body: body, timeout: ASK_TIMEOUT_SECONDS)
                do {
                    response = try JSONDecoder().decode(AskResponse.self, from: data)
                } catch {
                    print("Couldn't decode /api/ask response: \(error)\n\(String(data: data, encoding: .utf8) ?? "")")
                    self.error = "Couldn't read the server's answer: \(error)"
                }
            } catch {
                print("POST /api/ask failed: \(error)")
                self.error = error.localizedDescription
            }
            loading = false
        }
    }
}

// ---------- panel view ----------

struct PanelView: View {
    @ObservedObject var model: PanelModel

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            if let message = model.message {
                Text(message).font(.body).fixedSize(horizontal: false, vertical: true)
            } else {
                askForm
                if let error = model.error {
                    Text(error).foregroundColor(.red).textSelection(.enabled)
                        .fixedSize(horizontal: false, vertical: true)
                }
                if model.loading {
                    HStack { ProgressView().controlSize(.small); Text("Asking your class, the sources and the AI…") }
                }
                if let response = model.response {
                    ScrollView { AnswerView(response: response, showAI: $model.showAI).frame(maxWidth: .infinity, alignment: .leading) }
                }
            }
        }
        .padding(16)
        .frame(width: 480, alignment: .topLeading)
        .frame(minHeight: 120, maxHeight: 640, alignment: .top)
    }

    var askForm: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("“\(model.quote)”")
                .font(.system(.body, design: .serif)).italic()
                .lineLimit(6)
                .fixedSize(horizontal: false, vertical: true)
            TextField("Ask a question about this passage, then press Enter", text: $model.question)
                .textFieldStyle(.roundedBorder)
                .onSubmit { model.ask() }
                .disabled(model.loading)
        }
    }
}

struct AnswerView: View {
    let response: AskResponse
    @Binding var showAI: Bool

    var visiblePeers: [Peer] { response.peer.filter { !$0.isLocked } }
    var lockedCount: Int { response.peer.filter { $0.isLocked }.count }
    func blocks(_ layer: String) -> [Blocked] { response.blocked.filter { $0.layer == layer } }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            if let located = response.located {
                Text([located.reading_title, located.section, "p. \(located.page)"].compactMap { $0 }.joined(separator: " › "))
                    .font(.caption).foregroundColor(.secondary)
            }

            // 1. From your class (empty layer hidden).
            if !visiblePeers.isEmpty || lockedCount > 0 {
                section("From your class") {
                    ForEach(visiblePeers) { peer in
                        VStack(alignment: .leading, spacing: 2) {
                            Text([peer.author, peer.cohort].compactMap { $0 }.joined(separator: " · ")).font(.caption.bold())
                            Text(peer.body ?? "").fixedSize(horizontal: false, vertical: true).textSelection(.enabled)
                        }
                    }
                    if lockedCount > 0 {
                        Text("\(lockedCount) classmate\(lockedCount == 1 ? "" : "s") annotated near here. Add a note or ask a question there to see theirs.")
                            .font(.callout).foregroundColor(.secondary)
                    }
                }
            }

            // 2. Sources, with the charter notices for this layer in its place.
            if !response.sources.isEmpty || !blocks("sources_ai").isEmpty || !response.skipped_sources.isEmpty {
                section("Sources") {
                    ForEach(response.sources) { source in
                        VStack(alignment: .leading, spacing: 2) {
                            link(source.title, source.url)
                            if let quote = source.quote {
                                Text(quote).font(.callout).foregroundColor(.secondary).fixedSize(horizontal: false, vertical: true)
                            }
                        }
                    }
                    ForEach(blocks("sources_ai")) { notice($0) }
                    if !response.skipped_sources.isEmpty {
                        Text("\(response.skipped_sources.count) result\(response.skipped_sources.count == 1 ? "" : "s") skipped:")
                            .font(.caption).foregroundColor(.secondary)
                        ForEach(response.skipped_sources) { skipped in
                            HStack(alignment: .firstTextBaseline, spacing: 4) {
                                if skipped.linkable { link(skipped.title ?? skipped.url, skipped.url).font(.caption) }
                                else { Text(skipped.title ?? skipped.url).font(.caption) }
                                Text("— \(skipped.reason)").font(.caption).foregroundColor(.secondary)
                            }
                        }
                    }
                }
            }

            // 3. AI explanation, collapsed behind a button.
            if response.ai_answer != nil || !blocks("ai_answer").isEmpty {
                section("AI explanation") {
                    if let ai = response.ai_answer {
                        Button(showAI ? "Hide AI explanation" : "Show AI explanation") { showAI.toggle() }
                        if showAI {
                            Text(ai.body).fixedSize(horizontal: false, vertical: true).textSelection(.enabled)
                        }
                    }
                    ForEach(blocks("ai_answer")) { notice($0) }
                }
            }

            if let located = response.located {
                Button("Open in reader") { openURL(SERVER_URL + located.reader_url) }
                    .buttonStyle(.borderedProminent)
            }
        }
    }

    func section<Content: View>(_ title: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title).font(.headline)
            content()
        }
    }

    func notice(_ blocked: Blocked) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(blocked.by == "no_sources" ? blocked.label : "Your class charter doesn't allow this (\(blocked.label)).")
                .font(.callout).foregroundColor(.orange)
            if let reason = blocked.reason, !reason.isEmpty {
                Text(reason).font(.caption).foregroundColor(.secondary)
            }
        }
    }

    func link(_ title: String, _ url: String) -> some View {
        Button(title) { openURL(url) }.buttonStyle(.link).multilineTextAlignment(.leading)
    }
}

func openURL(_ string: String) {
    guard let url = URL(string: string) else {
        print("Can't open bad URL: \(string)")
        return
    }
    NSWorkspace.shared.open(url)
}

// ---------- the floating panel ----------

final class AskPanel: NSPanel {
    override var canBecomeKey: Bool { true }
}

// ---------- app ----------

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    static var shared: AppDelegate!

    let model = PanelModel()
    var panel: AskPanel!
    var statusItem: NSStatusItem!
    var users: [User] = []
    var usersError: String?
    var hotKeyRef: EventHotKeyRef?

    func applicationDidFinishLaunching(_ notification: Notification) {
        AppDelegate.shared = self
        NSApp.setActivationPolicy(.accessory)  // no Dock icon, even when run outside the .app
        buildPanel()
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        statusItem.button?.image = NSImage(systemSymbolName: "text.quote", accessibilityDescription: "Dialectic")
        statusItem.button?.imagePosition = .imageLeading
        rebuildMenu()
        registerHotKey()
        Task { await loadUsers() }
        print("Dialectic running. Server: \(SERVER_URL). Hotkey: \(HOTKEY_LABEL).")
    }

    // dialectic://login?user=<id> (the web's "Use on Mac" link, SPEC §3.1)
    func application(_ application: NSApplication, open urls: [URL]) {
        for url in urls {
            let parts = URLComponents(url: url, resolvingAgainstBaseURL: false)
            guard url.scheme == "dialectic", url.host == "login",
                  let value = parts?.queryItems?.first(where: { $0.name == "user" })?.value, let id = Int(value) else {
                print("Ignoring unknown URL: \(url)")
                continue
            }
            setUser(id)
            Task {
                await loadUsers()
                let name = users.first(where: { $0.id == id })?.name ?? "user \(id)"
                showMessage("Signed in on this Mac as \(name).")
            }
        }
    }

    // ----- users & menu -----

    func loadUsers() async {
        do {
            let data = try await request("/api/users")
            users = try JSONDecoder().decode([User].self, from: data)
            usersError = nil
        } catch {
            print("GET /api/users failed: \(error)")
            usersError = error.localizedDescription
        }
        rebuildMenu()
    }

    var currentUserId: Int? { UserDefaults.standard.object(forKey: USER_DEFAULTS_KEY) as? Int }

    func setUser(_ id: Int) {
        UserDefaults.standard.set(id, forKey: USER_DEFAULTS_KEY)
        print("User set to \(id)")
        rebuildMenu()
    }

    func rebuildMenu() {
        guard statusItem != nil else { return }  // a dialectic:// URL can arrive before launch finishes
        let menu = NSMenu()
        let current = users.first(where: { $0.id == currentUserId })
        statusItem.button?.title = current.map { " \($0.name)" } ?? ""

        menu.addItem(withTitle: "Ask about selection (\(HOTKEY_LABEL))", action: #selector(hotkeyPressed), keyEquivalent: "")
        menu.addItem(.separator())
        menu.addItem(NSMenuItem(title: "I am:", action: nil, keyEquivalent: ""))
        if let usersError {
            let item = NSMenuItem(title: "Can't reach \(SERVER_URL): \(usersError)", action: nil, keyEquivalent: "")
            menu.addItem(item)
        }
        for user in users {
            let label = [user.name, user.role == "professor" ? "Professor" : user.cohort].compactMap { $0 }.joined(separator: " · ")
            let item = NSMenuItem(title: label, action: #selector(pickUser(_:)), keyEquivalent: "")
            item.tag = user.id
            item.state = user.id == currentUserId ? .on : .off
            item.indentationLevel = 1
            menu.addItem(item)
        }
        menu.addItem(withTitle: "Reload users", action: #selector(reloadUsers), keyEquivalent: "r")
        menu.addItem(.separator())
        menu.addItem(withTitle: "Quit Dialectic", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        for item in menu.items where item.action != #selector(NSApplication.terminate(_:)) { item.target = self }
        statusItem.menu = menu
    }

    @objc func pickUser(_ sender: NSMenuItem) { setUser(sender.tag) }
    @objc func reloadUsers() { Task { await loadUsers() } }

    // ----- hotkey -----

    func registerHotKey() {
        var spec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))
        let handlerStatus = InstallEventHandler(GetApplicationEventTarget(), { _, _, _ in
            DispatchQueue.main.async { AppDelegate.shared.hotkeyPressed() }
            return noErr
        }, 1, &spec, nil, nil)
        let hotKeyID = EventHotKeyID(signature: OSType(0x444C_4354), id: 1)  // "DLCT"
        let registerStatus = RegisterEventHotKey(HOTKEY_KEYCODE, HOTKEY_MODIFIERS, hotKeyID, GetApplicationEventTarget(), 0, &hotKeyRef)
        if handlerStatus != noErr || registerStatus != noErr {
            // Fail loudly: probably another app already owns ⌥⇧D.
            print("ERROR: couldn't register hotkey \(HOTKEY_LABEL) (handler \(handlerStatus), register \(registerStatus))")
            showMessage("Couldn't register the hotkey \(HOTKEY_LABEL). Another app may be using it.")
        }
    }

    @objc func hotkeyPressed() {
        Task { await captureAndShow() }
    }

    func captureAndShow() async {
        // Asks macOS to show the Accessibility prompt the first time; the human grants it.
        let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
        guard AXIsProcessTrustedWithOptions(options) else {
            showMessage(NO_ACCESSIBILITY_MESSAGE)
            return
        }
        if NSApp.isActive {
            // Our own panel is in front: hand focus back to the reading app so ⌘C copies from it.
            panel.orderOut(nil)
            NSApp.hide(nil)
            try? await Task.sleep(nanoseconds: 250_000_000)
        }
        let text = await copySelection()
        guard let text, !text.isEmpty else {
            showMessage(NO_SELECTION_MESSAGE)
            return
        }
        guard currentUserId != nil else {
            showMessage(NO_USER_MESSAGE)
            return
        }
        model.reset(quote: text)
        showPanel()
    }

    /// Simulate ⌘C in the front app, read the text, then put the old pasteboard back.
    func copySelection() async -> String? {
        let pasteboard = NSPasteboard.general
        let saved = (pasteboard.pasteboardItems ?? []).map { item -> NSPasteboardItem in
            let copy = NSPasteboardItem()
            for type in item.types {
                if let data = item.data(forType: type) { copy.setData(data, forType: type) }
            }
            return copy
        }
        let before = pasteboard.changeCount

        let source = CGEventSource(stateID: .privateState)  // private state: ignore the ⌥⇧ still held down
        let down = CGEvent(keyboardEventSource: source, virtualKey: CGKeyCode(kVK_ANSI_C), keyDown: true)
        let up = CGEvent(keyboardEventSource: source, virtualKey: CGKeyCode(kVK_ANSI_C), keyDown: false)
        down?.flags = .maskCommand
        up?.flags = .maskCommand
        down?.post(tap: .cghidEventTap)
        up?.post(tap: .cghidEventTap)

        let deadline = Date().addingTimeInterval(COPY_WAIT_SECONDS)
        while pasteboard.changeCount == before && Date() < deadline {
            try? await Task.sleep(nanoseconds: 20_000_000)
        }
        guard pasteboard.changeCount != before else {
            print("⌘C didn't change the pasteboard: nothing selected (or the app doesn't support copy)")
            return nil
        }
        let text = pasteboard.string(forType: .string)?.trimmingCharacters(in: .whitespacesAndNewlines)

        pasteboard.clearContents()
        if !saved.isEmpty { pasteboard.writeObjects(saved) }
        return text
    }

    // ----- panel -----

    func buildPanel() {
        panel = AskPanel(
            contentRect: NSRect(x: 0, y: 0, width: 480, height: 200),
            styleMask: [.titled, .closable, .resizable, .fullSizeContentView],
            backing: .buffered, defer: false
        )
        panel.title = "Dialectic"
        panel.titlebarAppearsTransparent = true
        panel.isFloatingPanel = true
        panel.level = .floating
        panel.hidesOnDeactivate = false
        panel.isReleasedWhenClosed = false
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        let hosting = NSHostingView(rootView: PanelView(model: model))
        hosting.sizingOptions = [.preferredContentSize]
        panel.contentView = hosting
    }

    func showMessage(_ text: String) {
        model.reset(quote: "")
        model.message = text
        showPanel()
    }

    func showPanel() {
        if !panel.isVisible { panel.center() }
        NSApp.activate(ignoringOtherApps: true)
        panel.makeKeyAndOrderFront(nil)
    }
}

@main
enum DialecticMain {
    static func main() {
        let app = NSApplication.shared
        let delegate = MainActor.assumeIsolated { AppDelegate() }
        app.delegate = delegate
        app.run()
    }
}
