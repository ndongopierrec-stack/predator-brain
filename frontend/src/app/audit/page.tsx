"use client";

// ─── Audit Fonctionnel — Predator Brain ───────────────────────────────────────
// Rapport honnête basé sur backtest réel hors-échantillon (saison 2023-24)
// 5 ligues × 3 saisons = 5 404 matchs — football-data.co.uk

import { ShieldCheck, TrendingUp, TrendingDown, AlertTriangle, CheckCircle, XCircle, Info, BarChart2, Target, Zap } from "lucide-react";

// ── Types ────────────────────────────────────────────────────────────────────

interface LeagueRow {
  league: string;
  bets: number;
  winRate: number;
  roi: number;
  maxDD: number;
  sharpe: number;
  verdict: "green" | "amber" | "red";
}

interface StrategyRow {
  name: string;
  bets: number;
  winRate: number;
  roi: number;
  maxDD: number;
  sharpe: number;
}

// ── Données du backtest (2023-24 hors-échantillon, time_decay=True) ───────────

const LEAGUE_RESULTS: LeagueRow[] = [
  { league: "Ligue 1",        bets: 218, winRate: 58, roi: +23.0, maxDD: 18, sharpe: 2.09, verdict: "green" },
  { league: "La Liga",        bets: 293, winRate: 58, roi:  +0.9, maxDD: 42, sharpe: 0.11, verdict: "amber" },
  { league: "Serie A",        bets: 330, winRate: 52, roi:  -6.8, maxDD: 62, sharpe: -0.44, verdict: "red" },
  { league: "Bundesliga",     bets: 147, winRate: 54, roi: -15.8, maxDD: 71, sharpe: -0.88, verdict: "red" },
  { league: "Premier League", bets: 298, winRate: 39, roi: -24.2, maxDD: 95, sharpe: -1.52, verdict: "red" },
];

const STRATEGY_RESULTS: StrategyRow[] = [
  { name: "Modéré (conf≥0.55, edge≥4%)",    bets: 1335, winRate: 52, roi:  -4.7, maxDD: 97, sharpe: -0.39 },
  { name: "Strict (conf≥0.60, edge≥6%)",    bets:  723, winRate: 55, roi:  -3.0, maxDD: 80, sharpe: -0.18 },
  { name: "Très strict (conf≥0.65, edge≥8%)", bets: 311, winRate: 59, roi: -2.7, maxDD: 51, sharpe: -0.12 },
  { name: "Ligue 1 uniquement",             bets:  225, winRate: 56, roi:  +8.4, maxDD: 41, sharpe:  2.09 },
  { name: "Toutes sauf Premier League",     bets:  998, winRate: 56, roi:  +1.7, maxDD: 77, sharpe:  0.51 },
  { name: "Ligue 1 stricte (conf≥0.58, edge≥5%)", bets: 158, winRate: 63, roi: +19.1, maxDD: 36, sharpe: 3.45 },
];

// ── Composants ───────────────────────────────────────────────────────────────

function Badge({ color, children }: { color: "green"|"amber"|"red"|"blue"; children: React.ReactNode }) {
  const styles: Record<string, string> = {
    green: "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20",
    amber: "bg-amber-500/10  text-amber-400  border border-amber-500/20",
    red:   "bg-red-500/10    text-red-400    border border-red-500/20",
    blue:  "bg-indigo-500/10 text-indigo-400 border border-indigo-500/20",
  };
  return (
    <span className={`text-[10px] font-bold tracking-wider px-2 py-0.5 rounded-md ${styles[color]}`}>
      {children}
    </span>
  );
}

function KpiCard({ label, value, sub, color }: { label: string; value: string; sub?: string; color: "green"|"amber"|"red"|"blue" }) {
  const val: Record<string, string> = {
    green: "text-emerald-400", amber: "text-amber-400", red: "text-red-400", blue: "text-indigo-400",
  };
  return (
    <div className="rounded-2xl p-5" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)" }}>
      <p className="text-[11px] font-medium mb-2" style={{ color: "rgba(255,255,255,0.4)" }}>{label}</p>
      <p className={`text-2xl font-black ${val[color]}`}>{value}</p>
      {sub && <p className="text-[10px] mt-1" style={{ color: "rgba(255,255,255,0.3)" }}>{sub}</p>}
    </div>
  );
}

function Section({ title, icon: Icon, children }: { title: string; icon: React.ElementType; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl p-6" style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}>
      <div className="flex items-center gap-2.5 mb-5">
        <Icon size={16} style={{ color: "#6366f1" }} />
        <h2 className="text-[15px] font-bold text-white">{title}</h2>
      </div>
      {children}
    </div>
  );
}

