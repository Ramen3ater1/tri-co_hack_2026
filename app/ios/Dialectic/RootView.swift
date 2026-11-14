// The main screen: the web reader full screen, a slim bar on top (who you are, Ask or note, setup),
// and the Ask | Note panel as a sheet (a side sheet on iPad, from the bottom on iPhone).
import DialecticKit
import SwiftUI

struct RootView: View {
    @EnvironmentObject var state: AppState
    @StateObject private var reader = ReaderController()
    @State private var showSetup = false

    var body: some View {
        VStack(spacing: 0) {
            topBar
            Divider().overlay(Theme.hairline)
            ReaderView(controller: reader)
                .ignoresSafeArea(edges: .bottom)
        }
        .background(Theme.ground)
        .onAppear { reader.signIn(as: state.user, users: state.users) }
        .onChange(of: state.userId) { reader.signIn(as: state.user, users: state.users) }
        .onChange(of: state.users.map(\.id)) { reader.signIn(as: state.user, users: state.users) }
        .onChange(of: state.server) { reader.open(path: "/") }
        .onChange(of: state.pendingPath) {
            if let path = state.pendingPath {
                state.composer = nil
                reader.open(path: path)
                state.pendingPath = nil
            }
        }
        .sheet(item: Binding(get: { state.composer.map(ComposerBox.init) }, set: { if $0 == nil { state.composer = nil } })) { box in
            ComposerSheet(model: box.model)
                .environmentObject(state)
                .presentationDetents([.medium, .large])
                .presentationDragIndicator(.visible)
        }
        .sheet(isPresented: $showSetup) { SetupView().environmentObject(state) }
        .onReceive(reader.$selectionToAsk) { quote in
            if let quote { state.openComposer(quote: quote); reader.selectionToAsk = nil }
        }
    }

    var topBar: some View {
        HStack(spacing: 10) {
            Menu {
                if let error = state.usersError { Text(error) }
                ForEach(state.users) { user in
                    Button { state.pick(user) } label: {
                        if user.id == state.userId { Label(userLabel(user), systemImage: "checkmark") } else { Text(userLabel(user)) }
                    }
                }
                Divider()
                Menu("Server") {
                    ForEach(SERVERS, id: \.url) { server in
                        Button { state.pickServer(server.url) } label: {
                            if server.url == state.server { Label(server.name, systemImage: "checkmark") } else { Text(server.name) }
                        }
                    }
                }
            } label: {
                Label(state.user?.name ?? "Who are you?", systemImage: "person.crop.circle")
                    .font(.system(size: 15, weight: .medium)).foregroundColor(Theme.ink)
                    .frame(minHeight: Theme.minHit)
            }
            Spacer()
            Button {
                Task { await reader.askAboutSelection() }
            } label: {
                Label("Ask or note", systemImage: "text.quote").font(.system(size: 15, weight: .semibold))
            }
            .buttonStyle(PrimaryButtonStyle())
            .help("Select a passage in the reader first")
            Button { showSetup = true } label: {
                Image(systemName: "hand.tap").font(.system(size: 17)).foregroundColor(Theme.ink).frame(width: Theme.minHit, height: Theme.minHit)
            }
            .accessibilityLabel("Ask from any app: set up")
        }
        .padding(.horizontal, 12)
        .background(Theme.panel)
        .overlay(alignment: .bottom) {
            if let message = reader.message {
                Text(message).font(.system(size: 13)).foregroundColor(.white)
                    .padding(.horizontal, 12).padding(.vertical, 8)
                    .background(Capsule().fill(Theme.ink))
                    .offset(y: 44)
                    .transition(.opacity)
            }
        }
        .zIndex(1)
    }

    func userLabel(_ user: User) -> String {
        [user.name, user.role == "professor" ? "Professor" : user.cohort].compactMap { $0 }.joined(separator: " · ")
    }
}

/// Wraps the model so `.sheet(item:)` gets an Identifiable.
struct ComposerBox: Identifiable {
    let model: ComposerModel
    var id: ObjectIdentifier { ObjectIdentifier(model) }
}

struct ComposerSheet: View {
    @ObservedObject var model: ComposerModel
    @EnvironmentObject var state: AppState
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ScrollView {
            ComposerView(model: model, users: state.users) {
                Button("Done") { dismiss() }.font(.system(size: 15, weight: .medium)).foregroundColor(Theme.you)
                    .frame(minHeight: Theme.minHit)
            }
            .padding(20)
        }
        .background(Theme.panel)
        .environment(\.openReader) { path in state.pendingPath = path }
    }
}
