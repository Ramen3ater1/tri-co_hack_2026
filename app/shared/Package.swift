// swift-tools-version:5.9
// DialecticKit: the code the iPad/iPhone app shares with the Mac app (API shapes and HTTP, the canvas look,
// the Ask | Note panel, reading text off a screenshot). See app/shared/README.md.
import PackageDescription

let package = Package(
    name: "DialecticKit",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [.library(name: "DialecticKit", targets: ["DialecticKit"])],
    targets: [.target(name: "DialecticKit", path: "Sources/DialecticKit")]
)