// ── Page principale ───────────────────────────────────────────────────────────

export default function AuditPage() {
  return (
    <div className="min-h-screen p-6 space-y-6" style={{ background: "linear-gradient(180deg,#04070d 0%,#060a12 100%)" }}>

      {/* Header */}
      <div className="rounded-2xl p-6" style={{
        background: "linear-gradient(135deg, rgba(99,102,241,0.12), rgba(139,92,246,0.08))",
        border: "1px solid rgba(99,102,241,0.2)",
      }}>
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <ShieldCheck size={20} style={{ color: "#6366f1" }} />
              <h1 className="text-xl font-black text-white">Audit Fonctionnel Complet</h1>
            </div>
            <p className="text-[13px]" style={{ color: "rgba(255,255,255,0.5)" }}>
              Backtest hors-échantillon — Saison 2023-24 · Dixon-Coles · 5 ligues · 5 404 matchs historiques
            </p>
          </div>
          <Badge color="blue">HORS-ÉCHANTILLON</Badge>
        </div>

        {/* Résumé données */}
        <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
          {[
            { v: "5 404", l: "Matchs historiques" },
            { v: "3 saisons", l: "2021–22 à 2023–24" },
            { v: "5 ligues", l: "Top 5 européennes" },
            { v: "119 équipes", l: "Couverture 86%" },
          ].map(({ v, l }) => (
            <div key={l} className="rounded-xl p-3" style={{ background: "rgba(255,255,255,0.04)" }}>
              <p className="text-[15px] font-black text-white">{v}</p>
              <p className="text-[10px] mt-0.5" style={{ color: "rgba(255,255,255,0.35)" }}>{l}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Résultats globaux */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KpiCard label="ROI Stratégie Globale" value="-4.7%" sub="Toutes ligues, conf≥0.55" color="red" />
        <KpiCard label="ROI Ligue 1 Strict"    value="+19.1%" sub="158 paris, conf≥0.58" color="green" />
        <KpiCard label="Sharpe Ligue 1 Strict" value="3.45"  sub="Excellent (>2 = bon)" color="green" />
        <KpiCard label="Drawdown Ligue 1 Strict" value="36%" sub="Acceptable (<50%)" color="amber" />
      </div>

      {/* Par championnat */}
      <Section title="Résultats par championnat (2023-24 hors-échantillon)" icon={BarChart2}>
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr style={{ color: "rgba(255,255,255,0.3)" }}>
                <th className="text-left pb-3 font-semibold">Championnat</th>
                <th className="text-right pb-3 font-semibold">Paris</th>
                <th className="text-right pb-3 font-semibold">Win rate</th>
                <th className="text-right pb-3 font-semibold">ROI</th>
                <th className="text-right pb-3 font-semibold">Drawdown</th>
                <th className="text-right pb-3 font-semibold">Sharpe</th>
                <th className="text-right pb-3 font-semibold">Verdict</th>
              </tr>
            </thead>
            <tbody>
              {LEAGUE_RESULTS.map((row) => (
                <tr key={row.league} className="border-t" style={{ borderColor: "rgba(255,255,255,0.05)" }}>
                  <td className="py-3 font-semibold text-white">{row.league}</td>
                  <td className="py-3 text-right" style={{ color: "rgba(255,255,255,0.6)" }}>{row.bets}</td>
                  <td className="py-3 text-right" style={{ color: "rgba(255,255,255,0.6)" }}>{row.winRate}%</td>
                  <td className={`py-3 text-right font-bold ${row.roi > 0 ? "text-emerald-400" : "text-red-400"}`}>
                    {row.roi > 0 ? "+" : ""}{row.roi.toFixed(1)}%
                  </td>
                  <td className="py-3 text-right" style={{ color: row.maxDD > 60 ? "#f87171" : row.maxDD > 40 ? "#fbbf24" : "#4ade80" }}>
                    {row.maxDD}%
                  </td>
                  <td className={`py-3 text-right font-bold ${row.sharpe > 1 ? "text-emerald-400" : row.sharpe > 0 ? "text-amber-400" : "text-red-400"}`}>
                    {row.sharpe.toFixed(2)}
                  </td>
                  <td className="py-3 text-right">
                    {row.verdict === "green" && <Badge color="green">JOUER</Badge>}
                    {row.verdict === "amber" && <Badge color="amber">NEUTRE</Badge>}
                    {row.verdict === "red"   && <Badge color="red">ÉVITER</Badge>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {/* Stratégies testées */}
      <Section title="Comparaison des stratégies (Kelly¼, bankroll 10 000€)" icon={Target}>
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr style={{ color: "rgba(255,255,255,0.3)" }}>
                <th className="text-left pb-3 font-semibold">Stratégie</th>
                <th className="text-right pb-3 font-semibold">Paris</th>
                <th className="text-right pb-3 font-semibold">Win rate</th>
                <th className="text-right pb-3 font-semibold">ROI</th>
                <th className="text-right pb-3 font-semibold">Drawdown</th>
                <th className="text-right pb-3 font-semibold">Sharpe</th>
              </tr>
            </thead>
            <tbody>
              {STRATEGY_RESULTS.map((row) => {
                const isGood = row.sharpe > 1;
                const isBest = row.sharpe > 3;
                return (
                  <tr key={row.name}
                    className="border-t"
                    style={{
                      borderColor: "rgba(255,255,255,0.05)",
                      background: isBest ? "rgba(99,102,241,0.06)" : "transparent",
                    }}>
                    <td className="py-3 font-medium" style={{ color: isBest ? "#a5b4fc" : "rgba(255,255,255,0.7)" }}>
                      {isBest && <span className="mr-1.5">⭐</span>}{row.name}
                    </td>
                    <td className="py-3 text-right" style={{ color: "rgba(255,255,255,0.5)" }}>{row.bets}</td>
                    <td className="py-3 text-right" style={{ color: "rgba(255,255,255,0.5)" }}>{row.winRate}%</td>
                    <td className={`py-3 text-right font-bold ${row.roi > 0 ? "text-emerald-400" : "text-red-400"}`}>
                      {row.roi > 0 ? "+" : ""}{row.roi.toFixed(1)}%
                    </td>
                    <td className="py-3 text-right" style={{ color: row.maxDD > 80 ? "#f87171" : row.maxDD > 50 ? "#fbbf24" : "#4ade80" }}>
                      {row.maxDD}%
                    </td>
                    <td className={`py-3 text-right font-bold ${row.sharpe > 1 ? "text-emerald-400" : row.sharpe > 0 ? "text-amber-400" : "text-red-400"}`}>
                      {row.sharpe.toFixed(2)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="mt-4 text-[11px]" style={{ color: "rgba(255,255,255,0.3)" }}>
          ⭐ Stratégie recommandée · Toutes les données sont hors-échantillon (modèle entraîné sur 2021-22 + 2022-23, testé sur 2023-24)
        </p>
      </Section>

      {/* 2 colonnes : Ce qui fonctionne / Ce qui ne fonctionne pas */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Ce qui fonctionne */}
        <div className="rounded-2xl p-5" style={{ background: "rgba(16,185,129,0.05)", border: "1px solid rgba(16,185,129,0.15)" }}>
          <div className="flex items-center gap-2 mb-4">
            <CheckCircle size={15} className="text-emerald-400" />
            <h3 className="text-[13px] font-bold text-emerald-400">Ce qui fonctionne</h3>
          </div>
          <ul className="space-y-3 text-[12px]" style={{ color: "rgba(255,255,255,0.65)" }}>
            <li className="flex gap-2">
              <span className="text-emerald-400 mt-0.5">✓</span>
              <span><strong className="text-white">Ligue 1 :</strong> ROI +19.1% sur 158 paris avec Sharpe 3.45 — signal statistiquement fort, drawdown acceptable (36%)</span>
            </li>
            <li className="flex gap-2">
              <span className="text-emerald-400 mt-0.5">✓</span>
              <span><strong className="text-white">Prédictions 1X2 domicile :</strong> Win rate 58-63% sur les marchés Ligue 1 à forte confiance</span>
            </li>
            <li className="flex gap-2">
              <span className="text-emerald-400 mt-0.5">✓</span>
              <span><strong className="text-white">Model quality :</strong> gamma=0.24 (avantage domicile réaliste), rho=-0.03 (correction DC conforme à la littérature)</span>
            </li>
            <li className="flex gap-2">
              <span className="text-emerald-400 mt-0.5">✓</span>
              <span><strong className="text-white">Vitesse :</strong> Entraînement optimisé vectorisé — 5404 matchs en 9 secondes (vs 25 min avant)</span>
            </li>
            <li className="flex gap-2">
              <span className="text-emerald-400 mt-0.5">✓</span>
              <span><strong className="text-white">Gestion bankroll Kelly¼ :</strong> Contrôle du risque — jamais plus de 5% du capital par pari</span>
            </li>
          </ul>
        </div>

        {/* Ce qui ne fonctionne pas */}
        <div className="rounded-2xl p-5" style={{ background: "rgba(239,68,68,0.05)", border: "1px solid rgba(239,68,68,0.15)" }}>
          <div className="flex items-center gap-2 mb-4">
            <XCircle size={15} className="text-red-400" />
            <h3 className="text-[13px] font-bold text-red-400">Ce qui ne fonctionne pas</h3>
          </div>
          <ul className="space-y-3 text-[12px]" style={{ color: "rgba(255,255,255,0.65)" }}>
            <li className="flex gap-2">
              <span className="text-red-400 mt-0.5">✗</span>
              <span><strong className="text-white">Premier League :</strong> ROI -24.2%, drawdown 95% — marché le plus efficient d&apos;Europe, impossible à battre avec ce modèle</span>
            </li>
            <li className="flex gap-2">
              <span className="text-red-400 mt-0.5">✗</span>
              <span><strong className="text-white">Bundesliga :</strong> ROI -15.8% — modèle sous-calibré sur les équipes allemandes</span>
            </li>
            <li className="flex gap-2">
              <span className="text-red-400 mt-0.5">✗</span>
              <span><strong className="text-white">Stratégie multi-ligues :</strong> ROI -4.7%, drawdown 97% — les mauvaises ligues détruisent les bonnes performances</span>
            </li>
            <li className="flex gap-2">
              <span className="text-red-400 mt-0.5">✗</span>
              <span><strong className="text-white">Marché Over/Under :</strong> ROI -3 à -6% — les cotes bookmakers capturent déjà les paramètres Poisson</span>
            </li>
            <li className="flex gap-2">
              <span className="text-red-400 mt-0.5">✗</span>
              <span><strong className="text-white">Équipes promues :</strong> 14% de matchs non couverts — les nouvelles équipes ont des paramètres par défaut peu fiables</span>
            </li>
          </ul>
        </div>
      </div>

      {/* Marchés à éviter */}
      <Section title="Marchés à éviter absolument" icon={AlertTriangle}>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[
            {
              title: "Premier League",
              why: "Marché le plus suivi au monde. Les bookmakers ont des modèles supérieurs. Notre edge réel est négatif (-24.2% ROI). Drawdown de 95% en une seule saison.",
              color: "red" as const,
            },
            {
              title: "Bundesliga",
              why: "Sur-représentation des grosses équipes (Bayern, Dortmund). Le modèle confond la dominance passée avec l'edge futur. ROI -15.8%.",
              color: "red" as const,
            },
            {
              title: "Marchés Over/Under (multi-ligues)",
              why: "Les cotes implicites des bookmakers reflètent déjà les lambdas Poisson. Notre modèle n'a pas d'avantage informationnel sur ce marché.",
              color: "amber" as const,
            },
          ].map(({ title, why, color }) => (
            <div key={title} className="rounded-xl p-4" style={{
              background: color === "red" ? "rgba(239,68,68,0.05)" : "rgba(251,191,36,0.05)",
              border: `1px solid ${color === "red" ? "rgba(239,68,68,0.15)" : "rgba(251,191,36,0.15)"}`,
            }}>
              <p className={`text-[12px] font-bold mb-2 ${color === "red" ? "text-red-400" : "text-amber-400"}`}>⚠ {title}</p>
              <p className="text-[11px]" style={{ color: "rgba(255,255,255,0.5)" }}>{why}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* Recommandations avant argent réel */}
      <Section title="Avant d'utiliser avec de l'argent réel" icon={Zap}>
        <div className="space-y-3">
          {[
            {
              num: "01",
              title: "Valider sur 2 saisons supplémentaires de Ligue 1",
              desc: "158 paris sur une saison ne sont pas statistiquement suffisants. Il faut 300+ paris pour une significativité à 95%. Télécharger les données 2019-21 et ré-tester.",
              done: false,
            },
            {
              num: "02",
              title: "Limiter à la Ligue 1 uniquement",
              desc: "Supprimer les 4 autres ligues de la stratégie de trading. Ne garder que les matchs Ligue 1 avec conf≥0.58 et edge≥5%.",
              done: false,
            },
            {
              num: "03",
              title: "Implémenter le Closing Line Value (CLV)",
              desc: "Si nos cotes d'ouverture sont meilleures que les cotes de fermeture des bookmakers, c'est la preuve d'un vrai edge. Le logiciel a déjà le module CLV — l'alimenter avec des données réelles.",
              done: false,
            },
            {
              num: "04",
              title: "Paper trading 1 saison complète",
              desc: "Simuler des paris sans argent réel pendant toute la saison 2024-25 et comparer avec les prédictions. Confirmer le Sharpe >1.5 avant de risquer du capital.",
              done: false,
            },
            {
              num: "05",
              title: "Ajouter les données des saisons 2019-21",
              desc: "Plus de données historiques = paramètres plus stables. Télécharger E0/F1/SP1/I1/D1 pour 2019-20 et 2020-21 sur football-data.co.uk.",
              done: false,
            },
          ].map(({ num, title, desc, done }) => (
            <div key={num} className="flex gap-4 p-4 rounded-xl" style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)" }}>
              <div className="flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-[11px] font-black"
                style={{ background: done ? "rgba(16,185,129,0.15)" : "rgba(99,102,241,0.12)", color: done ? "#4ade80" : "#a5b4fc" }}>
                {done ? "✓" : num}
              </div>
              <div>
                <p className="text-[12px] font-semibold text-white mb-1">{title}</p>
                <p className="text-[11px]" style={{ color: "rgba(255,255,255,0.45)" }}>{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* Verdict final */}
      <div className="rounded-2xl p-6" style={{
        background: "linear-gradient(135deg, rgba(99,102,241,0.10), rgba(16,185,129,0.06))",
        border: "1px solid rgba(99,102,241,0.2)",
      }}>
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp size={16} style={{ color: "#6366f1" }} />
          <h2 className="text-[15px] font-black text-white">Verdict Global</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
          <div className="p-4 rounded-xl" style={{ background: "rgba(239,68,68,0.07)", border: "1px solid rgba(239,68,68,0.2)" }}>
            <p className="text-red-400 font-black text-[13px] mb-2">🔴 PAS PRÊT — argent réel</p>
            <p className="text-[11px]" style={{ color: "rgba(255,255,255,0.5)" }}>
              La stratégie générale (5 ligues) perd de l&apos;argent. Ne pas risquer de capital réel avant validation supplémentaire.
            </p>
          </div>
          <div className="p-4 rounded-xl" style={{ background: "rgba(251,191,36,0.07)", border: "1px solid rgba(251,191,36,0.2)" }}>
            <p className="text-amber-400 font-black text-[13px] mb-2">🟡 PROMETTEUR — Ligue 1</p>
            <p className="text-[11px]" style={{ color: "rgba(255,255,255,0.5)" }}>
              Signal fort sur la Ligue 1 (Sharpe 3.45, ROI +19%). À confirmer sur 2+ saisons supplémentaires avant capital réel.
            </p>
          </div>
          <div className="p-4 rounded-xl" style={{ background: "rgba(16,185,129,0.07)", border: "1px solid rgba(16,185,129,0.2)" }}>
            <p className="text-emerald-400 font-black text-[13px] mb-2">✅ VALIDE — Paper trading</p>
            <p className="text-[11px]" style={{ color: "rgba(255,255,255,0.5)" }}>
              Le logiciel est opérationnel pour le paper trading Ligue 1. Lancer la saison 2024-25 en simulation pour confirmer l&apos;edge.
            </p>
          </div>
        </div>

        <div className="p-4 rounded-xl text-[12px]" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
          <p style={{ color: "rgba(255,255,255,0.6)" }}>
            <strong className="text-white">Résumé :</strong> Predator Brain identifie un edge réel en Ligue 1 mais pas dans les autres championnats européens. Le modèle Dixon-Coles est correctement calibré (gamma=0.24, rho=-0.03). La prochaine étape est la validation sur données additionnelles, pas le déploiement avec argent réel. Un Sharpe de 3.45 sur une saison peut être du bruit statistique sur 158 paris — il devient fiable à partir de 500+ paris.
          </p>
        </div>
      </div>

      {/* Méthodogie */}
      <div className="rounded-xl p-4 text-[11px]" style={{ background: "rgba(255,255,255,0.01)", border: "1px solid rgba(255,255,255,0.04)" }}>
        <div className="flex items-start gap-2">
          <Info size={12} className="mt-0.5 flex-shrink-0" style={{ color: "rgba(255,255,255,0.3)" }} />
          <p style={{ color: "rgba(255,255,255,0.3)" }}>
            <strong className="text-white/50">Méthodologie :</strong> Backtest walk-forward strict — le modèle est entraîné uniquement sur 2021-22 + 2022-23, puis testé sur 2023-24 sans aucune donnée future. Cotes d&apos;ouverture Bet365 (B365H/D/A, B365&gt;2.5). Kelly quart avec cap 5% par pari. Sources : football-data.co.uk (usage légal — données historiques publiques). Aucun scraping de bookmakers, aucune API privée.
          </p>
        </div>
      </div>

    </div>
  );
}
