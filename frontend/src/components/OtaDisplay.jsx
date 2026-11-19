import { Radio, WifiOff, Pause, Play } from "lucide-react";
import { useTimerSocket } from "@/hooks/useTimerSocket";
import { SourceSwitcher } from "@/components/SourceSwitcher";
import { useClock, pad, formatTimeLeft, levelFor, LEVEL_STYLES } from "@/components/VmixDisplay";

const BADGES = {
  playing: { cls: "bg-red-500/15 text-red-400", icon: Play, text: "On Air" },
  paused: { cls: "bg-neutral-700/40 text-neutral-300", icon: Pause, text: "Paused" },
  live: { cls: "bg-sky-500/15 text-sky-400", icon: Radio, text: "Live" },
};

function StatusBadge({ status }) {
  const b = BADGES[status];
  if (!b) {
    return (
      <span className="rounded-full bg-neutral-800/70 px-2.5 py-0.5 font-mono text-[0.85vw] uppercase tracking-widest text-neutral-500">
        Idle
      </span>
    );
  }
  const Icon = b.icon;
  return (
    <span data-testid="ota-status-badge" className={`flex items-center gap-1.5 rounded-full px-2.5 py-0.5 font-mono text-[0.85vw] uppercase tracking-widest ${b.cls}`}>
      <Icon size="0.9em" /> {b.text}
    </span>
  );
}

function OtaPanel({ clip }) {
  const level = levelFor(clip.status === "paused" ? "playing" : clip.status, clip.time_left);
  const style = LEVEL_STYLES[clip.status === "paused" ? "paused" : level] || LEVEL_STYLES.idle;
  const hasTime = clip.status === "playing" || clip.status === "paused";
  const progress = hasTime && clip.total > 0 ? Math.min(100, (clip.elapsed / clip.total) * 100) : 0;

  return (
    <div data-testid="ota-clip-panel" className="relative flex flex-[1.2] items-center overflow-hidden border-t border-neutral-800/80 px-[4vw]">
      <div className={`absolute left-0 top-0 h-full w-[8px] ${style.accent}`} />
      <div className="flex w-full items-center justify-between gap-6">
        <div className="flex min-w-0 flex-col gap-3">
          <div className="flex items-center gap-3">
            <span className="font-mono text-[1.6vw] font-bold uppercase tracking-[0.35em] text-neutral-400">OnTheAir</span>
            {clip.id && (
              <span className="rounded-sm bg-neutral-800/70 px-2 py-0.5 font-mono text-[0.85vw] uppercase tracking-widest text-neutral-500">
                Clip {clip.id}
              </span>
            )}
            <StatusBadge status={clip.status} />
          </div>
          <div data-testid="ota-clip-title" className="truncate font-mono text-[1.5vw] text-neutral-300" title={clip.title}>
            {clip.title || "—"}
          </div>
        </div>
        <div
          data-testid="ota-timeleft"
          className={`shrink-0 font-mono font-bold leading-none tabular-nums text-[16vw] ${style.text} ${style.glow} ${level === "danger" && clip.status === "playing" ? "animate-pulse" : ""}`}
        >
          {hasTime ? formatTimeLeft(clip.time_left) : "--:--"}
        </div>
      </div>
      <div className="absolute bottom-0 left-0 h-[6px] w-full bg-neutral-900">
        <div className={`h-full transition-[width] duration-200 ease-linear ${style.accent}`} style={{ width: `${progress}%` }} />
      </div>
    </div>
  );
}

const EMPTY = { id: null, title: "", elapsed: 0, total: 0, time_left: 0, status: "idle" };

export function OtaDisplay() {
  const now = useClock();
  const { state, connected } = useTimerSocket();
  const ota = state?.ota;

  return (
    <div data-testid="ota-display" className="flex h-screen w-screen flex-col overflow-hidden bg-black text-white">
      <SourceSwitcher />
      <div className="flex flex-1 flex-col items-center justify-center px-[4vw]">
        <div className="mb-2 font-mono text-[1.1vw] uppercase tracking-[0.6em] text-neutral-500">OnTheAir · Local Time</div>
        <div data-testid="wall-clock" className="font-mono font-bold leading-none tabular-nums text-[15vw]">
          {pad(now.getHours())}<span className="text-neutral-700">:</span>
          {pad(now.getMinutes())}<span className="text-neutral-700">:</span>
          {pad(now.getSeconds())}
        </div>
      </div>

      <OtaPanel clip={ota?.clip || EMPTY} />

      <div className="flex items-center justify-between border-t border-neutral-900 px-[3vw] py-2 font-mono text-[0.8vw] uppercase tracking-widest">
        <span className="text-neutral-600">HyperDeck {ota?.host ?? "—"}:{ota?.port ?? 9993}</span>
        <span data-testid="ota-connection-status" className={`flex items-center gap-2 ${connected ? "text-neutral-500" : "animate-pulse text-red-500"}`}>
          {connected ? (
            <>
              <span className={`h-2 w-2 rounded-full ${ota?.connected ? "bg-emerald-500" : "bg-red-500"}`} />
              {ota?.connected ? "OnTheAir connected" : `OnTheAir offline (${ota?.host ?? ""}:${ota?.port ?? 9993})`}
            </>
          ) : (
            <>
              <WifiOff size="1em" /> Reconnecting…
            </>
          )}
        </span>
      </div>
    </div>
  );
}
