import { Link, useLocation } from "react-router-dom";

// Subtle segmented control (top-right) to switch the kiosk display between the
// CasparCG and vMix sources. Semi-transparent so it stays out of the way.
export function SourceSwitcher() {
  const { pathname } = useLocation();
  const tabs = [
    { to: "/", label: "CasparCG" },
    { to: "/vmix", label: "vMix" },
  ];

  return (
    <div
      data-testid="source-switcher"
      className="fixed right-6 top-6 z-50 flex gap-1 rounded-full border border-neutral-800 bg-neutral-950/70 p-1 backdrop-blur-md"
    >
      {tabs.map((t) => {
        const active = pathname === t.to;
        return (
          <Link
            key={t.to}
            to={t.to}
            data-testid={`switch-${t.label.toLowerCase()}`}
            className={`rounded-full px-4 py-1.5 font-mono text-[0.8vw] uppercase tracking-[0.2em] transition-colors ${
              active
                ? "bg-white text-black"
                : "text-neutral-400 hover:text-white"
            }`}
          >
            {t.label}
          </Link>
        );
      })}
    </div>
  );
}
