"use client";

import { useState, useEffect, useCallback } from "react";
import {
  BarChart2, RefreshCw, Play, AlertTriangle, CheckCircle2,
  TrendingUp, TrendingDown, Minus, Zap, Brain, FlaskConical,
  Info, Download
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

interface TableRow {
  model: string;
  league: string;
  market: string;
  roi_mean: number | null;
  n_bets: number;
  n_seasons: number;
  n_seasons_pos: number;
  brier_mean: number | null;
  bm_brier: number | null;
  beats_bm_brier: boolean | null;
  log_loss_mean: number | null;
  sharpe_mean: number | null;
  max_dd_mean: number | null;
  auc_mean: number | null;
  status: string;
}

interface Report {
  verdict: string;
  still_no_money_mode: boolean;
  n_valide: number;
  models_beating_dc: Array<{ model: string; roi_mean: number }>;
  best_calibration: { model: string; market: string; league: string; brier: number } | null;
  best_league: { league: string; avg_roi: number } | null;
  worst_league: { league: string; avg_roi: number } | null;
  best_market: { market: string; avg_roi: number } | null;
  n_models_beating_bm_brier: number;
}

const MODEL_COLORS: Record<string, string> = {
  dc:     "#6366f1",
  logreg: "#06b6d4",
  rf:     "#22c55e",
  xgb:    "#f59e0b",
  lgbm:   "#ec4899",
};

const MODEL_LABELS: Record<string, string> = {
  dc:     "Dixon-Coles",
  logreg: "Logistic Reg.",
  rf:     "Random Forest",
  xgb:    "XGBoost",
  lgbm:   "LightGBM",
};

const MARKET_LABELS: Record<string, string> = {
  home_win: "1X2 Domicile",
  over_25:  "Over 2.5",
  btts:     "BTTS",
};

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  VALIDE:       { label: "VALIDE",      color: "#22c55e", bg: "rgba(34,197,94,0.12)" },
  PROMETTEUR:   { label: "PROMETTEUR",  color: "#06b6d4", bg: "rgba(6,182,212,0.12)" },
  OK:           { label: "OK",          color: "#94a3b8", bg: "rgba(148,163,184,0.10)" },
  A_CONFIRMER:  { label: "À CONFIRMER", color: "#f59e0b", bg: "rgba(245,158,11,0.12)" },
  RISQUE_ELEVE: { label: "RISQUE",      color: "#f97316", bg: "rgba(249,115,22,0.12)" },
  A_EVITER:     { label: "À ÉVITER",    color: "#ef4444", bg: "rgba(239,68,68,0.12)" },
  INCONNU:      { label: "INCONNU",     color: "#475569", bg: "rgba(71,85,105,0.10)" },
};

function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.INCONNU;
  return (
    <span className="text-[9px] font-black tracking-widest px-1.5 py-0.5 rounded-md"
      style={{ color: cfg.color, background: cfg.bg }}>
      {cfg.label}
    </span>
  );
}

function RoiCell({ value }: { value: number | null }) {
  if (value === null || value === undefined) return <span className="text-[rgba(255,255,255,0.2)]">—</span>;
  const color = value > 3 ? "#22c55e" : value > 0 ? "#86efac" : value > -3 ? "#fbbf24" : "#ef4444";
  return <span style={{ color }} className="font-bold">{value > 0 ? "+" : ""}{value.toFixed(1)}%</span>;
}

function BrierCell({ brier, bm }: { brier: number | null; bm: number | null }) {
  if (!brier) return <span className="text-[rgba(255,255,255,0.2)]">—</span>;
  const beats = bm !== null && brier < bm;
  return (
    <span style={{ color: beats ? "#22c55e" : "rgba(255,255,255,0.5)" }}>
      {brier.toFixed(4)}
      {bm && <span className="ml-1 text-[9px]" style={{ color: "rgba(255,255,255,0.3)" }}>
        / {bm.toFixed(4)}</span>}
      {beats && <span className="ml-1 text-[9px]" style={{ color: "#22c55e" }}>✓</span>}
    </span>
  );
}

