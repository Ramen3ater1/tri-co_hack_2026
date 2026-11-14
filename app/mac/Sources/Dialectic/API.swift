// API shapes and HTTP calls (SPEC §6; checked against app/backend/main.py and ask.py).
import Foundation

// ---------- shapes ----------

struct User: Decodable {
    let id: Int
    let name: String
    let role: String?
    let cohort: String?
}

struct Rect: Codable, Equatable {
    let x: Double
    let y: Double
    let w: Double
    let h: Double
}

struct Author: Decodable {
    let id: Int
    let name: String
    let role: String?
    let cohort: String?
}

/// One item of GET /readings/{id}/annotations. Locked ones are only `{id, page, rects, locked: true}` (SPEC §3.4).
struct Annotation: Decodable, Identifiable {
    let id: Int
    let reading_id: Int?
    let parent_id: Int?
    let kind: String?
    let page: Int?
    let section: String?
    let via: String?
    let quote: String?
    let rects: [Rect]?
    let body: String?
    let created_at: String?
    let author: Author?
    let badge: String?
    let locked: Bool?
    let replies: [Annotation]?
    let group: Int?          // locked only: notes near each other share a group (SPEC §6)
    let group_notes: Int?    // locked only: how many notes the group's lock card counts

    var isLocked: Bool { locked == true }
}

/// A saved note from POST /api/note: an annotation plus where to open it.
struct SavedNote: Decodable {
    let id: Int
    let page: Int?
    let section: String?
    let reader_url: String
}

struct AskRequest: Encodable {
    let quote: String
    let question: String
}

struct NoteRequest: Encodable {
    let quote: String
    let body: String
    let share_with_future: Bool
}

struct ReplyRequest: Encodable {
    let body: String
    let parent_id: Int
}

struct LocateRequest: Encodable {
    let text: String
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

/// A peer annotation in an /ask answer, or a locked one (no author or text).
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
    var domain: String { URL(string: url)?.host?.replacingOccurrences(of: "www.", with: "") ?? url }
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

/// PROPOSED POST /api/locate response (design.md §3.2). `annotations` is only in the stub file.
struct PageLine: Decodable {
    let text: String
    let rect: Rect
}

struct LocateResponse: Decodable {
    let located: Located
    let lines: [PageLine]
    let annotations: [Annotation]?
}

struct APIError: LocalizedError {
    let status: Int
    let message: String
    var errorDescription: String? { message }
}

// ---------- HTTP ----------

func currentUserId() -> Int? { UserDefaults.standard.object(forKey: USER_DEFAULTS_KEY) as? Int }

func request(_ path: String, method: String = "GET", body: Data? = nil, timeout: TimeInterval = 15) async throws -> Data {
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
        throw APIError(status: status, message: "Server said \(status): \(errorDetail(data))")
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

func get<T: Decodable>(_ path: String, as type: T.Type) async throws -> T {
    try decode(type, try await request(path), from: "GET \(path)")
}

func post<T: Decodable, B: Encodable>(_ path: String, _ body: B, as type: T.Type, timeout: TimeInterval = 15) async throws -> T {
    let data = try await request(path, method: "POST", body: try JSONEncoder().encode(body), timeout: timeout)
    return try decode(type, data, from: "POST \(path)")
}

/// POST /api/locate, or the stub file while the route doesn't exist.
/// Returns (response, isStub).
func locate(text: String) async throws -> (LocateResponse, Bool) {
    do {
        return (try await post("/api/locate", LocateRequest(text: text), as: LocateResponse.self), false)
    } catch let error as APIError where error.status == 405 || (error.status == 404 && !error.message.contains("course reading")) {
        // STUB: POST /api/locate pending Owen's OK (design.md §3.2). Remove this branch once the route exists.
        print("POST /api/locate isn't on the server (\(error.status)): using stub-locate-response.json")
        return (try loadStub(), true)
    }
}

func loadStub() throws -> LocateResponse {
    guard let url = Bundle.main.url(forResource: "stub-locate-response", withExtension: "json") else {
        throw APIError(status: 0, message: "stub-locate-response.json isn't in the app bundle: build with build.sh")
    }
    return try decode(LocateResponse.self, try Data(contentsOf: url), from: "the stub locate file")
}

// ---------- text matching (same idea as locate.py: letters and digits only) ----------

func squash(_ text: String) -> String {
    String(text.decomposedStringWithCompatibilityMapping.lowercased().unicodeScalars
        .filter { CharacterSet.alphanumerics.contains($0) && !CharacterSet.nonBaseCharacters.contains($0) }
        .map(Character.init))
}

/// "2026-11-14T04:33:12" (server local time) → "just now", "5 min ago" or "04:33".
func relativeTime(_ iso: String?) -> String? {
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
