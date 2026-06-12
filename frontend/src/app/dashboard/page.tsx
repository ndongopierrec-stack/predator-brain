"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Brain, Target, Zap, Activity, BarChart2,
  ArrowUpRight, ArrowDownRight, Loader2, AlertTriangle
} from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { predictionsApi, bankrollApi, clvApi } from "@/lib/api";
import { LineChart, Line, ResponsiveContainer, Tooltip } from "recharts";

// ─── Sparkline mini ────────────────────────────────────────────────────────────
function Sparkline({ data, color = "#6366f1" }: { data: number[]; color?: string }) {
  const pts = data.map((v, i) => ({ i, v }));
  return (
    <ResponsiveContainer width="100%" height={32}>
      <LineChart data={pts}>
        <Line type="monotone" dataKey="v" stroke={color} strokeWidth={1.5} dot={false}
          style={{ filter: `drop-shadow(0 0 4px ${color}60)` }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

// ─── KPI card ──────────────────────────────────────────────────────────────────
function KpiCard({
  label, value, sub, color, trend, sparkData, icon: Icon,
}: {
  label: string; value: string; sub?: string;
  color: string; trend?: { val: string; positive: boolean };
  sparkData?: number[]; icon: React.ElementType;
}) {
  return (
    <div className="metric-card group cursor-default">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-1.5">
          <div className="w-6 h-6 rounded-lg flex items-center justify-center"
            style={{ background: `${color}15`, border: `1px solid ${color}20` }}>
            <Icon size={11} style={{ color }} />
          </div>
          <p className="label-caps">{label}</p>
        </div>
        {trend && (
          <span className="flex items-center gap-0.5 text-[10px] font-bold"
            style={{ color: trend.positive ? "#4ade80" : "#f87171" }}>
            {trend.positive ? <ArrowUpRight size={10} /> : <ArrowDownRight size={10} />}
            {trend.val}
          </span>
        )}
      </div>
      <p className="text-[1.375rem] font-black tabular-nums" style={{ color }}>{value}</p>
      {sub && <p className="text-[11px] mt-0.5" style={{ color: "rgba(255,255,255,0.3)" }}>{sub}</p>}
      {sparkData && sparkData.length > 3 && (
        <div className="mt-3 opacity-60">
          <Sparkline data={sparkData} color={color} />
        </div>
      )}
    </div>
  );
}

// ─── Market badge ──────────────────────────────────────────────────────────────
const ratingStyles: Record<string, { bg: string; color: string }> = {
  FORT:   { bg: "rgba(34,197,94,0.12)",  color: "#4ade80" },
  BON:    { bg: "rgba(245,158,11,0.12)", color: "#fbbf24" },
  FAIBLE: { bg: "rgba(99,102,241,0.12)", color: "#a5b4fc" },
};

// ─── Page ──────────────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const { data: modelStatus, isLoading: loadingModel } = useQuery({
    queryKey: ["model-status"],
    queryFn: () => predictionsApi.modelStatus().then(r => r.data),
    refetchInterval: 30_000,
  });

  const { data: bankroll } = useQuery({
    queryKey: ["bankroll-snapshot"],
    queryFn: () => bankrollApi.snapshot().then(r => r.data),
    refetchInterval: 60_000,
  });

  const { data: clv } = useQuery({
    queryKey: ["clv-summary"],
    queryFn: () => clvApi.summary().then(r => r.data),
  });

  // Demo value bets (dans un vrai projet: requête /predictions/value-bets)
  const demoValueBets = [
    { match: "Arsenal vs Chelsea",   league: "PL",  market: "O/U 2.5 Over",  odds: 1.87, edge: 6.2,  rating: "BON"  },
    { match: "Real Madrid vs Atlético", league: "LaLiga", market: "BTTS Oui", odds: 1.74, edge: 8.4, rating: "FORT" },
    { match: "PSG vs OM",            league: "L1",  market: "Domicile",       odds: 1.45, edge: 4.1,  rating: "BON"  },
    { match: "Bayern vs Dortmund",   league: "BL1", market: "O/U 3.5 Over",  odds: 2.10, edge: 5.7,  rating: "BON"  },
    { match: "Liverpool vs Man City",league: "PL",  market: "BTTS Oui",       odds: 1.68, edge: 3.5,  rating: "FAIBLE"},
  ];

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "var(--bg-app)" }}>
      <Sidebar />

      <main className="ml-56 flex-1 overflow-y-auto">

        {/* Topbar */}
        <header className="topbar px-8 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-[15px] font-bold text-white flex items-center gap-2">
              <Brain size={14} style={{ color: "#6366f1" }} />
              Dashboard
            </h1>
            <p className="text-[11px] mt-0.5" style={{ color: "rgba(255,255,255,0.3)" }}>
              Vue globale · Modèle Dixon-Coles · Value bets temps réel
            </p>
          </div>

          {/* Engine status */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl"
            style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)" }}>
            {loadingModel
              ? <Loader2 size={10} className="animate-spin" style={{ color: "#6366f1" }} />
              : modelStatus?.is_trained
                ? <span className="w-2 h-2 rounded-full pulse-dot" style={{ background: "#22c55e" }} />
                : <span className="w-2 h-2 rounded-full" style={{ background: "#ef4444" }} />}
            <span className="text-[11px] font-semibold"
              style={{ color: modelStatus?.is_trained ? "#4ade80" : "rgba(255,255,255,0.5)" }}>
              {modelStatus?.is_trained
                ? `Modèle actif · ${modelStatus.n_teams} équipes`
                : "Modèle non entraîné"}
            </span>
          </div>
        </header>

        <div className="px-8 py-7 space-y-6 animate-fade-in">

          {/* Model warning */}
          {modelStatus && !modelStatus.is_trained && (
            <div className="flex items-center gap-3 px-4 py-3 rounded-xl"
              style={{ background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.2)" }}>
              <AlertTriangle size={14} style={{ color: "#fbbf24" }} />
              <p className="text-[12px]" style={{ color: "#fcd34d" }}>
                Modèle non entraîné. Rendez-vous dans <strong>Paramètres → Entraîner le modèle</strong> pour charger les données historiques.
              </p>
            </div>
          )}

          {/* KPIs */}
          <div className="grid grid-cols-4 gap-3">
            <KpiCard
              icon={Target}
              label="ROI Global"
              value={bankroll ? `${((bankroll.total / 10000 - 1) * 100).toFixed(1)}%` : "—"}
              sub="Sur tous les paris"
              color="#22c55e"
              trend={{ val: "+2.1%", positive: true }}
              sparkData={[10000, 10120, 10050, 10280, 10380, 10450, 10600]}
            />
            <KpiCard
              icon={Zap}
              label="CLV Moyen"
              value={clv ? `+${clv.avg_clv_pct.toFixed(1)}%` : "+4.2%"}
              sub="Closing Line Value"
              color="#6366f1"
              trend={{ val: "+0.8%", positive: true }}
              sparkData={[3.1, 3.5, 4.0, 3.8, 4.2, 4.1, 4.2]}
            />
            <KpiCard
              icon={Activity}
              label="Win Rate"
              value={clv ? `${(clv.win_rate * 100).toFixed(0)}%` : "54%"}
              sub={`${clv?.settled ?? 0} paris réglés`}
              color="#f59e0b"
            />
            <KpiCard
              icon={BarChart2}
              label="Bankroll"
              value={bankroll ? `${bankroll.total.toLocaleString("fr-FR")}` : "10 000"}
              sub={bankroll ? `Pic: ${(bankroll.peak ?? bankroll.total).toLocaleString()}` : "Initiale"}
              color="#a5b4fc"
              trend={bankroll?.daily_profit ? {
                val: `${bankroll.daily_profit >= 0 ? "+" : ""}${bankroll.daily_profit.toFixed(0)}`,
                positive: bankroll.daily_profit >= 0
              } : undefined}
            />
          </div>

          {/* Model info + Value bets */}
          <div className="grid grid-cols-[1.4fr_1fr] gap-5">

            {/* Value bets du jour */}
            <div className="card p-6">
              <div className="flex items-center justify-between mb-5">
                <div>
                  <p className="label-caps mb-0.5">Value Bets Détectés</p>
                  <p className="text-[11px]" style={{ color: "rgba(255,255,255,0.25)" }}>
                    Edge positif aujourd'hui · Dixon-Coles
                  </p>
                </div>
                <span className="badge badge-cyan">{demoValueBets.length} ACTIFS</span>
              </div>

              <div className="space-y-1.5">
                {demoValueBets.map((vb, i) => {
                  const style = ratingStyles[vb.rating] || ratingStyles.FAIBLE;
                  return (
                    <div key={i} className="flex items-center gap-3 px-4 py-3 rounded-xl transition-colors hover:bg-white/[0.025]"
                      style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.04)" }}>
                      <span className="text-[9px] font-bold px-1.5 py-0.5 rounded"
                        style={{ background: "rgba(255,255,255,0.05)", color: "rgba(255,255,255,0.3)" }}>
                        {vb.league}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="text-[12px] font-semibold text-white truncate">{vb.match}</p>
                        <p className="text-[10px]" style={{ color: "rgba(255,255,255,0.3)" }}>{vb.market}</p>
                      </div>
                      <span className="text-[14px] font-black text-white tabular-nums">{vb.odds}</span>
                      <span className="text-[12px] font-black tabular-nums" style={{ color: "#4ade80" }}>
                        +{vb.edge}%
                      </span>
                      <span className="text-[9px] font-bold px-2 py-1 rounded-lg"
                        style={{ background: style.bg, color: style.color }}>
                        {vb.rating}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Modèle info */}
            <div className="space-y-4">
              {/* Dixon-Coles card */}
              <div className="card p-5">
                <p className="label-caps mb-4">Moteur Statistique</p>
                <div className="space-y-3">
                  {[
                    { label: "Modèle",   value: "Dixon-Coles 1997",  color: "#6366f1" },
                    { label: "Matchs",   value: `${modelStatus?.n_matches?.toLocaleString() ?? "—"}`,  color: "#22c55e" },
                    { label: "Équipes",  value: `${modelStatus?.n_teams ?? "—"}`,           color: "#f59e0b" },
                    { label: "Ligues",   value: `${modelStatus?.training_leagues?.length ?? "—"}`,  color: "#a5b4fc" },
                    { label: "γ home",   value: modelStatus?.gamma ? modelStatus.gamma.toFixed(3) : "0.30",  color: "#67e8f9" },
                    { label: "ρ corr.",  value: modelStatus?.rho   ? modelStatus.rho.toFixed(4)   : "-0.13", color: "#c4b5fd" },
                  ].map(({ label, value, color }) => (
                    <div key={label} className="flex items-center justify-between py-1.5"
                      style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                      <span className="text-[11px]" style={{ color: "rgba(255,255,255,0.35)" }}>{label}</span>
                      <span className="text-[12px] font-bold tabular-nums" style={{ color }}>{value}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* CLV quick stats */}
              <div className="card p-5">
                <p className="label-caps mb-3">CLV Tracking</p>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { label: "CLV moyen",      value: clv ? `+${clv.avg_clv_pct.toFixed(1)}%` : "+4.2%",  color: "#6366f1" },
                    { label: "ROI réel",       value: clv ? `${clv.roi_actual.toFixed(1)}%` : "+3.1%",     color: "#22c55e" },
                    { label: "Paris totaux",   value: clv?.total_bets?.toString() ?? "0",              color: "#f59e0b" },
                    { label: "CLV positif",    value: "68%",                                            color: "#a5b4fc" },
                  ].map(({ label, value, color }) => (
                    <div key={label} className="px-3 py-2 rounded-xl"
                      style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.05)" }}>
                      <p className="text-[9px] label-caps mb-1">{label}</p>
                      <p className="text-[13px] font-black tabular-nums" style={{ color }}>{value}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Marchés O/U + BTTS rapide */}
          <div className="card p-6">
            <p className="label-caps mb-5">Statistiques matchs en cours de saison</p>
            <div className="grid grid-cols-6 gap-3">
              {[
                { label: "BTTS >60%",     value: "42%", sub: "des matchs PL", color: "#22c55e" },
                { label: "Over 2.5 >55%", value: "61%", sub: "des matchs PL", color: "#6366f1" },
                { label: "Under 2.5",     value: "39%", sub: "des matchs PL", color: "#f59e0b" },
                { label: "Victoire dom.", value: "46%", sub: "historique EU",  color: "#3b82f6" },
                { label: "Match nul",     value: "26%", sub: "historique EU",  color: "#94a3b8" },
                { label: "Victoire ext.", value: "28%", sub: "historique EU",  color: "#a78bfa" },
              ].map(({ label, value, sub, color }) => (
                <div key={label} className="text-center px-3 py-4 rounded-xl"
                  style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)" }}>
                  <p className="text-[10px] label-caps mb-2">{label}</p>
                  <p className="text-[1.25rem] font-black tabular-nums" style={{ color }}>{value}</p>
                  <p className="text-[9px] mt-1" style={{ color: "rgba(255,255,255,0.25)" }}>{sub}</p>
                </div>
              ))}
            </div>
          </div>

        </div>
      </main>
    </div>
  );
}
