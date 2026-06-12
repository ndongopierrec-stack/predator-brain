"use client";

import { useState, useEffect, useCallback } from "react";
import {
  TrendingUp, TrendingDown, Minus, AlertTriangle,
  CheckCircle2, XCircle, RefreshCw, Brain, Zap,
  BarChart2, Target, DollarSign, Activity, Info,
  Play, Download
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

const MARKET_LABELS: Record<string, string> = {
  home_win: "1X2 Domicile",
  over_25:  "Over 2.5",
  btts:     "BTTS",
  away_win: "1X2 Extérieur",
};

const MODEL_LABELS: Record<string, string> = {
  dc:     "Dixon-Coles",
  logreg: "Logistic Reg.",
  rf:     "Random Forest",
  xgb:    "XGBoost",
  lgbm:   "LightGBM",
};

const MODEL_COLORS: Record<string, string> = {
  dc:     "#6366f1",
  logreg: "#06b6d4",
  rf:     "#22c55e",
  xgb:    "#f59e0b",
  lgbm:   "#ec4899",
};

type Verdict = "PROFITABLE" | "BREAK_EVEN" | "NOT_PROFITABLE" | "INSUFFICIENT_DATA";

const VERDICT_CONFIG: Record<Verdict, { label: string; color: string; bg: string; icon: any }> = {
  PROFITABLE:        { label: "PROFITABLE",           color: "#22c55e", bg: "rgba(34,197,94,0.08)",   icon: CheckCircle2 },
  BREAK_EVEN:        { label: "ÉQUILIBRE",             color: "#f59e0b", bg: "rgba(245,158,11,0.08)",  icon: Minus },
  NOT_PROFITABLE:    { label: "NON PROFITABLE",        color: "#ef4444", bg: "rgba(239,68,68,0.08)",   icon: XCircle },
  INSUFFICIENT_DATA: { label: "DONNÉES INSUFFISANTES", color: "#6366f1", bg: "rgba(99,102,241,0.08)", icon: Info },
};

function RoiBar({ value }: { value: number | null }) {
  if (value === null || value === undefined) return <span style={{ color: "rgba(255,255,255,0.2)" }}>—</span>;
  const w = Math.min(Math.abs(value) * 5, 100);
  const color = value > 3 ? "#22c55e" : value > 0 ? "#86efac" : value > -3 ? "#fbbf24" : "#ef4444";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full" style={{ background: "rgba(255,255,255,0.06)" }}>
        <div className="h-full rounded-full" style={{ width: `${w}%`, background: color }} />
      </div>
      <span className="text-xs font-bold w-14 text-right" style={{ color }}>
        {value > 0 ? "+" : ""}{value.toFixed(1)}%
      </span>
    </div>
  );
}

function KpiCard({ icon: Icon, label, value, sub, color = "#6366f1" }: {
  icon: any; label: string; value: string | number | null; sub?: string; color?: string;
}) {
  return (
    <div className="rounded-2xl p-4" style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}>
      <div className="flex items-center gap-2 mb-2">
        <Icon size={13} style={{ color }} />
        <span className="text-[10px] font-semibold" style={{ color: "rgba(255,255,255,0.4)" }}>{label}</span>
      </div>
      <p className="text-lg font-black text-white">
        {value === null || value === undefined ? "—" : value}
      </p>
      {sub && <p className="text-[10px] mt-0.5" style={{ color: "rgba(255,255,255,0.3)" }}>{sub}</p>}
    </div>
  );
}

