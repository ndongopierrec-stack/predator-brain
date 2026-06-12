"use client";

import { useState } from "react";
import { TrendingUp, Search, RefreshCw, ArrowUpRight, ArrowDownRight } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";

const BOOKMAKERS = ["Pinnacle", "Bet365", "Betway", "1xBet", "Winamax", "Betclic", "Unibet"];

const DEMO_ODDS = [
  {
    match: "Real Madrid vs Atlético",  date: "Auj. 21:00", league: "LaLiga",
    markets: {
      "1X2": {
        home:  { Pinnacle: 2.05, Bet365: 1.95, Betway: 2.00, Winamax: 2.08, Betclic: 1.98 },
        draw:  { Pinnacle: 3.50, Bet365: 3.40, Betway: 3.45, Winamax: 3.55, Betclic: 3.40 },
        away:  { Pinnacle: 3.70, Bet365: 3.60, Betway: 3.65, Winamax: 3.75, Betclic: 3.62 },
      },
      "BTTS": {
        yes: { Pinnacle: 1.74, Bet365: 1.70, Betway: 1.72, Winamax: 1.76, Betclic: 1.71 },
        no:  { Pinnacle: 2.15, Bet365: 2.10, Betway: 2.12, Winamax: 2.18, Betclic: 2.11 },
      },
    },
    fair_odds: { home: 1.88, draw: 3.72, away: 4.20, btts_yes: 1.62, btts_no: 2.50 },
    opening:   { home: 2.10, away: 3.80 },
  },
  {
    match: "Arsenal vs Chelsea",       date: "Auj. 20:00", league: "PL",
    markets: {
      "1X2": {
        home:  { Pinnacle: 1.85, Bet365: 1.80, Betway: 1.82, Winamax: 1.87, Betclic: 1.81 },
        draw:  { Pinnacle: 3.80, Bet365: 3.70, Betway: 3.75, Winamax: 3.85, Betclic: 3.72 },
        away:  { Pinnacle: 4.20, Bet365: 4.00, Betway: 4.10, Winamax: 4.25, Betclic: 4.05 },
      },
      "BTTS": {
        yes: { Pinnacle: 1.87, Bet365: 1.82, Betway: 1.84, Winamax: 1.90, Betclic: 1.83 },
        no:  { Pinnacle: 1.98, Bet365: 1.95, Betway: 1.96, Winamax: 2.00, Betclic: 1.96 },
      },
    },
    fair_odds: { home: 1.72, draw: 4.10, away: 4.80, btts_yes: 1.74, btts_no: 2.30 },
    opening:   { home: 1.80, away: 4.50 },
  },
];

function OddsCell({ val, best, fair, label }: { val: number; best: number; fair: number; label: string }) {
  const isBest = Math.abs(val - best) < 0.001;
  const value = val > fair;
  return (
    <div className="relative text-center px-2 py-2 rounded-lg transition-all"
      style={isBest
        ? { background: "rgba(34,197,94,0.12)", border: "1px solid rgba(34,197,94,0.2)" }
        : { border: "1px solid transparent" }}>
      <p className="text-[13px] font-black tabular-nums" style={{ color: isBest ? "#4ade80" : "rgba(255,255,255,0.7)" }}>
        {val.toFixed(2)}
      </p>
      {value && <p className="text-[8px] font-bold" style={{ color: "#fbbf24" }}>VALUE</p>}
      {isBest && <p className="text-[8px]" style={{ color: "rgba(34,197,94,0.7)" }}>MEILLEUR</p>}
    </div>
  );
}

