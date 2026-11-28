const PATHS: Record<string, string> = {
  dashboard: "M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z",
  cases: "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
  plus: "M12 5v14M5 12h14",
  history: "M3 12a9 9 0 1 0 3-6.7M3 4v5h5M12 7v5l3 2",
  user: "M20 21a8 8 0 0 0-16 0M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
  shield: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z",
  shieldPlus: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6zM12 9v6M9 12h6",
  scan: "M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  home: "M3 11l9-8 9 8M5 10v10h14V10",
  logout: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9",
  menu: "M4 6h16M4 12h16M4 18h16",
  close: "M6 6l12 12M18 6L6 18",
  check: "M5 12.5l4.5 4.5L19 7",
  spark: "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z",
  lock: "M6 11h12v9H6zM8 11V8a4 4 0 0 1 8 0v3",
  camera: "M4 8h3l2-3h6l2 3h3v11H4zM12 17a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z",
  arrow: "M5 12h14M13 6l6 6-6 6",
};

export default function Icon({ name, size = 20, className = "" }: { name: keyof typeof PATHS | string; size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      <path d={PATHS[name]} />
    </svg>
  );
}

export function Logo({ size = 36 }: { size?: number }) {
  return (
    <span className="inline-flex shrink-0 items-center justify-center" style={{ width: size, height: size }} aria-hidden="true">
      <svg width={size} height={size} viewBox="0 0 36 36" fill="none">
        {/* Rounded medical cross */}
        <path
          d="M14 3.5h8a2.5 2.5 0 0 1 2.5 2.5v5.5H30a2.5 2.5 0 0 1 2.5 2.5v8a2.5 2.5 0 0 1-2.5 2.5h-5.5V30a2.5 2.5 0 0 1-2.5 2.5h-8a2.5 2.5 0 0 1-2.5-2.5v-5.5H6A2.5 2.5 0 0 1 3.5 22v-8A2.5 2.5 0 0 1 6 11.5h5.5V6A2.5 2.5 0 0 1 14 3.5Z"
          fill="#15573E"
        />
        {/* Lighter botanical accent on right/top arm */}
        <path
          d="M18 3.5h4a2.5 2.5 0 0 1 2.5 2.5v5.5H30a2.5 2.5 0 0 1 2.5 2.5v4H18V3.5Z"
          fill="#2D8A65"
          fillOpacity="0.65"
        />
        {/* Leaf + AI circuit stem */}
        <path d="M18 27V11" stroke="#EFFAF4" strokeWidth="1.7" strokeLinecap="round" />
        <path d="M18 19.5c-2.6-.3-4.6-1.8-5.4-4.2 2.5-.2 4.5.9 5.4 3.1" fill="#A9E5C9" />
        <path d="M18 16.5c2.6-.3 4.6-1.8 5.4-4.2-2.5-.2-4.5.9-5.4 3.1" fill="#D5F5E5" />
        {/* Circuit nodes */}
        <path d="M18 22.5h-6.5M18 21h7" stroke="#EFFAF4" strokeWidth="1.4" strokeLinecap="round" />
        <circle cx="10.2" cy="22.5" r="1.6" fill="#EFFAF4" />
        <circle cx="26.2" cy="21" r="1.6" fill="#EFFAF4" />
        <circle cx="18" cy="9.4" r="1.6" fill="#EFFAF4" />
      </svg>
    </span>
  );
}
