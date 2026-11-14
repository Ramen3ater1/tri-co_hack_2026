// swift-tools-version:5.9
// Dialectic Mac hotkey app (SPEC §3.9). Build the .app with ./build.sh, not plain `swift build`:
// the URL scheme and "no Dock icon" need an Info.plist inside a bundle.
import PackageDescription

let package = Package(
    name: "Dialectic",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(name: "Dialectic", path: "Sources/Dialectic")
    ]
)
