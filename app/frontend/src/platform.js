// "Use on Mac" links only make sense on a real Mac, where the menu-bar app can be installed.
// iPadOS Safari (and the iOS app's web view) also say "Macintosh" in the user agent, so a
// touch screen rules it out: Macs report 0 touch points, iPads 5.
export const IS_MAC = /Macintosh/.test(navigator.userAgent) && navigator.maxTouchPoints <= 1;
