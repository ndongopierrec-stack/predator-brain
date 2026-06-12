"use client";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Target, Plus, CheckCircle, Loader2, BarChart2 } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { clvApi } from "@/lib/api";
import { BarChart, Bar, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis, LineChart, Line, CartesianGrid } from "recharts";

function DarkTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="px-3 py-2 rounded-xl text-[11px]"
      style={{ background: "#0d1829", border: "1px solid rgba(255,255,255,0.1)" }}>
      <p style={{ color: "rgba(255,255,255,0.4)" }}>{label}</p>
      {payload.map((p: any, i: number) => (
        <p key={i} style={{ color: p.color }} className="font-bold">{p.name}: {typeof p.value === "number" ? p.value.toFixed(2) : p.value}</p>
      ))}
    </div>
  );
}

const CLV_SIGNAL_COLORS: Record<string, string> = {
  EXCELLENT: "#4ade80",
  GOOD:      "#86efac",
  NEUTRAL:   "#94a3b8",
  BAD:       "#f87171",
  TERRIBLE:  "#ef4444",
};

const DEMO_BETS = [
  { bet_id: "1", teams: "Arsenal vs Chelsea",    market: "BTTS Oui",     odds_taken: 1.85, odds_closing: 1.62, clv_pct: 14.2, clv_signal: "EXCELLENT", result_actual: "WON",  profit: 8.5  },
  { bet_id: "2", teams: "Real Madrid vs Barça",  market: "O/U 2.5 Over", odds_taken: 1.90, odds_closing: 1.78, clv_pct: 6.7,  clv_signal: "GOOD",      result_actual: "WON",  profit: 9.0  },
  { bet_id: "3", teams: "PSG vs OM",             market: "Domicile",     odds_taken: 1.42, odds_closing: 1.48, clv_pct: -4.1, clv_signal: "BAD",        result_actual: "WON",  profit: 4.2  },
  { bet_id: "4", teams: "Bayern vs Leipzig",     market: "Domicile",     odds_taken: 1.55, odds_closing: 1.45, clv_pct: 6.9,  clv_signal: "GOOD",       result_actual: "WON",  profit: 5.5  },
  { bet_id: "5", teams: "Liverpool vs Everton",  market: "BTTS Oui",     odds_taken: 1.72, odds_closing: 1.85, clv_pct: -7.0, clv_signal: "BAD",        result_actual: "LOST", profit: -10  },
];

// Répartition CLV demo
const DIST_DATA = [
  { signal: "EXCELLENT", count: 12, color: "#4ade80" },
  { signal: "GOOD",      count: 28, color: "#86efac" },
  { signal: "NEUTRAL",   count: 15, color: "#94a3b8" },
  { signal: "BAD",       count: 8,  color: "#f87171" },
  { signal: "TERRIBLE",  count: 3,  color: "#ef4444" },
];

// CLV cumulatif demo
const CLV_CURVE = Array.from({ length: 30 }, (_, i) => ({
  paris: i + 1,
  clv: (i + 1) * 0.18 + Math.sin(i) * 0.5,
}));

