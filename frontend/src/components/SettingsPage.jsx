import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Save, Loader2 } from "lucide-react";
import { useTimerSocket } from "@/hooks/useTimerSocket";

const API = "/api/settings";

function Field({ label, testId, ...props }) {
  return (
    <label className="flex flex-col gap-2">
      <span className="font-mono text-xs uppercase tracking-[0.2em] text-neutral-500">{label}</span>
      <input
        data-testid={testId}
        className="rounded-md border border-neutral-800 bg-neutral-950 px-4 py-3 font-mono text-lg text-white outline-none transition-colors focus:border-emerald-500"
        {...props}
      />
    </label>
  );
}

function Section({ title, children, aside }) {
  return (
    <section className="border-t border-neutral-900 py-8">
      <div className="mb-6 flex items-center justify-between">
        <h2 className="font-mono text-sm uppercase tracking-[0.3em] text-neutral-300">{title}</h2>
        {aside}
      </div>
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">{children}</div>
    </section>
  );
}

const SOURCE_LIST = [
  { id: "casparcg", label: "CasparCG" },
  { id: "vmix", label: "vMix" },
  { id: "ota", label: "OnTheAir" },
];

function SourceToggles({ sources, onToggle }) {
  return (
    <section className="py-8">
      <h2 className="mb-2 font-mono text-sm uppercase tracking-[0.3em] text-neutral-300">Surse active</h2>
      <p className="mb-5 text-sm text-neutral-500">Sursele oprite nu mai folosesc rețeaua și dispar din meniul de sus.</p>
      <div className="flex flex-wrap gap-3">
        {SOURCE_LIST.map((src) => {
          const on = sources[src.id];
          return (
            <button
              key={src.id}
              type="button"
              data-testid={`settings-source-${src.id}`}
              aria-pressed={on}
              onClick={() => onToggle(src.id)}
              className={`flex items-center gap-3 rounded-full border px-5 py-2.5 font-mono text-sm uppercase tracking-[0.15em] transition-colors ${on ? "border-emerald-500/60 bg-emerald-500/10 text-white" : "border-neutral-800 text-neutral-500 hover:text-neutral-300"}`}
            >
              <span className={`h-2 w-2 rounded-full ${on ? "bg-emerald-400" : "bg-neutral-700"}`} />
              {src.label}
              <span className="text-xs text-neutral-500">{on ? "Pornit" : "Oprit"}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

function StatusDot({ ok, label, testId }) {
  return (
    <span data-testid={testId} className="flex items-center gap-2 font-mono text-xs uppercase tracking-widest text-neutral-400">
      <span className={`h-2 w-2 rounded-full ${ok ? "bg-emerald-500" : "bg-red-500"}`} />
      {label}
    </span>
  );
}

export default function SettingsPage() {
  const { state } = useTimerSocket();
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);

  useEffect(() => {
    fetch(API).then((r) => r.json()).then((data) => setForm((prev) => prev ?? data)).catch(() => setMsg({ ok: false, text: "Nu pot citi setările" }));
  }, []);

  const set = (key) => (e) => {
    const value = e.target.value;
    setForm((f) => ({ ...f, [key]: value }));
  };
  const setCh = (i, key) => (e) => {
    const value = e.target.value;
    setForm((f) => ({ ...f, channels: f.channels.map((c, idx) => (idx === i ? { ...c, [key]: value } : c)) }));
  };

  const setOut = (i, key) => (e) => {
    const value = e.target.value;
    setForm((f) => ({ ...f, ota_outputs: f.ota_outputs.map((o, idx) => (idx === i ? { ...o, [key]: value } : o)) }));
  };

  const toggleSource = (id) => {
    setForm((f) => {
      const next = { ...f.sources, [id]: !f.sources[id] };
      return Object.values(next).some(Boolean) ? { ...f, sources: next } : f;
    });
  };

  const setMode = (mode) => {
    const base = mode === "api" ? 8081 : 9993;
    setForm((f) => ({ ...f, ota_mode: mode, ota_outputs: f.ota_outputs.map((o, i) => ({ ...o, port: base + i })) }));
  };

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    setMsg(null);
    const body = {
      vmix_host: String(form.vmix_host).trim(),
      vmix_port: Number(form.vmix_port),
      osc_port: Number(form.osc_port),
      ota_host: String(form.ota_host).trim(),
      ota_mode: form.ota_mode,
      ota_count: Number(form.ota_count),
      sources: form.sources,
      ota_outputs: form.ota_outputs.map((o) => ({ name: String(o.name).trim(), port: Number(o.port) })),
      channels: form.channels.map((c) => ({ channel: Number(c.channel), layer: Number(c.layer) })),
    };
    try {
      const r = await fetch(API, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      if (!r.ok) throw new Error();
      setForm(await r.json());
      setMsg({ ok: true, text: "Salvat. Setările sunt active imediat." });
    } catch {
      setMsg({ ok: false, text: "Valori invalide. Verifică IP-ul și porturile." });
    } finally {
      setSaving(false);
    }
  };

  const vmix = state?.vmix;
  const osc = state?.osc;
  const ota = state?.ota;

  return (
    <div data-testid="settings-page" className="min-h-screen bg-black px-8 py-10 text-white sm:px-16">
      <div className="mx-auto max-w-3xl">
        <Link to="/" data-testid="settings-back-link" className="mb-10 inline-flex items-center gap-2 font-mono text-xs uppercase tracking-[0.2em] text-neutral-500 transition-colors hover:text-white">
          <ArrowLeft size={14} /> Înapoi la timer
        </Link>
        <h1 className="mb-2 text-4xl font-semibold tracking-tight sm:text-5xl">Setări</h1>
        <p className="mb-8 text-sm text-neutral-500">Modificările se aplică imediat, fără restart.</p>

        {!form ? (
          <Loader2 className="animate-spin text-neutral-500" data-testid="settings-loading" />
        ) : (
          <form onSubmit={save}>
            <SourceToggles sources={form.sources} onToggle={toggleSource} />
            <Section title="vMix" aside={vmix && form.sources.vmix && <StatusDot testId="settings-vmix-status" ok={vmix.connected} label={vmix.connected ? "Conectat" : "Deconectat"} />}>
              <Field label="IP vMix" testId="settings-vmix-host" value={form.vmix_host} onChange={set("vmix_host")} placeholder="172.16.50.25" required />
              <Field label="Port vMix" testId="settings-vmix-port" type="number" min={1} max={65535} value={form.vmix_port} onChange={set("vmix_port")} required />
            </Section>

            <Section title="OnTheAir Video" aside={ota && form.sources.ota && <StatusDot testId="settings-ota-status" ok={ota.outputs.every((o) => o.connected)} label={`${ota.outputs.filter((o) => o.connected).length}/${ota.outputs.length} conectate`} />}>
              <Field label="IP Mac OnTheAir" testId="settings-ota-host" value={form.ota_host} onChange={set("ota_host")} placeholder="192.168.1.100" required />
              <div className="flex flex-col gap-2">
                <span className="font-mono text-xs uppercase tracking-[0.2em] text-neutral-500">Conexiune</span>
                <div data-testid="settings-ota-mode" className="flex gap-1 rounded-md border border-neutral-800 bg-neutral-950 p-1">
                  {[
                    { id: "api", label: "REST API" },
                    { id: "hyperdeck", label: "HyperDeck" },
                  ].map((m) => (
                    <button
                      key={m.id}
                      type="button"
                      data-testid={`settings-ota-mode-${m.id}`}
                      onClick={() => setMode(m.id)}
                      className={`flex-1 rounded px-3 py-2.5 font-mono text-sm uppercase tracking-[0.15em] transition-colors ${form.ota_mode === m.id ? "bg-white text-black" : "text-neutral-400 hover:text-white"}`}
                    >
                      {m.label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex flex-col gap-2 sm:col-span-2">
                <span className="font-mono text-xs uppercase tracking-[0.2em] text-neutral-500">Câte playere folosești</span>
                <div data-testid="settings-ota-count" className="flex gap-1 rounded-md border border-neutral-800 bg-neutral-950 p-1">
                  {form.ota_outputs.map((_, i) => (
                    <button
                      key={i}
                      type="button"
                      data-testid={`settings-ota-count-${i + 1}`}
                      aria-pressed={form.ota_count === i + 1}
                      onClick={() => setForm((f) => ({ ...f, ota_count: i + 1 }))}
                      className={`flex-1 rounded px-3 py-2.5 font-mono text-sm uppercase tracking-[0.15em] transition-colors ${form.ota_count === i + 1 ? "bg-white text-black" : "text-neutral-400 hover:text-white"}`}
                    >
                      {i + 1}
                    </button>
                  ))}
                </div>
              </div>
              {form.ota_outputs.slice(0, form.ota_count).map((o, i) => (
                <div key={i} className="contents">
                  <Field label={`Output ${i + 1} · Nume pe ecran`} testId={`settings-ota-out${i + 1}-name`} value={o.name} maxLength={40} onChange={setOut(i, "name")} required />
                  <Field label={`Output ${i + 1} · Port ${form.ota_mode === "api" ? "API" : "HyperDeck"}`} testId={`settings-ota-out${i + 1}-port`} type="number" min={1} max={65535} value={o.port} onChange={setOut(i, "port")} required />
                </div>
              ))}
            </Section>

            <Section title="CasparCG (OSC)" aside={osc && form.sources.casparcg && <StatusDot testId="settings-osc-status" ok={osc.listening} label={osc.listening ? "Ascultă" : "Port blocat"} />}>
              <Field label="Port OSC (UDP)" testId="settings-osc-port" type="number" min={1} max={65535} value={form.osc_port} onChange={set("osc_port")} required />
              <div />
              {form.channels.map((c, i) => (
                <div key={c.id} className="contents">
                  <Field label={`Timer ${i + 1} · Canal`} testId={`settings-ch${i + 1}-channel`} type="number" min={1} value={c.channel} onChange={setCh(i, "channel")} required />
                  <Field label={`Timer ${i + 1} · Layer`} testId={`settings-ch${i + 1}-layer`} type="number" min={0} value={c.layer} onChange={setCh(i, "layer")} required />
                </div>
              ))}
            </Section>

            <div className="flex items-center gap-6 border-t border-neutral-900 pt-8">
              <button type="submit" disabled={saving} data-testid="settings-save-button" className="inline-flex items-center gap-2 rounded-full bg-white px-6 py-3 font-mono text-sm uppercase tracking-[0.2em] text-black transition-opacity hover:opacity-80 disabled:opacity-50">
                {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />} Salvează
              </button>
              {msg && (
                <span data-testid="settings-message" className={`text-sm ${msg.ok ? "text-emerald-400" : "text-red-400"}`}>{msg.text}</span>
              )}
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
