"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Wallet, Calculator, AlertTriangle, TrendingUp, Shield, Loader2 } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { bankrollApi } from "@/lib/api";
import { AreaChart, Area, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid, ReferenceLine } from "recharts";

function DarkTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="px-3 py-2 rounded-xl text-[11px]"
      style={{ background: "#0d1829", border: "1px solid rgba(255,255,255,0.1)" }}>
      <p style={{ color: "rgba(255,255,255,0.4)" }}>{label}</p>
      {payload.map((p: any, i: number) => (
        <p key={i} style={{ color: p.color }} className="font-bold">{p.name}: {p.value?.toFixed(2)}</p>
      ))}
    </div>
  );
}

const STRATEGY_OPTIONS = [
  { value: "FLAT",          label: "Flat (mise fixe)" },
  { value: "FLAT_PCT",      label: "Flat % de bankroll" },
  { value: "KELLY_FULL",    label: "Kelly complet" },
  { value: "KELLY_HALF",    label: "Kelly ½" },
  { value: "KELLY_QUARTER", label: "Kelly ¼ (recommandé)" },
  { value: "KELLY_TENTH",   label: "Kelly 1/10" },
];

const RISK_COLORS: Record<string, string> = {
  CONSERVATIVE: "#4ade80",
  MODERATE:     "#fbbf24",
  AGGRESSIVE:   "#f87171",
  VERY_HIGH:    "#ef4444",
};

