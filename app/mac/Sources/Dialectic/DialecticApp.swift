// Dialectic Mac app (SPEC §3.9, design.md): read anywhere, and Dialectic sits on top of the page.
//   ⌥⇧D  ask about the selected text      (Panels.swift)
//   ⌥⇧N  write a note on the selected text (Panels.swift)
//   ⌥⇧H  show / hide classmates' highlights over the reading window (Overlay.swift)
// Menu-bar app; a normal app (menu bar, Dock icon) while the reader window is open. Talks to the same server as the web app; keeps no data of its own.
import AppKit
import Carbon.HIToolbox
import Combine
import SwiftUI

// ---------- tunables ----------

/// The server a fresh install starts on. CI builds set it to the dev copy (.github/workflows/mac-app.yml).
let DEFAULT_SERVER_URL = "http://localhost:8000"
/// The menu-bar "Server" submenu (DEPLOY.md lists the copies). The pick is remembered.
let SERVERS: [(name: String, url: String)] = [
    ("Dev: newest work", "https://dialectic-dev.yaggy.dev"),
    ("Demo: the judges' copy", "https://dialectic.yaggy.dev"),
    ("Sandbox: the public copy", "https://dialectic-sandbox.yaggy.dev"),
    ("This Mac (localhost:8000)", "http://localhost:8000"),
]
let SERVER_DEFAULTS_KEY = "serverURL"
/// The server in use: the one picked in the menu, else DEFAULT_SERVER_URL.
var SERVER_URL: String { UserDefaults.standard.string(forKey: SERVER_DEFAULTS_KEY) ?? DEFAULT_SERVER_URL }
/// "Report a problem…" opens this GitHub issue form, as the web app's button does (CLAUDE.md, Feedback issues).
let NEW_ISSUE_URL = "https://github.com/Ramen3ater1/tri-co_hack_2026/issues/new"
let HOTKEY_MODIFIERS = UInt32(optionKey | shiftKey)
let HOTKEY_ASK_KEY = UInt32(kVK_ANSI_D)
let HOTKEY_NOTE_KEY = UInt32(kVK_ANSI_N)
let HOTKEY_HIGHLIGHTS_KEY = UInt32(kVK_ANSI_H)
let HOTKEY_ASK_LABEL = "⌥⇧D"
let HOTKEY_NOTE_LABEL = "⌥⇧N"
let HOTKEY_HIGHLIGHTS_LABEL = "⌥⇧H"
/// How long to wait for the front app to put the selection on the pasteboard after ⌘C.
let COPY_WAIT_SECONDS = 0.6
/// /api/ask searches the web and calls the LLM, so it can take a while.
let ASK_TIMEOUT_SECONDS: TimeInterval = 120
let USER_DEFAULTS_KEY = "userId"

let NO_TEXT_IN_BOX_MESSAGE = "Couldn't read any text in that box."
let NO_USER_MESSAGE = "Pick who you are in the Dialectic menu-bar menu first."
let NO_ACCESSIBILITY_MESSAGE =
    "Dialectic needs Accessibility access to copy your selection. Turn it on in System Settings → Privacy & Security → Accessibility, then try again."
let NO_SCREEN_RECORDING_MESSAGE =
    "Dialectic needs Screen Recording access to find the page you're reading (the screenshot stays on this Mac). Turn it on in System Settings → Privacy & Security → Screen Recording, restart Dialectic, then press \(HOTKEY_HIGHLIGHTS_LABEL) again."

enum HotKey: UInt32 {
    case ask = 1, note = 2, highlights = 3
}

