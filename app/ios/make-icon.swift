// Draws the iOS app icon (1024 px, full bleed) from app/frontend/public/icon.svg's shapes.
// Run: swift make-icon.swift Dialectic/Assets.xcassets/AppIcon.appiconset/icon-1024.png
import AppKit
let s: CGFloat = 1024, k = s / 64
let ctx = CGContext(data: nil, width: 1024, height: 1024, bitsPerComponent: 8, bytesPerRow: 0,
                    space: CGColorSpace(name: CGColorSpace.sRGB)!, bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
ctx.translateBy(x: 0, y: s); ctx.scaleBy(x: 1, y: -1)  // SVG coordinates: top-left origin
func c(_ hex: UInt32) -> CGColor { CGColor(srgbRed: CGFloat(hex >> 16 & 255) / 255, green: CGFloat(hex >> 8 & 255) / 255, blue: CGFloat(hex & 255) / 255, alpha: 1) }
ctx.setFillColor(c(0x22201C)); ctx.fill(CGRect(x: 0, y: 0, width: s, height: s))
// D: M20 16h12a16 16 0 0 1 0 32H20z
let d = CGMutablePath()
d.move(to: CGPoint(x: 20 * k, y: 16 * k)); d.addLine(to: CGPoint(x: 32 * k, y: 16 * k))
d.addArc(center: CGPoint(x: 32 * k, y: 32 * k), radius: 16 * k, startAngle: -.pi / 2, endAngle: .pi / 2, clockwise: false)
d.addLine(to: CGPoint(x: 20 * k, y: 48 * k)); d.closeSubpath()
ctx.addPath(d); ctx.setStrokeColor(c(0xF7F5F0)); ctx.setLineWidth(5 * k); ctx.strokePath()
ctx.addPath(CGPath(roundedRect: CGRect(x: 27 * k, y: 27 * k, width: 14 * k, height: 5 * k), cornerWidth: 2 * k, cornerHeight: 2 * k, transform: nil))
ctx.setFillColor(c(0xFFF4C9)); ctx.fillPath()
let rep = NSBitmapImageRep(cgImage: ctx.makeImage()!)
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: CommandLine.arguments[1]))
