// How to ask from any app: build the two-step shortcut once, then put it on Back Tap or AssistiveTouch.
import DialecticKit
import SwiftUI

let SETUP_STEPS: [(title: String, detail: String)] = [
    ("Make the shortcut", "Open Shortcuts → + → add Take Screenshot, then add Dialectic's Ask Dialectic Here. Tap its Screenshot field and pick the Screenshot from the step before. Name it Ask Dialectic Here."),
    ("A note version (optional)", "Same again with Note Dialectic Here."),
    ("Back Tap (iPhone)", "Settings → Accessibility → Touch → Back Tap → Double Tap → pick Ask Dialectic Here. Now double-tap the back of the phone while you read."),
    ("AssistiveTouch (iPad)", "Settings → Accessibility → Touch → AssistiveTouch → on. Under Custom Actions, set Double-Tap (or Long Press) to Ask Dialectic Here. Now tap the floating button while you read."),
    ("Use it", "Open the reading in any app (Notability, Files, Safari), trigger it, type your question. The answer card shows over the app: your class first, then sources. The screenshot stays on your device; only the recognised text is sent."),
]

struct SetupView: View {
    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject var state: AppState

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    Text("Ask from any app").font(.system(size: 24, weight: .semibold, design: .serif)).foregroundColor(Theme.ink)
                    Text("Inside Dialectic, select a passage and tap Ask or note (or Ask Dialectic in the menu over the selection). To ask while you read somewhere else, set this up once:")
                        .font(.system(size: 15)).foregroundColor(Theme.muted).fixedSize(horizontal: false, vertical: true)
                    ForEach(Array(SETUP_STEPS.enumerated()), id: \.offset) { index, step in
                        HStack(alignment: .top, spacing: 12) {
                            Pin(number: index + 1, color: Theme.you)
                            VStack(alignment: .leading, spacing: 4) {
                                Text(step.title).font(.system(size: 16, weight: .semibold)).foregroundColor(Theme.ink)
                                Text(step.detail).font(.system(size: 14)).foregroundColor(Theme.ink).fixedSize(horizontal: false, vertical: true)
                            }
                        }
                    }
                    if state.user == nil {
                        Text(NO_USER_TEXT).font(.system(size: 14)).foregroundColor(Theme.warning)
                    }
                    Button("Open Shortcuts") { UIApplication.shared.open(URL(string: "shortcuts://")!) }
                        .buttonStyle(PrimaryButtonStyle())
                }
                .padding(24)
                .frame(maxWidth: 640, alignment: .leading)
            }
            .background(Theme.panel)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
        }
    }
}
