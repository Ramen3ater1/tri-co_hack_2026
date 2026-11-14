// Seminar table (ideas/04-seminar-table.md): a round table of the people whose notes you can see, the reading's
// pages knotted in the middle, and each open note on the spoke between its author's seat and its page.
// Read-only. The engagement lock stays the server's: locked notes arrive with no author, so they're drawn only as a
// dashed count on their page, never joined to a seat. AI has no seat; its answers hang off questions and are hidden
// until you switch them on.
import DialecticKit
import SwiftUI

let SEMINAR_MAX_SEATS = 10            // more people than this fold into a "+N" note under the table
let SEMINAR_SHOW_AI_DEFAULT = false   // AI comes last (charter rule 1)
let SEMINAR_SPOKE_START = 0.40        // how far from the page toward the seat a note sits (0 = page, 1 = seat)
let SEMINAR_SPOKE_STEP = 0.11         // extra distance for each further note by the same person on the same page

// ---------- data ----------

struct CourseReading: Decodable, Identifiable {
    let id: Int
    let title: String
    let status: String?
}

struct CourseResponse: Decodable { let readings: [CourseReading] }

/// The lock fields of GET /readings/{id}/annotations that `Annotation` doesn't carry (SPEC §6).
struct LockInfo: Decodable {
    let id: Int
    let page: Int?
    let locked: Bool?
    let group: Int?
    let group_notes: Int?
}

struct Seat: Identifiable {
    let id: Int
    let name: String
    let role: Role
    let badge: String?
}

enum SeminarPick: Identifiable {
    case note(Annotation)
    case seat(Seat)
    case locked(page: Int, count: Int)

    var id: String {
        switch self {
        case .note(let a): return "n\(a.id)"
        case .seat(let s): return "s\(s.id)"
        case .locked(let page, _): return "l\(page)"
        }
    }
}

@MainActor
final class SeminarModel: ObservableObject {
    @Published var readings: [CourseReading] = []
    @Published var readingId: Int?
    @Published var notes: [Annotation] = []        // open top-level notes and questions
    @Published var lockedByPage: [Int: Int] = [:]  // page → how many locked notes
    @Published var error: String?

    func load() async {
        do {
            let course = try await get("/api/course", as: CourseResponse.self)
            readings = course.readings.filter { ($0.status ?? "ready") == "ready" }
            if readingId == nil { readingId = readings.first?.id }
            guard let readingId else { notes = []; lockedByPage = [:]; return }
            let data = try await request("/api/readings/\(readingId)/annotations")
            let all = try JSONDecoder().decode([Annotation].self, from: data)
            let locks = try JSONDecoder().decode([LockInfo].self, from: data)
            notes = all.filter { !$0.isLocked && $0.parent_id == nil && $0.author?.role != "ai" && $0.page != nil }
            // One lock card per group (SPEC §3.3); add the groups up per page.
            var groups: [Int: (page: Int, count: Int)] = [:]
            for lock in locks where lock.locked == true {
                groups[lock.group ?? lock.id] = (lock.page ?? 1, lock.group_notes ?? 1)
            }
            lockedByPage = groups.values.reduce(into: [:]) { $0[$1.page, default: 0] += $1.count }
            error = nil
        } catch {
            print("Seminar load failed: \(error)")
            self.error = error.localizedDescription
        }
    }

    var pages: [Int] { Array(Set(notes.compactMap(\.page) + lockedByPage.keys)).sorted() }

    /// Everyone you can see something from: professor first, then you, then classmates by how much they wrote.
    func seats(me: User?) -> (shown: [Seat], hidden: Int) {
        var counts: [Int: (author: Author, n: Int)] = [:]
        for note in notes {
            for a in [note] + (note.replies ?? []) {
                guard let author = a.author, author.role != "ai" else { continue }
                counts[author.id] = (author, (counts[author.id]?.n ?? 0) + 1)
            }
        }
        var people = counts.values.map { entry in
            Seat(id: entry.author.id, name: entry.author.name, role: Role.of(authorId: entry.author.id, role: entry.author.role),
                 badge: entry.author.role == "professor" ? "Professor" : entry.author.cohort)
        }
        if let me, counts[me.id] == nil { people.append(Seat(id: me.id, name: me.name, role: .you, badge: "You")) }
        func rank(_ s: Seat) -> Int { s.role == .professor ? 0 : s.role == .you ? 1 : 2 }
        people.sort { (rank($0), -(counts[$0.id]?.n ?? 0), $0.name) < (rank($1), -(counts[$1.id]?.n ?? 0), $1.name) }
        return (Array(people.prefix(SEMINAR_MAX_SEATS)), max(0, people.count - SEMINAR_MAX_SEATS))
    }
}