export default function ModelComparisonPage() {
  const [table, setTable] = useState<TableRow[]>([]);
  const [report, setReport] = useState<Report | null>(null);
  const [status, setStatus] = useState<any>(null);
  const [running, setRunning] = useState(false);
  const [filterLeague, setFilterLeague] = useState("all");
  const [filterMarket, setFilterMarket] = useState("all");
  const [filterModel, setFilterModel] = useState("all");
  const [sortField, setSortField] = useState<keyof TableRow>("roi_mean");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    try {
      const [statusRes, resultsRes, reportRes] = await Promise.all([
        fetch(`${API}/api/v1/model-comparison/status`),
        fetch(`${API}/api/v1/model-comparison/results`),
        fetch(`${API}/api/v1/model-comparison/report`),
      ]);

      if (statusRes.ok) setStatus(await statusRes.json());

      if (resultsRes.ok) {
        const d = await resultsRes.json();
        setTable(d.table ?? []);
      }

      if (reportRes.ok) {
        const r = await reportRes.json();
        if (r.available) setReport(r);
      }
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  async function handleRun() {
    setRunning(true);
    try {
      await fetch(`${API}/api/v1/model-comparison/run`, { method: "POST" });
      // Poller toutes les 30s
      const poll = setInterval(async () => {
        const s = await fetch(`${API}/api/v1/model-comparison/status`);
        const data = await s.json();
        setStatus(data);
        if (!data.running && data.results_available) {
          clearInterval(poll);
          setRunning(false);
          fetchAll();
        }
      }, 30_000);
    } catch {
      setRunning(false);
    }
  }

  // Filtrage + tri
  const leagues = ["all", ...Array.from(new Set(table.map(r => r.league)))];
  const markets = ["all", ...Array.from(new Set(table.map(r => r.market)))];
  const models  = ["all", ...Array.from(new Set(table.map(r => r.model)))];

  const filtered = table
    .filter(r => filterLeague === "all" || r.league === filterLeague)
    .filter(r => filterMarket === "all" || r.market === filterMarket)
    .filter(r => filterModel  === "all" || r.model  === filterModel)
    .sort((a, b) => {
      const av = (a as any)[sortField] ?? -999;
      const bv = (b as any)[sortField] ?? -999;
      return sortDir === "desc" ? bv - av : av - bv;
    });

  function toggleSort(field: keyof TableRow) {
    if (sortField === field) setSortDir(d => d === "desc" ? "asc" : "desc");
    else { setSortField(field); setSortDir("desc"); }
  }

  function exportCsv() {
    const h = ["model","league","market","roi_mean","n_bets","n_seasons","n_seasons_pos",
                "brier_mean","bm_brier","sharpe_mean","max_dd_mean","auc_mean","status"];
    const rows = filtered.map(r => h.map(k => (r as any)[k] ?? "").join(","));
    const blob = new Blob([[h.join(","), ...rows].join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = "model_comparison.csv"; a.click();
  }

  const noMoney = status?.no_money_mode !== false;

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="p-6 space-y-6 max-w-[1400px]">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black text-white flex items-center gap-2">
            <BarChart2 size={20} style={{ color: "#6366f1" }} />
            Comparaison Modèles V2
          </h1>
          <p className="text-sm mt-1" style={{ color: "rgba(255,255,255,0.4)" }}>
            Dixon-Coles · Logistic Reg. · Random Forest · XGBoost · LightGBM — Walk-forward strict
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={exportCsv}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold transition-all"
            style={{ background: "rgba(255,255,255,0.06)", color: "rgba(255,255,255,0.6)" }}>
            <Download size={12} /> Export CSV
          </button>
          <button onClick={fetchAll}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold transition-all"
            style={{ background: "rgba(255,255,255,0.06)", color: "rgba(255,255,255,0.6)" }}>
            <RefreshCw size={12} /> Actualiser
          </button>
          <button onClick={handleRun} disabled={running}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold transition-all"
            style={{
              background: running ? "rgba(99,102,241,0.3)" : "rgba(99,102,241,0.2)",
              color: "#a5b4fc",
              border: "1px solid rgba(99,102,241,0.3)",
              opacity: running ? 0.7 : 1,
            }}>
            {running ? <><RefreshCw size={12} className="animate-spin" /> Calcul en cours...</> :
                       <><Play size={12} /> Lancer calcul</>}
          </button>
        </div>
      </div>

      {/* No Money Mode banner */}
      {noMoney && (
        <div className="rounded-2xl p-4 flex items-center gap-3"
          style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.3)" }}>
          <AlertTriangle size={18} style={{ color: "#ef4444" }} className="flex-shrink-0" />
          <div>
            <p className="text-sm font-black" style={{ color: "#ef4444" }}>
              🔴 NO MONEY MODE — MODÈLE EN VALIDATION
            </p>
            <p className="text-xs mt-0.5" style={{ color: "rgba(239,68,68,0.7)" }}>
              Aucun modèle n&apos;atteint encore le statut VALIDE. 0€ de vrai argent jusqu&apos;à : 500+ paris, 4+ saisons positives, ROI WF &gt;3%, Brier &lt; baseline bookmaker.
            </p>
          </div>
        </div>
      )}

      {/* Status calcul */}
      {status && (
        <div className="rounded-xl p-3 flex items-center gap-3 text-xs"
          style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
          <div className="w-2 h-2 rounded-full"
            style={{ background: status.running ? "#f59e0b" : status.results_available ? "#22c55e" : "#475569" }} />
          <span style={{ color: "rgba(255,255,255,0.5)" }}>
            {status.running ? "Calcul en cours..." :
             status.results_available ? `Résultats disponibles — ${status.generated_at?.slice(0,19).replace("T"," ")}` :
             "Pas de résultats. Cliquer sur 'Lancer calcul'."}
          </span>
        </div>
      )}

      {/* Rapport honnête */}
      {report && (
        <div className="rounded-2xl p-5 space-y-4"
          style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
          <div className="flex items-center gap-2">
            <Brain size={14} style={{ color: "#6366f1" }} />
            <h2 className="text-sm font-black text-white">Rapport Honnête V2</h2>
            <span className="text-[9px] font-black px-2 py-0.5 rounded-full"
              style={{ background: "rgba(99,102,241,0.2)", color: "#a5b4fc" }}>AUDIT</span>
          </div>

          {/* Verdict */}
          <div className="rounded-xl p-3"
            style={{
              background: report.still_no_money_mode
                ? "rgba(239,68,68,0.06)" : "rgba(34,197,94,0.06)",
              border: `1px solid ${report.still_no_money_mode ? "rgba(239,68,68,0.2)" : "rgba(34,197,94,0.2)"}`,
            }}>
            <p className="text-xs font-semibold" style={{ color: report.still_no_money_mode ? "#f87171" : "#86efac" }}>
              {report.verdict}
            </p>
          </div>

          {/* Grid de stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              {
                label: "Modèles battant DC",
                value: report.models_beating_dc?.length > 0
                  ? report.models_beating_dc.map(m => `${MODEL_LABELS[m.model] || m.model} (${m.roi_mean > 0 ? "+" : ""}${m.roi_mean.toFixed(1)}%)`)
                      .join(", ")
                  : "Aucun",
                color: report.models_beating_dc?.length > 0 ? "#22c55e" : "#ef4444",
              },
              {
                label: "Meilleure calibration",
                value: report.best_calibration
                  ? `${MODEL_LABELS[report.best_calibration.model] || report.best_calibration.model} (Brier ${report.best_calibration.brier.toFixed(4)})`
                  : "N/A",
                color: "#06b6d4",
              },
              {
                label: "Meilleure ligue",
                value: report.best_league
                  ? `${report.best_league.league} (${report.best_league.avg_roi > 0 ? "+" : ""}${report.best_league.avg_roi.toFixed(1)}%)`
                  : "N/A",
                color: "#f59e0b",
              },
              {
                label: "Meilleur marché",
                value: report.best_market
                  ? `${MARKET_LABELS[report.best_market.market] || report.best_market.market} (${report.best_market.avg_roi > 0 ? "+" : ""}${report.best_market.avg_roi.toFixed(1)}%)`
                  : "N/A",
                color: "#ec4899",
              },
            ].map(({ label, value, color }) => (
              <div key={label} className="rounded-xl p-3"
                style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
                <p className="text-[10px] font-semibold mb-1" style={{ color: "rgba(255,255,255,0.35)" }}>{label}</p>
                <p className="text-xs font-bold" style={{ color }}>{value}</p>
              </div>
            ))}
          </div>

          {/* Infos supplémentaires */}
          <div className="flex gap-4 text-xs flex-wrap">
            <span style={{ color: "rgba(255,255,255,0.4)" }}>
              Modèles VALIDES : <strong style={{ color: report.n_valide > 0 ? "#22c55e" : "#ef4444" }}>{report.n_valide}</strong>
            </span>
            <span style={{ color: "rgba(255,255,255,0.4)" }}>
              Battent Brier BM : <strong style={{ color: report.n_models_beating_bm_brier > 0 ? "#22c55e" : "#94a3b8" }}>{report.n_models_beating_bm_brier}</strong>
            </span>
            <span style={{ color: "rgba(255,255,255,0.4)" }}>
              Ligue pire : <strong style={{ color: "#ef4444" }}>
                {report.worst_league ? `${report.worst_league.league} (${report.worst_league.avg_roi.toFixed(1)}%)` : "N/A"}
              </strong>
            </span>
          </div>

          {/* Règle officielle */}
          <div className="rounded-xl p-3 flex gap-2"
            style={{ background: "rgba(99,102,241,0.06)", border: "1px solid rgba(99,102,241,0.15)" }}>
            <Info size={13} style={{ color: "#a5b4fc" }} className="flex-shrink-0 mt-0.5" />
            <p className="text-[10px]" style={{ color: "rgba(165,180,252,0.7)" }}>
              <strong style={{ color: "#a5b4fc" }}>Règle officielle V2 :</strong>{" "}
              500+ paris · ROI WF &gt;3% · Sharpe &gt;1 · 4+/5 saisons positives · Drawdown acceptable ·
              Brier &lt; baseline bookmaker · CLV positif → statut VALIDE requis avant argent réel.
            </p>
          </div>
        </div>
      )}

      {/* Sans résultats — état vide */}
      {!loading && table.length === 0 && (
        <div className="rounded-2xl p-12 text-center"
          style={{ background: "rgba(255,255,255,0.02)", border: "1px dashed rgba(255,255,255,0.08)" }}>
          <FlaskConical size={32} className="mx-auto mb-3" style={{ color: "rgba(255,255,255,0.2)" }} />
          <p className="text-sm font-semibold" style={{ color: "rgba(255,255,255,0.3)" }}>
            Aucun résultat disponible
          </p>
          <p className="text-xs mt-1" style={{ color: "rgba(255,255,255,0.2)" }}>
            Cliquer sur "Lancer calcul" pour démarrer le walk-forward ML.
            <br />Durée estimée : 5–15 minutes selon les données disponibles.
          </p>
          <button onClick={handleRun} disabled={running}
            className="mt-4 flex items-center gap-2 mx-auto px-5 py-2.5 rounded-xl text-sm font-bold"
            style={{ background: "rgba(99,102,241,0.2)", color: "#a5b4fc", border: "1px solid rgba(99,102,241,0.3)" }}>
            <Play size={14} />
            Lancer le calcul V2
          </button>
        </div>
      )}

      {/* Table de comparaison */}
      {table.length > 0 && (
        <div className="rounded-2xl overflow-hidden"
          style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}>

          {/* Filtres */}
          <div className="p-4 border-b flex gap-3 flex-wrap items-center"
            style={{ borderColor: "rgba(255,255,255,0.06)" }}>
            <span className="text-xs font-semibold" style={{ color: "rgba(255,255,255,0.4)" }}>Filtres :</span>

            {[
              { label: "Ligue", value: filterLeague, set: setFilterLeague, options: leagues },
              { label: "Marché", value: filterMarket, set: setFilterMarket, options: markets },
              { label: "Modèle", value: filterModel, set: setFilterModel, options: models },
            ].map(({ label, value, set, options }) => (
              <select key={label} value={value} onChange={e => set(e.target.value)}
                className="text-xs px-2 py-1.5 rounded-lg outline-none"
                style={{ background: "rgba(255,255,255,0.06)", color: "rgba(255,255,255,0.7)", border: "1px solid rgba(255,255,255,0.08)" }}>
                {options.map(o => (
                  <option key={o} value={o} style={{ background: "#0a0e1a" }}>
                    {o === "all" ? `Toutes ${label}s` : (MARKET_LABELS[o] || MODEL_LABELS[o] || o)}
                  </option>
                ))}
              </select>
            ))}

            <span className="ml-auto text-xs" style={{ color: "rgba(255,255,255,0.3)" }}>
              {filtered.length} résultats
            </span>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
                  {[
                    { key: "model",       label: "Modèle" },
                    { key: "league",      label: "Ligue" },
                    { key: "market",      label: "Marché" },
                    { key: "roi_mean",    label: "ROI moy." },
                    { key: "n_bets",      label: "N paris" },
                    { key: "n_seasons_pos", label: "Sais. +" },
                    { key: "brier_mean",  label: "Brier / BM" },
                    { key: "log_loss_mean", label: "Log-loss" },
                    { key: "sharpe_mean", label: "Sharpe" },
                    { key: "max_dd_mean", label: "Max DD" },
                    { key: "auc_mean",    label: "AUC" },
                    { key: "status",      label: "Statut" },
                  ].map(col => (
                    <th key={col.key}
                      onClick={() => toggleSort(col.key as keyof TableRow)}
                      className="px-3 py-2.5 text-left cursor-pointer select-none whitespace-nowrap"
                      style={{ color: sortField === col.key ? "#a5b4fc" : "rgba(255,255,255,0.3)", fontWeight: 600 }}>
                      {col.label}
                      {sortField === col.key && (
                        <span className="ml-1">{sortDir === "desc" ? "↓" : "↑"}</span>
                      )}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((row, i) => (
                  <tr key={i}
                    style={{
                      borderBottom: "1px solid rgba(255,255,255,0.04)",
                      background: i % 2 === 0 ? "transparent" : "rgba(255,255,255,0.01)",
                    }}>
                    {/* Modèle */}
                    <td className="px-3 py-2.5">
                      <span className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full flex-shrink-0"
                          style={{ background: MODEL_COLORS[row.model] ?? "#6366f1" }} />
                        <span style={{ color: "rgba(255,255,255,0.8)" }}>
                          {MODEL_LABELS[row.model] ?? row.model}
                        </span>
                      </span>
                    </td>
                    {/* Ligue */}
                    <td className="px-3 py-2.5" style={{ color: "rgba(255,255,255,0.6)" }}>{row.league}</td>
                    {/* Marché */}
                    <td className="px-3 py-2.5" style={{ color: "rgba(255,255,255,0.5)" }}>
                      {MARKET_LABELS[row.market] ?? row.market}
                    </td>
                    {/* ROI */}
                    <td className="px-3 py-2.5"><RoiCell value={row.roi_mean} /></td>
                    {/* N paris */}
                    <td className="px-3 py-2.5" style={{ color: row.n_bets >= 500 ? "#22c55e" : "rgba(255,255,255,0.5)" }}>
                      {row.n_bets.toLocaleString()}
                    </td>
                    {/* Saisons + */}
                    <td className="px-3 py-2.5" style={{ color: "rgba(255,255,255,0.5)" }}>
                      <span style={{ color: row.n_seasons_pos >= 4 ? "#22c55e" : "rgba(255,255,255,0.5)" }}>
                        {row.n_seasons_pos}
                      </span>
                      <span style={{ color: "rgba(255,255,255,0.25)" }}>/{row.n_seasons}</span>
                    </td>
                    {/* Brier */}
                    <td className="px-3 py-2.5"><BrierCell brier={row.brier_mean} bm={row.bm_brier} /></td>
                    {/* Log-loss */}
                    <td className="px-3 py-2.5" style={{ color: "rgba(255,255,255,0.4)" }}>
                      {row.log_loss_mean?.toFixed(4) ?? "—"}
                    </td>
                    {/* Sharpe */}
                    <td className="px-3 py-2.5">
                      {row.sharpe_mean !== null && row.sharpe_mean !== undefined ? (
                        <span style={{ color: row.sharpe_mean >= 1 ? "#22c55e" : row.sharpe_mean > 0 ? "#fbbf24" : "#ef4444" }}>
                          {row.sharpe_mean.toFixed(2)}
                        </span>
                      ) : <span style={{ color: "rgba(255,255,255,0.2)" }}>—</span>}
                    </td>
                    {/* Max DD */}
                    <td className="px-3 py-2.5">
                      {row.max_dd_mean !== null && row.max_dd_mean !== undefined ? (
                        <span style={{ color: row.max_dd_mean <= 25 ? "#22c55e" : row.max_dd_mean <= 40 ? "#fbbf24" : "#ef4444" }}>
                          {row.max_dd_mean.toFixed(1)}%
                        </span>
                      ) : <span style={{ color: "rgba(255,255,255,0.2)" }}>—</span>}
                    </td>
                    {/* AUC */}
                    <td className="px-3 py-2.5" style={{ color: "rgba(255,255,255,0.4)" }}>
                      {row.auc_mean?.toFixed(3) ?? "—"}
                    </td>
                    {/* Statut */}
                    <td className="px-3 py-2.5"><StatusBadge status={row.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Légende */}
          <div className="p-4 border-t flex gap-4 flex-wrap"
            style={{ borderColor: "rgba(255,255,255,0.06)" }}>
            <span className="text-[10px]" style={{ color: "rgba(255,255,255,0.25)" }}>
              Brier/BM : score Brier du modèle / baseline bookmaker (✓ = modèle meilleur)
            </span>
            <span className="text-[10px]" style={{ color: "rgba(255,255,255,0.25)" }}>
              Sharpe ≥ 1 = bon · Max DD ≤ 25% = acceptable · Sais.+ ≥ 4 = robuste
            </span>
          </div>
        </div>
      )}

      {/* Grille résumé par modèle */}
      {table.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {Object.keys(MODEL_LABELS).map(m => {
            const rows = table.filter(r => r.model === m);
            if (rows.length === 0) return null;
            const rois = rows.map(r => r.roi_mean).filter(v => v !== null) as number[];
            const avgRoi = rois.length ? rois.reduce((a, b) => a + b, 0) / rois.length : null;
            const nValide = rows.filter(r => r.status === "VALIDE").length;
            const bestBrier = rows.map(r => r.brier_mean).filter(v => v !== null).sort()[0];
            return (
              <div key={m} className="rounded-2xl p-4"
                style={{ background: "rgba(255,255,255,0.02)", border: `1px solid ${MODEL_COLORS[m]}22` }}>
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-2.5 h-2.5 rounded-full" style={{ background: MODEL_COLORS[m] }} />
                  <p className="text-xs font-black text-white">{MODEL_LABELS[m]}</p>
                </div>
                <div className="space-y-1.5">
                  <div className="flex justify-between text-[10px]">
                    <span style={{ color: "rgba(255,255,255,0.4)" }}>ROI moyen</span>
                    <RoiCell value={avgRoi !== null ? Math.round(avgRoi * 10) / 10 : null} />
                  </div>
                  <div className="flex justify-between text-[10px]">
                    <span style={{ color: "rgba(255,255,255,0.4)" }}>Brier min</span>
                    <span style={{ color: "rgba(255,255,255,0.6)" }}>
                      {bestBrier !== undefined ? bestBrier.toFixed(4) : "—"}
                    </span>
                  </div>
                  <div className="flex justify-between text-[10px]">
                    <span style={{ color: "rgba(255,255,255,0.4)" }}>Statuts VALIDE</span>
                    <span style={{ color: nValide > 0 ? "#22c55e" : "rgba(255,255,255,0.4)" }}>
                      {nValide} / {rows.length}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
