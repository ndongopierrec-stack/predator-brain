"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Ticket, Play, Loader2, Star, AlertTriangle, ChevronDown } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { predictionsApi } from "@/lib/api";

type TicketType = "SAFE" | "BALANCED" | "RISKY" | "JACKPOT";

const TICKET_PROFILES: Record<TicketType, { label: string; desc: string; legs: string; odds: string; color: string; emoji: string }> = {
  SAFE:     { label: "Sécurisé",   desc: "2-3 sélections, cote 2.5–6",   legs: "2-3",  odds: "2.5×–6×",   color: "#4ade80", emoji: "🛡️" },
  BALANCED: { label: "Équilibré",  desc: "3-5 sélections, cote 5–15",    legs: "3-5",  odds: "5×–15×",    color: "#fbbf24", emoji: "⚖️" },
  RISKY:    { label: "Risqué",     desc: "4-6 sélections, cote 10–50",   legs: "4-6",  odds: "10×–50×",   color: "#f87171", emoji: "🎯" },
  JACKPOT:  { label: "Jackpot",    desc: "5-8 sélections, cote 40–200",  legs: "5-8",  odds: "40×–200×",  color: "#c4b5fd", emoji: "💥" },
};

// Tickets démo
const DEMO_TICKETS: Record<TicketType, any[]> = {
  SAFE: [
    {
      legs: [
        { match: "Real Madrid vs Atlético", market: "BTTS Oui",      odds: 1.74, edge: 8.4, conf: 82 },
        { match: "Bayern vs Dortmund",      market: "Over 2.5",       odds: 1.80, edge: 6.4, conf: 71 },
      ],
      total_odds: 3.13, combined_prob: 0.58, fair_odds: 1.72,
      implied_edge_pct: 82.0, quality_score: 87, risk_rating: "FAIBLE",
      recommended_stake_pct: 2.5, recommended_stake_abs: 250,
      is_recommended: true,
      summary: "Deux sélections à forte valeur, marchés indépendants, confiance élevée.",
      warnings: [],
    },
  ],
  BALANCED: [
    {
      legs: [
        { match: "Arsenal vs Chelsea",      market: "BTTS Oui",      odds: 1.87, edge: 7.8, conf: 78 },
        { match: "PSG vs OM",               market: "Over 2.5",      odds: 1.75, edge: 5.1, conf: 69 },
        { match: "Inter vs Milan",          market: "BTTS Oui",      odds: 1.68, edge: 4.3, conf: 66 },
      ],
      total_odds: 5.49, combined_prob: 0.38, fair_odds: 2.63,
      implied_edge_pct: 108.8, quality_score: 79, risk_rating: "MODÉRÉ",
      recommended_stake_pct: 1.5, recommended_stake_abs: 150,
      is_recommended: true,
      summary: "Trois sélections avec edge positif. Marchés BTTS / O/U diversifiés.",
      warnings: [],
    },
  ],
  RISKY: [
    {
      legs: [
        { match: "Arsenal vs Chelsea",      market: "Over 3.5",      odds: 2.10, edge: 6.4, conf: 62 },
        { match: "Real Madrid vs Barça",    market: "Over 3.5",      odds: 2.25, edge: 5.2, conf: 58 },
        { match: "Liverpool vs Man City",   market: "BTTS Oui",      odds: 1.68, edge: 3.7, conf: 60 },
        { match: "Séville vs Betis",        market: "Extérieur",     odds: 3.40, edge: 3.2, conf: 55 },
      ],
      total_odds: 26.93, combined_prob: 0.12, fair_odds: 8.33,
      implied_edge_pct: 223.3, quality_score: 64, risk_rating: "ÉLEVÉ",
      recommended_stake_pct: 0.75, recommended_stake_abs: 75,
      is_recommended: false,
      summary: "Sélections risquées à cote élevée. Gestion stricte de la mise obligatoire.",
      warnings: ["Corrélation légère entre les matchs anglais", "Cote totale élevée — risque important"],
    },
  ],
  JACKPOT: [
    {
      legs: [
        { match: "Arsenal vs Chelsea",    market: "Over 3.5",    odds: 2.10, edge: 6.4, conf: 62 },
        { match: "Real Madrid vs Barça",  market: "Over 3.5",    odds: 2.25, edge: 5.2, conf: 58 },
        { match: "Liverpool vs Man City", market: "BTTS Oui",    odds: 1.68, edge: 3.7, conf: 60 },
        { match: "Séville vs Betis",      market: "Extérieur",   odds: 3.40, edge: 3.2, conf: 55 },
        { match: "PSG vs OM",             market: "Over 2.5",    odds: 1.75, edge: 5.1, conf: 69 },
        { match: "Bayern vs Leipzig",     market: "Domicile",    odds: 1.45, edge: 4.0, conf: 72 },
      ],
      total_odds: 67.6, combined_prob: 0.048, fair_odds: 20.8,
      implied_edge_pct: 225.0, quality_score: 51, risk_rating: "TRÈS ÉLEVÉ",
      recommended_stake_pct: 0.25, recommended_stake_abs: 25,
      is_recommended: false,
      summary: "Ticket jackpot 6 sélections. Probabilité faible, gain potentiel élevé.",
      warnings: ["Ticket jackpot : mise maximale 0.25% de bankroll", "Ne jamais miser plus que conseillé"],
    },
  ],
};

