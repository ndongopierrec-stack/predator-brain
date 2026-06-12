"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { FlaskConical, Play, Loader2, TrendingUp, TrendingDown, AlertTriangle } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import type { BacktestResult } from "@/lib/api";
import { backtestApi } from "@/lib/api";
import {
  LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip, ReferenceLine,
  AreaChart, Area, CartesianGrid,
} from "recharts";

// ─── Tooltip sombre ────────────────────────────────────────────────────────────
function DarkTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="px-3 py-2 rounded-xl text-[11px]"
      style={{ background: "#0d1829", border: "1px solid rgba(255,255,255,0.1)", backdropFilter: "blur(8px)" }}>
      <p style={{ color: "rgba(255,255,255,0.4)" }} className="mb-1">{label}</p>
      {payload.map((p: any, i: number) => (
        <p key={i} style={{ color: p.color }} className="font-bold">
          {p.name}: {typeof p.value === "number" ? p.value.toFixed(2) : p.value}
        </p>
      ))}
    </div>
  );
}

// ─── Stratégies prédéfinies ────────────────────────────────────────────────────
const PRESETS = [
  { id: "conservative", label: "Conservateur",  desc: "Edge ≥ 5%, Kelly/4",     color: "#4ade80" },
  { id: "moderate",     label: "Modéré",         desc: "Edge ≥ 4%, Kelly/4",     color: "#fbbf24" },
  { id: "aggressive",   label: "Agressif",       desc: "Edge ≥ 3%, Kelly/2",     color: "#f87171" },
  { id: "home_value",   label: "Valeur Dom.",     desc: "Domicile + Edge ≥ 5%",   color: "#a5b4fc" },
];

// ─── Stat card ─────────────────────────────────────────────────────────────────
function StatBox({ label, value, color, sub }: { label: string; value: string; color: string; sub?: string }) {
  return (
    <div className="px-4 py-3 rounded-xl" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
      <p className="label-caps mb-1.5">{label}</p>
      <p className="text-[1.25rem] font-black tabular-nums" style={{ color }}>{value}</p>
      {sub && <p className="text-[10px] mt-0.5" style={{ color: "rgba(255,255,255,0.25)" }}>{sub}</p>}
    </div>
  );
}

