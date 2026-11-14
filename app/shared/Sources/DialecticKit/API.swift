// API shapes and HTTP calls (SPEC §6). Adapted from app/mac/Sources/Dialectic/API.swift; keep the two in step.
import Foundation

// ---------- settings (the app picks the server and the person) ----------

public let SERVERS: [(name: String, url: String)] = [
    ("Dev: newest work", "https://dialectic-dev.yaggy.dev"),
    ("Demo: the judges' copy", "https://dialectic.yaggy.dev"),
    ("Sandbox: the public copy", "https://dialectic-sandbox.yaggy.dev"),
]
public let DEFAULT_SERVER_URL = "https://dialectic-dev.yaggy.dev"
public let SERVER_DEFAULTS_KEY = "serverURL"
public let USER_DEFAULTS_KEY = "userId"
public let ASK_TIMEOUT_SECONDS: TimeInterval = 120

/// The server in use: the one picked in the app, else DEFAULT_SERVER_URL.
public var SERVER_URL: String { UserDefaults.standard.string(forKey: SERVER_DEFAULTS_KEY) ?? DEFAULT_SERVER_URL }
public func currentUserId() -> Int? { UserDefaults.standard.object(forKey: USER_DEFAULTS_KEY) as? Int }

/// Shown when nobody is picked yet; each app sets its own wording.
public var NO_USER_MESSAGE = "Pick who you are in Dialectic first."

// ---------- shapes ----------

public struct User: Codable, Identifiable, Hashable {
    public let id: Int
    public let name: String
    public let role: String?
    public let cohort: String?
}

public struct Rect: Codable, Equatable {
    public let x: Double
    public let y: Double
    public let w: Double
    public let h: Double
}

public struct Author: Decodable {
    public let id: Int
    public let name: String
    public let role: String?
    public let cohort: String?
}

/// One item of GET /readings/{id}/annotations. Locked ones are only `{id, page, rects, locked: true}` (SPEC §3.4).
public struct Annotation: Decodable, Identifiable {
    public let id: Int
    public let reading_id: Int?
    public let parent_id: Int?
    public let kind: String?
    public let page: Int?
    public let section: String?
    public let quote: String?
    public let body: String?
    public let created_at: String?
    public let author: Author?
    public let badge: String?
    public let locked: Bool?
    public let replies: [Annotation]?

    public var isLocked: Bool { locked == true }
}

public struct SavedNote: Decodable {
    public let id: Int
    public let page: Int?
    public let section: String?
    public let reader_url: String
}

struct AskRequest: Encodable {
    let quote: String
    let question: String
    let source_app: String?
}

struct NoteRequest: Encodable {
    let quote: String
    let body: String
    let share_with_future: Bool
    let source_app: String?
}

public struct AskResponse: Decodable {
    public let question_id: Int
    public let peer: [Peer]
    public let sources: [Source]
    public let ai_answer: AIAnswer?
    public let skipped_sources: [Skipped]
    public let blocked: [Blocked]
    public let located: Located?
}

public struct Peer: Decodable, Identifiable {
    public let annotation_id: Int?
    let id_: Int?
    public let author: String?
    public let cohort: String?
    public let page: Int?
    public let quote: String?
    public let body: String?
    public let locked: Bool?

    public var id: Int { annotation_id ?? id_ ?? -1 }
    public var isLocked: Bool { locked == true }

    enum CodingKeys: String, CodingKey {
        case annotation_id, author, cohort, page, quote, body, locked
        case id_ = "id"
    }
}

public struct Source: Decodable, Identifiable {
    public let source_id: Int?
    public let title: String
    public let url: String
    public let quote: String?
    public var id: String { url }
    public var domain: String { URL(string: url)?.host?.replacingOccurrences(of: "www.", with: "") ?? url }
}

public struct AIAnswer: Decodable {
    public let annotation_id: Int
    public let body: String
}

public struct Skipped: Decodable, Identifiable {
    public let url: String
    public let title: String?
    public let why: String
    public let reason: String
    public var id: String { url }
    /// not_permitted / not_covered are ruled out by the charter: show them, don't link them (SPEC §6).
    public var linkable: Bool { why == "unreachable" || why == "no_answer" }
}

