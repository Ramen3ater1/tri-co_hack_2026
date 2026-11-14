// "Use on Mac" links only make sense on a real Mac, where the menu-bar app can be installed.
// iPadOS Safari (and the iOS app's web view) also say "Macintosh" in the user agent, so a
// touch screen rules it out: Macs report 0 touch points, iPads 5.
const LOOKS_LIKE_MAC = /Macintosh/.test(navigator.userAgent) && navigator.maxTouchPoints <= 1;

// DEMO: ?mac=0 on any page hides the Mac links (to film the browser-only experience on a Mac),
// ?mac=1 brings them back. Remembered in this browser until changed.
const MAC_SETTING_KEY = 'dialectic.mac';
const macParam = new URLSearchParams(window.location.search).get('mac');
if (macParam === '0' || macParam === '1') localStorage.setItem(MAC_SETTING_KEY, macParam);

export const IS_MAC = LOOKS_LIKE_MAC && localStorage.getItem(MAC_SETTING_KEY) !== '0';
