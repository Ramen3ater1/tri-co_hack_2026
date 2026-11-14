// The look from josue's canvas (design.md §5). Light mode only. Copied from app/mac Style.swift, made public.
import SwiftUI

// ---------- tokens ----------

public extension Color {
    init(hex: UInt32, alpha: Double = 1) {
        self.init(.sRGB, red: Double((hex >> 16) & 0xFF) / 255, green: Double((hex >> 8) & 0xFF) / 255,
                  blue: Double(hex & 0xFF) / 255, opacity: alpha)
    }
}

public enum Theme {
    public static let ground = Color(hex: 0xF4F3EE)
    public static let panel = Color.white
    public static let ink = Color(hex: 0x161513)
    public static let muted = Color(hex: 0x5A5750)
    public static let hairline = Color(hex: 0x5A5750, alpha: 0.35)
    public static let professor = Color(hex: 0x2F8F5B)
    public static let classmate = Color(hex: 0xD83FB7)
    public static let classmatePin = Color(hex: 0xA8308F)
    public static let you = Color(hex: 0x2B5BB5)
    public static let warning = Color(hex: 0xB86A12)
    public static let highlightAlpha = 0.22
    public static let panelRadius: CGFloat = 16
    public static let cardRadius: CGFloat = 12
    public static let minHit: CGFloat = 44

    /// Passages and quotes: New York (the system serif). Literata isn't on a stock Mac.
    public static func serif(_ size: CGFloat = 14) -> Font { .system(size: size, design: .serif) }
}

/// Highlight colour is by role, not by person (design.md §5). AI is never drawn on the page.
public enum Role {
    case professor, classmate, you, ai

    public var color: Color {
        switch self {
        case .professor: return Theme.professor
        case .classmate: return Theme.classmate
        case .you: return Theme.you
        case .ai: return Theme.muted
        }
    }

    public var pinColor: Color { self == .classmate ? Theme.classmatePin : color }

    public static func of(authorId: Int?, role: String?) -> Role {
        if let authorId, authorId == currentUserId() { return .you }
        if role == "professor" { return .professor }
        if role == "ai" { return .ai }
        return .classmate
    }
}

// ---------- small pieces ----------

/// A key combination drawn as a bordered pill, e.g. ⌃⌥D.
public struct KeyCap: View {
    let label: String
    public init(label: String) { self.label = label }
    public var body: some View {
        Text(label)
            .font(.system(size: 11, weight: .medium))
            .foregroundColor(Theme.ink)
            .padding(.horizontal, 6).padding(.vertical, 2)
            .background(RoundedRectangle(cornerRadius: 5).fill(Theme.panel))
            .overlay(RoundedRectangle(cornerRadius: 5).stroke(Theme.hairline, lineWidth: 1))
    }
}

/// Small uppercase section label: FROM YOUR CLASS, SOURCES, 2 REPLIES.
public struct SectionLabel: View {
    let text: String
    public init(_ text: String) { self.text = text }
    public var body: some View {
        Text(text.uppercased())
            .font(.system(size: 10.5, weight: .semibold))
            .tracking(0.6)
            .foregroundColor(Theme.muted)
    }
}

/// The quoted passage as a chip: blue at 14%, serif.
public struct QuoteChip: View {
    let text: String
    var lineLimit: Int? = 5
    public init(text: String, lineLimit: Int? = 5) { self.text = text; self.lineLimit = lineLimit }
    public var body: some View {
        Text("“\(text)”")
            .font(Theme.serif(14))
            .foregroundColor(Theme.ink)
            .lineLimit(lineLimit)
            .fixedSize(horizontal: false, vertical: true)
            .padding(.horizontal, 10).padding(.vertical, 8)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(RoundedRectangle(cornerRadius: 10).fill(Theme.you.opacity(0.14)))
    }
}

/// Numbered round pin that links a box on the page to its margin card.
public struct Pin: View {
    let number: Int
    let color: Color
    public init(number: Int, color: Color) { self.number = number; self.color = color }
    public var body: some View {
        Text("\(number)")
            .font(.system(size: 10, weight: .bold))
            .foregroundColor(.white)
            .frame(width: 18, height: 18)
            .background(Circle().fill(color))
    }
}

public struct Badge: View {
    let text: String
    let color: Color
    public init(text: String, color: Color) { self.text = text; self.color = color }
    public var body: some View {
        Text(text)
            .font(.system(size: 10.5, weight: .medium))
            .foregroundColor(color)
            .padding(.horizontal, 6).padding(.vertical, 1)
            .background(Capsule().fill(color.opacity(0.12)))
    }
}

/// A margin card: 3px left edge in the role colour, author bold, badge, then content.
public struct RoleCard<Content: View>: View {
    let role: Role
    var dashed = false
    @ViewBuilder let content: () -> Content
    public init(role: Role, dashed: Bool = false, @ViewBuilder content: @escaping () -> Content) {
        self.role = role; self.dashed = dashed; self.content = content
    }

