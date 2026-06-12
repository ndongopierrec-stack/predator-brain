"use client";

// ─── Strategy Lab — Predator Brain ────────────────────────────────────────────
// Tableau de bord de validation walk-forward et sensibilité.
// Toutes les données viennent des résultats walk-forward générés par le backend.

import { useEffect, useState } from "react";
import axios from "axios";
import { FlaskConical, TrendingUp, TrendingDown, AlertTriangle,
         CheckCircle, XCircle, BarChart2, Activity, RefreshCw } from "lucide-react";

const API = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8001/api/v1");

// ── Types ────────────────────────────────────────────────────────────────────

interface WfRow {
  league: string; test_season: string; config: string;
  bets: number; win_rate: number; roi: number; max_dd: number; sharpe: number;
  n_train: number; n_test: number;
}

interface SensRow {
  conf: number; edge: number; bets: number;
  win_rate: number; roi: number; sharpe: number; max_dd: number;
}

interface LeagueStatus {
  avg_roi: number; avg_dd: number; n_seasons: number;
  n_positive: number; total_bets: number; status: string;
  issues: string[]; max_stake_pct: number; real_money: boolean;
}

interface ValidationStatus {
  global_status: string;
  no_money_mode: boolean;
  model_ready: boolean;
  n_matches_trained: number;
  walk_forward_available: boolean;
  generated_at: string;
  leagues: Record<string, LeagueStatus>;
  global_rules: { max_stake_global: number; paper_only: boolean; message: string };
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function statusColor(s: string): string {
  return {
    VALIDE:       "text-emerald-400",
    PROMETTEUR:   "text-emerald-300",
    OK:           "text-amber-400",
    A_CONFIRMER:  "text-amber-300",
    RISQUE_ELEVE: "text-orange-400",
    A_EVITER:     "text-red-400",
    INCONNU:      "text-slate-400",
  }[s] ?? "text-slate-400";
}

function statusBg(s: string): string {
  return {
    VALIDE:       "bg-emerald-500/10 border-emerald-500/25",
    PROMETTEUR:   "bg-emerald-500/08 border-emerald-500/20",
    OK:           "bg-amber-500/10 border-amber-500/25",
    A_CONFIRMER:  "bg-amber-500/08 border-amber-500/20",
    RISQUE_ELEVE: "bg-orange-500/10 border-orange-500/25",
    A_EVITER:     "bg-red-500/10 border-red-500/25",
    INCONNU:      "bg-slate-500/10 border-slate-500/25",
  }[s] ?? "bg-slate-500/10 border-slate-500/25";
}

function statusLabel(s: string): string {
  return {
    VALIDE:       "✅ VALIDÉ",
    PROMETTEUR:   "🟢 PROMETTEUR",
    OK:           "🟡 NEUTRE",
    A_CONFIRMER:  "🟡 À CONFIRMER",
    RISQUE_ELEVE: "🟠 RISQUE ÉLEVÉ",
    A_EVITER:     "🔴 À ÉVITER",
    INCONNU:      "⚪ INCONNU",
  }[s] ?? s;
}

function roiColor(v: number): string {
  return v > 0 ? "text-emerald-400" : v < 0 ? "text-red-400" : "text-slate-400";
}

// ── Composants ───────────────────────────────────────────────────────────────

function NoMoneyBanner({ rules }: { rules: ValidationStatus["global_rules"] }) {
  if (!rules.paper_only) return null;
  return (
    <div className="rounded-2xl p-4 flex items-start gap-3"
      style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.25)" }}>
      <AlertTriangle size={18} className="text-red-400 flex-shrink-0 mt-0.5" />
      <div>
        <p className="text-[13px] font-black text-red-400 mb-1">
          MODE NO-MONEY — Argent réel interdit
        </p>
        <p className="text-[12px]" style={{ color: "rgba(255,255,255,0.55)" }}>
          {rules.message}
        </p>
        <p className="text-[11px] mt-2 font-semibold text-orange-400">
          Mise max autorisée : {rules.max_stake_global}% du capital · Paper trading uniquement
        </p>
      </div>
    </div>
  );
}

