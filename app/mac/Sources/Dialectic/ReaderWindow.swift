// The Mac app's reader: the web app in a window (josue's pick, Sat 05:25). No native PDF reader:
// every reader feature is built once, on the web, and shows up here too.
import AppKit
import SwiftUI
import WebKit

/// The web reader. In production FastAPI serves the built frontend on the server's own port.
/// In development use Vite's address instead (`npm run dev` in app/frontend: http://localhost:5173).
var READER_URL: String { SERVER_URL }  // follows the menu's Server pick
let READER_SIZE = NSSize(width: 1280, height: 860)
/// localStorage keys the web app reads (app/frontend/src/api.js and colors.js).
let WEB_USER_KEY = "dialectic_user"     // the whole user object from GET /api/users
let WEB_USERS_KEY = "dialectic_users"   // the user list, for person colours

/// Open a reader path (e.g. located.reader_url) in the app's window, not the browser.
@MainActor
func openInReader(_ path: String) {
    AppDelegate.shared.reader.open(path: path)
}

@MainActor
final class ReaderModel: ObservableObject {
    @Published var failure: String?
}

struct ReaderFailureView: View {
    let message: String
    let retry: () -> Void
    var body: some View {
        VStack(spacing: 14) {
            Text(message).font(.system(size: 15)).foregroundColor(Theme.ink).multilineTextAlignment(.center)
                .textSelection(.enabled)
            Button("Retry", action: retry).buttonStyle(PrimaryButtonStyle())
        }
        .padding(32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Theme.ground)
        .environment(\.colorScheme, .light)
    }
}

@MainActor
final class ReaderWindowController: NSObject, WKNavigationDelegate, WKUIDelegate, NSWindowDelegate {
    let window: NSWindow
    let webView: WKWebView
    private let model = ReaderModel()
    private var failureView: NSView!
    private var signedInAs: Int?
    private(set) var lastURL: URL?  // read by Report a problem…

    override init() {
        window = NSWindow(contentRect: NSRect(origin: .zero, size: READER_SIZE),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "Dialectic"
        window.isReleasedWhenClosed = false
        window.setFrameAutosaveName("DialecticReader")
        webView = WKWebView(frame: .zero, configuration: WKWebViewConfiguration())
        super.init()
        window.delegate = self
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.autoresizingMask = [.width, .height]

        let container = NSView(frame: NSRect(origin: .zero, size: READER_SIZE))
        webView.frame = container.bounds
        container.addSubview(webView)
        failureView = NSHostingView(rootView: AnyView(EmptyView()))
        failureView.frame = container.bounds
        failureView.autoresizingMask = [.width, .height]
        failureView.isHidden = true
        container.addSubview(failureView)
        window.contentView = container
        if !window.setFrameUsingName("DialecticReader") { window.center() }
    }

    func show() {
        if webView.url == nil { open(path: "/") }
        bringToFront()
    }

    /// While the reader window is open Dialectic is a normal app: menu bar, Dock icon, ⌘Tab.
    /// Menu-bar-only (.accessory) apps never get the menu bar, even with a window in front.
    private func bringToFront() {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
        window.makeKeyAndOrderFront(nil)
    }

    /// Closing the reader window makes Dialectic menu-bar-only again (hotkeys and overlay keep working).
    func windowWillClose(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
    }

    func open(path: String) {
        guard let url = URL(string: READER_URL + path) else {
            showFailure("Bad reader address: \(READER_URL + path)")
            return
        }
        load(url)
        bringToFront()
    }

    private func load(_ url: URL) {
        lastURL = url
        failureView.isHidden = true
        webView.load(URLRequest(url: url))
    }

    /// Sign the web app in as the Mac menu's user (SPEC §3.1 stores the user in localStorage), then reload.
    func signIn(as user: User?, users: [User]) {
        guard user?.id != signedInAs else { return }
        signedInAs = user?.id
        let controller = webView.configuration.userContentController
        controller.removeAllUserScripts()
        if let user {
            let encoder = JSONEncoder()
            let userJSON = String(data: try! encoder.encode(WebUser(user)), encoding: .utf8)!
            let usersJSON = String(data: try! encoder.encode(users.map(WebUser.init)), encoding: .utf8)!
            let source = """
            localStorage.setItem(\(jsString(WEB_USER_KEY)), \(jsString(userJSON)));
            localStorage.setItem(\(jsString(WEB_USERS_KEY)), \(jsString(usersJSON)));
            """
            controller.addUserScript(WKUserScript(source: source, injectionTime: .atDocumentStart, forMainFrameOnly: true))
            print("Reader: signed in as \(user.name)")
        }
        if webView.url != nil { webView.reload() }
    }

    // ----- loading and links -----

    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                 decisionHandler: @escaping @MainActor (WKNavigationActionPolicy) -> Void) {
        // Links to other sites (sources, text fragments) open in the default browser.
        if let url = action.request.url, isExternal(url) {
            NSWorkspace.shared.open(url)
            decisionHandler(.cancel)
            return
        }
        decisionHandler(.allow)
    }