export default function BankrollPage() {
  const qc = useQueryClient();

  // Formulaire Kelly
  const [edge, setEdge]       = useState("5.0");
  const [odds, setOdds]       = useState("2.00");
  const [prob, setProb]       = useState("55");
  const [strat, setStrat]     = useState("KELLY_QUARTER");
  const [stakeResult, setStakeResult] = useState<any>(null);

  const { data: snap }  = useQuery({ queryKey: ["bankroll-snapshot"],    queryFn: () => bankrollApi.snapshot().then(r => r.data),    refetchInterval: 30_000 });
  const { data: perf }  = useQuery({ queryKey: ["bankroll-performance"], queryFn: () => bankrollApi.performance().then(r => r.data) });
  const { data: alerts } = useQuery({ queryKey: ["bankroll-alerts"],     queryFn: () => bankrollApi.alerts().then(r => r.data) });

  const calcStake = useMutation({
    mutationFn: () => bankrollApi.calculateStake({
      edge_pct: parseFloat(edge),
      odds: parseFloat(odds),
      prob_model: parseFloat(prob) / 100,
      bankroll: 10000,
      strategy: strat,
    }).then(r => r.data),
    onSuccess: setStakeResult,
  });

  // Courbe equity demo
  const equityCurve = snap?.equity_curve?.length
    ? snap.equity_curve.map((v: number, i: number) => ({ day: `J${i + 1}`, val: v }))
    : Array.from({ length: 30 }, (_, i) => ({ day: `J${i + 1}`, val: 10000 + i * 25 + (Math.random() - 0.4) * 120 }));

  const initialBankroll = 10000;

  // Alertes
  const alertList: { msg: string; level: "warning" | "danger" | "critical" }[] = alerts?.alerts ?? [];

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "var(--bg-app)" }}>
      <Sidebar />
      <main className="ml-56 flex-1 overflow-y-auto">

        <header className="topbar px-8 py-4">
          <h1 className="text-[15px] font-bold text-white flex items-center gap-2">
            <Wallet size={14} style={{ color: "#22c55e" }} />
            Bankroll
          </h1>
          <p className="text-[11px] mt-0.5" style={{ color: "rgba(255,255,255,0.3)" }}>
            Gestion du risque · Kelly Criterion · Drawdown tracker
          </p>
        </header>

        <div className="px-8 py-7 space-y-5 animate-fade-in">

          {/* Alertes */}
          {alertList.length > 0 && (
            <div className="space-y-2">
              {alertList.map((a, i) => (
                <div key={i} className="flex items-center gap-3 px-4 py-3 rounded-xl"
                  style={{
                    background: a.level === "critical" ? "rgba(239,68,68,0.1)" : a.level === "danger" ? "rgba(239,68,68,0.07)" : "rgba(245,158,11,0.07)",
                    border: `1px solid ${a.level === "critical" ? "rgba(239,68,68,0.3)" : a.level === "danger" ? "rgba(239,68,68,0.2)" : "rgba(245,158,11,0.2)"}`,
                  }}>
                  <AlertTriangle size={13} style={{ color: a.level === "warning" ? "#fbbf24" : "#f87171" }} />
                  <p className="text-[12px]" style={{ color: "rgba(255,255,255,0.7)" }}>{a.msg}</p>
                </div>
              ))}
            </div>
          )}

          {/* KPIs snapshot */}
          <div className="grid grid-cols-5 gap-3">
            {[
              { label: "Bankroll",       value: snap ? `${snap.total.toLocaleString("fr-FR")} €` : "10 000 €",                           color: "#4ade80" },
              { label: "Profit/Perte",   value: snap ? `${snap.total - initialBankroll >= 0 ? "+" : ""}${(snap.total - initialBankroll).toFixed(0)} €` : "+0 €", color: "#6366f1" },
              { label: "ROI",            value: perf ? `${(perf.roi_pct >= 0 ? "+" : "")}${perf.roi_pct.toFixed(1)}%` : "—",             color: "#fbbf24" },
              { label: "Drawdown max",   value: snap ? `-${snap.drawdown_max?.toFixed(1) ?? 0}%` : "0%",                               color: "#f87171" },
              { label: "Exposition",     value: snap ? `${snap.exposure_pct?.toFixed(1) ?? 0}%` : "0%",                                  color: "#a5b4fc" },
            ].map(({ label, value, color }) => (
              <div key={label} className="metric-card">
                <p className="label-caps mb-2">{label}</p>
                <p className="text-[1.2rem] font-black tabular-nums" style={{ color }}>{value}</p>
              </div>
            ))}
          </div>

          {/* Courbe equity */}
          <div className="card p-6">
            <p className="label-caps mb-5">Évolution de la bankroll</p>
            <ResponsiveContainer width="100%" height={180}>
              <AreaChart data={equityCurve}>
                <defs>
                  <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#22c55e" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#22c55e" stopOpacity={0}    />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(255,255,255,0.04)" strokeDasharray="4 4" />
                <XAxis dataKey="day"  stroke="rgba(255,255,255,0.15)" tick={{ fontSize: 10 }} />
                <YAxis stroke="rgba(255,255,255,0.15)" tick={{ fontSize: 10 }} />
                <Tooltip content={<DarkTooltip />} />
                <ReferenceLine y={initialBankroll} stroke="rgba(255,255,255,0.15)" strokeDasharray="4 4" />
                <Area type="monotone" dataKey="val" name="Bankroll (€)"
                  stroke="#22c55e" strokeWidth={2} fill="url(#eqGrad)" dot={false}
                  style={{ filter: "drop-shadow(0 0 4px rgba(34,197,94,0.4))" }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Kelly Calculator + résultat */}
          <div className="grid grid-cols-2 gap-5">
            <div className="card p-6">
              <p className="label-caps mb-5 flex items-center gap-2">
                <Calculator size={11} /> Calculateur Kelly
              </p>
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="label-caps block mb-2">Edge (%)</label>
                    <input className="input-pro" type="number" step="0.1" value={edge} onChange={e => setEdge(e.target.value)} />
                  </div>
                  <div>
                    <label className="label-caps block mb-2">Cote bookmaker</label>
                    <input className="input-pro" type="number" step="0.01" value={odds} onChange={e => setOdds(e.target.value)} />
                  </div>
                </div>
                <div>
                  <label className="label-caps block mb-2">Probabilité modèle (%)</label>
                  <input className="input-pro" type="number" step="0.5" value={prob} onChange={e => setProb(e.target.value)} />
                </div>
                <div>
                  <label className="label-caps block mb-2">Stratégie de mise</label>
                  <select className="input-pro" value={strat} onChange={e => setStrat(e.target.value)}>
                    {STRATEGY_OPTIONS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                  </select>
                </div>
                <button className="btn-primary w-full" onClick={() => calcStake.mutate()} disabled={calcStake.isPending}>
                  {calcStake.isPending ? <><Loader2 size={12} className="animate-spin" /> Calcul...</> : <><Calculator size={12} /> Calculer la mise</>}
                </button>
              </div>
            </div>

            <div className="card p-6">
              <p className="label-caps mb-5 flex items-center gap-2">
                <Shield size={11} /> Recommandation
              </p>
              {stakeResult ? (
                <div className="space-y-4">
                  {/* Backend retourne { recommended: {...}, kelly_comparison: {...} } */}
                  {(() => {
                    const rec = stakeResult.recommended ?? stakeResult;
                    const kc  = stakeResult.kelly_comparison;
                    return (
                      <>
                        <div className="text-center py-4 rounded-xl"
                          style={{ background: "rgba(34,197,94,0.07)", border: "1px solid rgba(34,197,94,0.15)" }}>
                          <p className="label-caps mb-1">Mise recommandée</p>
                          <p className="text-[2rem] font-black tabular-nums" style={{ color: "#4ade80" }}>
                            {(rec.stake_abs ?? rec.stake_amount)?.toFixed(2) ?? "—"} €
                          </p>
                          <p className="text-[11px] mt-0.5" style={{ color: "rgba(255,255,255,0.3)" }}>
                            {rec.stake_pct?.toFixed(2)}% de la bankroll
                          </p>
                        </div>

                        {kc && (
                          <div className="space-y-2">
                            <p className="label-caps">Comparaison Kelly</p>
                            {Object.entries(kc).map(([key, val]: [string, any]) => (
                              <div key={key} className="flex items-center justify-between py-2"
                                style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                                <span className="text-[11px]" style={{ color: "rgba(255,255,255,0.4)" }}>
                                  {key.replace(/_/g, " ")}
                                </span>
                                <span className="text-[12px] font-bold tabular-nums" style={{ color: "#a5b4fc" }}>
                                  {val?.abs?.toFixed(2)} € ({val?.pct?.toFixed(2)}%)
                                </span>
                              </div>
                            ))}
                          </div>
                        )}

                        {rec.risk_level && (
                          <div className="flex items-center justify-between px-3 py-2 rounded-lg"
                            style={{ background: "rgba(255,255,255,0.03)" }}>
                            <span className="text-[11px]" style={{ color: "rgba(255,255,255,0.4)" }}>Niveau de risque</span>
                            <span className="text-[11px] font-bold" style={{ color: RISK_COLORS[rec.risk_level] ?? "#a5b4fc" }}>
                              {rec.risk_level}
                            </span>
                          </div>
                        )}
                      </>
                    );
                  })()}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-48">
                  <TrendingUp size={24} className="mb-3" style={{ color: "rgba(255,255,255,0.1)" }} />
                  <p className="text-[12px]" style={{ color: "rgba(255,255,255,0.25)" }}>
                    Remplissez le formulaire et cliquez Calculer
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Règles bankroll */}
          <div className="card p-6">
            <p className="label-caps mb-4">Règles de gestion actives</p>
            <div className="grid grid-cols-3 gap-3">
              {[
                { label: "Mise max / pari",     value: "5%",   desc: "de la bankroll" },
                { label: "Perte max / jour",    value: "10%",  desc: "limite quotidienne" },
                { label: "Exposition max",      value: "20%",  desc: "paris ouverts simultanés" },
                { label: "Paris max ouverts",   value: "10",   desc: "tickets simultanés" },
                { label: "Max / championnat",   value: "10%",  desc: "par ligue" },
                { label: "Stratégie défaut",    value: "Kelly ¼", desc: "conservateur" },
              ].map(({ label, value, desc }) => (
                <div key={label} className="px-4 py-3 rounded-xl"
                  style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)" }}>
                  <p className="label-caps mb-1">{label}</p>
                  <p className="text-[16px] font-black" style={{ color: "#6366f1" }}>{value}</p>
                  <p className="text-[10px]" style={{ color: "rgba(255,255,255,0.25)" }}>{desc}</p>
                </div>
              ))}
            </div>
          </div>

        </div>
      </main>
    </div>
  );
}