export default function CLVPage() {
  const [form, setForm] = useState({
    teams: "", league: "PL", market: "BTTS Oui", bookmaker: "Pinnacle",
    odds_taken: "", stake: "10", prob_model: "", model_edge: "",
  });
  const [showForm, setShowForm] = useState(false);

  const { data: summary } = useQuery({
    queryKey: ["clv-summary"],
    queryFn: () => clvApi.summary().then(r => r.data),
  });

  const record = useMutation({
    mutationFn: () => clvApi.recordBet({
      ...form,
      odds_taken: parseFloat(form.odds_taken),
      stake: parseFloat(form.stake),
      prob_model: form.prob_model ? parseFloat(form.prob_model) / 100 : undefined,
      model_edge_at_placement: form.model_edge ? parseFloat(form.model_edge) / 100 : undefined,
    }).then(r => r.data),
    onSuccess: () => setShowForm(false),
  });

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "var(--bg-app)" }}>
      <Sidebar />
      <main className="ml-56 flex-1 overflow-y-auto">

        <header className="topbar px-8 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-[15px] font-bold text-white flex items-center gap-2">
              <Target size={14} style={{ color: "#8b5cf6" }} />
              CLV — Closing Line Value
              <span className="text-[9px] font-black px-2 py-0.5 rounded-full"
                style={{ background: "rgba(139,92,246,0.15)", color: "#c4b5fd" }}>PRO</span>
            </h1>
            <p className="text-[11px] mt-0.5" style={{ color: "rgba(255,255,255,0.3)" }}>
              Battre le marché sur 500 paris · Le seul vrai indicateur de long terme
            </p>
          </div>
          <button className="btn-primary" onClick={() => setShowForm(!showForm)}>
            <Plus size={12} /> Enregistrer un pari
          </button>
        </header>

        <div className="px-8 py-7 space-y-5 animate-fade-in">

          {/* Formulaire enregistrement */}
          {showForm && (
            <div className="card p-6">
              <p className="label-caps mb-5">Enregistrer un pari (avant fermeture des cotes)</p>
              <div className="grid grid-cols-3 gap-4 mb-4">
                <div className="col-span-2">
                  <label className="label-caps block mb-2">Match (équipes)</label>
                  <input className="input-pro" placeholder="Arsenal vs Chelsea"
                    value={form.teams} onChange={e => setForm({ ...form, teams: e.target.value })} />
                </div>
                <div>
                  <label className="label-caps block mb-2">Ligue</label>
                  <select className="input-pro" value={form.league} onChange={e => setForm({ ...form, league: e.target.value })}>
                    {["PL","LaLiga","BL1","L1","SerA"].map(l => <option key={l}>{l}</option>)}
                  </select>
                </div>
                <div>
                  <label className="label-caps block mb-2">Marché</label>
                  <input className="input-pro" value={form.market}
                    onChange={e => setForm({ ...form, market: e.target.value })} />
                </div>
                <div>
                  <label className="label-caps block mb-2">Bookmaker</label>
                  <input className="input-pro" value={form.bookmaker}
                    onChange={e => setForm({ ...form, bookmaker: e.target.value })} />
                </div>
                <div>
                  <label className="label-caps block mb-2">Cote prise</label>
                  <input className="input-pro" type="number" step="0.01" placeholder="2.10"
                    value={form.odds_taken} onChange={e => setForm({ ...form, odds_taken: e.target.value })} />
                </div>
                <div>
                  <label className="label-caps block mb-2">Mise (€)</label>
                  <input className="input-pro" type="number" value={form.stake}
                    onChange={e => setForm({ ...form, stake: e.target.value })} />
                </div>
                <div>
                  <label className="label-caps block mb-2">P_modèle (%)</label>
                  <input className="input-pro" type="number" step="0.1" placeholder="58.0"
                    value={form.prob_model} onChange={e => setForm({ ...form, prob_model: e.target.value })} />
                </div>
                <div>
                  <label className="label-caps block mb-2">Edge modèle (%)</label>
                  <input className="input-pro" type="number" step="0.1" placeholder="6.2"
                    value={form.model_edge} onChange={e => setForm({ ...form, model_edge: e.target.value })} />
                </div>
              </div>
              <div className="flex gap-3">
                <button className="btn-primary" onClick={() => record.mutate()} disabled={record.isPending}>
                  {record.isPending ? <><Loader2 size={12} className="animate-spin" /> Enregistrement...</> : <><CheckCircle size={12} /> Enregistrer</>}
                </button>
                <button className="btn-ghost" onClick={() => setShowForm(false)}>Annuler</button>
              </div>
            </div>
          )}

          {/* KPIs CLV */}
          <div className="grid grid-cols-5 gap-3">
            {[
              { label: "CLV moyen",       value: summary ? `+${summary.avg_clv_pct.toFixed(1)}%` : "+4.8%", color: "#8b5cf6" },
              { label: "CLV médian",      value: summary ? `+${summary.median_clv_pct?.toFixed(1) ?? "3.2"}%` : "+3.2%", color: "#a5b4fc" },
              { label: "ROI réel",        value: summary ? `+${summary.roi_actual.toFixed(1)}%` : "+3.1%",   color: "#4ade80" },
              { label: "CLV positif",     value: summary ? `${summary.pct_positive?.toFixed(0) ?? "68"}%` : "68%", color: "#fbbf24" },
              { label: "Paris trackés",   value: summary ? summary.total_bets.toString() : "66",              color: "#67e8f9" },
            ].map(({ label, value, color }) => (
              <div key={label} className="metric-card">
                <p className="label-caps mb-2">{label}</p>
                <p className="text-[1.3rem] font-black tabular-nums" style={{ color }}>{value}</p>
              </div>
            ))}
          </div>

          {/* CLV curve + distribution */}
          <div className="grid grid-cols-[1.5fr_1fr] gap-5">
            {/* CLV cumulatif */}
            <div className="card p-6">
              <p className="label-caps mb-4 flex items-center gap-2"><BarChart2 size={11} /> CLV cumulatif</p>
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={CLV_CURVE}>
                  <CartesianGrid stroke="rgba(255,255,255,0.04)" strokeDasharray="4 4" />
                  <XAxis dataKey="paris" stroke="rgba(255,255,255,0.15)" tick={{ fontSize: 10 }} />
                  <YAxis stroke="rgba(255,255,255,0.15)" tick={{ fontSize: 10 }} />
                  <Tooltip content={<DarkTooltip />} />
                  <Line type="monotone" dataKey="clv" name="CLV (%)" stroke="#8b5cf6" strokeWidth={2}
                    dot={false} style={{ filter: "drop-shadow(0 0 5px rgba(139,92,246,0.6))" }} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Distribution */}
            <div className="card p-6">
              <p className="label-caps mb-4">Répartition CLV</p>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={DIST_DATA} layout="vertical">
                  <XAxis type="number" stroke="rgba(255,255,255,0.15)" tick={{ fontSize: 10 }} />
                  <YAxis type="category" dataKey="signal" stroke="rgba(255,255,255,0.15)" tick={{ fontSize: 10 }} width={65} />
                  <Tooltip content={<DarkTooltip />} />
                  <Bar dataKey="count" name="Paris" radius={[0, 4, 4, 0]}>
                    {DIST_DATA.map((d, i) => <Cell key={i} fill={d.color} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Historique des paris CLV */}
          <div className="card overflow-hidden">
            <div className="px-5 py-3 flex items-center justify-between"
              style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
              <p className="label-caps">Historique CLV</p>
              <p className="text-[10px]" style={{ color: "rgba(255,255,255,0.25)" }}>
                CLV = (cote_prise / cote_clôture − 1) × 100
              </p>
            </div>
            <div className="grid text-[9px] font-bold uppercase tracking-widest px-5 py-2.5"
              style={{ gridTemplateColumns: "2fr 1fr 80px 80px 80px 80px 70px",
                color: "rgba(255,255,255,0.2)", borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
              <span>Match · Marché</span>
              <span>BM</span>
              <span className="text-right">Cote prise</span>
              <span className="text-right">Cote clôture</span>
              <span className="text-center">CLV</span>
              <span className="text-center">Signal</span>
              <span className="text-center">Résultat</span>
            </div>

            {DEMO_BETS.map((b, i) => {
              const sc = CLV_SIGNAL_COLORS[b.clv_signal] ?? "#94a3b8";
              return (
                <div key={b.bet_id} className="grid items-center px-5 py-3.5"
                  style={{ gridTemplateColumns: "2fr 1fr 80px 80px 80px 80px 70px",
                    borderBottom: i < DEMO_BETS.length - 1 ? "1px solid rgba(255,255,255,0.03)" : "none" }}>
                  <div>
                    <p className="text-[12px] font-semibold text-white">{b.teams}</p>
                    <p className="text-[10px]" style={{ color: "rgba(255,255,255,0.3)" }}>{b.market}</p>
                  </div>
                  <span className="text-[11px]" style={{ color: "rgba(255,255,255,0.4)" }}>Pinnacle</span>
                  <span className="text-[13px] font-bold tabular-nums text-right text-white">{b.odds_taken.toFixed(2)}</span>
                  <span className="text-[13px] font-bold tabular-nums text-right" style={{ color: "rgba(255,255,255,0.5)" }}>{b.odds_closing.toFixed(2)}</span>
                  <span className="text-[13px] font-black tabular-nums text-center" style={{ color: b.clv_pct >= 0 ? "#4ade80" : "#f87171" }}>
                    {b.clv_pct >= 0 ? "+" : ""}{b.clv_pct.toFixed(1)}%
                  </span>
                  <span className="text-[9px] font-bold text-center" style={{ color: sc }}>{b.clv_signal}</span>
                  <span className={`text-[10px] font-bold text-center ${b.result_actual === "WON" ? "text-green-400" : "text-red-400"}`}>
                    {b.result_actual === "WON" ? "✓ Gagné" : "✗ Perdu"}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Note pédagogique */}
          <div className="px-5 py-4 rounded-xl" style={{ background: "rgba(139,92,246,0.06)", border: "1px solid rgba(139,92,246,0.15)" }}>
            <p className="text-[11px]" style={{ color: "rgba(255,255,255,0.5)" }}>
              <strong style={{ color: "#c4b5fd" }}>Pourquoi le CLV ?</strong> Un CLV moyen positif sur 500+ paris
              signifie que vous battez le marché de façon systématique. Le win rate seul est insuffisant :
              un CLV positif à 54% de win rate vaut mieux qu'un CLV négatif à 60%. Le marché est le meilleur
              estimateur de la probabilité réelle. Si votre cote était meilleure que la cote finale — vous étiez
              du bon côté.
            </p>
          </div>

        </div>
      </main>
    </div>
  );
}