// ---------- view ----------

struct SeminarView: View {
    @EnvironmentObject var state: AppState
    @Environment(\.dismiss) private var dismiss
    @StateObject private var model = SeminarModel()
    @State private var pick: SeminarPick?
    @State private var showAI = SEMINAR_SHOW_AI_DEFAULT

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider().overlay(Theme.hairline)
            if state.userId == nil {
                Text("Choose who you are first (top-left menu), then open the table.")
                    .font(.system(size: 14)).foregroundColor(.secondary).padding(20)
            } else if let error = model.error {
                Text(error).font(.system(size: 14)).foregroundColor(.red).padding(20).textSelection(.enabled)
            }
            GeometryReader { geo in table(in: geo.size) }
                .padding(12)
            legend
        }
        .background(Theme.ground)
        .task { if state.userId != nil { await model.load() } }  // the API needs x-user-id
        .sheet(item: $pick) { pick in
            ScrollView { detail(pick).padding(20) }
                .background(Theme.panel)
                .presentationDetents([.medium, .large])
                .presentationDragIndicator(.visible)
        }
    }

    var header: some View {
        HStack(spacing: 10) {
            VStack(alignment: .leading, spacing: 2) {
                Text("The table").font(Theme.serif(20))
                Text(subtitle).font(.system(size: 12)).foregroundColor(Theme.muted)
            }
            Spacer()
            if model.readings.count > 1 {
                Menu {
                    ForEach(model.readings) { reading in
                        Button(reading.title) { model.readingId = reading.id; Task { await model.load() } }
                    }
                } label: { Label("Reading", systemImage: "book").font(.system(size: 14)) }
            }
            Toggle(isOn: $showAI) { Text("AI context").font(.system(size: 13)) }
                .toggleStyle(.button).tint(Theme.muted)
            Button { Task { await model.load() } } label: {
                Image(systemName: "arrow.clockwise").frame(width: Theme.minHit, height: Theme.minHit)
            }.accessibilityLabel("Refresh")
            Button("Done") { dismiss() }.font(.system(size: 15, weight: .medium)).foregroundColor(Theme.you)
                .frame(minHeight: Theme.minHit)
        }
        .padding(.horizontal, 16)
        .background(Theme.panel)
    }

    var subtitle: String {
        let title = model.readings.first { $0.id == model.readingId }?.title ?? "No reading yet"
        let waiting = model.lockedByPage.values.reduce(0, +)
        return waiting > 0 ? "\(title) · \(waiting) notes waiting for your note" : title
    }

    var legend: some View {
        HStack(spacing: 14) {
            legendItem(Circle().fill(Theme.classmate), "note")
            legendItem(Circle().stroke(Theme.classmate, lineWidth: 2), "question")
            legendItem(Circle().stroke(Theme.classmate, style: StrokeStyle(lineWidth: 1.5, dash: [3, 2])), "locked: write near it to open")
        }
        .font(.system(size: 12)).foregroundColor(Theme.muted)
        .padding(.bottom, 12)
    }

    func legendItem<S: View>(_ shape: S, _ text: String) -> some View {
        HStack(spacing: 5) { shape.frame(width: 10, height: 10); Text(text) }
    }

    // ---------- the table ----------

    @ViewBuilder
    func table(in size: CGSize) -> some View {
        let side = min(size.width, size.height)
        let center = CGPoint(x: size.width / 2, y: size.height / 2)
        let seatRadius = side * 0.42
        let knotRadius = side * 0.13
        let seating = model.seats(me: state.user)
        let seats = seating.shown
        let hidden = seating.hidden
        let pages = model.pages
        let seatPos = Dictionary(uniqueKeysWithValues: seats.enumerated().map { i, seat in
            (seat.id, point(center, seatRadius, angle: -90 + 360 * Double(i) / Double(max(seats.count, 1))))
        })
        let pagePos = Dictionary(uniqueKeysWithValues: pages.enumerated().map { i, page in
            (page, point(center, pages.count == 1 ? 0 : knotRadius, angle: -90 + 360 * Double(i) / Double(max(pages.count, 1))))
        })
        let placed = placeNotes(seatPos: seatPos, pagePos: pagePos, center: center)

        ZStack {
            Circle().fill(Color(hex: 0xEAE7DE)).frame(width: side * 0.78, height: side * 0.78).position(center)
            Circle().fill(Theme.ground).overlay(Circle().stroke(Theme.hairline, lineWidth: 1))
                .frame(width: knotRadius * 2 + 70, height: knotRadius * 2 + 70).position(center)

            // Lines: seat → note → page, reply → its author's seat.
            Path { path in
                for p in seatPos.values { path.move(to: p); path.addLine(to: center) }
            }.stroke(Theme.hairline.opacity(0.35), lineWidth: 1)
            ForEach(placed, id: \.note.id) { item in
                Path { path in
                    if let s = seatPos[item.note.author?.id ?? -1] { path.move(to: s); path.addLine(to: item.at) }
                    if let p = pagePos[item.note.page ?? -1] { path.move(to: item.at); path.addLine(to: p) }
                    for reply in visibleReplies(item.note) {
                        if let s = seatPos[reply.author?.id ?? -1] { path.move(to: item.at); path.addLine(to: s) }
                    }
                }
                .stroke(role(of: item.note).color.opacity(0.35), lineWidth: 1.2)
            }
            ForEach(Array(model.lockedByPage.keys.sorted()), id: \.self) { page in
                if let p = pagePos[page] {
                    let at = lockSpot(page: p, center: center, knotRadius: knotRadius)
                    Path { path in path.move(to: p); path.addLine(to: at) }
                        .stroke(Theme.classmate.opacity(0.6), style: StrokeStyle(lineWidth: 1.2, dash: [4, 4]))
                }
            }

            // Pages in the knot
            ForEach(pages, id: \.self) { page in
                Text("p. \(page)").font(Theme.serif(13)).italic()
                    .padding(.horizontal, 10).padding(.vertical, 5)
                    .background(Capsule().fill(Theme.panel))
                    .overlay(Capsule().stroke(Theme.hairline, lineWidth: 1))
                    .position(pagePos[page] ?? center)
            }

            // Locked clusters: a count and a page, nothing else.
            ForEach(Array(model.lockedByPage.keys.sorted()), id: \.self) { page in
                if let p = pagePos[page], let count = model.lockedByPage[page] {
                    Button { pick = .locked(page: page, count: count) } label: {
                        Text("\(count)").font(.system(size: 13, weight: .semibold)).foregroundColor(Theme.classmate)
                            .frame(width: 34, height: 34)
                            .background(Circle().fill(Theme.panel))
                            .overlay(Circle().stroke(Theme.classmate, style: StrokeStyle(lineWidth: 1.5, dash: [4, 3])))
                            .frame(width: Theme.minHit, height: Theme.minHit)
                    }
                    .position(lockSpot(page: p, center: center, knotRadius: knotRadius))
                    .accessibilityLabel(lockedTitle(count))
                }
            }

            // Notes and questions
            ForEach(placed, id: \.note.id) { item in
                Button { pick = .note(item.note) } label: { noteDot(item.note).frame(width: Theme.minHit, height: Theme.minHit) }
                    .position(item.at)
                    .accessibilityLabel("\(item.note.kind ?? "note") by \(item.note.author?.name ?? "someone"), page \(item.note.page ?? 0)")
            }

            // Seats
            ForEach(seats) { seat in
                Button { pick = .seat(seat) } label: {
                    VStack(spacing: 3) {
                        Text(String(seat.name.prefix(1))).font(.system(size: 16, weight: .semibold)).foregroundColor(.white)
                            .frame(width: 40, height: 40)
                            .background(Circle().fill(seat.role.color))
                            .overlay(Circle().stroke(Theme.panel, lineWidth: 3))
                        Text(seat.name).font(.system(size: 12)).foregroundColor(Theme.ink).lineLimit(1)
                        if let badge = seat.badge { Text(badge).font(.system(size: 10)).foregroundColor(Theme.muted).lineLimit(1) }
                    }
                    .frame(width: 96)
                }
                .position(seatPos[seat.id] ?? center)
            }

            if hidden > 0 {
                Text("+\(hidden) more at the table").font(.system(size: 12)).foregroundColor(Theme.muted)
                    .position(x: center.x, y: center.y + side * 0.5 - 8)
            }
            if pages.isEmpty && model.error == nil {
                Text("No notes you can see on this reading yet.").font(.system(size: 14)).foregroundColor(Theme.muted)
                    .position(center)
            }
        }
    }

    struct Placed { let note: Annotation; let at: CGPoint }

    /// Each note on the spoke from its page toward its author's seat; repeats by the same person step further out.
    func placeNotes(seatPos: [Int: CGPoint], pagePos: [Int: CGPoint], center: CGPoint) -> [Placed] {
        var seen: [String: Int] = [:]
        return model.notes.compactMap { note in
            guard let page = note.page, let p = pagePos[page] else { return nil }
            let key = "\(page)-\(note.author?.id ?? -1)"
            let k = seen[key, default: 0]
            seen[key] = k + 1
            // TODO(edge): an author folded into "+N" has no seat; their note sits outward from its page instead.
            let target = seatPos[note.author?.id ?? -1] ?? CGPoint(x: p.x + (p.x - center.x) * 3, y: p.y + (p.y - center.y) * 3)
            let t = SEMINAR_SPOKE_START + SEMINAR_SPOKE_STEP * Double(k)
            return Placed(note: note, at: CGPoint(x: p.x + (target.x - p.x) * t, y: p.y + (target.y - p.y) * t))
        }
    }

    func lockSpot(page: CGPoint, center: CGPoint, knotRadius: CGFloat) -> CGPoint {
        // Outward from the page and turned a little, so it never sits on a spoke toward anyone's seat.
        let angle = atan2(page.y - center.y, page.x - center.x) + 0.45
        let r = (hypot(page.x - center.x, page.y - center.y)) + 60
        return CGPoint(x: center.x + r * cos(angle), y: center.y + r * sin(angle))
    }

    func point(_ c: CGPoint, _ r: CGFloat, angle degrees: Double) -> CGPoint {
        let a = degrees * .pi / 180
        return CGPoint(x: c.x + r * cos(a), y: c.y + r * sin(a))
    }

    func role(of a: Annotation) -> Role { Role.of(authorId: a.author?.id, role: a.author?.role) }

    func visibleReplies(_ a: Annotation) -> [Annotation] {
        (a.replies ?? []).filter { showAI || $0.author?.role != "ai" }
    }

    @ViewBuilder
    func noteDot(_ a: Annotation) -> some View {
        let color = role(of: a).color
        if a.kind == "question" {
            Text("?").font(.system(size: 11, weight: .bold)).foregroundColor(color)
                .frame(width: 20, height: 20)
                .background(Circle().fill(Theme.panel))
                .overlay(Circle().stroke(color, lineWidth: 2.5))
        } else {
            Circle().fill(color).frame(width: 18, height: 18)
        }
    }

    // ---------- the sheet ----------

    @ViewBuilder
    func detail(_ pick: SeminarPick) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            switch pick {
            case .note(let a):
                thread(a)
                openButton(page: a.page, annotation: a.id)
            case .seat(let seat):
                Text(seat.name).font(Theme.serif(20))
                if let badge = seat.badge { Badge(text: badge, color: seat.role.color) }
                SectionLabel("Annotations")
                if notes(by: seat).isEmpty { Text("Only replies from them are open to you.").font(.system(size: 14)).foregroundColor(Theme.muted) }
                ForEach(notes(by: seat)) { a in Button { self.pick = .note(a) } label: { card(a) }.buttonStyle(.plain) }
                Text("Notes you haven't unlocked aren't shown or counted here, so a seat never tells you who wrote a locked note.")
                    .font(.system(size: 12)).foregroundColor(Theme.muted)
            case .locked(let page, let count):
                RoleCard(role: .classmate, dashed: true) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(lockedTitle(count)).font(.system(size: 15, weight: .semibold)).foregroundColor(Theme.classmate)
                        Text(LOCKED_HINT).font(.system(size: 14))
                    }
                }
                openButton(page: page, annotation: nil, title: "Write a note on p. \(page)")
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    func notes(by seat: Seat) -> [Annotation] { model.notes.filter { $0.author?.id == seat.id } }

    func thread(_ a: Annotation) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            card(a)
            let replies = visibleReplies(a)
            if !replies.isEmpty {
                SectionLabel("\(replies.count) repl\(replies.count == 1 ? "y" : "ies")")
                ForEach(replies) { r in card(r).padding(.leading, 14) }
            }
            if !showAI && (a.replies ?? []).contains(where: { $0.author?.role == "ai" }) {
                Button("Still stuck? Show the AI explanation") { showAI = true }.buttonStyle(QuietButtonStyle())
            }
        }
    }

    func card(_ a: Annotation) -> some View {
        let r = role(of: a)
        return RoleCard(role: r) {
            VStack(alignment: .leading, spacing: 6) {
                AuthorLine(name: a.author?.name ?? "Someone", role: r, badge: a.badge,
                           detail: [a.page.map { "p. \($0)" }, a.kind == "question" ? "question" : nil].compactMap { $0 }.joined(separator: " · "))
                if let quote = a.quote, !quote.isEmpty { QuoteChip(text: quote, lineLimit: 2) }
                Text(a.body ?? "").font(.system(size: 14)).fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    func openButton(page: Int?, annotation: Int?, title: String = "Open in reader") -> some View {
        Button(title) {
            guard let readingId = model.readingId else { return }
            var path = "/readings/\(readingId)?page=\(page ?? 1)"
            if let annotation { path += "&annotation=\(annotation)" }
            pick = nil
            state.pendingPath = path
            dismiss()
        }
        .buttonStyle(PrimaryButtonStyle())
    }
}