function LeagueCard({ name, s }: { name: string; s: LeagueStatus }) {
  return (
    <div className={`rounded-2xl p-5 border ${statusBg(s.status)}`}>
      <div className="flex items-start justify-between mb-3">
        <p className="text-[14px] font-black text-white">{name}</p>
        <span className={`text-[10px] font-black ${statusColor(s.status)}`}>
          {statusLabel(s.status)}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-2 mb-3">
        {[
          { l: "ROI moyen", v: `${s.avg_roi > 0 ? "+" : ""}${s.avg_roi.toFixed(1)}%`, c: roiColor(s.avg_roi) },
          { l: "Saisons +", v: `${s.n_positive}/${s.n_seasons}`, c: s.n_positive >= s.n_seasons / 2 ? "text-emerald-400" : "text-red-400" },
          { l: "Paris total", v: s.total_bets.toLocaleString(), c: s.total_bets >= 500 ? "text-emerald-400" : "text-amber-400" },
        ].map(({ l, v, c }) => (
          <div key={l}>
            <p className="text-[9px] mb-1" style={{ color: "rgba(255,255,255,0.3)" }}>{l}</p>
            <p className={`text-[13px] font-bold ${c}`}>{v}</p>
          </div>
        ))}
      </div>
      <div className="text-[10px] space-y-1">
        <p style={{ color: "rgba(255,255,255,0.35)" }}>
          Mise max : <strong className="text-white">{s.max_stake_pct.toFixed(1)}%</strong> · DD moy : <strong style={{ color: s.avg_dd > 50 ? "#f87171" : "#fbbf24" }}>{s.avg_dd.toFixed(0)}%</strong>
        </p>
        {s.issues.slice(0, 2).map((iss, i) => (
          <p key={i} className="text-red-400/70">• {iss}</p>
        ))}
        {!s.real_money && (
          <p className="text-amber-400/80 font-semibold">⚠ Paper trading uniquement</p>
        )}
      </div>
    </div>
  );
}

