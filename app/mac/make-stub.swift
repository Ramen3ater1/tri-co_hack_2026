import PDFKit
// STUB: POST /api/locate pending Owen's OK. Writes the stub (page 2 lines + demo annotations) from the seed PDF:
//   swift make-stub.swift ../backend/seed/souls-of-black-folk-ch1.pdf > stub-locate-response.json
let doc = PDFDocument(url: URL(fileURLWithPath: CommandLine.arguments[1]))!
let page = doc.page(at: 1)!
let box = page.bounds(for: .mediaBox)
func frac(_ b: CGRect) -> [String: Double] {
    let r = ["x": (b.minX - box.minX) / box.width, "y": (box.maxY - b.maxY) / box.height, "w": b.width / box.width, "h": b.height / box.height]
    return r.mapValues { (Double($0) * 10000).rounded() / 10000 }
}
var lines: [[String: Any]] = []
for line in page.selection(for: box)!.selectionsByLine() {
    let t = (line.string ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
    if !t.isEmpty { lines.append(["text": t, "rect": frac(line.bounds(for: page))]) }
}
func rects(_ quote: String) -> [[String: Double]] {
    // The quote may run across a line break, so match its words with any whitespace between them.
    let pattern = quote.split(separator: " ").map { NSRegularExpression.escapedPattern(for: String($0)) }.joined(separator: "\\s+")
    let text = page.string!
    guard let match = try! NSRegularExpression(pattern: pattern).firstMatch(in: text, range: NSRange(text.startIndex..., in: text)),
          let sel = page.selection(for: match.range) else {
        fatalError("Quote not found on page 2: \(quote)")
    }
    return sel.selectionsByLine().map { frac($0.bounds(for: page)) }
}
func open(_ id: Int, _ quote: String, _ body: String, _ name: String, _ role: String, _ cohort: String, _ badge: Any) -> [String: Any] {
    ["id": id, "reading_id": 1, "parent_id": NSNull(), "kind": "note", "page": 2, "section": NSNull(), "via": "web",
     "quote": quote, "rects": rects(quote), "body": body, "cited_source_ids": NSNull(), "share_with_future": true,
     "created_at": "2026-11-14T01:00:00Z", "author": ["id": 1, "name": name, "role": role, "cohort": cohort],
     "badge": badge, "locked": false, "replies": []]
}
let annotations: [[String: Any]] = [
    open(3, "a sort of seventh son, born with a veil, and gifted with second-sight",
         "Folklore: a seventh son born with a caul (a 'veil') was said to have second sight. Du Bois turns the veil into a gift as well as a barrier.",
         "Prof. Rivera", "professor", "Fall 2026", "Professor"),
    open(2, "shut out from their world by a vast veil",
         "First appearance of the Veil, one of the book's governing images. Track where it returns in later chapters.",
         "Prof. Rivera", "professor", "Fall 2026", "Professor"),
    ["id": 4, "page": 2, "rects": rects("this double-consciousness, this sense of always looking at one’s self through the eyes of others"), "locked": true],
    ["id": 6, "page": 2, "rects": rects("two warring ideals in one dark body"), "locked": true],
]
let stub: [String: Any] = [
    "_comment": "STUB: POST /api/locate pending Owen's OK (design.md §3.2). Page 2 of the seed PDF, demo annotations as GET /readings/1/annotations returns them for Ben.",
    "located": ["reading_id": 1, "reading_title": "The Souls of Black Folk, Ch. 1: Of Our Spiritual Strivings", "page": 2,
                "section": "Of Our Spiritual Strivings", "reader_url": "/readings/1?page=2"],
    "lines": lines,
    "annotations": annotations,
]
print(String(data: try! JSONSerialization.data(withJSONObject: stub, options: [.prettyPrinted, .sortedKeys]), encoding: .utf8)!)
