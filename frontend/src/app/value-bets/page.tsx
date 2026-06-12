"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Zap, Filter, RefreshCw, TrendingUp, Target, ChevronDown, Search } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { predictionsApi } from "@/lib/api";

// ─── Gauge circulaire pour l'edge ──────────────────────────────────────────────
function EdgeGauge({ edge, size = 52 }: { edge: number; size?: number }) {
  const pct = Math.min(Math.max(edge, 0), 30) / 30;
  const r = (size - 6) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - pct);
  const color = edge >= 8 ? "#4ade80" : edge >= 4 ? "#fbbf24" : "#a5b4fc";
  return (
    <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none"
        stroke="rgba(255,255,255,0.06)" strokeWidth={5} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none"
        stroke={color} strokeWidth={5} strokeLinecap="round"
        strokeDasharray={circ} strokeDashoffset={offset}
        style={{ filter: `drop-shadow(0 0 4px ${color}80)`, transition: "stroke-dashoffset 0.5s ease" }} />
      <text x={size / 2} y={size / 2} textAnchor="middle" dominantBaseline="central"
        style={{ fill: color, fontSize: size * 0.26, fontWeight: 800, fontVariantNumeric: "tabular-nums",
          transform: `rotate(90deg) translateX(${size / 2}px) translateY(${-size / 2}px)` }}>
        {edge.toFixed(1)}%
      </text>
    </svg>
  );
}

// ─── Données demo ───────────────────────────────────────────────────────────────
const DEMO_BETS = [
  { id: 1, match: "Real Madrid vs Atlético",  league: "LaLiga", date: "Auj. 21:00", market: "BTTS Oui",      odds: 1.74, edge: 9.2, rating: "FORT",   conf: 82, kelly_pct: 2.3 },
  { id: 2, match: "Arsenal vs Chelsea",       league: "PL",     date: "Auj. 20:00", market: "O/U 2.5 Over",  odds: 1.87, edge: 7.8, rating: "FORT",   conf: 78, kelly_pct: 2.0 },
  { id: 3, match: "Bayern vs Dortmund",       league: "BL1",    date: "Auj. 18:30", market: "O/U 3.5 Over",  odds: 2.10, edge: 6.4, rating: "BON",    conf: 71, kelly_pct: 1.6 },
  { id: 4, match: "PSG vs OM",                league: "L1",     date: "Dem. 21:00", market: "Domicile",       odds: 1.45, edge: 5.1, rating: "BON",    conf: 69, kelly_pct: 1.3 },
  { id: 5, match: "Inter vs Milan",           league: "SerA",   date: "Dem. 20:45", market: "BTTS Oui",      odds: 1.68, edge: 4.3, rating: "BON",    conf: 66, kelly_pct: 1.1 },
  { id: 6, match: "Liverpool vs Man City",    league: "PL",     date: "Auj. 17:30", market: "BTTS Oui",      odds: 1.66, edge: 3.7, rating: "FAIBLE", conf: 62, kelly_pct: 0.9 },
  { id: 7, match: "Séville vs Betis",         league: "LaLiga", date: "Dem. 19:00", market: "Extérieur",      odds: 3.40, edge: 3.2, rating: "FAIBLE", conf: 58, kelly_pct: 0.5 },
  { id: 8, match: "Man United vs Tottenham",  league: "PL",     date: "Dim. 16:00", market: "O/U 2.5 Under", odds: 1.91, edge: 2.9, rating: "FAIBLE", conf: 55, kelly_pct: 0.4 },
];

const RATING_STYLE: Record<string, { bg: string; color: string; border: string }> = {
  FORT:   { bg: "rgba(34,197,94,0.1)",   color: "#4ade80", border: "rgba(34,197,94,0.25)"  },
  BON:    { bg: "rgba(245,158,11,0.1)",  color: "#fbbf24", border: "rgba(245,158,11,0.25)" },
  FAIBLE: { bg: "rgba(99,102,241,0.1)",  color: "#a5b4fc", border: "rgba(99,102,241,0.25)" },
};