const RISK_COLORS: Record<string, string> = {
  "FAIBLE":     "#4ade80",
  "MODÉRÉ":     "#fbbf24",
  "ÉLEVÉ":      "#f87171",
  "TRÈS ÉLEVÉ": "#ef4444",
};

export default function TicketBuilderPage() {
  const [ticketType, setTicketType] = useState<TicketType>("BALANCED");
  const [stake, setStake] = useState("100");
  const [generated, setGenerated] = useState(false);

  const generate = useMutation({
    mutationFn: () => predictionsApi.generateTicket({ ticket_type: ticketType, n_tickets: 3 }).then(r => r.data),
    onSuccess: () => setGenerated(true),
    onError: () => setGenerated(true), // Affiche demo si backend offline
  });

  const tickets = DEMO_TICKETS[ticketType];
  const profile = TICKET_PROFILES[ticketType];
  const stakeNum = parseFloat(stake) || 100;

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "var(--bg-app)" }}>
      <Sidebar />
      <main className="ml-56 flex-1 overflow-y-auto">

        <header className="topbar px-8 py-4">
          <h1 className="text-[15px] font-bold text-white flex items-center gap-2">
            <Ticket size={14} style={{ color: "#f59e0b" }} />
            Générateur de Tickets
          </h1>
          <p className="text-[11px] mt-0.5" style={{ color: "rgba(255,255,255,0.3)" }}>
            Tickets combinés intelligents · Anti-corrélation · Kelly recommandé
          </p>
        </header>

        <div className="px-8 py-7 space-y-5 animate-fade-in">

          {/* Sélecteur de type */}
          <div className="grid grid-cols-4 gap-3">
            {(Object.entries(TICKET_PROFILES) as [TicketType, typeof TICKET_PROFILES[TicketType]][]).map(([key, p]) => (
              <button key={key} onClick={() => { setTicketType(key); setGenerated(false); }}
                className="px-4 py-4 rounded-xl text-left transition-all"
                style={ticketType === key
                  ? { background: `rgba(255,255,255,0.06)`, border: `1.5px solid ${p.color}40`, color: p.color }
                  : { background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", color: "rgba(255,255,255,0.45)" }}>
                <div className="flex items-center gap-2 mb-1.5">
                  <span>{p.emoji}</span>
                  <p className="text-[13px] font-bold">{p.label}</p>
                </div>
                <p className="text-[10px]" style={{ color: "rgba(255,255,255,0.3)" }}>{p.desc}</p>
                <div className="flex gap-2 mt-2">
                  <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: "rgba(255,255,255,0.05)", color: "rgba(255,255,255,0.3)" }}>
                    {p.legs} sélections
                  </span>
                  <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: "rgba(255,255,255,0.05)", color: "rgba(255,255,255,0.3)" }}>
                    cote {p.odds}
                  </span>
                </div>
              </button>
            ))}
          </div>

          {/* Paramètres + bouton */}
          <div className="card p-5 flex items-end gap-5">
            <div className="flex-1">
              <label className="label-caps block mb-2">Mise de base (€)</label>
              <input className="input-pro max-w-48" type="number" value={stake}
                onChange={e => setStake(e.target.value)} />
            </div>
            <button className="btn-primary" onClick={() => generate.mutate()} disabled={generate.isPending}>
              {generate.isPending
                ? <><Loader2 size={12} className="animate-spin" /> Génération...</>
                : <><Play size={12} /> Générer les tickets</>}
            </button>
          </div>

          {/* Tickets générés */}
          {(generated || true) && tickets.map((ticket, ti) => (
            <div key={ti} className="card overflow-hidden">
              {/* Header ticket */}
              <div className="px-6 pt-5 pb-4 flex items-center justify-between"
                style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                <div className="flex items-center gap-3">
                  {ticket.is_recommended && (
                    <Star size={12} style={{ color: "#fbbf24" }} fill="#fbbf24" />
                  )}
                  <div>
                    <p className="text-[13px] font-bold text-white">
                      Ticket {profile.emoji} {profile.label} #{ti + 1}
                    </p>
                    <p className="text-[10px] mt-0.5" style={{ color: "rgba(255,255,255,0.35)" }}>
                      {ticket.summary}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-center">
                    <p className="label-caps mb-0.5">Cote totale</p>
                    <p className="text-[1.5rem] font-black tabular-nums" style={{ color: profile.color }}>
                      ×{ticket.total_odds.toFixed(2)}
                    </p>
                  </div>
                  <div className="text-center">
                    <p className="label-caps mb-0.5">Prob. réelle</p>
                    <p className="text-[1.25rem] font-black tabular-nums" style={{ color: "#a5b4fc" }}>
                      {(ticket.combined_prob * 100).toFixed(0)}%
                    </p>
                  </div>
                  <div className="text-center">
                    <p className="label-caps mb-0.5">Risque</p>
                    <p className="text-[12px] font-bold" style={{ color: RISK_COLORS[ticket.risk_rating] ?? "#a5b4fc" }}>
                      {ticket.risk_rating}
                    </p>
                  </div>
                </div>
              </div>

              {/* Sélections */}
              <div className="px-6 py-3 space-y-1.5">
                {ticket.legs.map((leg: any, li: number) => (
                  <div key={li} className="flex items-center gap-4 py-2.5 px-3 rounded-xl"
                    style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.04)" }}>
                    <span className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-black flex-shrink-0"
                      style={{ background: "rgba(99,102,241,0.2)", color: "#a5b4fc" }}>{li + 1}</span>
                    <div className="flex-1">
                      <p className="text-[12px] font-semibold text-white">{leg.match}</p>
                      <p className="text-[10px]" style={{ color: "rgba(255,255,255,0.3)" }}>{leg.market}</p>
                    </div>
                    <span className="text-[14px] font-black text-white tabular-nums">{leg.odds}</span>
                    <span className="text-[11px] font-bold tabular-nums" style={{ color: "#4ade80" }}>+{leg.edge}%</span>
                    <div className="w-20">
                      <div className="h-1 rounded-full mb-0.5" style={{ background: "rgba(255,255,255,0.06)" }}>
                        <div className="h-full rounded-full" style={{ width: `${leg.conf}%`, background: leg.conf >= 75 ? "#4ade80" : leg.conf >= 60 ? "#fbbf24" : "#6366f1" }} />
                      </div>
                      <p className="text-[9px] text-right" style={{ color: "rgba(255,255,255,0.3)" }}>{leg.conf}%</p>
                    </div>
                  </div>
                ))}
              </div>

              {/* Mise + avertissements */}
              <div className="px-6 pb-5">
                <div className="flex items-center justify-between p-3 rounded-xl mt-2"
                  style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
                  <div>
                    <p className="label-caps mb-1">Mise recommandée (Kelly ¼)</p>
                    <p className="text-[1.125rem] font-black" style={{ color: "#4ade80" }}>
                      {(stakeNum * ticket.recommended_stake_pct / 100).toFixed(2)} € ({ticket.recommended_stake_pct}% bankroll)
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="label-caps mb-1">Gain potentiel</p>
                    <p className="text-[1.125rem] font-black" style={{ color: "#fbbf24" }}>
                      {(stakeNum * ticket.recommended_stake_pct / 100 * ticket.total_odds).toFixed(2)} €
                    </p>
                  </div>
                </div>

                {ticket.warnings.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {ticket.warnings.map((w: string, wi: number) => (
                      <div key={wi} className="flex items-center gap-2 px-3 py-1.5 rounded-lg"
                        style={{ background: "rgba(245,158,11,0.07)", border: "1px solid rgba(245,158,11,0.15)" }}>
                        <AlertTriangle size={10} style={{ color: "#fbbf24" }} />
                        <p className="text-[10px]" style={{ color: "#fcd34d" }}>{w}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

        </div>
      </main>
    </div>
  );
}