public struct Blocked: Decodable, Identifiable {
    public let layer: String  // "sources_ai" | "ai_answer"
    public let by: String     // "toggle" | "rule" | "no_sources"
    public let label: String
    public let reason: String?
    public var id: String { layer + by + label }
}

public struct Located: Decodable {
    public let reading_id: Int
    public let reading_title: String
    public let page: Int
    public let section: String?
    public let reader_url: String
}

public struct APIError: LocalizedError {
    public let status: Int
    public let message: String
    public var errorDescription: String? { message }
    /// The server's "This passage isn't in a course reading." (a 404 from locating the quote).
    public var notInReading: Bool { status == 404 && message.contains("course reading") }
}

// ---------- HTTP ----------

public func request(_ path: String, method: String = "GET", body: Data? = nil, timeout: TimeInterval = 15) async throws -> Data {
    guard let url = URL(string: SERVER_URL + path) else { throw APIError(status: 0, message: "Bad URL: \(SERVER_URL + path)") }
    var req = URLRequest(url: url, timeoutInterval: timeout)
    req.httpMethod = method
    if let userId = currentUserId() {
        req.setValue(String(userId), forHTTPHeaderField: "X-User-Id")
    }
    if let body {
        req.httpBody = body
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
    }
    let (data, response) = try await URLSession.shared.data(for: req)
    let status = (response as? HTTPURLResponse)?.statusCode ?? 0
    if !(200..<300).contains(status) {
        // A 404 detail is written for people ("This passage isn't in a course reading."): show it as is.
        throw APIError(status: status, message: status == 404 ? errorDetail(data) : "Server said \(status): \(errorDetail(data))")
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

func decode<T: Decodable>(_ type: T.Type, _ data: Data, from what: String) throws -> T {
    do {
        return try JSONDecoder().decode(type, from: data)
    } catch {
        print("Couldn't decode \(what): \(error)\n\(String(data: data, encoding: .utf8) ?? "")")
        throw APIError(status: 0, message: "Couldn't read the server's answer to \(what): \(error)")
    }
}

public func get<T: Decodable>(_ path: String, as type: T.Type) async throws -> T {
    try decode(type, try await request(path), from: "GET \(path)")
}

public func post<T: Decodable, B: Encodable>(_ path: String, _ body: B, as type: T.Type, timeout: TimeInterval = 15) async throws -> T {
    let data = try await request(path, method: "POST", body: try JSONEncoder().encode(body), timeout: timeout)
    return try decode(type, data, from: "POST \(path)")
}

public func fetchUsers() async throws -> [User] { try await get("/api/users", as: [User].self) }

public func ask(quote: String, question: String, sourceApp: String? = nil) async throws -> AskResponse {
    try await post("/api/ask", AskRequest(quote: quote, question: question, source_app: sourceApp), as: AskResponse.self,
                   timeout: ASK_TIMEOUT_SECONDS)
}

public func saveNote(quote: String, body: String, share: Bool, sourceApp: String? = nil) async throws -> SavedNote {
    try await post("/api/note", NoteRequest(quote: quote, body: body, share_with_future: share, source_app: sourceApp), as: SavedNote.self)
}

public func annotations(readingId: Int) async throws -> [Annotation] {
    try await get("/api/readings/\(readingId)/annotations", as: [Annotation].self)
}

// ---------- small helpers ----------

/// "2026-11-14T04:33:12" (server local time) → "just now", "5 min ago" or "04:33".
public func relativeTime(_ iso: String?) -> String? {
    guard let iso else { return nil }
    let formatter = DateFormatter()
    formatter.locale = Locale(identifier: "en_US_POSIX")
    formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
    guard let date = formatter.date(from: String(iso.prefix(19))) else { return nil }
    let seconds = Date().timeIntervalSince(date)
    if seconds < 90 { return "just now" }
    if seconds < 3600 { return "\(Int(seconds / 60)) min ago" }
    formatter.dateFormat = "HH:mm"
    return formatter.string(from: date)
}

public let LOCKED_HINT = "Add a note or ask a question to see them."
public func lockedTitle(_ n: Int) -> String { "\(n) note\(n == 1 ? "" : "s") near here" }

public func contextTitle(_ verb: String, section: String?, page: Int?) -> String {
    let place = [section, page.map { "p. \($0)" }].compactMap { $0 }.joined(separator: ", ")
    return place.isEmpty ? verb : "\(verb) · \(place)"
}