function WfTable({ rows, selectedLeague }: { rows: WfRow[]; selectedLeague: string }) {
  const filtered = rows.filter(r => r.league === selectedLeague && r.config === "Med (0.58/5%)");
  if (!filtered.length) return (
    <p className="text-[12px]" style={{ color: "rgba(255,255,255,0.3)" }}>
      Pas de données walk-forward pour cette ligue. Lancez le script walk_forward_analysis.py.
    </p>
  );
  const avgRoi = filtered.reduce((s, r) => s + r.roi, 0) / filtered.length;
  const nPos   = filtered.filter(r => r.roi > 0).length;
  return (
    <div>
      <table className="w-full text-[12px]">
        <thead>
          <tr style={{ color: "rgba(255,255,255,0.3)" }}>
            <th className="text-left pb-3 font-semibold">Saison test</th>
            <th className="text-right pb-3 font-semibold">Entraîn.</th>
            <th className="text-right pb-3 font-semibold">Paris</th>
            <th className="text-right pb-3 font-semibold">WR</th>
            <th className="text-right pb-3 font-semibold">ROI</th>
            <th className="text-right pb-3 font-semibold">DD</th>
            <th className="text-right pb-3 font-semibold">Sharpe</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map(r => (
            <tr key={r.test_season} className="border-t" style={{ borderColor: "rgba(255,255,255,0.05)" }}>
              <td className="py-2.5 font-semibold text-white">{r.test_season}</td>
              <td className="py-2.5 text-right text-xs" style={{ color: "rgba(255,255,255,0.4)" }}>{r.n_train}</td>
              <td className="py-2.5 text-right" style={{ color: "rgba(255,255,255,0.6)" }}>{r.bets}</td>
              <td className="py-2.5 text-right" style={{ color: "rgba(255,255,255,0.6)" }}>{r.win_rate.toFixed(0)}%</td>
              <td className={`py-2.5 text-right font-bold ${roiColor(r.roi)}`}>
                {r.roi > 0 ? "+" : ""}{r.roi.toFixed(1)}%
              </td>
              <td className="py-2.5 text-right" style={{ color: r.max_dd > 60 ? "#f87171" : r.max_dd > 40 ? "#fbbf24" : "#4ade80" }}>
                {r.max_dd.toFixed(0)}%
              </td>
              <td className={`py-2.5 text-right font-bold ${r.sharpe > 1 ? "text-emerald-400" : r.sharpe > 0 ? "text-amber-400" : "text-red-400"}`}>
                {r.sharpe.toFixed(2)}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t-2" style={{ borderColor: "rgba(255,255,255,0.12)" }}>
            <td className="pt-3 font-black text-white text-[11px]">MOYENNE</td>
            <td />
            <td className="pt-3 text-right font-bold" style={{ color: "rgba(255,255,255,0.6)" }}>
              {filtered.reduce((s, r) => s + r.bets, 0)}
            </td>
            <td />
            <td className={`pt-3 text-right font-black ${roiColor(avgRoi)}`}>
              {avgRoi > 0 ? "+" : ""}{avgRoi.toFixed(1)}%
            </td>
            <td />
            <td className="pt-3 text-right font-bold text-slate-400">
              {nPos}/{filtered.length} +
            </td>
          </tr>
        </tfoot>
      </table>
      <p className="mt-3 text-[10px]" style={{ color: "rgba(255,255,255,0.25)" }}>
        Config : conf≥0.58, edge≥5%, Kelly×0.20, max 5%/pari, bankroll 10 000€
      </p>
    </div>
  );
}

function SensitivityTable({ rows }: { rows: SensRow[] }) {
  if (!rows.length) return (
    <p className="text-[12px]" style={{ color: "rgba(255,255,255,0.3)" }}>
      Données de sensibilité non disponibles. Lancer le script walk_forward_analysis.py.
    </p>
  );

  // Organiser en grille conf × edge
  const confs = [...new Set(rows.map(r => r.conf))].sort();
  const edges = [...new Set(rows.map(r => r.edge))].sort();

  return (
    <div className="overflow-x-auto">
      <p className="text-[11px] mb-3" style={{ color: "rgba(255,255,255,0.35)" }}>
        ROI sur la 2ème moitié des saisons disponibles. Vert = profitable.
      </p>
      <table className="text-[11px] w-full">
        <thead>
          <tr>
            <th className="text-left pb-2 pr-4 font-semibold" style={{ color: "rgba(255,255,255,0.4)" }}>
              Conf \ Edge→
            </th>
            {edges.map(e => (
              <th key={e} className="text-center pb-2 px-2 font-semibold" style={{ color: "rgba(255,255,255,0.4)" }}>
                {(e * 100).toFixed(0)}%
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {confs.map(conf => (
            <tr key={conf} className="border-t" style={{ borderColor: "rgba(255,255,255,0.05)" }}>
              <td className="py-2 pr-4 font-semibold text-white">{conf.toFixed(2)}</td>
              {edges.map(edge => {
                const cell = rows.find(r => r.conf === conf && r.edge === edge);
                if (!cell) return <td key={edge} className="py-2 px-2 text-center text-slate-600">-</td>;
                const bg = cell.roi > 5 ? "rgba(16,185,129,0.20)" :
                           cell.roi > 0 ? "rgba(16,185,129,0.08)" :
                           cell.roi > -5 ? "rgba(251,191,36,0.05)" :
                                          "rgba(239,68,68,0.08)";
                const tc = cell.roi > 0 ? "#4ade80" : cell.roi > -5 ? "#fbbf24" : "#f87171";
                return (
                  <td key={edge} className="py-2 px-2 text-center rounded">
                    <div className="rounded-md px-1 py-1" style={{ background: bg }}>
                      <p className="font-bold" style={{ color: tc }}>
                        {cell.roi > 0 ? "+" : ""}{cell.roi.toFixed(1)}%
                      </p>
                      <p className="text-[9px]" style={{ color: "rgba(255,255,255,0.3)" }}>
                        {cell.bets}p
                      </p>
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-[10px]" style={{ color: "rgba(255,255,255,0.2)" }}>
        Anti-overfitting : aucune combinaison optimisée sur 2023-24 uniquement. Valeurs sur la moitié test de toutes les saisons disponibles.
      </p>
    </div>
  );
}

// ── Page principale ───────────────────────────────────────────────────────────

export default function StrategyLabPage() {
  const [status, setStatus]       = useState<ValidationStatus | null>(null);
  const [wfRows, setWfRows]       = useState<WfRow[]>([]);
  const [sensRows, setSensRows]   = useState<SensRow[]>([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState<string | null>(null);
  const [selectedLeague, setSelectedLeague] = useState("Ligue 1");

  const LEAGUES = ["Ligue 1", "Premier League", "La Liga", "Bundesliga", "Serie A"];

  async function fetchAll() {
    setLoading(true);
    setError(null);
    try {
      const [s, wf, sens] = await Promise.all([
        axios.get(`${API}/validation/status`),
        axios.get(`${API}/validation/walk-forward`),
        axios.get(`${API}/validation/sensitivity?league=Ligue%201`),
      ]);
      setStatus(s.data);
      setWfRows(wf.data.results || []);
      setSensRows(sens.data.table || []);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchAll(); }, []);

  async function fetchSens(league: string) {
    try {
      const r = await axios.get(`${API}/validation/sensitivity?league=${encodeURIComponent(league)}`);
      setSensRows(r.data.table || []);
    } catch { /* silencieux */ }
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="text-center">
        <Activity size={24} className="mx-auto mb-3 text-indigo-400 animate-pulse" />
        <p className="text-[13px]" style={{ color: "rgba(255,255,255,0.4)" }}>
          Chargement des données de validation...
        </p>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen p-6 space-y-5" style={{ background: "linear-gradient(180deg,#04070d 0%,#060a12 100%)" }}>

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <FlaskConical size={20} style={{ color: "#6366f1" }} />
          <div>
            <h1 className="text-xl font-black text-white">Strategy Lab</h1>
            <p className="text-[11px]" style={{ color: "rgba(255,255,255,0.35)" }}>
              Validation walk-forward stricte · Anti-overfitting · No Money Mode
            </p>
          </div>
        </div>
        <button onClick={fetchAll}
          className="flex items-center gap-2 px-3 py-2 rounded-xl text-[12px] font-semibold transition-all"
          style={{ background: "rgba(99,102,241,0.10)", color: "#a5b4fc", border: "1px solid rgba(99,102,241,0.2)" }}>
          <RefreshCw size={12} />
          Actualiser
        </button>
      </div>

      {error && (
        <div className="rounded-xl p-4 text-[12px]"
          style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.25)", color: "#fca5a5" }}>
          <p className="font-bold mb-1">Erreur de connexion au backend</p>
          <p>{error}</p>
          <p className="mt-2 text-orange-400">
            Lancez d&apos;abord le backend (start-backend.bat), puis python scripts/walk_forward_analysis.py
          </p>
        </div>
      )}

      {/* Bannière No Money Mode */}
      {status?.global_rules && <NoMoneyBanner rules={status.global_rules} />}

      {/* Statut global */}
      {status && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            {
              l: "Statut global",
              v: statusLabel(status.global_status),
              c: statusColor(status.global_status),
              sub: "Pire ligue = statut global"
            },
            {
              l: "Modèle entraîné",
              v: status.model_ready ? "Oui" : "Non",
              c: status.model_ready ? "text-emerald-400" : "text-red-400",
              sub: `${status.n_matches_trained.toLocaleString()} matchs`
            },
            {
              l: "WF disponible",
              v: status.walk_forward_available ? "Oui" : "Non",
              c: status.walk_forward_available ? "text-emerald-400" : "text-amber-400",
              sub: status.generated_at !== "N/A" ? new Date(status.generated_at).toLocaleDateString("fr-FR") : "Jamais lancé"
            },
            {
              l: "Mise max globale",
              v: `${status.global_rules.max_stake_global}%`,
              c: "text-amber-400",
              sub: status.global_rules.paper_only ? "Paper trading" : "Trading réel OK"
            },
          ].map(({ l, v, c, sub }) => (
            <div key={l} className="rounded-2xl p-4"
              style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)" }}>
              <p className="text-[10px] mb-2" style={{ color: "rgba(255,255,255,0.35)" }}>{l}</p>
              <p className={`text-[15px] font-black ${c}`}>{v}</p>
              <p className="text-[9px] mt-1" style={{ color: "rgba(255,255,255,0.25)" }}>{sub}</p>
            </div>
          ))}
        </div>
      )}

      {/* Statut par ligue */}
      {status && Object.keys(status.leagues).length > 0 && (
        <div>
          <h2 className="text-[14px] font-bold text-white mb-3 flex items-center gap-2">
            <BarChart2 size={14} style={{ color: "#6366f1" }} />
            Statut par ligue (walk-forward strict)
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
            {Object.entries(status.leagues).map(([name, s]) => (
              <LeagueCard key={name} name={name} s={s} />
            ))}
          </div>
        </div>
      )}

      {/* Walk-forward saison par saison */}
      <div className="rounded-2xl p-6" style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-[14px] font-bold text-white flex items-center gap-2">
            <TrendingUp size={14} style={{ color: "#6366f1" }} />
            Walk-forward saison par saison
          </h2>
          <div className="flex gap-2">
            {LEAGUES.filter(l => wfRows.some(r => r.league === l)).map(l => (
              <button key={l}
                onClick={() => setSelectedLeague(l)}
                className="text-[10px] font-semibold px-2.5 py-1.5 rounded-lg transition-all"
                style={selectedLeague === l ? {
                  background: "rgba(99,102,241,0.20)", color: "#a5b4fc", border: "1px solid rgba(99,102,241,0.35)"
                } : {
                  background: "rgba(255,255,255,0.04)", color: "rgba(255,255,255,0.4)", border: "1px solid rgba(255,255,255,0.08)"
                }}>
                {l.replace("Premier League", "PL").replace("Bundesliga", "BL").replace("Serie A", "SA")}
              </button>
            ))}
          </div>
        </div>
        <WfTable rows={wfRows} selectedLeague={selectedLeague} />
      </div>

      {/* Tableau de sensibilité */}
      <div className="rounded-2xl p-6" style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-[14px] font-bold text-white flex items-center gap-2">
            <Activity size={14} style={{ color: "#6366f1" }} />
            Sensibilité conf × edge — Ligue 1
          </h2>
          <div className="flex gap-2">
            {["Ligue 1", "Premier League"].filter(l => wfRows.some(r => r.league === l)).map(l => (
              <button key={l}
                onClick={() => fetchSens(l)}
                className="text-[10px] font-semibold px-2.5 py-1.5 rounded-lg transition-all"
                style={{ background: "rgba(255,255,255,0.04)", color: "rgba(255,255,255,0.4)", border: "1px solid rgba(255,255,255,0.08)" }}>
                {l.replace("Premier League", "PL")}
              </button>
            ))}
          </div>
        </div>
        <SensitivityTable rows={sensRows} />
      </div>

      {/* Message de verdict */}
      <div className="rounded-2xl p-5" style={{
        background: "rgba(239,68,68,0.05)", border: "1px solid rgba(239,68,68,0.15)"
      }}>
        <div className="flex items-start gap-3">
          <XCircle size={16} className="text-red-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-[13px] font-black text-red-400 mb-2">
              Verdict actuel : AUCUNE STRATÉGIE VALIDÉE
            </p>
            <div className="text-[12px] space-y-1.5" style={{ color: "rgba(255,255,255,0.55)" }}>
              <p>• Walk-forward sur 5 saisons Ligue 1 : ROI moyen <strong className="text-red-400">-3.7%</strong>, seulement 2/5 saisons positives</p>
              <p>• Tableau de sensibilité : <strong className="text-red-400">aucune combinaison conf/edge n&apos;est positive</strong> sur la moitié test</p>
              <p>• Le signal +19.1% sur 2023-24 seul est du <strong className="text-amber-400">bruit statistique</strong> — non reproductible sur les saisons précédentes</p>
              <p>• Premier League : -4.5% moyen, 1/3 saisons positives — marché trop efficient</p>
            </div>
            <div className="mt-3 p-3 rounded-xl" style={{ background: "rgba(255,255,255,0.03)" }}>
              <p className="text-[11px] font-semibold text-amber-400 mb-1">Ce qui est nécessaire pour validation :</p>
              <div className="text-[11px] space-y-1" style={{ color: "rgba(255,255,255,0.45)" }}>
                <p>□ 500+ paris sur une même stratégie</p>
                <p>□ 4+ saisons positives consécutives</p>
                <p>□ Drawdown max &lt;40% sur toutes les saisons</p>
                <p>□ ROI moyen &gt;3% walk-forward</p>
                <p>□ Sharpe moyen &gt;1.0</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Instructions pour relancer */}
      <div className="rounded-xl p-4 text-[11px]"
        style={{ background: "rgba(99,102,241,0.05)", border: "1px solid rgba(99,102,241,0.15)" }}>
        <p className="text-indigo-400 font-semibold mb-2">Pour mettre à jour les résultats :</p>
        <code className="block text-[10px] p-2 rounded-lg" style={{ background: "rgba(0,0,0,0.3)", color: "#c4b5fd" }}>
          cd backend &amp;&amp; python scripts/download_extended_data.py &amp;&amp; python scripts/walk_forward_analysis.py
        </code>
        <p className="mt-2" style={{ color: "rgba(255,255,255,0.3)" }}>
          Puis rechargez cette page. Les résultats sont sauvegardés dans data/walk_forward_results.json
        </p>
      </div>

    </div>
  );
}
