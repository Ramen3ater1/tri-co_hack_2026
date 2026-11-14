// The web reader in a WKWebView, as on the Mac (ReaderWindow.swift): every reader feature is built once, on the web.
// Select text, then "Ask or note" (the bar button or the edit menu's "Ask Dialectic") opens the native panel.
import DialecticKit
import SwiftUI
import UIKit
import WebKit

/// localStorage keys the web app reads (app/frontend/src/api.js and colors.js).
let WEB_USER_KEY = "dialectic_user"
let WEB_USERS_KEY = "dialectic_users"
let NO_SELECTION_MESSAGE = "Select a passage in the reader first."
let MESSAGE_SECONDS = 2.5
let EDIT_MENU_TITLE = "Ask Dialectic"

@MainActor
final class ReaderController: NSObject, ObservableObject, WKNavigationDelegate, WKUIDelegate {
    let webView: ReaderWebView
    @Published var failure: String?
    @Published var message: String?
    @Published var selectionToAsk: String?
    private var signedInAs: Int?
    private var lastURL: URL?

    override init() {
        webView = ReaderWebView(frame: .zero, configuration: WKWebViewConfiguration())
        super.init()
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.allowsBackForwardNavigationGestures = true
        webView.onAskSelection = { [weak self] in Task { await self?.askAboutSelection() } }
    }

    func open(path: String) {
        guard let url = URL(string: SERVER_URL + path) else {
            failure = "Bad reader address: \(SERVER_URL + path)"
            return
        }
        load(url)
    }

    private func load(_ url: URL) {
        lastURL = url
        failure = nil
        webView.load(URLRequest(url: url))
    }

    func retry() { load(lastURL ?? URL(string: SERVER_URL + "/")!) }

    /// Sign the web app in as the picked person (SPEC §3.1 keeps the user in localStorage), then (re)load.
    func signIn(as user: User?, users: [User]) {
        guard user?.id != signedInAs || webView.url == nil else { return }
        signedInAs = user?.id
        let controller = webView.configuration.userContentController
        controller.removeAllUserScripts()
        if let user {
            let encoder = JSONEncoder()
            let userJSON = String(data: try! encoder.encode(user), encoding: .utf8)!
            let usersJSON = String(data: try! encoder.encode(users), encoding: .utf8)!
            let source = """
            localStorage.setItem(\(jsString(WEB_USER_KEY)), \(jsString(userJSON)));
            localStorage.setItem(\(jsString(WEB_USERS_KEY)), \(jsString(usersJSON)));
            """
            controller.addUserScript(WKUserScript(source: source, injectionTime: .atDocumentStart, forMainFrameOnly: true))
            print("Reader: signed in as \(user.name)")
        }
        if webView.url == nil { open(path: "/") } else { webView.reload() }
    }

    func askAboutSelection() async {
        let selected = (try? await webView.evaluateJavaScript("window.getSelection().toString()")) as? String ?? ""
        let quote = selected.trimmingCharacters(in: .whitespacesAndNewlines)
        if quote.isEmpty { flash(NO_SELECTION_MESSAGE) } else { selectionToAsk = quote }
    }

    func flash(_ text: String) {
        withAnimation { message = text }
        Task {
            try? await Task.sleep(for: .seconds(MESSAGE_SECONDS))
            withAnimation { if message == text { message = nil } }
        }
    }

    // ----- links and failures -----

    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction) async -> WKNavigationActionPolicy {
        // The log-in page's "Use on Mac" link (dialectic://login?user=…) signs this app in instead.
        if let url = action.request.url, url.scheme == "dialectic" {
            AppState.shared.handle(url)
            return .cancel
        }
        // Links to other sites (sources, text fragments) open in Safari.
        if let url = action.request.url, isExternal(url) {
            await UIApplication.shared.open(url)
            return .cancel
        }
        return .allow
    }

    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                 for action: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = action.request.url {
            if isExternal(url) { UIApplication.shared.open(url) } else { load(url) }
        }
        return nil
    }

    /// Picking a person on the web log-in page signs the native side (asks, notes, shortcut) in as them too.
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        Task {
            guard let json = try? await webView.evaluateJavaScript("localStorage.getItem('\(WEB_USER_KEY)')") as? String,
                  let user = try? JSONDecoder().decode(User.self, from: Data(json.utf8)),
                  user.id != AppState.shared.userId else { return }
            signedInAs = user.id   // already signed in on the web: no reload
            AppState.shared.userId = user.id
            UserDefaults.standard.set(user.id, forKey: USER_DEFAULTS_KEY)
        }
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { failed(error) }
    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) { failed(error) }

    private func failed(_ error: Error) {
        if (error as NSError).code == NSURLErrorCancelled { return }  // a newer load replaced this one
        print("Reader failed to load \(lastURL?.absoluteString ?? SERVER_URL): \(error)")
        failure = "Can't reach the Dialectic reader at \(SERVER_URL). Is the server running?\n\n\(error.localizedDescription)"
    }

    private func isExternal(_ url: URL) -> Bool {
        guard let scheme = url.scheme, scheme == "http" || scheme == "https" else { return false }
        let reader = URL(string: SERVER_URL)
        return url.host != reader?.host || url.port != reader?.port
    }
}

/// Adds "Ask Dialectic" to the edit menu that appears over selected text.
final class ReaderWebView: WKWebView {
    var onAskSelection: () -> Void = {}

    override func buildMenu(with builder: UIMenuBuilder) {
        super.buildMenu(with: builder)
        let ask = UIAction(title: EDIT_MENU_TITLE, image: UIImage(systemName: "text.quote")) { [weak self] _ in self?.onAskSelection() }
        builder.insertChild(UIMenu(title: "", options: .displayInline, children: [ask]), atStartOfMenu: .standardEdit)
    }
}

struct ReaderView: View {
    @ObservedObject var controller: ReaderController

    var body: some View {
        ZStack {
            WebViewHost(webView: controller.webView)
            if let failure = controller.failure {
                VStack(spacing: 14) {
                    Text(failure).font(.system(size: 15)).foregroundColor(Theme.ink).multilineTextAlignment(.center)
                        .textSelection(.enabled)
                    Button("Retry") { controller.retry() }.buttonStyle(PrimaryButtonStyle())
                }
                .padding(32)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Theme.ground)
            }
        }
    }
}

struct WebViewHost: UIViewRepresentable {
    let webView: WKWebView
    func makeUIView(context: Context) -> WKWebView { webView }
    func updateUIView(_ view: WKWebView, context: Context) {}
}

func jsString(_ text: String) -> String {
    String(data: try! JSONEncoder().encode(text), encoding: .utf8)!
}
