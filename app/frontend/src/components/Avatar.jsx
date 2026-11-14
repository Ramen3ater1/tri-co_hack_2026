import { colorFor, initial } from '../colors.js';

// A person's coloured circle. `person` is an annotation's author ({id, name, role}) or {name}.
export default function Avatar({ person, size = '' }) {
  const color = colorFor(person);
  const label = person?.role === 'ai' ? 'AI' : initial(person?.name);
  return (
    <span className={`avatar ${size}`} style={{ background: color.bg, color: color.ink }} aria-hidden="true">
      {label}
    </span>
  );
}
