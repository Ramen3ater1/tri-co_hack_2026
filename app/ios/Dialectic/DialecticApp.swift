// Dialectic for iPad and iPhone (app/ios/README.md). The reader is the web app; the Ask | Note panel and
// the "Ask Dialectic Here" shortcut are native, from DialecticKit (app/shared), shared with the Mac app.
import DialecticKit
import SwiftUI

let SOURCE_APP = "Dialectic for iPad/iPhone"   // sent as source_app with every ask and note
let NO_USER_TEXT = "Pick who you are in Dialectic first (the person button, top left)."

@MainActor
final class AppState: ObservableObject {
    static let shared = AppState()

    @Published var users: [User] = []
    @Published var usersError: String?
    @Published var userId: Int? = currentUserId()
    @Published var server: String = SERVER_URL
    /// A reader path to open, set by "Open in reader", a shortcut's answer card or dialectic://open?path=…
    @Published var pendingPath: String?
    /// The Ask | Note panel, when it's open.
    @Published var composer: ComposerModel?

    var user: User? { users.first { $0.id == userId } }

    init() { NO_USER_MESSAGE = NO_USER_TEXT }

    func loadUsers() async {
        do {
            users = try await fetchUsers()
            usersError = nil
        } catch {
            print("GET /api/users failed: \(error)")
            usersError = "Can't reach \(SERVER_URL): \(error.localizedDescription)"
        }
    }

    func pick(_ user: User) {
        UserDefaults.standard.set(user.id, forKey: USER_DEFAULTS_KEY)
        userId = user.id
    }

    func pickServer(_ url: String) {
        UserDefaults.standard.set(url, forKey: SERVER_DEFAULTS_KEY)
        server = url
        users = []
        Task { await loadUsers() }
    }

    func openComposer(quote: String, mode: ComposerMode? = nil) {
        let text = quote.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        composer = ComposerModel(quote: text, sourceApp: SOURCE_APP, mode: mode)
    }

    /// dialectic://login?user=<id> (the web log-in page's link) and dialectic://open?path=/readings/2?page=3
    func handle(_ url: URL) {
        let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems ?? []
        switch url.host {
        case "login":
            if let id = items.first(where: { $0.name == "user" })?.value.flatMap(Int.init) {
                UserDefaults.standard.set(id, forKey: USER_DEFAULTS_KEY)
                userId = id
            }
        case "open":
            pendingPath = items.first(where: { $0.name == "path" })?.value
        default:
            print("Unknown link: \(url)")
        }
    }
}

@main
struct DialecticApp: App {
    @StateObject private var state = AppState.shared

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(state)
                .environment(\.colorScheme, .light)   // light mode only
                .preferredColorScheme(.light)
                .onOpenURL { state.handle($0) }
                .task { await state.loadUsers() }
        }
    }
}
