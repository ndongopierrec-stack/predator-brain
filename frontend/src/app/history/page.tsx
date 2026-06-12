"use client";

import { useState } from "react";
import { History, Filter, TrendingUp, TrendingDown } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";

const STATUS_STYLE: Record<string, { bg: string; color: string; label: string }> = {
  WON:     { bg: "rgba(34,197,94,0.1)",   color: "#4ade80", label: "Gagné"  },
  LOST:    { bg: "rgba(239,68,68,0.1)",   color: "#f87171", label: "Perdu"  },
  PENDING: { bg: "rgba(245,158,11,0.1)",  color: "#fbbf24", label: "En cours" },
  VOID:    { bg: "rgba(100,116,139,0.1)", color: "#94a3b8", label: "Annulé" },
};

const DEMO_HISTORY = [
  { id: 1,  date: "2026-06-11", match: "Arsenal vs Chelsea",        league: "PL",     market: "BTTS Oui",     odds: 1.85, stake: 18.5, status: "WON",  profit: 15.7,  clv: 14.2,  edge: 7.8 },
  { id: 2,  date: "2026-06-11", match: "Real Madrid vs Barça",      league: "LaLiga", market: "Over 2.5",     odds: 1.90, stake: 16.0, status: "WON",  profit: 14.4,  clv: 6.7,   edge: 5.1 },
  { id: 3,  date: "2026-06-10", match: "PSG vs OM",                 league: "L1",     market: "Domicile",     odds: 1.42, stake: 13.0, status: "WON",  profit: 5.5,   clv: -4.1,  edge: 3.2 },
  { id: 4,  date: "2026-06-10", match: "Bayern vs Leipzig",         league: "BL1",    market: "Domicile",     odds: 1.55, stake: 14.0, status: "WON",  profit: 7.7,   clv: 6.9,   edge: 4.0 },
  { id: 5,  date: "2026-06-09", match: "Liverpool vs Everton",      league: "PL",     market: "BTTS Oui",     odds: 1.72, stake: 10.0, status: "LOST", profit: -10.0, clv: -7.0,  edge: 2.1 },
  { id: 6,  date: "2026-06-09", match: "Inter vs Milan",            league: "SerA",   market: "BTTS Oui",     odds: 1.68, stake: 11.0, status: "LOST", profit: -11.0, clv: 4.3,   edge: 4.3 },
  { id: 7,  date: "2026-06-08", match: "Tottenham vs Man United",   league: "PL",     market: "Over 2.5",     odds: 2.05, stake: 12.5, status: "WON",  profit: 13.1,  clv: 8.1,   edge: 6.2 },
  { id: 8,  date: "2026-06-08", match: "Atlético vs Séville",       league: "LaLiga", market: "Under 2.5",    odds: 1.95, stake: 9.5,  status: "PENDING", profit: 0, clv: 5.2, edge: 4.8 },
];