const LEAGUE_COLORS: Record<string, string> = {
  PL: "#4ade80", LaLiga: "#f59e0b", L1: "#3b82f6", BL1: "#ef4444", SerA: "#a78bfa",
};

export default function ValueBetsPage() {
  const [filter, setFilter] = useState<"ALL" | "FORT" | "BON" | "FAIBLE">("ALL");
  const [search, setSearch] = useState("");

  const { data: modelStatus } = useQuery({
    queryKey: ["model-status"],
    queryFn: () => predictionsApi.modelStatus().then(r => r.data),
  });

  const filtered = DEMO_BETS.filter(b => {
    if (filter !== "ALL" && b.rating !== filter) return false;
    if (search && !b.match.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const stats = {
    total: DEMO_BETS.length,
    fort: DEMO_BETS.filter(b => b.rating === "FORT").length,
    avgEdge: (DEMO_BETS.reduce((s, b) => s + b.edge, 0) / DEMO_BETS.length).toFixed(1),
    avgOdds: (DEMO_BETS.reduce((s, b) => s + b.odds, 0) / DEMO_BETS.length).toFixed(2),
  };

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "var(--bg-app)" }}>
      <Sidebar />
      <main className="ml-56 flex-1 overflow-y-auto">

        {/* Topbar */}
        <header className="topbar px-8 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-[15px] font-bold text-white flex items-center gap-2">
              <Zap size={14} style={{ color: "#06b6d4" }} />
              Value Bets
              <span className="text-[9px] font-black px-2 py-1 rounded-full"
                style={{ background: "rgba(6,182,212,0.15)", color: "#67e8f9" }}>LIVE</span>
            </h1>
            <p className="text-[11px] mt-0.5" style={{ color: "rgba(255,255,255,0.3)" }}>
              Opportunités avec edge positif · Dixon-Coles · Mis à jour en temps réel
            </p>
          </div>
          <button className="btn-ghost flex items-center gap-2" title="Rafraîchir">
            <RefreshCw size={11} />
            Actualiser
          </button>
        </header>

        <div className="px-8 py-7 space-y-5 animate-fade-in">

          {/* Stats rapides */}
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: "Opportunités",  value: stats.total.toString(), color: "#67e8f9" },
              { label: "Forte valeur",  value: stats.fort.toString(),  color: "#4ade80" },
              { label: "Edge moyen",    value: `+${stats.avgEdge}%`,   color: "#6366f1" },
              { label: "Cote moyenne",  value: stats.avgOdds,          color: "#f59e0b" },
            ].map(({ label, value, color }) => (
              <div key={label} className="metric-card">
                <p className="label-caps mb-2">{label}</p>
                <p className="text-[1.5rem] font-black tabular-nums" style={{ color }}>{value}</p>
              </div>
            ))}
          </div>

          {/* Filtres + search */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl"
              style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)" }}>
              <Filter size={10} style={{ color: "rgba(255,255,255,0.3)" }} />
              {(["ALL", "FORT", "BON", "FAIBLE"] as const).map(f => (
                <button key={f} onClick={() => setFilter(f)}
                  className="px-3 py-1 rounded-lg text-[11px] font-bold transition-all"
                  style={filter === f
                    ? { background: "rgba(99,102,241,0.2)", color: "#a5b4fc" }
                    : { color: "rgba(255,255,255,0.35)" }}>
                  {f}
                </button>
              ))}
            </div>

            <div className="relative flex-1 max-w-64">
              <Search size={11} className="absolute left-3 top-1/2 -translate-y-1/2"
                style={{ color: "rgba(255,255,255,0.25)" }} />
              <input
                className="input-pro pl-8"
                placeholder="Rechercher un match..."
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>
          </div>

          {/* Liste value bets */}
          <div className="card overflow-hidden">
            {/* Header */}
            <div className="grid gap-4 px-5 py-3 text-[9px] font-bold uppercase tracking-widest"
              style={{ gridTemplateColumns: "2fr 1fr 1fr 80px 80px 70px 90px", color: "rgba(255,255,255,0.2)",
                borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
              <span>Match · Marché</span>
              <span>Ligue</span>
              <span>Horaire</span>
              <span className="text-right">Cote</span>
              <span className="text-center">Edge</span>
              <span className="text-center">Confiance</span>
              <span className="text-right">Kelly/4 (%)</span>
            </div>

            {filtered.map((bet, i) => {
              const rs = RATING_STYLE[bet.rating];
              const lc = LEAGUE_COLORS[bet.league] || "#94a3b8";
              return (
                <div key={bet.id} className="grid gap-4 px-5 py-4 items-center transition-colors hover:bg-white/[0.02] cursor-pointer"
                  style={{ gridTemplateColumns: "2fr 1fr 1fr 80px 80px 70px 90px",
                    borderBottom: i < filtered.length - 1 ? "1px solid rgba(255,255,255,0.03)" : "none" }}>
                  {/* Match + marché + rating */}
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-[9px] font-bold px-1.5 py-0.5 rounded"
                        style={{ background: rs.bg, color: rs.color, border: `1px solid ${rs.border}` }}>
                        {bet.rating}
                      </span>
                      <p className="text-[12.5px] font-semibold text-white truncate">{bet.match}</p>
                    </div>
                    <p className="text-[10px]" style={{ color: "rgba(255,255,255,0.3)" }}>{bet.market}</p>
                  </div>

                  {/* Ligue */}
                  <span className="text-[11px] font-bold tabular-nums" style={{ color: lc }}>{bet.league}</span>

                  {/* Horaire */}
                  <span className="text-[11px]" style={{ color: "rgba(255,255,255,0.4)" }}>{bet.date}</span>

                  {/* Cote */}
                  <span className="text-[14px] font-black text-white tabular-nums text-right">{bet.odds}</span>

                  {/* Edge gauge */}
                  <div className="flex justify-center">
                    <EdgeGauge edge={bet.edge} size={44} />
                  </div>

                  {/* Confiance */}
                  <div className="flex flex-col items-center gap-1">
                    <span className="text-[11px] font-bold tabular-nums text-white">{bet.conf}%</span>
                    <div className="w-full h-1 rounded-full" style={{ background: "rgba(255,255,255,0.06)" }}>
                      <div className="h-full rounded-full transition-all"
                        style={{ width: `${bet.conf}%`,
                          background: bet.conf >= 75 ? "#4ade80" : bet.conf >= 60 ? "#fbbf24" : "#6366f1" }} />
                    </div>
                  </div>

                  {/* Kelly */}
                  <span className="text-[13px] font-black tabular-nums text-right" style={{ color: "#4ade80" }}>
                    {bet.kelly_pct.toFixed(1)}%
                  </span>
                </div>
              );
            })}

            {filtered.length === 0 && (
              <div className="py-16 text-center">
                <Target size={24} className="mx-auto mb-3" style={{ color: "rgba(255,255,255,0.1)" }} />
                <p className="text-[13px]" style={{ color: "rgba(255,255,255,0.3)" }}>
                  Aucune opportunité pour ce filtre
                </p>
              </div>
            )}
          </div>

          {/* Légende méthode */}
          <div className="flex items-center gap-5 px-4 py-3 rounded-xl"
            style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.04)" }}>
            <TrendingUp size={11} style={{ color: "rgba(255,255,255,0.2)" }} />
            <p className="text-[10px]" style={{ color: "rgba(255,255,255,0.25)" }}>
              <strong style={{ color: "rgba(255,255,255,0.5)" }}>Méthode :</strong> Edge = P_model × cote_bookmaker − 1 ·
              Marge Pinnacle supprimée · Kelly Quarter conservateur ·
              FORT ≥ 8% · BON 4–8% · FAIBLE 3–4%
            </p>
          </div>

        </div>
      </main>
    </div>
  );
}
