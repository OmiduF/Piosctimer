import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Settings } from "lucide-react";

// Subtle segmented control (top-right) to switch the kiosk display between the
// CasparCG and vMix sources. Semi-transparent so it stays out of the way.
export function SourceSwitcher() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const [sources, setSources] = useState(null);

  useEffect(() => {
    fetch("/api/settings").then((r) => r.json()).then((d) => setSources(d.sources)).catch(() => {});
  }, []);

  const allTabs = [
    { to: "/", label: "CasparCG", src: "casparcg" },
    { to: "/vmix", label: "vMix", src: "vmix" },
    { to: "/ota", label: "OnTheAir", id: "ota", src: "ota" },
  ];
  const tabs = sources ? allTabs.filter((t) => sources[t.src]) : allTabs;

  // if the current page's source is switched off, jump to the first active one
  useEffect(() => {
    if (sources && tabs.length && !tabs.some((t) => t.to === pathname)) navigate(tabs[0].to, { replace: true });
  }, [sources, pathname]); // eslint-disable-line react-hooks/exhaustive-deps

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
            data-testid={`switch-${t.id || t.label.toLowerCase()}`}
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
      <Link
        to="/settings"
        data-testid="switch-settings"
        title="Setări"
        className="flex items-center rounded-full px-3 text-neutral-500 transition-colors hover:text-white"
      >
        <Settings size="0.9vw" />
      </Link>
    </div>
  );
}