    public var body: some View {
        HStack(spacing: 0) {
            if !dashed { Rectangle().fill(role.color).frame(width: 3) }
            VStack(alignment: .leading, spacing: 6) { content() }
                .padding(12)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .background(Theme.panel)
        .clipShape(RoundedRectangle(cornerRadius: Theme.cardRadius))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.cardRadius)
                .stroke(dashed ? Theme.classmate : Theme.hairline,
                        style: StrokeStyle(lineWidth: dashed ? 1.5 : 1, dash: dashed ? [5, 3] : []))
        )        .fixedSize(horizontal: false, vertical: true)  // the edge bar must not stretch the card
    }
}

/// Author line for a card: "Ana  [Spring 2026]" or "You (Ben) · just now, from your Mac".
public struct AuthorLine: View {
    let name: String
    let role: Role
    let badge: String?
    var detail: String? = nil
    var pin: Int? = nil
    public init(name: String, role: Role, badge: String?, detail: String? = nil, pin: Int? = nil) {
        self.name = name; self.role = role; self.badge = badge; self.detail = detail; self.pin = pin
    }

    public var body: some View {
        HStack(spacing: 6) {
            if let pin { Pin(number: pin, color: role.pinColor) }
            Text(role == .you ? "You (\(name))" : name).font(.system(size: 13, weight: .bold)).foregroundColor(Theme.ink)
            if let badge { Badge(text: badge, color: role == .classmate ? Theme.classmatePin : role.color) }
            if let detail { Text("· \(detail)").font(.system(size: 11.5)).foregroundColor(Theme.muted) }
            Spacer(minLength: 0)
        }
    }
}

public struct PrimaryButtonStyle: ButtonStyle {
    var color = Theme.you
    public init(color: Color = Theme.you) { self.color = color }
    public func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 13, weight: .semibold))
            .foregroundColor(.white)
            .padding(.horizontal, 16)
            .frame(minHeight: Theme.minHit)
            .background(RoundedRectangle(cornerRadius: 10).fill(color.opacity(configuration.isPressed ? 0.8 : 1)))
            .contentShape(Rectangle())
    }
}

public struct QuietButtonStyle: ButtonStyle {
    public init() {}
    public func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 13, weight: .medium))
            .foregroundColor(Theme.ink)
            .padding(.horizontal, 14)
            .frame(minHeight: Theme.minHit)
            .frame(maxWidth: .infinity)
            .background(RoundedRectangle(cornerRadius: 10).fill(Theme.ground.opacity(configuration.isPressed ? 0.6 : 1)))
            .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.hairline, lineWidth: 1))
            .contentShape(Rectangle())
    }
}

/// Multi-line text box with a placeholder, in the canvas style.
public struct TextArea: View {
    let placeholder: String
    @Binding var text: String
    var height: CGFloat = 80
    public init(placeholder: String, text: Binding<String>, height: CGFloat = 80) {
        self.placeholder = placeholder; self._text = text; self.height = height
    }

    public var body: some View {
        ZStack(alignment: .topLeading) {
            TextEditor(text: $text)
                .font(.system(size: 13))
                .scrollContentBackground(.hidden)
                .padding(6)
            if text.isEmpty {
                Text(placeholder).font(.system(size: 13)).foregroundColor(Theme.muted)
                    .padding(.horizontal, 11).padding(.vertical, 6)
                    .allowsHitTesting(false)
            }
        }
        .frame(height: height)
        .background(RoundedRectangle(cornerRadius: 10).fill(Theme.panel))
        .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.hairline, lineWidth: 1))
    }
}

/// The panel surface: white, radius 16, hairline border.
public struct PanelSurface: ViewModifier {
    public func body(content: Content) -> some View {
        content
            .padding(16)
            .background(RoundedRectangle(cornerRadius: Theme.panelRadius).fill(Theme.panel))
            .overlay(RoundedRectangle(cornerRadius: Theme.panelRadius).stroke(Theme.hairline, lineWidth: 1))
            .environment(\.colorScheme, .light)
    }
}

public extension View {
    func panelSurface() -> some View { modifier(PanelSurface()) }
}

/// A text link in the accent colour. Opens through SwiftUI's openURL, so each app decides where links go.
public struct LinkButton: View {
    let title: String
    let url: String
    var size: CGFloat
    @Environment(\.openURL) private var openURL
    public init(title: String, url: String, size: CGFloat = 13) { self.title = title; self.url = url; self.size = size }
    public var body: some View {
        Button { if let link = URL(string: url) { openURL(link) } } label: {
            Text(title).font(.system(size: size, weight: .medium)).foregroundColor(Theme.you)
                .multilineTextAlignment(.leading).fixedSize(horizontal: false, vertical: true)
        }
        .buttonStyle(.plain)
    }
}
