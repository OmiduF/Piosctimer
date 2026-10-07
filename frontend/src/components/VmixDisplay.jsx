import { useEffect, useState } from "react";
import { Radio, WifiOff, Clapperboard, Eye } from "lucide-react";
import { useTimerSocket } from "@/hooks/useTimerSocket";
import { SourceSwitcher } from "@/components/SourceSwitcher";

function useClock() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 250);
    return () => clearInterval(id);
  }, []);
  return now;
}

function pad(n) {
  return String(n).padStart(2, "0");
}

function formatTimeLeft(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${pad(m)}:${pad(rem)}`;
}

function levelFor(status, timeLeft) {
  if (status !== "playing") return status; // idle | live
  if (timeLeft <= 10) return "danger";
  if (timeLeft <= 30) return "warn";
  return "ok";
}

const LEVEL_STYLES = {
  ok: { text: "text-white", accent: "bg-emerald-500", glow: "" },
  warn: { text: "text-amber-400", accent: "bg-amber-400", glow: "" },
  danger: {
    text: "text-red-500",
    accent: "bg-red-500",
    glow: "drop-shadow-[0_0_25px_rgba(239,68,68,0.55)]",
  },
  idle: { text: "text-neutral-600", accent: "bg-neutral-700", glow: "" },
  live: { text: "text-sky-400", accent: "bg-sky-500", glow: "" },
};

function RoleBadge({ role, status }) {
  const isProgram = role === "program";
  if (status === "live") {
    return (
      <span className="flex items-center gap-1.5 rounded-full bg-sky-500/15 px-2.5 py-0.5 font-mono text-[0.85vw] uppercase tracking-widest text-sky-400">
        <Radio size="0.9em" /> Live
      </span>
    );
  }
  if (status === "idle") {
    return (
      <span className="rounded-full bg-neutral-800/70 px-2.5 py-0.5 font-mono text-[0.85vw] uppercase tracking-widest text-neutral-500">
        Idle
      </span>
    );
  }
  return (
    <span
      className={`flex items-center gap-1.5 rounded-full px-2.5 py-0.5 font-mono text-[0.85vw] uppercase tracking-widest ${
        isProgram
          ? "bg-red-500/15 text-red-400"
          : "bg-emerald-500/15 text-emerald-400"
      }`}
    >
      {isProgram ? <Clapperboard size="0.9em" /> : <Eye size="0.9em" />}
      {isProgram ? "On Air" : "Next"}
    </span>
  );
}

function VmixPanel({ data, label }) {
  const level = levelFor(data.status, data.time_left);
  const style = LEVEL_STYLES[level] || LEVEL_STYLES.idle;
  const isDanger = level === "danger";
  const progress =
    data.status === "playing" && data.total > 0
      ? Math.min(100, (data.elapsed / data.total) * 100)
      : 0;

  const timeText =
    data.status === "playing" ? formatTimeLeft(data.time_left) : "--:--";

  return (
    <div
      data-testid={`vmix-${data.role}-panel`}
      className="relative flex flex-1 items-center overflow-hidden border-t border-neutral-800/80 px-[4vw]"
    >
      <div className={`absolute left-0 top-0 h-full w-[8px] ${style.accent}`} />

      <div className="flex w-full items-center justify-between gap-6">
        <div className="flex min-w-0 flex-col gap-3">
          <div className="flex items-center gap-3">
            <span className="font-mono text-[1.6vw] font-bold uppercase tracking-[0.35em] text-neutral-400">
              {label}
            </span>
            {data.number != null && data.status !== "idle" && (
              <span className="rounded-sm bg-neutral-800/70 px-2 py-0.5 font-mono text-[0.85vw] uppercase tracking-widest text-neutral-500">
                IN {data.number}
              </span>
            )}
            <RoleBadge role={data.role} status={data.status} />
          </div>
          <div
            data-testid={`vmix-${data.role}-title`}
            className="truncate font-mono text-[1.5vw] text-neutral-300"
            title={data.title}
          >
            {data.title || "—"}
          </div>
        </div>

        <div className="shrink-0 text-right">
          <div
            data-testid={`vmix-${data.role}-timeleft`}
            className={`font-mono font-bold leading-none tabular-nums text-[13vw] ${style.text} ${style.glow} ${
              isDanger ? "animate-pulse" : ""
            }`}
          >
            {timeText}
          </div>
        </div>
      </div>

      <div className="absolute bottom-0 left-0 h-[6px] w-full bg-neutral-900">
        <div
          className={`h-full transition-[width] duration-200 ease-linear ${style.accent}`}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}

const emptyInput = (role) => ({
  role,
  number: null,
  title: "",
  elapsed: 0,
  total: 0,
  time_left: 0,
  status: "idle",
});

export function VmixDisplay() {
  const now = useClock();
  const { state, connected } = useTimerSocket();

  const vmix = state?.vmix;
  const program = vmix?.program || emptyInput("program");
  const preview = vmix?.preview || emptyInput("preview");
  const vmixOnline = vmix?.connected;

  return (
    <div
      data-testid="vmix-display"
      className="flex h-screen w-screen flex-col overflow-hidden bg-black text-white"
    >
      <SourceSwitcher />

      {/* Clock */}
      <div className="flex flex-[0.9] flex-col items-center justify-center px-[4vw]">
        <div className="mb-2 font-mono text-[1.1vw] uppercase tracking-[0.6em] text-neutral-500">
          vMix · Local Time
        </div>
        <div
          data-testid="wall-clock"
          className="font-mono font-bold leading-none tabular-nums text-[15vw]"
        >
          {pad(now.getHours())}
          <span className="text-neutral-700">:</span>
          {pad(now.getMinutes())}
          <span className="text-neutral-700">:</span>
          {pad(now.getSeconds())}
        </div>
      </div>

      <VmixPanel data={program} label="Program" />
      <VmixPanel data={preview} label="Preview" />

      {/* Connection footer */}
      <div className="flex items-center justify-between border-t border-neutral-900 px-[3vw] py-2 font-mono text-[0.8vw] uppercase tracking-widest">
        <span className="flex items-center gap-2 text-neutral-600">
          vMix API {vmix?.host ?? "—"}:{vmix?.port ?? 8088}
        </span>
        <span
          data-testid="vmix-connection-status"
          className={`flex items-center gap-2 ${
            connected ? "text-neutral-500" : "text-red-500 animate-pulse"
          }`}
        >
          {connected ? (
            <>
              <span
                className={`h-2 w-2 rounded-full ${
                  vmixOnline ? "bg-emerald-500" : "bg-red-500"
                }`}
              />
              {vmixOnline
                ? "vMix connected"
                : `vMix offline (${vmix?.host ?? ""}:${vmix?.port ?? 8088})`}
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
