import { useEffect, useState } from "react";
import { Radio, WifiOff, Clapperboard } from "lucide-react";
import { useTimerSocket } from "@/hooks/useTimerSocket";

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

// Always MM:SS (per requirement)
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

function ChannelPanel({ data }) {
  const level = levelFor(data.status, data.time_left);
  const style = LEVEL_STYLES[level] || LEVEL_STYLES.idle;
  const isDanger = level === "danger";
  const progress =
    data.status === "playing" && data.total > 0
      ? Math.min(100, (data.elapsed / data.total) * 100)
      : 0;

  return (
    <div
      data-testid={`channel-panel-${data.id}`}
      className="relative flex flex-1 items-center overflow-hidden border-t border-neutral-800/80 px-[4vw]"
    >
      {/* left accent bar */}
      <div className={`absolute left-0 top-0 h-full w-[8px] ${style.accent}`} />

      <div className="flex w-full items-center justify-between gap-6">
        {/* label + filename */}
        <div className="flex min-w-0 flex-col gap-3">
          <div className="flex items-center gap-3">
            <span className="font-mono text-[1.6vw] font-bold uppercase tracking-[0.35em] text-neutral-400">
              CH{data.channel}
            </span>
            <span className="rounded-sm bg-neutral-800/70 px-2 py-0.5 font-mono text-[0.85vw] uppercase tracking-widest text-neutral-500">
              L{data.layer}
            </span>
            <StatusBadge status={data.status} />
          </div>
          <div
            data-testid={`channel-filename-${data.id}`}
            className="truncate font-mono text-[1.5vw] text-neutral-300"
            title={data.filename}
          >
            {data.filename || (data.status === "idle" ? "—" : "—")}
          </div>
        </div>

        {/* countdown */}
        <div className="shrink-0 text-right">
          {data.status === "playing" && (
            <div
              data-testid={`channel-timeleft-${data.id}`}
              className={`font-mono font-bold leading-none tabular-nums text-[13vw] ${style.text} ${style.glow} ${
                isDanger ? "animate-pulse" : ""
              }`}
            >
              {formatTimeLeft(data.time_left)}
            </div>
          )}
          {data.status === "live" && (
            <div
              data-testid={`channel-timeleft-${data.id}`}
              className={`font-mono font-bold leading-none text-[13vw] ${style.text}`}
            >
              --:--
            </div>
          )}
          {data.status === "idle" && (
            <div
              data-testid={`channel-timeleft-${data.id}`}
              className={`font-mono font-bold leading-none text-[13vw] ${style.text}`}
            >
              --:--
            </div>
          )}
        </div>
      </div>

      {/* progress bar */}
      <div className="absolute bottom-0 left-0 h-[6px] w-full bg-neutral-900">
        <div
          className={`h-full transition-[width] duration-200 ease-linear ${style.accent}`}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}

function StatusBadge({ status }) {
  if (status === "playing") {
    return (
      <span className="flex items-center gap-1.5 rounded-full bg-emerald-500/15 px-2.5 py-0.5 font-mono text-[0.85vw] uppercase tracking-widest text-emerald-400">
        <Clapperboard size="0.9em" /> On Air
      </span>
    );
  }
  if (status === "live") {
    return (
      <span className="flex items-center gap-1.5 rounded-full bg-sky-500/15 px-2.5 py-0.5 font-mono text-[0.85vw] uppercase tracking-widest text-sky-400">
        <Radio size="0.9em" /> Live
      </span>
    );
  }
  return (
    <span className="rounded-full bg-neutral-800/70 px-2.5 py-0.5 font-mono text-[0.85vw] uppercase tracking-widest text-neutral-500">
      Idle
    </span>
  );
}

function emptyChannel(id, channel, layer) {
  return {
    id,
    channel,
    layer,
    filename: "",
    elapsed: 0,
    total: 0,
    time_left: 0,
    status: "idle",
  };
}

export function TimerDisplay() {
  const now = useClock();
  const { state, connected } = useTimerSocket();

  const channels =
    state?.channels && state.channels.length
      ? state.channels
      : [emptyChannel("ch1", 1, 10), emptyChannel("ch2", 2, 10)];

  const oscConnected = state?.osc?.connected;

  return (
    <div
      data-testid="timer-display"
      className="flex h-screen w-screen flex-col overflow-hidden bg-black text-white"
    >
      {/* Clock */}
      <div className="flex flex-[0.9] flex-col items-center justify-center px-[4vw]">
        <div className="mb-2 font-mono text-[1.1vw] uppercase tracking-[0.6em] text-neutral-500">
          Local Time
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

      {/* Channels stacked */}
      <ChannelPanel data={channels[0]} />
      <ChannelPanel data={channels[1]} />

      {/* Connection footer */}
      <div className="flex items-center justify-between border-t border-neutral-900 px-[3vw] py-2 font-mono text-[0.8vw] uppercase tracking-widest">
        <span className="flex items-center gap-2 text-neutral-600">
          Timer CasparCG · OSC {state?.osc?.port ?? 7250}
        </span>
        <span
          data-testid="connection-status"
          className={`flex items-center gap-2 ${
            connected ? "text-neutral-500" : "text-red-500 animate-pulse"
          }`}
        >
          {connected ? (
            <>
              <span
                className={`h-2 w-2 rounded-full ${
                  oscConnected ? "bg-emerald-500" : "bg-amber-500"
                }`}
              />
              {oscConnected ? "OSC receiving" : "Waiting for CasparCG OSC"}
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