export default function HistoryPage() {
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  const filtered = DEMO_HISTORY.filter(b => statusFilter === "ALL" || b.status === statusFilter);
  const totalProfit = filtered.filter(b => b.status !== "PENDING").reduce((s, b) => s + b.profit, 0);
  const wins = filtered.filter(b => b.status === "WON").length;
  const settled = filtered.filter(b => b.status !== "PENDING" && b.status !== "VOID").length;

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "var(--bg-app)" }}>
      <Sidebar />
      <main className="ml-56 flex-1 overflow-y-auto">

        <header className="topbar px-8 py-4">
          <h1 className="text-[15px] font-bold text-white flex items-center gap-2">
            <History size={14} style={{ color: "#94a3b8" }} />
            Historique des paris
          </h1>
          <p className="text-[11px] mt-0.5" style={{ color: "rgba(255,255,255,0.3)" }}>
            Traçabilité complète · CLV par pari · Exportable
          </p>
        </header>

        <div className="px-8 py-7 space-y-5 animate-fade-in">

          {/* Stats résumé */}
          <div className="grid grid-cols-5 gap-3">
            {[
              { label: "Paris totaux", value: DEMO_HISTORY.length.toString(), color: "#a5b4fc" },
              { label: "Win rate",     value: settled > 0 ? `${((wins / settled) * 100).toFixed(0)}%` : "—", color: "#fbbf24" },
              { label: "Profit net",   value: `${totalProfit >= 0 ? "+" : ""}${totalProfit.toFixed(1)} €`, color: totalProfit >= 0 ? "#4ade80" : "#f87171" },
              { label: "CLV moyen",    value: `+${(DEMO_HISTORY.reduce((s, b) => s + b.clv, 0) / DEMO_HISTORY.length).toFixed(1)}%`, color: "#8b5cf6" },
              { label: "Edge moyen",   value: `+${(DEMO_HISTORY.reduce((s, b) => s + b.edge, 0) / DEMO_HISTORY.length).toFixed(1)}%`, color: "#67e8f9" },
            ].map(({ label, value, color }) => (
              <div key={label} className="metric-card">
                <p className="label-caps mb-2">{label}</p>
                <p className="text-[1.3rem] font-black tabular-nums" style={{ color }}>{value}</p>
              </div>
            ))}
          </div>

          {/* Filtres */}
          <div className="flex items-center gap-2">
            <Filter size={10} style={{ color: "rgba(255,255,255,0.3)" }} />
            {["ALL", "WON", "LOST", "PENDING", "VOID"].map(f => (
              <button key={f} onClick={() => setStatusFilter(f)}
                className="px-3 py-1 rounded-lg text-[11px] font-bold transition-all"
                style={statusFilter === f
                  ? { background: "rgba(99,102,241,0.2)", color: "#a5b4fc" }
                  : { color: "rgba(255,255,255,0.35)" }}>
                {f === "ALL" ? "Tous" : STATUS_STYLE[f]?.label ?? f}
              </button>
            ))}
          </div>

          {/* Tableau */}
          <div className="card overflow-hidden">
            <div className="grid text-[9px] font-bold uppercase tracking-widest px-5 py-3"
              style={{ gridTemplateColumns: "80px 2fr 80px 1fr 70px 70px 70px 70px 80px",
                color: "rgba(255,255,255,0.2)", borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
              <span>Date</span>
              <span>Match</span>
              <span>Ligue</span>
              <span>Marché</span>
              <span className="text-right">Cote</span>
              <span className="text-right">Mise</span>
              <span className="text-center">CLV</span>
              <span className="text-center">Edge</span>
              <span className="text-right">P/L</span>
            </div>

            {filtered.map((b, i) => {
              const ss = STATUS_STYLE[b.status];
              return (
                <div key={b.id} className="grid items-center px-5 py-3.5 hover:bg-white/[0.02] transition-colors"
                  style={{ gridTemplateColumns: "80px 2fr 80px 1fr 70px 70px 70px 70px 80px",
                    borderBottom: i < filtered.length - 1 ? "1px solid rgba(255,255,255,0.03)" : "none" }}>
                  <span className="text-[10px]" style={{ color: "rgba(255,255,255,0.3)" }}>
                    {b.date.slice(5)}
                  </span>
                  <div>
                    <p className="text-[12px] font-semibold text-white truncate">{b.match}</p>
                    <span className="text-[9px] font-bold px-1.5 py-0.5 rounded mt-0.5 inline-block"
                      style={{ background: ss.bg, color: ss.color }}>{ss.label}</span>
                  </div>
                  <span className="text-[11px] font-bold" style={{ color: "rgba(255,255,255,0.4)" }}>{b.league}</span>
                  <span className="text-[11px]" style={{ color: "rgba(255,255,255,0.45)" }}>{b.market}</span>
                  <span className="text-[13px] font-bold text-white tabular-nums text-right">{b.odds}</span>
                  <span className="text-[12px] tabular-nums text-right" style={{ color: "rgba(255,255,255,0.5)" }}>{b.stake} €</span>
                  <span className="text-[12px] font-bold tabular-nums text-center"
                    style={{ color: b.clv >= 3 ? "#4ade80" : b.clv >= 0 ? "#94a3b8" : "#f87171" }}>
                    {b.clv >= 0 ? "+" : ""}{b.clv.toFixed(1)}%
                  </span>
                  <span className="text-[11px] font-bold tabular-nums text-center" style={{ color: "#a5b4fc" }}>
                    +{b.edge.toFixed(1)}%
                  </span>
                  <span className="text-[13px] font-black tabular-nums text-right"
                    style={{ color: b.profit > 0 ? "#4ade80" : b.profit < 0 ? "#f87171" : "rgba(255,255,255,0.3)" }}>
                    {b.profit > 0 ? "+" : ""}{b.profit.toFixed(1)} €
                  </span>
                </div>
              );
            })}
          </div>

        </div>
      </main>
    </div>
  );
}