export default function ProfitabilityPage() {
  const [report, setReport] = useState<any>(null);
  const [verdict, setVerdict]   = useState<any>(null);
  const [mlStatus, setMlStatus] = useState<any>(null);
  const [scoreBet, setScoreBet] = useState<any>(null);
  const [loading, setLoading]   = useState(true);
  const [training, setTraining] = useState(false);

  // Formulaire score bet
  const [form, setForm] = useState({
    prob_model: 0.55, implied_bm: 0.45, odds: 2.2,
    market: "home_win", elo_diff: 50, market_signal: 60,
  });

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [repRes, verdRes, mlRes] = await Promise.all([
        fetch(`${API}/api/v1/profitability/report`),
        fetch(`${API}/api/v1/profitability/verdict`),
        fetch(`${API}/api/v1/profitability/ml-status`),
      ]);
      if (repRes.ok)  setReport(await repRes.json());
      if (verdRes.ok) setVerdict(await verdRes.json());
      if (mlRes.ok)   setMlStatus(await mlRes.json());
    } catch { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  async function handleTrainML() {
    setTraining(true);
    try {
      await fetch(`${API}/api/v1/profitability/train-ml`, { method: "POST" });
      // Attendre ~40s puis rafraîchir
      setTimeout(async () => {
        const r = await fetch(`${API}/api/v1/profitability/ml-status`);
        if (r.ok) setMlStatus(await r.json());
        setTraining(false);
      }, 40_000);
    } catch { setTraining(false); }
  }

  async function handleScoreBet() {
    try {
      const r = await fetch(`${API}/api/v1/profitability/score-bet`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, season_phase: 0.5, rest_diff: 0 }),
      });
      if (r.ok) setScoreBet(await r.json());
    } catch { /* ignore */ }
  }

  const verdictKey = (verdict?.verdict ?? "INSUFFICIENT_DATA") as Verdict;
  const vcfg = VERDICT_CONFIG[verdictKey];
  const VIcon = vcfg.icon;

  const globalData = report?.global ?? {};
  const noMoney = report?.no_money_mode !== false;

  return (
    <div className="p-6 space-y-6 max-w-[1400px]">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black text-white flex items-center gap-2">
            <DollarSign size={20} style={{ color: "#22c55e" }} />
            Audit de Rentabilité
          </h1>
          <p className="text-sm mt-1" style={{ color: "rgba(255,255,255,0.4)" }}>
            Walk-forward strict · CLV live · ML Scorer · Preuve mathématique d&apos;edge
          </p>
        </div>
        <button onClick={fetchAll}
          className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold"
          style={{ background: "rgba(255,255,255,0.06)", color: "rgba(255,255,255,0.6)" }}>
          <RefreshCw size={12} /> Actualiser
        </button>
      </div>

      {/* No Money Mode */}
      {noMoney && (
        <div className="rounded-2xl p-4 flex items-center gap-3"
          style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.3)" }}>
          <AlertTriangle size={16} style={{ color: "#ef4444" }} className="flex-shrink-0" />
          <p className="text-xs font-semibold" style={{ color: "#f87171" }}>
            🔴 NO MONEY MODE — Aucun modèle n&apos;a encore prouvé son edge. 0€ de vrai argent.
          </p>
        </div>
      )}

      {/* VERDICT */}
      {verdict && (
        <div className="rounded-2xl p-6"
          style={{ background: vcfg.bg, border: `2px solid ${vcfg.color}33` }}>
          <div className="flex items-center gap-3 mb-3">
            <VIcon size={24} style={{ color: vcfg.color }} />
            <div>
              <p className="text-xs font-semibold" style={{ color: "rgba(255,255,255,0.5)" }}>VERDICT GLOBAL</p>
              <h2 className="text-xl font-black" style={{ color: vcfg.color }}>{vcfg.label}</h2>
            </div>
            <div className="ml-auto text-right">
              <p className="text-xs" style={{ color: "rgba(255,255,255,0.4)" }}>ROI moyen WF</p>
              <p className="text-lg font-black" style={{ color: vcfg.color }}>
                {verdict.avg_roi_pct !== null && verdict.avg_roi_pct !== undefined
                  ? `${verdict.avg_roi_pct > 0 ? "+" : ""}${verdict.avg_roi_pct.toFixed(1)}%`
                  : "—"}
              </p>
            </div>
          </div>
          {verdict.details?.map((d: string, i: number) => (
            <p key={i} className="text-xs mt-1" style={{ color: "rgba(255,255,255,0.6)" }}>{d}</p>
          ))}
        </div>
      )}

      {/* KPIs globaux */}
      {report?.available && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <KpiCard icon={BarChart2} label="Total paris WF" color="#6366f1"
            value={globalData.total_bets?.toLocaleString() ?? "—"}
            sub="Walk-forward strict" />
          <KpiCard icon={TrendingUp} label="ROI moyen"
            color={globalData.avg_roi_pct > 0 ? "#22c55e" : "#ef4444"}
            value={globalData.avg_roi_pct !== null ? `${globalData.avg_roi_pct > 0 ? "+" : ""}${globalData.avg_roi_pct?.toFixed(1)}%` : "—"}
            sub="Moyenne toutes saisons" />
          <KpiCard icon={Activity} label="Saisons positives" color="#f59e0b"
            value={globalData.pct_seasons_positive !== null ? `${globalData.pct_seasons_positive?.toFixed(0)}%` : "—"}
            sub="% saisons > 0% ROI" />
          <KpiCard icon={AlertTriangle} label="Drawdown max" color="#ef4444"
            value={globalData.max_drawdown_pct !== null ? `${globalData.max_drawdown_pct?.toFixed(1)}%` : "—"}
            sub="Pire série perdante" />
        </div>
      )}

      {/* Grid par ligue + par modèle */}
      {report?.available && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

          {/* Par ligue */}
          <div className="rounded-2xl p-5"
            style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}>
            <h3 className="text-xs font-black text-white mb-4 flex items-center gap-2">
              <Target size={12} style={{ color: "#6366f1" }} /> ROI par ligue
            </h3>
            <div className="space-y-3">
              {Object.entries(report.by_league ?? {})
                .sort(([, a]: any, [, b]: any) => (b.avg_roi ?? -99) - (a.avg_roi ?? -99))
                .map(([league, d]: [string, any]) => (
                  <div key={league}>
                    <div className="flex justify-between text-[10px] mb-1">
                      <span style={{ color: "rgba(255,255,255,0.6)" }}>{league}</span>
                      <span style={{ color: "rgba(255,255,255,0.3)" }}>{d.n_bets?.toLocaleString()} paris</span>
                    </div>
                    <RoiBar value={d.avg_roi} />
                  </div>
                ))}
            </div>
          </div>

          {/* Par modèle */}
          <div className="rounded-2xl p-5"
            style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}>
            <h3 className="text-xs font-black text-white mb-4 flex items-center gap-2">
              <Brain size={12} style={{ color: "#6366f1" }} /> ROI par modèle
            </h3>
            <div className="space-y-3">
              {Object.entries(report.by_model ?? {})
                .sort(([, a]: any, [, b]: any) => (b.avg_roi ?? -99) - (a.avg_roi ?? -99))
                .map(([model, d]: [string, any]) => (
                  <div key={model}>
                    <div className="flex justify-between text-[10px] mb-1">
                      <span className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full" style={{ background: MODEL_COLORS[model] ?? "#6366f1" }} />
                        <span style={{ color: "rgba(255,255,255,0.6)" }}>{MODEL_LABELS[model] ?? model}</span>
                      </span>
                      <span style={{ color: d.n_valide > 0 ? "#22c55e" : "rgba(255,255,255,0.3)" }}>
                        {d.n_valide > 0 ? `✓ ${d.n_valide} VALIDE` : `${d.n_bets?.toLocaleString()} paris`}
                      </span>
                    </div>
                    <RoiBar value={d.avg_roi} />
                  </div>
                ))}
            </div>
          </div>
        </div>
      )}

      {/* Par marché */}
      {report?.available && (
        <div className="rounded-2xl p-5"
          style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}>
          <h3 className="text-xs font-black text-white mb-4 flex items-center gap-2">
            <Zap size={12} style={{ color: "#f59e0b" }} /> ROI par marché
          </h3>
          <div className="grid grid-cols-3 gap-4">
            {Object.entries(report.by_market ?? {})
              .sort(([, a]: any, [, b]: any) => (b.avg_roi ?? -99) - (a.avg_roi ?? -99))
              .map(([market, d]: [string, any]) => (
                <div key={market} className="rounded-xl p-3"
                  style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.05)" }}>
                  <p className="text-[10px] font-semibold mb-2" style={{ color: "rgba(255,255,255,0.5)" }}>
                    {MARKET_LABELS[market] ?? market}
                  </p>
                  <RoiBar value={d.avg_roi} />
                  <p className="text-[9px] mt-1" style={{ color: "rgba(255,255,255,0.25)" }}>
                    {d.n_bets?.toLocaleString()} paris
                  </p>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* CLV temps réel */}
      {report?.available && (
        <div className="rounded-2xl p-5"
          style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}>
          <h3 className="text-xs font-black text-white mb-4 flex items-center gap-2">
            <Target size={12} style={{ color: "#06b6d4" }} /> CLV Tracking (paris réels)
            <span className="text-[9px] px-1.5 py-0.5 rounded-md" style={{ background: "rgba(6,182,212,0.15)", color: "#67e8f9" }}>
              PINNACLE PROXY
            </span>
          </h3>
          <div className="grid grid-cols-3 gap-3 text-center">
            {[
              { label: "Paris trackés", value: report.clv_realtime?.n_bets_tracked ?? 0 },
              { label: "CLV moyen", value: report.clv_realtime?.avg_clv_pct !== null
                  ? `${(report.clv_realtime?.avg_clv_pct ?? 0) > 0 ? "+" : ""}${(report.clv_realtime?.avg_clv_pct ?? 0).toFixed(1)}%`
                  : "—" },
              { label: "CLV positif", value: report.clv_realtime?.pct_clv_positive !== null
                  ? `${(report.clv_realtime?.pct_clv_positive ?? 0).toFixed(0)}%`
                  : "—" },
            ].map(({ label, value }) => (
              <div key={label} className="rounded-xl p-3" style={{ background: "rgba(6,182,212,0.06)", border: "1px solid rgba(6,182,212,0.15)" }}>
                <p className="text-[10px] mb-1" style={{ color: "rgba(103,232,249,0.6)" }}>{label}</p>
                <p className="text-base font-black" style={{ color: "#67e8f9" }}>{value}</p>
              </div>
            ))}
          </div>
          {report.clv_realtime?.n_bets_tracked === 0 && (
            <p className="text-[10px] mt-3" style={{ color: "rgba(255,255,255,0.3)" }}>
              Aucun pari réel enregistré. Utiliser POST /api/v1/clv/record-bet pour commencer le tracking.
            </p>
          )}
        </div>
      )}

      {/* ML Bet Scorer */}
      <div className="rounded-2xl p-5"
        style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xs font-black text-white flex items-center gap-2">
            <Brain size={12} style={{ color: "#ec4899" }} /> ML Bet Scorer
            <span className="text-[9px] px-1.5 py-0.5 rounded-md" style={{ background: "rgba(236,72,153,0.15)", color: "#f9a8d4" }}>
              XGBOOST
            </span>
          </h3>
          <button onClick={handleTrainML} disabled={training}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold"
            style={{
              background: "rgba(236,72,153,0.15)", color: "#f9a8d4",
              border: "1px solid rgba(236,72,153,0.3)",
              opacity: training ? 0.6 : 1,
            }}>
            {training ? <><RefreshCw size={10} className="animate-spin" />Entraînement...</> : <><Play size={10} />Entraîner (~30s)</>}
          </button>
        </div>

        {/* Statut ML */}
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div className="rounded-xl p-3" style={{ background: "rgba(236,72,153,0.06)", border: "1px solid rgba(236,72,153,0.1)" }}>
            <p className="text-[10px] mb-1" style={{ color: "rgba(249,168,212,0.6)" }}>Statut</p>
            <p className="text-xs font-bold" style={{ color: mlStatus?.scorer_info?.trained ? "#22c55e" : "#ef4444" }}>
              {mlStatus?.scorer_info?.trained ? "✓ Entraîné" : "Non entraîné — cliquer 'Entraîner'"}
            </p>
          </div>
          <div className="rounded-xl p-3" style={{ background: "rgba(236,72,153,0.06)", border: "1px solid rgba(236,72,153,0.1)" }}>
            <p className="text-[10px] mb-1" style={{ color: "rgba(249,168,212,0.6)" }}>Données d&apos;entraînement</p>
            <p className="text-xs font-bold" style={{ color: "#f9a8d4" }}>
              {mlStatus?.scorer_info?.n_train?.toLocaleString() ?? "—"} matchs
            </p>
          </div>
        </div>

        {/* Formulaire score bet */}
        <div className="border-t pt-4" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
          <p className="text-[10px] font-semibold mb-3" style={{ color: "rgba(255,255,255,0.5)" }}>
            TESTER UN PARI POTENTIEL
          </p>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-3">
            {[
              { key: "prob_model", label: "Prob. modèle", step: 0.01, min: 0, max: 1 },
              { key: "implied_bm", label: "Prob. implicite BM", step: 0.01, min: 0, max: 1 },
              { key: "odds",       label: "Cote",         step: 0.05, min: 1.01, max: 20 },
              { key: "elo_diff",   label: "Diff. Elo",    step: 10, min: -300, max: 300 },
              { key: "market_signal", label: "Signal marché (0-100)", step: 5, min: 0, max: 100 },
            ].map(({ key, label, step, min, max }) => (
              <div key={key}>
                <label className="block text-[9px] mb-1" style={{ color: "rgba(255,255,255,0.4)" }}>{label}</label>
                <input type="number" step={step} min={min} max={max}
                  value={(form as any)[key]}
                  onChange={e => setForm(f => ({ ...f, [key]: parseFloat(e.target.value) || 0 }))}
                  className="w-full text-xs px-2 py-1.5 rounded-lg outline-none"
                  style={{ background: "rgba(255,255,255,0.06)", color: "white", border: "1px solid rgba(255,255,255,0.1)" }} />
              </div>
            ))}
          </div>
          <button onClick={handleScoreBet}
            className="w-full py-2 rounded-xl text-xs font-bold"
            style={{ background: "rgba(236,72,153,0.2)", color: "#f9a8d4", border: "1px solid rgba(236,72,153,0.3)" }}>
            Calculer ML Score
          </button>

          {scoreBet && (
            <div className="mt-3 rounded-xl p-4"
              style={{
                background: scoreBet.ml_score >= 70 ? "rgba(34,197,94,0.06)" :
                            scoreBet.ml_score >= 50 ? "rgba(245,158,11,0.06)" : "rgba(239,68,68,0.06)",
                border: `1px solid ${
                  scoreBet.ml_score >= 70 ? "rgba(34,197,94,0.2)" :
                  scoreBet.ml_score >= 50 ? "rgba(245,158,11,0.2)" : "rgba(239,68,68,0.2)"
                }`,
              }}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-black text-white">ML SCORE</span>
                <span className="text-2xl font-black" style={{
                  color: scoreBet.ml_score >= 70 ? "#22c55e" : scoreBet.ml_score >= 50 ? "#f59e0b" : "#ef4444"
                }}>{scoreBet.ml_score}/100</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-[10px]">
                {[
                  ["Recommandation", scoreBet.recommendation],
                  ["P(Profit)", `${(scoreBet.prob_profit * 100).toFixed(1)}%`],
                  ["P(CLV+)", `${(scoreBet.prob_clv_positive * 100).toFixed(1)}%`],
                  ["Edge vs BM", `${(scoreBet.edge_vs_bm * 100).toFixed(1)}%`],
                  ["Kelly suggéré", `${scoreBet.kelly_suggested.toFixed(1)}%`],
                  ["ML dispo", scoreBet.ml_available ? "✓ Oui" : "Heuristique"],
                ].map(([k, v]) => (
                  <div key={k} className="flex justify-between">
                    <span style={{ color: "rgba(255,255,255,0.4)" }}>{k}</span>
                    <span style={{ color: "rgba(255,255,255,0.8)" }} className="font-semibold">{v}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Règle officielle */}
      <div className="rounded-2xl p-4 flex gap-3"
        style={{ background: "rgba(99,102,241,0.06)", border: "1px solid rgba(99,102,241,0.15)" }}>
        <Info size={14} style={{ color: "#a5b4fc" }} className="flex-shrink-0 mt-0.5" />
        <div className="text-[10px] space-y-1" style={{ color: "rgba(165,180,252,0.7)" }}>
          <p><strong style={{ color: "#a5b4fc" }}>Règle officielle V2 :</strong> Pour passer PROFITABLE :</p>
          <p>500+ paris · ROI WF &gt;3% · Sharpe &gt;1 · 4+/5 saisons positives · DD &lt;40% · Brier &lt; bookmaker · CLV moyen &gt;0%</p>
          <p style={{ color: "rgba(255,255,255,0.4)" }}>
            Règle absolue : préférer un logiciel qui dit &ldquo;ne joue pas&rdquo; plutôt qu&apos;un logiciel qui fait perdre de l&apos;argent.
          </p>
        </div>
      </div>

    </div>
  );
}
