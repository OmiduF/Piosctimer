import { Radio, WifiOff, Pause, Play } from "lucide-react";
import { useTimerSocket } from "@/hooks/useTimerSocket";
import { SourceSwitcher } from "@/components/SourceSwitcher";
import { useClock, pad, formatTimeLeft, levelFor, LEVEL_STYLES } from "@/components/VmixDisplay";

const BADGES = {
  playing: { cls: "bg-red-500/15 text-red-400", icon: Play, text: "On Air" },
  paused: { cls: "bg-neutral-700/40 text-neutral-300", icon: Pause, text: "Paused" },
  live: { cls: "bg-sky-500/15 text-sky-400", icon: Radio, text: "Live" },
};

function StatusBadge({ status, testId }) {
  const b = BADGES[status];
  if (!b) {
    return (
      <span data-testid={testId} className="rounded-full bg-neutral-800/70 px-2.5 py-0.5 font-mono text-[0.85vw] uppercase tracking-widest text-neutral-500">
        Idle
      </span>
    );
  }
  const Icon = b.icon;
  return (
    <span data-testid={testId} className={`flex items-center gap-1.5 rounded-full px-2.5 py-0.5 font-mono text-[0.85vw] uppercase tracking-widest ${b.cls}`}>
      <Icon size="0.9em" /> {b.text}
    </span>
  );
}

function OtaPanel({ output, index }) {
  const clip = output.clip;
  const level = levelFor(clip.status === "paused" ? "playing" : clip.status, clip.time_left);
  const style = LEVEL_STYLES[clip.status === "paused" ? "paused" : level] || LEVEL_STYLES.idle;
  const hasTime = clip.status === "playing" || clip.status === "paused";
  const progress = hasTime && clip.total > 0 ? Math.min(100, (clip.elapsed / clip.total) * 100) : 0;

  return (
    <div data-testid={`ota-output-${index + 1}-panel`} className="relative flex flex-1 items-center overflow-hidden border-t border-neutral-800/80 px-[4vw]">
      <div className={`absolute left-0 top-0 h-full w-[8px] ${style.accent}`} />
      <div className="flex w-full items-center justify-between gap-6">
        <div className="flex min-w-0 flex-col gap-3">
          <div className="flex items-center gap-3">
            <span data-testid={`ota-output-${index + 1}-name`} className="font-mono text-[1.4vw] font-bold uppercase tracking-[0.3em] text-neutral-400">{output.name}</span>
            {!output.connected && (
              <span data-testid={`ota-output-${index + 1}-offline`} className="flex items-center gap-1.5 rounded-full bg-red-500/15 px-2.5 py-0.5 font-mono text-[0.85vw] uppercase tracking-widest text-red-400">
                <WifiOff size="0.9em" /> Offline :{output.port}
              </span>
            )}
            {clip.id && (
              <span className="rounded-sm bg-neutral-800/70 px-2 py-0.5 font-mono text-[0.85vw] uppercase tracking-widest text-neutral-500">
                Clip {clip.id}
              </span>
            )}
            {output.connected && <StatusBadge status={clip.status} testId={`ota-output-${index + 1}-status`} />}
          </div>
          <div data-testid={`ota-output-${index + 1}-title`} className="truncate font-mono text-[1.3vw] text-neutral-300" title={clip.title}>
            {clip.title || "—"}
          </div>
        </div>
        <div
          data-testid={`ota-output-${index + 1}-timeleft`}
          className={`shrink-0 font-mono font-bold leading-none tabular-nums text-[9vw] ${style.text} ${style.glow} ${level === "danger" && clip.status === "playing" ? "animate-pulse" : ""}`}
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

const EMPTY_CLIP = { id: null, title: "", elapsed: 0, total: 0, time_left: 0, status: "idle" };
const EMPTY_OUTPUTS = [1, 2, 3].map((n) => ({ id: `out${n}`, name: `Output ${n}`, port: 9992 + n, connected: false, clip: EMPTY_CLIP }));

export function OtaDisplay() {
  const now = useClock();
  const { state, connected } = useTimerSocket();
  const ota = state?.ota;
  const outputs = ota?.outputs || EMPTY_OUTPUTS;
  const online = outputs.filter((o) => o.connected).length;
  const total = outputs.length;

  return (
    <div data-testid="ota-display" className="flex h-screen w-screen flex-col overflow-hidden bg-black text-white">
      <SourceSwitcher />
      <div className="flex flex-[0.8] flex-col items-center justify-center px-[4vw] pt-[3vh]">
        <div className="mb-2 font-mono text-[1.1vw] uppercase tracking-[0.6em] text-neutral-500">OnTheAir · Local Time</div>
        <div data-testid="wall-clock" className="font-mono font-bold leading-none tabular-nums text-[11vw]">
          {pad(now.getHours())}<span className="text-neutral-700">:</span>
          {pad(now.getMinutes())}<span className="text-neutral-700">:</span>
          {pad(now.getSeconds())}
        </div>
      </div>

      {(ota?.outputs || EMPTY_OUTPUTS).map((o, i) => (
        <OtaPanel key={o.id} output={o} index={i} />
      ))}

      <div className="flex items-center justify-between border-t border-neutral-900 px-[3vw] py-2 font-mono text-[0.8vw] uppercase tracking-widest">
        <span className="text-neutral-600">{ota?.mode === "hyperdeck" ? "HyperDeck" : "REST API"} {ota?.host ?? "—"} · {(ota?.outputs || EMPTY_OUTPUTS).map((o) => o.port).join(" / ")}</span>
        <span data-testid="ota-connection-status" className={`flex items-center gap-2 ${connected ? "text-neutral-500" : "animate-pulse text-red-500"}`}>
          {connected ? (
            <>
              <span className={`h-2 w-2 rounded-full ${online === total ? "bg-emerald-500" : online ? "bg-amber-400" : "bg-red-500"}`} />
              OnTheAir {online}/{total} connected
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
