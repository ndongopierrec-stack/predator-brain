"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Brain, Play, Loader2, BarChart2 } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { predictionsApi, AnalysisResult } from "@/lib/api";

// ─── Score matrix ──────────────────────────────────────────────────────────────
function ScoreMatrix({ matrix, homeGoals = 5, awayGoals = 5 }: {
  matrix: number[][];
  homeGoals?: number;
  awayGoals?: number;
}) {
  const max = Math.max(...matrix.flat());
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ borderCollapse: "collapse", fontSize: 11 }}>
        <thead>
          <tr>
            <th className="px-2 py-1 text-[9px]" style={{ color: "rgba(255,255,255,0.3)" }}>⬇Ext / Dom➡</th>
            {Array.from({ length: homeGoals + 1 }, (_, i) => (
              <th key={i} className="w-9 h-8 text-[10px] font-bold" style={{ color: "rgba(255,255,255,0.4)" }}>{i}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.slice(0, awayGoals + 1).map((row, j) => (
            <tr key={j}>
              <td className="px-2 py-0.5 text-[10px] font-bold" style={{ color: "rgba(255,255,255,0.4)" }}>{j}</td>
              {row.slice(0, homeGoals + 1).map((prob, i) => {
                const intensity = max > 0 ? prob / max : 0;
                const isLikeliest = prob === max;
                return (
                  <td key={i} className="w-9 h-8 text-center text-[9px] font-bold tabular-nums rounded"
                    style={{
                      background: `rgba(99,102,241,${intensity * 0.7})`,
                      color: intensity > 0.4 ? "rgba(255,255,255,0.9)" : "rgba(255,255,255,0.4)",
                      border: isLikeliest ? "1px solid rgba(99,102,241,0.8)" : "1px solid transparent",
                      boxShadow: isLikeliest ? "0 0 8px rgba(99,102,241,0.4)" : "none",
                    }}>
                    {(prob * 100).toFixed(1)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Barre de probabilité ──────────────────────────────────────────────────────
function ProbBar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-[11px]" style={{ color: "rgba(255,255,255,0.5)" }}>{label}</span>
        <span className="text-[13px] font-black tabular-nums" style={{ color }}>
          {(value * 100).toFixed(1)}%
        </span>
      </div>
      <div className="h-1.5 rounded-full" style={{ background: "rgba(255,255,255,0.06)" }}>
        <div className="h-full rounded-full transition-all duration-700"
          style={{ width: `${value * 100}%`, background: color, boxShadow: `0 0 6px ${color}60` }} />
      </div>
    </div>
  );
}

// ─── Page ──────────────────────────────────────────────────────────────────────
export default function PredictionsPage() {
  const [homeTeam, setHomeTeam] = useState("");
  const [awayTeam, setAwayTeam] = useState("");
  const [result, setResult] = useState<AnalysisResult | null>(null);

  const analyze = useMutation({
    mutationFn: () => predictionsApi.analyze({ home_team: homeTeam, away_team: awayTeam }).then(r => r.data),
    onSuccess: (data) => setResult(data),
  });

  const pred = result?.prediction;

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "var(--bg-app)" }}>
      <Sidebar />
      <main className="ml-56 flex-1 overflow-y-auto">

        <header className="topbar px-8 py-4">
          <h1 className="text-[15px] font-bold text-white flex items-center gap-2">
            <Brain size={14} style={{ color: "#6366f1" }} />
            Prédictions
          </h1>
          <p className="text-[11px] mt-0.5" style={{ color: "rgba(255,255,255,0.3)" }}>
            Analyse Dixon-Coles · Score matrix · Value bets par marché
          </p>
        </header>

        <div className="px-8 py-7 space-y-6 animate-fade-in">

          {/* Formulaire */}
          <div className="card p-6">
            <p className="label-caps mb-5">Analyser un match</p>
            <div className="grid grid-cols-[1fr_auto_1fr_auto] gap-4 items-end">
              <div>
                <label className="label-caps block mb-2">Équipe domicile</label>
                <input className="input-pro" placeholder="ex. Arsenal"
                  value={homeTeam} onChange={e => setHomeTeam(e.target.value)} />
              </div>
              <div className="pb-2 text-[11px] font-bold" style={{ color: "rgba(255,255,255,0.2)" }}>VS</div>
              <div>
                <label className="label-caps block mb-2">Équipe extérieure</label>
                <input className="input-pro" placeholder="ex. Chelsea"
                  value={awayTeam} onChange={e => setAwayTeam(e.target.value)} />
              </div>
              <button className="btn-primary"
                disabled={!homeTeam || !awayTeam || analyze.isPending}
                onClick={() => analyze.mutate()}>
                {analyze.isPending
                  ? <><Loader2 size={12} className="animate-spin" /> Analyse...</>
                  : <><Play size={12} /> Analyser</>}
              </button>
            </div>
            {analyze.isError && (
              <p className="mt-3 text-[11px]" style={{ color: "#f87171" }}>
                Erreur : {(analyze.error as any)?.response?.data?.detail ?? "Connexion backend impossible"}
              </p>
            )}
          </div>

          {/* Résultats */}
          {pred && (
            <div className="space-y-5">
              {/* Header résultat */}
              <div className="card p-6">
                <div className="flex items-center justify-between mb-6">
                  <div>
                    <p className="text-[18px] font-black text-white">
                      {result?.home_team} <span style={{ color: "rgba(255,255,255,0.3)" }}>vs</span> {result?.away_team}
                    </p>
                    <p className="text-[11px] mt-1" style={{ color: "rgba(255,255,255,0.3)" }}>
                      Score le plus probable : <strong style={{ color: "#a5b4fc" }}>{pred.most_likely_score}</strong>
                      {" "}· λ dom = {pred.lambda_home.toFixed(2)} · λ ext = {pred.lambda_away.toFixed(2)}
                    </p>
                  </div>
                  <div className="text-center">
                    <p className="label-caps mb-1">Confiance</p>
                    <p className="text-[1.75rem] font-black tabular-nums" style={{ color: "#6366f1" }}>
                      {(pred.confidence * 100).toFixed(0)}%
                    </p>
                  </div>
                </div>

                {/* 1X2 */}
                <div className="grid grid-cols-3 gap-3 mb-6">
                  {[
                    { label: "Victoire Dom.", value: pred.prob_home,  color: "#4ade80" },
                    { label: "Match Nul",     value: pred.prob_draw,  color: "#f59e0b" },
                    { label: "Victoire Ext.", value: pred.prob_away,  color: "#f87171" },
                  ].map(({ label, value, color }) => (
                    <div key={label} className="text-center px-4 py-4 rounded-xl"
                      style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
                      <p className="label-caps mb-2">{label}</p>
                      <p className="text-[2rem] font-black tabular-nums" style={{ color }}>
                        {(value * 100).toFixed(1)}%
                      </p>
                    </div>
                  ))}
                </div>

                {/* Autres marchés */}
                <div className="grid grid-cols-2 gap-5">
                  <div className="space-y-3">
                    <p className="label-caps mb-3">Buts Over/Under</p>
                    <ProbBar label="Over 1.5" value={pred.prob_over_15} color="#4ade80" />
                    <ProbBar label="Over 2.5" value={pred.prob_over_25} color="#fbbf24" />
                    <ProbBar label="Over 3.5" value={pred.prob_over_35} color="#f87171" />
                  </div>
                  <div className="space-y-3">
                    <p className="label-caps mb-3">BTTS</p>
                    <ProbBar label="BTTS Oui" value={pred.prob_btts_yes} color="#67e8f9" />
                    <ProbBar label="BTTS Non" value={pred.prob_btts_no}  color="#94a3b8" />
                    <p className="label-caps mt-4 mb-3">Résultat exact</p>
                    <p className="text-[16px] font-black" style={{ color: "#c4b5fd" }}>{pred.most_likely_score}</p>
                  </div>
                </div>
              </div>

              {/* Score matrix */}
              <div className="card p-6">
                <p className="label-caps mb-4 flex items-center gap-2">
                  <BarChart2 size={11} />
                  Matrice Dixon-Coles — Probabilités par score (%)
                </p>
                {pred.score_matrix && pred.score_matrix.length > 0
                  ? <ScoreMatrix matrix={pred.score_matrix} />
                  : <p className="text-[11px]" style={{ color: "rgba(255,255,255,0.3)" }}>Matrice non disponible</p>}
                <p className="text-[9px] mt-3" style={{ color: "rgba(255,255,255,0.2)" }}>
                  Correction ρ Dixon-Coles appliquée sur scores 0-0, 1-0, 0-1, 1-1 · La cellule encadrée = score le plus probable
                </p>
              </div>

              {/* Value bets détectés */}
              {result?.value_bets && result.value_bets.length > 0 && (
                <div className="card p-6">
                  <p className="label-caps mb-4">Value Bets Détectés sur ce match</p>
                  <div className="space-y-2">
                    {result.value_bets.map((vb, i) => (
                      <div key={i} className="flex items-center justify-between px-4 py-3 rounded-xl"
                        style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)" }}>
                        <div>
                          <p className="text-[12px] font-semibold text-white">{vb.market}</p>
                          <p className="text-[10px] mt-0.5" style={{ color: "rgba(255,255,255,0.3)" }}>
                            P_modèle: {(vb.prob_model * 100).toFixed(1)}%
                          </p>
                        </div>
                        <div className="flex items-center gap-4">
                          <div className="text-right">
                            <p className="text-[11px]" style={{ color: "rgba(255,255,255,0.3)" }}>Cote BM</p>
                            <p className="text-[14px] font-black text-white tabular-nums">{vb.bookmaker_odds.toFixed(2)}</p>
                          </div>
                          <div className="text-right">
                            <p className="text-[11px]" style={{ color: "rgba(255,255,255,0.3)" }}>Edge</p>
                            <p className="text-[14px] font-black tabular-nums" style={{ color: "#4ade80" }}>
                              +{(vb.edge_pct).toFixed(1)}%
                            </p>
                          </div>
                          <span className="text-[10px] font-bold px-2.5 py-1 rounded-lg"
                            style={vb.value_rating === "FORT"
                              ? { background: "rgba(34,197,94,0.1)", color: "#4ade80" }
                              : { background: "rgba(245,158,11,0.1)", color: "#fbbf24" }}>
                            {vb.value_rating}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Empty state */}
          {!pred && !analyze.isPending && (
            <div className="flex flex-col items-center justify-center py-20">
              <div className="w-16 h-16 rounded-2xl flex items-center justify-center mb-4"
                style={{ background: "rgba(99,102,241,0.08)", border: "1px solid rgba(99,102,241,0.15)" }}>
                <Brain size={24} style={{ color: "rgba(99,102,241,0.5)" }} />
              </div>
              <p className="text-[14px] font-semibold" style={{ color: "rgba(255,255,255,0.3)" }}>
                Entrez deux équipes pour démarrer l'analyse
              </p>
              <p className="text-[11px] mt-1" style={{ color: "rgba(255,255,255,0.15)" }}>
                Le modèle Dixon-Coles calculera les probabilités et détectera les value bets
              </p>
            </div>
          )}

        </div>
      </main>
    </div>
  );
}