export default function OddsComparisonPage() {
  const [search, setSearch] = useState("");
  const [selectedMarket, setSelectedMarket] = useState<"1X2" | "BTTS">("1X2");

  const filtered = DEMO_ODDS.filter(m =>
    !search || m.match.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "var(--bg-app)" }}>
      <Sidebar />
      <main className="ml-56 flex-1 overflow-y-auto">

        <header className="topbar px-8 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-[15px] font-bold text-white flex items-center gap-2">
              <TrendingUp size={14} style={{ color: "#3b82f6" }} />
              Comparateur de Cotes
            </h1>
            <p className="text-[11px] mt-0.5" style={{ color: "rgba(255,255,255,0.3)" }}>
              Meilleure cote · Cote juste Predator Brain · Mouvements · Value
            </p>
          </div>
          <div className="flex items-center gap-3">
            {/* Market toggle */}
            <div className="flex items-center gap-1 p-1 rounded-xl"
              style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)" }}>
              {["1X2", "BTTS"].map(m => (
                <button key={m} onClick={() => setSelectedMarket(m as any)}
                  className="px-3 py-1 rounded-lg text-[11px] font-bold transition-all"
                  style={selectedMarket === m
                    ? { background: "rgba(99,102,241,0.2)", color: "#a5b4fc" }
                    : { color: "rgba(255,255,255,0.35)" }}>
                  {m}
                </button>
              ))}
            </div>
            <button className="btn-ghost flex items-center gap-2">
              <RefreshCw size={11} /> Actualiser
            </button>
          </div>
        </header>

        <div className="px-8 py-7 space-y-5 animate-fade-in">

          {/* Recherche */}
          <div className="relative max-w-80">
            <Search size={11} className="absolute left-3 top-1/2 -translate-y-1/2"
              style={{ color: "rgba(255,255,255,0.25)" }} />
            <input className="input-pro pl-8" placeholder="Rechercher un match..."
              value={search} onChange={e => setSearch(e.target.value)} />
          </div>

          {/* Tableaux de cotes */}
          {filtered.map((match, mi) => {
            const mkData = match.markets[selectedMarket];
            const bms = Object.keys(Object.values(mkData)[0]);
            const outcomes = Object.keys(mkData);
            const fair = match.fair_odds;

            // Calcul marge
            const pinnacleOdds = Object.values(mkData).map((o: any) => o.Pinnacle ?? 0);
            const margin = ((pinnacleOdds.reduce((s, o) => s + 1 / o, 0) - 1) * 100);

            // Mouvement sur cote domicile
            const movHome = match.opening.home - (mkData as any).home?.Pinnacle;
            const hasMovement = selectedMarket === "1X2";

            return (
              <div key={mi} className="card overflow-hidden">
                {/* Match header */}
                <div className="px-5 py-4 flex items-center justify-between"
                  style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-[9px] font-bold px-1.5 py-0.5 rounded"
                        style={{ background: "rgba(255,255,255,0.05)", color: "rgba(255,255,255,0.3)" }}>
                        {match.league}
                      </span>
                      <p className="text-[14px] font-bold text-white">{match.match}</p>
                    </div>
                    <p className="text-[10px]" style={{ color: "rgba(255,255,255,0.3)" }}>{match.date}</p>
                  </div>
                  <div className="flex items-center gap-4">
                    {/* Marge */}
                    <div className="text-right">
                      <p className="label-caps mb-0.5">Marge Pinnacle</p>
                      <p className="text-[12px] font-bold" style={{ color: margin < 3 ? "#4ade80" : "#fbbf24" }}>
                        {margin.toFixed(2)}%
                      </p>
                    </div>
                    {/* Mouvement */}
                    {hasMovement && (
                      <div className="text-right">
                        <p className="label-caps mb-0.5">Mvt Dom.</p>
                        <p className="text-[12px] font-bold flex items-center gap-1 justify-end"
                          style={{ color: movHome > 0 ? "#4ade80" : "#f87171" }}>
                          {movHome > 0 ? <ArrowDownRight size={11} /> : <ArrowUpRight size={11} />}
                          {Math.abs(movHome).toFixed(2)}
                        </p>
                      </div>
                    )}
                  </div>
                </div>

                {/* Tableau cotes */}
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse" }}>
                    <thead>
                      <tr>
                        <th className="px-5 py-2.5 text-left label-caps" style={{ minWidth: 120 }}>Marché</th>
                        <th className="px-2 py-2.5 text-center label-caps" style={{ minWidth: 80, color: "#a5b4fc" }}>Cote juste</th>
                        {bms.map(bm => (
                          <th key={bm} className="px-2 py-2.5 text-center label-caps" style={{ minWidth: 88 }}>{bm}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {outcomes.map((outcome, oi) => {
                        const oddsMap = (mkData as any)[outcome] as Record<string, number>;
                        const best = Math.max(...Object.values(oddsMap));
                        const fairKey = outcome === "home" ? fair.home : outcome === "draw" ? fair.draw :
                          outcome === "away" ? fair.away : outcome === "yes" ? fair.btts_yes : fair.btts_no;
                        const outcomeLabel = outcome === "home" ? "Domicile" : outcome === "draw" ? "Nul" :
                          outcome === "away" ? "Extérieur" : outcome === "yes" ? "BTTS Oui" : "BTTS Non";
                        return (
                          <tr key={oi} style={{ borderTop: "1px solid rgba(255,255,255,0.03)" }}>
                            <td className="px-5 py-2 text-[12px] font-semibold text-white">{outcomeLabel}</td>
                            <td className="px-2 py-2 text-center text-[12px] font-bold tabular-nums"
                              style={{ color: "#a5b4fc" }}>{fairKey?.toFixed(2) ?? "—"}</td>
                            {bms.map(bm => (
                              <td key={bm} className="px-2 py-2">
                                {oddsMap[bm]
                                  ? <OddsCell val={oddsMap[bm]} best={best} fair={fairKey ?? 0} label={bm} />
                                  : <span style={{ color: "rgba(255,255,255,0.15)", fontSize: 12 }}>—</span>}
                              </td>
                            ))}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            );
          })}

          {/* Légende */}
          <div className="flex items-center gap-6 px-4 py-3 rounded-xl"
            style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.04)" }}>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded" style={{ background: "rgba(34,197,94,0.2)", border: "1px solid rgba(34,197,94,0.3)" }} />
              <p className="text-[10px]" style={{ color: "rgba(255,255,255,0.35)" }}>Meilleure cote disponible</p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[8px] font-bold" style={{ color: "#fbbf24" }}>VALUE</span>
              <p className="text-[10px]" style={{ color: "rgba(255,255,255,0.35)" }}>Cote supérieure à la cote juste Predator Brain</p>
            </div>
            <p className="text-[10px] ml-auto" style={{ color: "rgba(255,255,255,0.2)" }}>
              Cote juste = 1 / P_modèle Dixon-Coles · Source : The Odds API
            </p>
          </div>

        </div>
      </main>
    </div>
  );
}
