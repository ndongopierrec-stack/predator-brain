"use client";

import { useQuery } from "@tanstack/react-query";
import { predictionsApi } from "@/lib/api";
import {
  AlertTriangle, CheckCircle, XCircle, Activity,
  Database, TrendingUp, Shield, Zap, Info
} from "lucide-react";

interface ModelQuality {
  is_trained: boolean;
  warning_level: "OK" | "WARNING" | "CRITICAL";
  warnings: string[];
  model_params?: {
    gamma: number; rho: number;
    n_teams: number; n_matches_trained: number;
  };
  dataset?: {
    total_matches: number; date_from: string; date_to: string;
    avg_goals: number; home_win_rate: number; draw_rate: number;
    away_win_rate: number; over_25_rate: number; btts_rate: number;
  };
  leagues?: string[];
  by_league?: Record<string, {
    matches: number; teams: number;
    known_teams: number; coverage_pct: number;
  }>;
  top_teams?: {
    attack: Array<{ team: string; score: number }>;
    defense: Array<{ team: string; score: number }>;
  };
  interpretation?: { gamma_meaning: string; rho_meaning: string };
  recommendations?: string[];
}

export default function ModelQualityPage() {
  const { data, isLoading, error, refetch } = useQuery<ModelQuality>({
    queryKey: ["model-quality"],
    queryFn: async () => {
      const res = await predictionsApi.modelQuality();
      return res.data as ModelQuality;
    },
    refetchInterval: 30000,
  });

  const levelColor = {
    OK:       "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
    WARNING:  "text-amber-400 bg-amber-500/10 border-amber-500/30",
    CRITICAL: "text-red-400 bg-red-500/10 border-red-500/30",
  };

  const levelIcon = {
    OK:       <CheckCircle className="w-5 h-5 text-emerald-400" />,
    WARNING:  <AlertTriangle className="w-5 h-5 text-amber-400" />,
    CRITICAL: <XCircle className="w-5 h-5 text-red-400" />,
  };

  if (isLoading) return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500" />
    </div>
  );

  if (error || !data) return (
    <div className="p-6 text-red-400 bg-red-500/10 rounded-xl border border-red-500/20">
      Erreur de chargement des métriques qualité.
    </div>
  );

  const wl = data.warning_level ?? "CRITICAL";

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Activity className="w-7 h-7 text-indigo-400" />
            Qualité du Modèle
          </h1>
          <p className="text-slate-400 mt-1">
            Calibration Dixon-Coles · Couverture par championnat · Avertissements
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium transition-colors"
        >
          Actualiser
        </button>
      </div>

      {/* Statut global */}
      <div className={`rounded-xl border p-5 ${levelColor[wl]}`}>
        <div className="flex items-start gap-3">
          {levelIcon[wl]}
          <div>
            <h2 className="font-semibold">
              {wl === "OK" && "Modèle correctement calibré"}
              {wl === "WARNING" && "Modèle opérationnel avec avertissements"}
              {wl === "CRITICAL" && "Modèle non utilisable pour paris réels"}
            </h2>
            <ul className="mt-2 space-y-1">
              {data.warnings?.map((w, i) => (
                <li key={i} className="text-sm opacity-90">{w}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      {!data.is_trained ? (
        /* Pas entraîné */
        <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-8 text-center">
          <XCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-white mb-2">Modèle non entraîné</h3>
          <p className="text-slate-400 mb-4">
            Aucune donnée historique chargée. Les prédictions utilisent des valeurs génériques.
          </p>
          <ol className="text-left text-sm text-slate-400 space-y-1 max-w-md mx-auto">
            <li>1. Téléchargez des CSV depuis <a href="https://www.football-data.co.uk" target="_blank" className="text-indigo-400 underline">football-data.co.uk</a></li>
            <li>2. Placez-les dans <code className="bg-slate-700 px-1 rounded">data/raw/</code></li>
            <li>3. Cliquez sur <strong className="text-white">Réentraîner</strong> dans Paramètres</li>
          </ol>
        </div>
      ) : (
        <>
          {/* KPI cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <KpiCard
              label="Matchs d'entraînement"
              value={data.model_params?.n_matches_trained?.toLocaleString() ?? "—"}
              icon={<Database className="w-4 h-4" />}
              color="indigo"
            />
            <KpiCard
              label="Équipes modélisées"
              value={data.model_params?.n_teams?.toString() ?? "—"}
              icon={<Shield className="w-4 h-4" />}
              color="purple"
            />
            <KpiCard
              label="Avantage domicile (γ)"
              value={data.model_params?.gamma?.toFixed(3) ?? "—"}
              icon={<TrendingUp className="w-4 h-4" />}
              color="cyan"
              sub="Norme: 0.20–0.35"
            />
            <KpiCard
              label="Correction ρ (Dixon-Coles)"
              value={data.model_params?.rho?.toFixed(4) ?? "—"}
              icon={<Zap className="w-4 h-4" />}
              color="amber"
              sub="Norme: −0.10 à −0.15"
            />
          </div>

          {/* Dataset stats */}
          {data.dataset && (
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-5">
              <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4">
                Statistiques du Dataset
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <StatRow label="Période" value={`${data.dataset.date_from} → ${data.dataset.date_to}`} span />
                <StatRow label="Victoire domicile" value={`${data.dataset.home_win_rate}%`} bench="~46%" />
                <StatRow label="Match nul" value={`${data.dataset.draw_rate}%`} bench="~27%" />
                <StatRow label="Victoire extérieure" value={`${data.dataset.away_win_rate}%`} bench="~27%" />
                <StatRow label="Over 2.5" value={`${data.dataset.over_25_rate}%`} bench="~51%" />
                <StatRow label="BTTS" value={`${data.dataset.btts_rate}%`} bench="~49%" />
                <StatRow label="Buts / match" value={data.dataset.avg_goals?.toFixed(2)} bench="~2.65" />
              </div>
              <p className="text-xs text-slate-500 mt-3">
                <Info className="w-3 h-3 inline mr-1" />
                Les benchmarks correspondent aux moyennes européennes sur 10 saisons.
              </p>
            </div>
          )}

          {/* Couverture par championnat */}
          {data.by_league && Object.keys(data.by_league).length > 0 && (
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-5">
              <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4">
                Couverture par Championnat
              </h3>
              <div className="space-y-3">
                {Object.entries(data.by_league)
                  .sort((a, b) => b[1].matches - a[1].matches)
                  .map(([league, stats]) => (
                    <div key={league} className="flex items-center gap-4">
                      <div className="w-36 text-sm text-slate-300 truncate">{league}</div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <div className="flex-1 bg-slate-700 rounded-full h-2">
                            <div
                              className={`h-2 rounded-full transition-all ${
                                stats.coverage_pct >= 90 ? "bg-emerald-500" :
                                stats.coverage_pct >= 70 ? "bg-amber-500" : "bg-red-500"
                              }`}
                              style={{ width: `${stats.coverage_pct}%` }}
                            />
                          </div>
                          <span className={`text-xs font-mono w-12 text-right ${
                            stats.coverage_pct >= 90 ? "text-emerald-400" :
                            stats.coverage_pct >= 70 ? "text-amber-400" : "text-red-400"
                          }`}>
                            {stats.coverage_pct}%
                          </span>
                        </div>
                      </div>
                      <div className="text-xs text-slate-500 w-32 text-right">
                        {stats.known_teams}/{stats.teams} équipes · {stats.matches} matchs
                      </div>
                    </div>
                  ))}
              </div>
              <p className="text-xs text-slate-500 mt-3">
                <Info className="w-3 h-3 inline mr-1" />
                Couverture = % d'équipes présentes dans le modèle. En dessous de 70%, les prédictions sont moins fiables.
              </p>
            </div>
          )}

          {/* Top équipes */}
          {data.top_teams && (
            <div className="grid md:grid-cols-2 gap-4">
              <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-5">
                <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-3">
                  Top Attaques (α)
                </h3>
                <div className="space-y-2">
                  {data.top_teams.attack.map((t, i) => (
                    <div key={t.team} className="flex items-center gap-3">
                      <span className="text-xs text-slate-500 w-4">{i + 1}</span>
                      <span className="text-sm text-white flex-1">{t.team}</span>
                      <span className="text-xs font-mono text-emerald-400">+{t.score.toFixed(3)}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-5">
                <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-3">
                  Top Défenses (β bas = solide)
                </h3>
                <div className="space-y-2">
                  {data.top_teams.defense.map((t, i) => (
                    <div key={t.team} className="flex items-center gap-3">
                      <span className="text-xs text-slate-500 w-4">{i + 1}</span>
                      <span className="text-sm text-white flex-1">{t.team}</span>
                      <span className="text-xs font-mono text-cyan-400">{t.score.toFixed(3)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Interprétation */}
          {data.interpretation && (
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-5">
              <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-3">
                Interprétation des Paramètres
              </h3>
              <div className="space-y-2 text-sm text-slate-400">
                <p>📐 {data.interpretation.gamma_meaning}</p>
                <p>📉 {data.interpretation.rho_meaning}</p>
              </div>
            </div>
          )}

          {/* Recommandations */}
          {data.recommendations && (
            <div className="bg-indigo-500/10 border border-indigo-500/20 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-indigo-300 uppercase tracking-wider mb-3">
                Recommandations d&apos;utilisation
              </h3>
              <ul className="space-y-1">
                {data.recommendations.map((r, i) => (
                  <li key={i} className="text-sm text-slate-300">{r}</li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function KpiCard({ label, value, icon, color, sub }: {
  label: string; value: string; icon: React.ReactNode;
  color: "indigo" | "purple" | "cyan" | "amber"; sub?: string;
}) {
  const colors = {
    indigo: "text-indigo-400 bg-indigo-500/10",
    purple: "text-purple-400 bg-purple-500/10",
    cyan:   "text-cyan-400 bg-cyan-500/10",
    amber:  "text-amber-400 bg-amber-500/10",
  };
  return (
    <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4">
      <div className={`inline-flex p-2 rounded-lg mb-3 ${colors[color]}`}>{icon}</div>
      <p className="text-xs text-slate-400 mb-1">{label}</p>
      <p className="text-xl font-bold text-white">{value}</p>
      {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
    </div>
  );
}

function StatRow({ label, value, bench, span }: {
  label: string; value?: string | number | null;
  bench?: string; span?: boolean;
}) {
  return (
    <div className={span ? "col-span-2" : ""}>
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-sm text-white font-medium">{value ?? "—"}</p>
      {bench && <p className="text-xs text-slate-600">Référence: {bench}</p>}
    </div>
  );
}
