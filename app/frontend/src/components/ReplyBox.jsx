import { useLayoutEffect, useRef } from 'react';

// Multi-line reply box: grows with its text up to MAX_HEIGHT, then scrolls.
// Enter sends (like the old one-line input); Shift+Enter starts a new line.
const MAX_HEIGHT = 160;

export default function ReplyBox({ id, value, onChange, onSend, placeholder, autoFocus }) {
  const ref = useRef(null);

  // Resize to fit the text on every change (also shrinks back after sending).
  useLayoutEffect(() => {
    const box = ref.current;
    box.style.height = 'auto';
    box.style.height = Math.min(box.scrollHeight + 2, MAX_HEIGHT) + 'px';
  }, [value]);

  function onKeyDown(event) {
    // isComposing: don't send while an IME (e.g. Japanese input) is mid-word.
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      onSend(event);
    }
  }

  return (
    <textarea
      ref={ref}
      id={id}
      className="textarea"
      rows={1}
      placeholder={placeholder}
      autoFocus={autoFocus}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      onKeyDown={onKeyDown}
    />
  );
}