// ---------- app ----------

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    static var shared: AppDelegate!

    let panels = PanelController()
    let overlay = OverlayController()
    let reader = ReaderWindowController()
    var statusItem: NSStatusItem!
    var users: [User] = []
    var usersError: String?
    var hotKeyRefs: [EventHotKeyRef?] = []
    var watching: AnyCancellable?

    func applicationDidFinishLaunching(_ notification: Notification) {
        AppDelegate.shared = self
        NSApp.setActivationPolicy(.accessory)  // no Dock icon, even when run outside the .app
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        statusItem.button?.image = NSImage(systemSymbolName: "text.quote", accessibilityDescription: "Dialectic")
        statusItem.button?.imagePosition = .imageLeading
        installMainMenu()
        rebuildMenu()
        registerHotKeys()
        Task {
            await loadUsers()
            reader.show()  // the web reader, signed in as the menu's user
        }
        print("Dialectic running. Server: \(SERVER_URL). Hotkeys: \(HOTKEY_ASK_LABEL) ask, \(HOTKEY_NOTE_LABEL) note, \(HOTKEY_HIGHLIGHTS_LABEL) highlights.")
    }

    /// Clicking the Dock icon (shown while the reader window is open or minimised) brings the reader back.
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        reader.show()
        return false
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
            users = try await get("/api/users", as: [User].self)
            usersError = nil
        } catch {
            print("GET /api/users failed: \(error)")
            usersError = error.localizedDescription
        }
        rebuildMenu()
    }

    func setUser(_ id: Int) {
        UserDefaults.standard.set(id, forKey: USER_DEFAULTS_KEY)
        print("User set to \(id)")
        rebuildMenu()
        overlay.refreshNow()  // the lock depends on who you are
    }

    func rebuildMenu() {
        guard statusItem != nil else { return }  // a dialectic:// URL can arrive before launch finishes
        let current = users.first(where: { $0.id == currentUserId() })
        statusItem.button?.title = current.map { " \($0.name)" } ?? ""
        statusItem.menu = makeMenu(forMenuBar: false)
        // The same menu as the app's own "Dialectic" menu, for while the reader window is open.
        NSApp.mainMenu?.items.first?.submenu = makeMenu(forMenuBar: true)
        reader.signIn(as: current, users: users)  // reloads the reader only if the user changed
    }

    /// The Dialectic menu: the status-bar icon's menu, and (forMenuBar) the app menu with Close Window.
    func makeMenu(forMenuBar: Bool) -> NSMenu {
        let menu = NSMenu(title: "Dialectic")
        menu.addItem(withTitle: "Open Dialectic", action: #selector(openReader), keyEquivalent: "o")
        menu.addItem(.separator())
        menu.addItem(withTitle: "Ask about selection (\(HOTKEY_ASK_LABEL))", action: #selector(askHotKey), keyEquivalent: "")
        menu.addItem(withTitle: "Note on selection (\(HOTKEY_NOTE_LABEL))", action: #selector(noteHotKey), keyEquivalent: "")
        let highlights = menu.addItem(withTitle: "Show classmates' highlights (\(HOTKEY_HIGHLIGHTS_LABEL))", action: #selector(highlightsHotKey), keyEquivalent: "")
        highlights.state = overlay.isActive ? .on : .off
        menu.addItem(.separator())
        menu.addItem(NSMenuItem(title: "I am:", action: nil, keyEquivalent: ""))
        if let usersError {
            menu.addItem(NSMenuItem(title: "Can't reach \(SERVER_URL): \(usersError)", action: nil, keyEquivalent: ""))
        }
        for user in users {
            let label = [user.name, user.role == "professor" ? "Professor" : user.cohort].compactMap { $0 }.joined(separator: " · ")
            let item = NSMenuItem(title: label, action: #selector(pickUser(_:)), keyEquivalent: "")
            item.tag = user.id
            item.state = user.id == currentUserId() ? .on : .off
            item.indentationLevel = 1
            menu.addItem(item)
        }
        menu.addItem(withTitle: "Reload users", action: #selector(reloadUsers), keyEquivalent: "r")
        menu.addItem(.separator())
        let serverMenu = NSMenu()
        for (index, server) in SERVERS.enumerated() {
            let item = NSMenuItem(title: server.name, action: #selector(pickServer(_:)), keyEquivalent: "")
            item.tag = index
            item.state = server.url == SERVER_URL ? .on : .off
            item.target = self
            serverMenu.addItem(item)
        }
        if !SERVERS.contains(where: { $0.url == SERVER_URL }) {
            serverMenu.addItem(NSMenuItem(title: "Other: \(SERVER_URL)", action: nil, keyEquivalent: ""))
        }
        let serverItem = menu.addItem(withTitle: "Server", action: nil, keyEquivalent: "")
        menu.setSubmenu(serverMenu, for: serverItem)
        menu.addItem(withTitle: "Report a problem…", action: #selector(reportProblem), keyEquivalent: "")
        for item in menu.items { item.target = self }
        menu.addItem(.separator())
        if forMenuBar {
            menu.addItem(withTitle: "Close Window", action: #selector(NSWindow.performClose(_:)), keyEquivalent: "w")
        }
        menu.addItem(withTitle: "Quit Dialectic", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        return menu
    }

    @objc func pickUser(_ sender: NSMenuItem) { setUser(sender.tag) }
    @objc func openReader() { reader.show() }
    @objc func reloadUsers() { Task { await loadUsers() } }

    // ----- server & feedback -----

    @objc func pickServer(_ sender: NSMenuItem) {
        let server = SERVERS[sender.tag]
        UserDefaults.standard.set(server.url, forKey: SERVER_DEFAULTS_KEY)
        print("Server set to \(server.url)")
        // Same seeded users on every copy, so the picked user carries over.
        Task {
            await loadUsers()
            reader.open(path: "/")
            overlay.refreshNow()
        }
    }

    /// The web app's "Report a problem" form, prefilled with what the Mac knows.
    @objc func reportProblem() {
        let user = users.first(where: { $0.id == currentUserId() })
        let build = Bundle.main.url(forResource: "version", withExtension: "txt")
            .flatMap { try? String(contentsOf: $0, encoding: .utf8) }?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? "local build"
        let os = ProcessInfo.processInfo.operatingSystemVersion
        var parts = URLComponents(string: NEW_ISSUE_URL)!
        parts.queryItems = [
            URLQueryItem(name: "template", value: "feedback.yml"),
            URLQueryItem(name: "page", value: "Mac app · server \(SERVER_URL) · reader at \(reader.lastURL?.absoluteString ?? "not opened")"),
            URLQueryItem(name: "user", value: user.map { "\($0.name) (\($0.role))" } ?? "not picked"),
            URLQueryItem(name: "browser", value: "Dialectic for Mac, build \(build) · macOS \(os.majorVersion).\(os.minorVersion).\(os.patchVersion)"),
        ]
        NSWorkspace.shared.open(parts.url!)
    }
    @objc func askHotKey() { hotKeyPressed(.ask) }
    @objc func noteHotKey() { hotKeyPressed(.note) }
    @objc func highlightsHotKey() { hotKeyPressed(.highlights) }

    // ----- hotkeys -----

    func registerHotKeys() {
        var spec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))
        let handlerStatus = InstallEventHandler(GetApplicationEventTarget(), { _, event, _ in
            var hotKeyID = EventHotKeyID()
            GetEventParameter(event, EventParamName(kEventParamDirectObject), EventParamType(typeEventHotKeyID), nil,
                              MemoryLayout<EventHotKeyID>.size, nil, &hotKeyID)
            let id = hotKeyID.id
            DispatchQueue.main.async {
                MainActor.assumeIsolated {
                    if let key = HotKey(rawValue: id) { AppDelegate.shared.hotKeyPressed(key) }
                }
            }
            return noErr
        }, 1, &spec, nil, nil)
        if handlerStatus != noErr { print("ERROR: couldn't install the hotkey handler (\(handlerStatus))") }

        for (key, code, label) in [(HotKey.ask, HOTKEY_ASK_KEY, HOTKEY_ASK_LABEL), (.note, HOTKEY_NOTE_KEY, HOTKEY_NOTE_LABEL),
                                   (.highlights, HOTKEY_HIGHLIGHTS_KEY, HOTKEY_HIGHLIGHTS_LABEL)] {
            var ref: EventHotKeyRef?
            let id = EventHotKeyID(signature: OSType(0x444C_4354), id: key.rawValue)  // "DLCT"
            let status = RegisterEventHotKey(code, HOTKEY_MODIFIERS, id, GetApplicationEventTarget(), 0, &ref)
            if status != noErr {
                // Fail loudly: probably another app already owns this combination.
                print("ERROR: couldn't register hotkey \(label) (\(status))")
                showMessage("Couldn't register the hotkey \(label). Another app may be using it.")
            }
            hotKeyRefs.append(ref)
        }
    }

    func hotKeyPressed(_ key: HotKey) {
        switch key {
        case .highlights:
            overlay.toggle()
            rebuildMenu()
        case .ask, .note:
            Task { await captureAndOpen(key) }
        }
    }

    func captureAndOpen(_ key: HotKey) async {
        // Asks macOS to show the Accessibility prompt the first time; the human grants it.
        let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
        guard AXIsProcessTrustedWithOptions(options) else {
            showMessage(NO_ACCESSIBILITY_MESSAGE)
            return
        }
        if panels.panel.isKeyWindow || NSApp.isActive {
            // Our own panel has focus: give it back to the reading app so ⌘C copies from there.
            panels.panel.orderOut(nil)
            NSApp.hide(nil)
            try? await Task.sleep(nanoseconds: 250_000_000)
        }
        var quote = await copySelection()
        if quote?.isEmpty ?? true {
            // Nothing copied (common in Notability with scanned or annotated PDFs): drag a box instead.
            guard CGPreflightScreenCaptureAccess() else {
                CGRequestScreenCaptureAccess()  // macOS shows its prompt; the human grants it
                showMessage(NO_SCREEN_RECORDING_MESSAGE)
                return
            }
            do {
                guard let boxText = try await textFromDraggedBox() else { return }  // Esc: cancelled
                guard !boxText.isEmpty else {
                    showMessage(NO_TEXT_IN_BOX_MESSAGE)
                    return
                }
                quote = boxText
            } catch {
                print("Box capture failed: \(error)")
                showMessage("Couldn't capture that box: \(error.localizedDescription)")
                return
            }
        }
        guard let text = quote else { return }
        guard currentUserId() != nil else {
            showMessage(NO_USER_MESSAGE)
            return
        }
        let context = overlay.model.active ? overlay.model.context(for: text) : nil
        if key == .ask {
            let model = AskModel()
            model.quote = text
            model.context = context
            model.onSaved = { [weak self] in self?.overlay.refreshNow() }
            watch(model.objectWillChange)
            panels.show(AskView(model: model, users: users))
        } else {
            let model = NoteModel()
            model.quote = text
            model.context = context
            model.onSaved = { [weak self] in self?.overlay.refreshNow() }
            watch(model.objectWillChange)
            panels.show(NoteView(model: model))
        }
    }

    /// Re-fit the panel whenever its content changes (an answer arriving makes it taller).
    func watch(_ publisher: ObservableObjectPublisher) {
        watching = publisher.sink { [weak self] _ in
            DispatchQueue.main.async { self?.panels.refit() }
        }
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

    /// Crosshair → drag a box (`screencapture -i`) → Vision on this Mac → text. The image is deleted
    /// straight away; only the text leaves the Mac. nil if the person pressed Esc.
    func textFromDraggedBox() async throws -> String? {
        let path = NSTemporaryDirectory() + "dialectic-box-\(UUID().uuidString).png"
        defer { try? FileManager.default.removeItem(atPath: path) }
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/sbin/screencapture")
        process.arguments = ["-i", "-x", path]  // interactive box, no sound
        try await withCheckedThrowingContinuation { (done: CheckedContinuation<Void, Error>) in
            process.terminationHandler = { _ in done.resume() }
            do { try process.run() } catch { done.resume(throwing: error) }
        }
        guard FileManager.default.fileExists(atPath: path) else { return nil }
        guard let source = CGImageSourceCreateWithURL(URL(fileURLWithPath: path) as CFURL, nil),
              let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
            throw APIError(status: 0, message: "Couldn't open the captured image")
        }
        let text = try await Task.detached { try recognizedText(image) }.value
        print("Box: read \(text.count) characters with Vision")
        return text
    }

    func showMessage(_ text: String) {
        panels.show(MessageView(text: text), nearMouse: false)
    }
}

@main
enum DialecticMain {
    static func main() {
        setvbuf(stdout, nil, _IOLBF, 0)  // logs show up line by line even when piped to a file
        // `Dialectic --render <dir>`: draw every screen with stub data to PNGs and quit (RenderCheck.swift).
        if CommandLine.arguments.count >= 3, CommandLine.arguments[1] == "--render" {
            MainActor.assumeIsolated { renderCheck(into: CommandLine.arguments[2]) }
            return
        }
        let app = NSApplication.shared
        let delegate = MainActor.assumeIsolated { AppDelegate() }
        app.delegate = delegate
        app.run()
    }
}
