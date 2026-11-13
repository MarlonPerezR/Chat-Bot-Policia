// SVGs tomados del mockup. `c` = color del trazo/relleno principal.
export const Shield = ({ size = 28 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" role="img" aria-label="Escudo LexPolicía">
    <path d="M12 2.5 4.5 5.5v6c0 4.6 3.1 8.4 7.5 9.9 4.4-1.5 7.5-5.3 7.5-9.9v-6L12 2.5Z" fill="#2E5A3E" />
    <path d="M8.8 12.1l2.2 2.2 4.2-4.4" stroke="#A7D8B4" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export const Pin = ({ c = "#2E5A3E" }) => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M12 21s7-5.5 7-11a7 7 0 1 0-14 0c0 5.5 7 11 7 11Z" stroke={c} strokeWidth="1.7" />
    <circle cx="12" cy="10" r="2.4" stroke={c} strokeWidth="1.7" />
  </svg>
);

export const Chevron = ({ c = "#6E9A7D", size = 14 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="m6 9 6 6 6-6" stroke={c} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export const Search = ({ c = "#86988B", size = 20 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <circle cx="11" cy="11" r="7" stroke={c} strokeWidth="1.8" />
    <path d="m20 20-3.2-3.2" stroke={c} strokeWidth="1.8" strokeLinecap="round" />
  </svg>
);

export const Mic = ({ c = "#4A5D51" }) => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <rect x="9" y="3" width="6" height="11" rx="3" stroke={c} strokeWidth="1.7" />
    <path d="M5 11a7 7 0 0 0 14 0M12 18v3" stroke={c} strokeWidth="1.7" strokeLinecap="round" />
  </svg>
);

export const Send = ({ c = "#fff", size = 20 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M12 19V5M6 11l6-6 6 6" stroke={c} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export const Clip = ({ c = "#2E5A3E" }) => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M20 11.5 12 19a4 4 0 0 1-6-6l8-7.5a2.6 2.6 0 0 1 4 4L10 17" stroke={c} strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export const Book = ({ c = "#2E5A3E" }) => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H18v15H6.5A2.5 2.5 0 0 0 4 20.5V5.5Z" stroke={c} strokeWidth="1.6" />
  </svg>
);

export const Scale = () => (
  <svg width="21" height="21" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M9 18V7l10-2v11" stroke="#2E5A3E" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    <circle cx="7" cy="18" r="2" stroke="#2E5A3E" strokeWidth="1.7" />
    <circle cx="17" cy="16" r="2" stroke="#2E5A3E" strokeWidth="1.7" />
  </svg>
);

export const Paw = () => (
  <svg width="21" height="21" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <circle cx="5" cy="9" r="1.6" stroke="#2E5A3E" strokeWidth="1.5" />
    <circle cx="9" cy="6" r="1.6" stroke="#2E5A3E" strokeWidth="1.5" />
    <circle cx="15" cy="6" r="1.6" stroke="#2E5A3E" strokeWidth="1.5" />
    <circle cx="19" cy="9" r="1.6" stroke="#2E5A3E" strokeWidth="1.5" />
    <path d="M8 16c0-2.2 1.8-4 4-4s4 1.8 4 4c0 1.7-1.3 3-3 3h-2c-1.7 0-3-1.3-3-3Z" stroke="#2E5A3E" strokeWidth="1.5" />
  </svg>
);

export const Camera = () => (
  <svg width="21" height="21" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <rect x="3" y="7" width="18" height="12" rx="2.5" stroke="#2E5A3E" strokeWidth="1.6" />
    <path d="M8 7l1.5-2.5h5L16 7" stroke="#2E5A3E" strokeWidth="1.6" strokeLinejoin="round" />
    <circle cx="12" cy="13" r="3" stroke="#2E5A3E" strokeWidth="1.6" />
  </svg>
);

export const Arrow = () => (
  <svg width="21" height="21" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M7 17 17 7M9 7h8v8" stroke="#2E5A3E" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export const ICONOS_FRECUENTES = { ruido: Scale, mascotas: Paw, grabar: Camera, prontopago: Arrow };