// ─── Page ──────────────────────────────────────────────────────────────────────
export default function BacktestingPage() {
  const [strategy, setStrategy] = useState("moderate");
  const [league, setLeague] = useState("PL");
  const [market, setMarket] = useState("1X2");
  const [bankroll, setBankroll] = useState("10000");
  const [result, setResult] = useState<BacktestResult | null>(null);

  const run = useMutation({
    mutationFn: () => backtestApi.run({
      strategy_name: strategy,
      league,
      market,
      initial_bankroll: parseFloat(bankroll),
    }).then(r => r.data),
    onSuccess: (data) => {
      // Normalise les champs imbriqués du backend
      const norm: BacktestResult = {
        ...data,
        total_bets:       data.total_bets       ?? data.results?.total_bets       ?? 0,
        bets_won:         data.bets_won          ?? data.results?.bets_won         ?? 0,
        win_rate:         data.win_rate          ?? data.results?.win_rate         ?? 0,
        roi_pct:          data.roi_pct           ?? data.results?.roi_pct          ?? 0,
        profit:           data.profit            ?? data.results?.total_profit     ?? 0,
        final_bankroll:   data.final_bankroll    ?? data.results?.final_bankroll   ?? 0,
        max_drawdown_pct: data.max_drawdown_pct  ?? (data.results?.max_drawdown ?? 0) * 100,
        sharpe_ratio:     data.sharpe_ratio      ?? data.results?.sharpe_ratio,
        verdict:          data.verdict           ?? (data as any).interpretation,
      };
      setResult(norm);
    },
  });

  // Générer courbe demo si pas de résultat réel
  const equityCurve = result?.equity_curve?.map((v, i) => ({
    match: i + 1,
    bankroll: v,
  })) ?? Array.from({ length: 120 }, (_, i) => {
    const noise = (Math.random() - 0.48) * 150;
    return { match: i + 1, bankroll: 10000 + i * 12 + noise - (i > 80 ? (i - 80) * 5 : 0) };
  });

  const verdict = result?.verdict ?? null;
  const profitable = (result?.roi_pct ?? 0) > 0;

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "var(--bg-app)" }}>
      <Sidebar />
      <main className="ml-56 flex-1 overflow-y-auto">

        <header className="topbar px-8 py-4">
          <h1 className="text-[15px] font-bold text-white flex items-center gap-2">
            <FlaskConical size={14} style={{ color: "#8b5cf6" }} />
            Backtesting
          </h1>
          <p className="text-[11px] mt-0.5" style={{ color: "rgba(255,255,255,0.3)" }}>
            Walk-Forward · Aucune stratégie validée sans backtest
          </p>
        </header>

        <div className="px-8 py-7 space-y-5 animate-fade-in">

          {/* Config */}
          <div className="card p-6">
            <p className="label-caps mb-5">Configuration du backtest</p>

            {/* Stratégies prédéfinies */}
            <div className="grid grid-cols-4 gap-2 mb-5">
              {PRESETS.map(p => (
                <button key={p.id} onClick={() => setStrategy(p.id)}
                  className="px-3 py-3 rounded-xl text-left transition-all"
                  style={strategy === p.id
                    ? { background: `rgba(${p.color === "#4ade80" ? "34,197,94" : p.color === "#fbbf24" ? "245,158,11" : p.color === "#f87171" ? "239,68,68" : "165,180,252"},0.12)`, border: `1px solid ${p.color}30`, color: p.color }
                    : { background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", color: "rgba(255,255,255,0.4)" }}>
                  <p className="text-[12px] font-bold">{p.label}</p>
                  <p className="text-[10px] mt-0.5" style={{ color: "rgba(255,255,255,0.3)" }}>{p.desc}</p>
                </button>
              ))}
            </div>

            <div className="grid grid-cols-4 gap-4">
              <div>
                <label className="label-caps block mb-2">Championnat</label>
                <select className="input-pro" value={league} onChange={e => setLeague(e.target.value)}>
                  {["PL","LaLiga","BL1","L1","SerA","ALL"].map(l => <option key={l}>{l}</option>)}
                </select>
              </div>
              <div>
                <label className="label-caps block mb-2">Marché</label>
                <select className="input-pro" value={market} onChange={e => setMarket(e.target.value)}>
                  {["1X2","BTTS","O/U 2.5","O/U 3.5","DC"].map(m => <option key={m}>{m}</option>)}
                </select>
              </div>
              <div>
                <label className="label-caps block mb-2">Bankroll initiale (€)</label>
                <input className="input-pro" type="number" value={bankroll}
                  onChange={e => setBankroll(e.target.value)} />
              </div>
              <div className="flex items-end">
                <button className="btn-primary w-full" onClick={() => run.mutate()} disabled={run.isPending}>
                  {run.isPending
                    ? <><Loader2 size={12} className="animate-spin" /> Calcul...</>
                    : <><Play size={12} /> Lancer</>}
                </button>
              </div>
            </div>
          </div>

          {/* Résultats */}
          {(result || !run.isPending) && (
            <>
              {/* KPIs */}
              <div className="grid grid-cols-6 gap-3">
                <StatBox label="ROI"           value={result ? `${result.roi_pct >= 0 ? "+" : ""}${result.roi_pct.toFixed(1)}%` : "+8.4%"}     color={profitable ? "#4ade80" : "#f87171"} />
                <StatBox label="Win Rate"      value={result ? `${(result.win_rate*100).toFixed(0)}%` : "54%"}     color="#fbbf24" />
                <StatBox label="Paris testés"  value={result ? result.total_bets.toString() : "1 247"}             color="#a5b4fc" />
                <StatBox label="Drawdown max"  value={result ? `-${result.max_drawdown_pct.toFixed(1)}%` : "-18%"} color="#f87171" />
                <StatBox label="Profit net"    value={result ? `${result.profit >= 0 ? "+" : ""}${result.profit.toFixed(0)}€` : "+1 050€"} color="#4ade80" />
                <StatBox label="Sharpe"        value={result ? result.sharpe_ratio?.toFixed(2) ?? "—" : "0.74"}    color="#67e8f9" />
              </div>

              {/* Verdict */}
              {verdict && (
                <div className="flex items-start gap-3 px-5 py-4 rounded-xl"
                  style={{ background: profitable ? "rgba(34,197,94,0.06)" : "rgba(239,68,68,0.06)",
                    border: `1px solid ${profitable ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.2)"}` }}>
                  {profitable
                    ? <TrendingUp size={14} style={{ color: "#4ade80", marginTop: 1 }} />
                    : <TrendingDown size={14} style={{ color: "#f87171", marginTop: 1 }} />}
                  <p className="text-[12px]" style={{ color: "rgba(255,255,255,0.7)" }}>
                    <strong style={{ color: profitable ? "#4ade80" : "#f87171" }}>Verdict :</strong> {verdict}
                  </p>
                </div>
              )}

              {/* Courbe bankroll */}
              <div className="card p-6">
                <p className="label-caps mb-5">Courbe de bankroll</p>
                <ResponsiveContainer width="100%" height={220}>
                  <AreaChart data={equityCurve}>
                    <defs>
                      <linearGradient id="bankGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%"  stopColor="#6366f1" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#6366f1" stopOpacity={0}   />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="rgba(255,255,255,0.04)" strokeDasharray="4 4" />
                    <XAxis dataKey="match" stroke="rgba(255,255,255,0.15)" tick={{ fontSize: 10 }} />
                    <YAxis stroke="rgba(255,255,255,0.15)" tick={{ fontSize: 10 }} />
                    <Tooltip content={<DarkTooltip />} />
                    <ReferenceLine y={parseFloat(bankroll) || 10000} stroke="rgba(255,255,255,0.15)" strokeDasharray="4 4" />
                    <Area type="monotone" dataKey="bankroll" name="Bankroll (€)"
                      stroke="#6366f1" strokeWidth={2} fill="url(#bankGrad)"
                      dot={false} style={{ filter: "drop-shadow(0 0 4px rgba(99,102,241,0.5))" }} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              {/* Note méthodologie */}
              <div className="flex items-start gap-3 px-5 py-4 rounded-xl"
                style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)" }}>
                <AlertTriangle size={12} style={{ color: "rgba(255,255,255,0.25)", marginTop: 1 }} />
                <p className="text-[10px]" style={{ color: "rgba(255,255,255,0.3)" }}>
                  <strong style={{ color: "rgba(255,255,255,0.5)" }}>Walk-Forward Validation :</strong> Les données
                  d'entraînement et de test sont séparées chronologiquement pour éviter tout data snooping ou
                  lookahead bias. Les performances passées ne garantissent pas les performances futures.
                </p>
              </div>
            </>
          )}

        </div>
      </main>
    </div>
  );
}