    /// target="_blank" links: external ones go to the browser, ours load in this window.
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                 for action: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = action.request.url {
            if isExternal(url) { NSWorkspace.shared.open(url) } else { load(url) }
        }
        return nil
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        failed(error)
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        failed(error)
    }

    func webView(_ webView: WKWebView, decidePolicyFor response: WKNavigationResponse,
                 decisionHandler: @escaping @MainActor (WKNavigationResponsePolicy) -> Void) {
        if response.isForMainFrame, let http = response.response as? HTTPURLResponse, http.statusCode >= 500 {
            print("Reader: \(http.statusCode) for \(http.url?.absoluteString ?? "?")")
        }
        decisionHandler(.allow)
    }

    private func failed(_ error: Error) {
        if (error as NSError).code == NSURLErrorCancelled { return }  // a newer load replaced this one
        print("Reader failed to load \(lastURL?.absoluteString ?? READER_URL): \(error)")
        showFailure("Can't reach the Dialectic reader at \(READER_URL). Is the server running?\n\n\(error.localizedDescription)")
    }

    private func showFailure(_ message: String) {
        (failureView as! NSHostingView<AnyView>).rootView = AnyView(ReaderFailureView(message: message, retry: { [weak self] in
            guard let self else { return }
            self.load(self.lastURL ?? URL(string: READER_URL + "/")!)
        }))
        failureView.isHidden = false
    }

    private func isExternal(_ url: URL) -> Bool {
        guard let scheme = url.scheme, scheme == "http" || scheme == "https" else { return false }
        let reader = URL(string: READER_URL)
        return url.host != reader?.host || url.port != reader?.port
    }
}

/// The user object exactly as the web app saves it at log-in.
struct WebUser: Encodable {
    let id: Int
    let name: String
    let role: String?
    let cohort: String?
    init(_ user: User) { id = user.id; name = user.name; role = user.role; cohort = user.cohort }
}

func jsString(_ text: String) -> String {
    String(data: try! JSONEncoder().encode(text), encoding: .utf8)!
}

/// The menu bar while the reader window is open, with an Edit menu so ⌘C / ⌘V / ⌘A work in its text boxes.
@MainActor
func installMainMenu() {
    let main = NSMenu()
    let appItem = NSMenuItem()
    appItem.submenu = NSMenu()  // filled by AppDelegate.rebuildMenu: the same items as the status-bar menu
    main.addItem(appItem)
    let editItem = NSMenuItem()
    let edit = NSMenu(title: "Edit")
    edit.addItem(withTitle: "Undo", action: Selector(("undo:")), keyEquivalent: "z")
    edit.addItem(withTitle: "Redo", action: Selector(("redo:")), keyEquivalent: "Z")
    edit.addItem(.separator())
    edit.addItem(withTitle: "Cut", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
    edit.addItem(withTitle: "Copy", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
    edit.addItem(withTitle: "Paste", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
    edit.addItem(withTitle: "Select All", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
    editItem.submenu = edit
    main.addItem(editItem)
    NSApp.mainMenu = main
}
