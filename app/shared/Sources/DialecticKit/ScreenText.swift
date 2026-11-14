// Reading a passage off a screenshot (the iPad/iPhone "Ask Dialectic Here" shortcut). Vision runs on the device;
// only the recognised text is sent. Same approach as the Mac's drag-a-box fallback (Overlay.swift).
import CoreGraphics
import Foundation
import Vision

public let MIN_QUOTE_LINE_CHARS = 25   // shorter lines are headers, page numbers, buttons
public let MAX_LOCATE_TRIES = 6        // each try is one POST; the shortcut has to answer in seconds

public struct ScreenLine {
    public let text: String
    public let rect: CGRect   // normalised 0–1, top-left origin
}

/// The text lines in an image, top to bottom.
public func recognizeLines(_ image: CGImage) throws -> [ScreenLine] {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false
    try VNImageRequestHandler(cgImage: image).perform([request])
    let lines: [ScreenLine] = (request.results ?? []).compactMap { observation in
        guard let text = observation.topCandidates(1).first?.string else { return nil }
        let box = observation.boundingBox  // normalised, bottom-left origin
        return ScreenLine(text: text, rect: CGRect(x: box.minX, y: 1 - box.maxY, width: box.width, height: box.height))
    }
    return lines.sorted { abs($0.rect.midY - $1.rect.midY) < $0.rect.height / 2 ? $0.rect.minX < $1.rect.minX : $0.rect.midY < $1.rect.midY }
}

/// Quotes to try, best first: pairs of body-text lines nearest the middle of the screen (what you're reading),
/// then single lines, longest first. The server says which one is in a course reading.
public func candidateQuotes(_ lines: [ScreenLine]) -> [String] {
    let body = lines.filter { $0.text.count >= MIN_QUOTE_LINE_CHARS }
    guard !body.isEmpty else { return [] }
    var out: [String] = []
    let byCentre = body.indices.sorted { abs(body[$0].rect.midY - 0.5) < abs(body[$1].rect.midY - 0.5) }
    for i in byCentre.prefix(3) where i + 1 < body.count {
        out.append(joinLines(body[i].text, body[i + 1].text))
    }
    for line in body.sorted(by: { $0.text.count > $1.text.count }) {
        out.append(line.text)
    }
    var seen = Set<String>()
    return out.filter { seen.insert($0).inserted }.prefix(MAX_LOCATE_TRIES).map { $0 }
}

/// "peremp-" + "torily" → "peremptorily"; otherwise a space.
func joinLines(_ a: String, _ b: String) -> String {
    a.hasSuffix("-") ? String(a.dropLast()) + b : a + " " + b
}

public struct NotInReading: LocalizedError {
    public let tried: Int
    public var errorDescription: String? {
        tried == 0 ? "Couldn't read any text on the screen."
                   : "This passage isn't in a course reading. (Tried \(tried) line\(tried == 1 ? "" : "s") from your screen.)"
    }
}

/// Runs `attempt` with each candidate quote until one is in a course reading. Returns that quote and its result.
public func firstInReading<T>(_ quotes: [String], _ attempt: (String) async throws -> T) async throws -> (String, T) {
    for quote in quotes {
        do {
            return (quote, try await attempt(quote))
        } catch let error as APIError where error.notInReading {
            continue
        }
    }
    throw NotInReading(tried: quotes.count)
}
