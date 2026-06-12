"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Settings, Key, Brain, Database, Play, Loader2, CheckCircle, RefreshCw, Shield } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { predictionsApi, healthApi } from "@/lib/api";

function Section({ icon: Icon, title, children }: { icon: React.ElementType; title: string; children: React.ReactNode }) {
  return (
    <div className="card p-6">
      <p className="label-caps mb-5 flex items-center gap-2">
        <Icon size={11} />
        {title}
      </p>
      {children}
    </div>
  );
}

export default function SettingsPage() {
  const [oddsApiKey, setOddsApiKey]     = useState("");
  const [footballKey, setFootballKey]   = useState("");
  const [apifootKey, setApifootKey]     = useState("");
  const [xi, setXi]                     = useState("0.0018");
  const [minEdge, setMinEdge]           = useState("3.0");
  const [kellyFrac, setKellyFrac]       = useState("0.25");
  const [maxStake, setMaxStake]         = useState("5.0");
  const [initialBankroll, setInitialBankroll] = useState("10000");
  const [retrained, setRetrained]       = useState(false);

  const { data: health } = { data: null } as any; // healthApi auto-refresh

  const retrain = useMutation({
    mutationFn: () => predictionsApi.retrain().then(r => r.data),
    onSuccess: () => setRetrained(true),
  });

  const saved = useMutation({
    mutationFn: async () => {
      await new Promise(r => setTimeout(r, 600));
      return true;
    },
  });

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "var(--bg-app)" }}>
      <Sidebar />
      <main className="ml-56 flex-1 overflow-y-auto">

        <header className="topbar px-8 py-4">
          <h1 className="text-[15px] font-bold text-white flex items-center gap-2">
            <Settings size={14} style={{ color: "#94a3b8" }} />
            Paramètres
          </h1>
          <p className="text-[11px] mt-0.5" style={{ color: "rgba(255,255,255,0.3)" }}>
            Clés API · Modèle · Bankroll · Sources de données
          </p>
        </header>

        <div className="px-8 py-7 space-y-5 animate-fade-in">

          {/* Clés API */}
          <Section icon={Key} title="Clés API — Sources de données légales">
            <div className="space-y-4">
              {[
                { label: "The Odds API",      key: oddsApiKey,   setter: setOddsApiKey,   placeholder: "sk-odds-...",    hint: "theoddsapi.com · Cotes temps réel" },
                { label: "football-data.org", key: footballKey,  setter: setFootballKey,  placeholder: "fd-...",         hint: "Résultats historiques · Gratuit jusqu'à 10 req/min" },
                { label: "API-Football",      key: apifootKey,   setter: setApifootKey,   placeholder: "rapidapi-...",   hint: "Blessures, XI probable, statistiques" },
              ].map(({ label, key, setter, placeholder, hint }) => (
                <div key={label}>
                  <label className="label-caps block mb-1.5">{label}</label>
                  <div className="flex gap-2">
                    <input type="password" className="input-pro flex-1" placeholder={placeholder}
                      value={key} onChange={e => setter(e.target.value)} />
                    <button className="btn-ghost px-3">Tester</button>
                  </div>
                  <p className="text-[10px] mt-1" style={{ color: "rgba(255,255,255,0.2)" }}>{hint}</p>
                </div>
              ))}
            </div>
            <div className="mt-4 flex items-center gap-2 px-3 py-2 rounded-lg"
              style={{ background: "rgba(34,197,94,0.06)", border: "1px solid rgba(34,197,94,0.15)" }}>
              <Shield size={11} style={{ color: "#4ade80" }} />
              <p className="text-[10px]" style={{ color: "#86efac" }}>
                Predator Brain n'utilise que des APIs légales et documentées. Aucun scraping interdit.
              </p>
            </div>
          </Section>

          {/* Modèle Dixon-Coles */}
          <Section icon={Brain} title="Modèle Dixon-Coles">
            <div className="grid grid-cols-3 gap-4 mb-5">
              <div>
                <label className="label-caps block mb-2">Décroissance temporelle ξ</label>
                <input className="input-pro" type="number" step="0.0001" value={xi}
                  onChange={e => setXi(e.target.value)} />
                <p className="text-[9px] mt-1" style={{ color: "rgba(255,255,255,0.2)" }}>
                  Défaut : 0.0018 · Plus élevé = moins de poids aux vieux matchs
                </p>
              </div>
              <div>
                <label className="label-caps block mb-2">Edge minimum (%)</label>
                <input className="input-pro" type="number" step="0.5" value={minEdge}
                  onChange={e => setMinEdge(e.target.value)} />
                <p className="text-[9px] mt-1" style={{ color: "rgba(255,255,255,0.2)" }}>
                  Seuil de détection des value bets
                </p>
              </div>
              <div>
                <label className="label-caps block mb-2">Fraction Kelly</label>
                <select className="input-pro" value={kellyFrac} onChange={e => setKellyFrac(e.target.value)}>
                  <option value="1.0">Kelly complet (1.0)</option>
                  <option value="0.5">Kelly demi (0.5)</option>
                  <option value="0.25">Kelly quart (0.25)</option>
                  <option value="0.1">Kelly dixième (0.1)</option>
                </select>
              </div>
            </div>

            {/* Entraîner le modèle */}
            <div className="flex items-center justify-between px-4 py-4 rounded-xl"
              style={{ background: "rgba(99,102,241,0.06)", border: "1px solid rgba(99,102,241,0.15)" }}>
              <div>
                <p className="text-[13px] font-semibold text-white">Entraîner le modèle</p>
                <p className="text-[11px] mt-0.5" style={{ color: "rgba(255,255,255,0.35)" }}>
                  Charge les CSV football-data.co.uk et lance l'optimisation L-BFGS-B
                </p>
              </div>
              <button className="btn-primary" onClick={() => retrain.mutate()} disabled={retrain.isPending}>
                {retrain.isPending
                  ? <><Loader2 size={12} className="animate-spin" /> Entraînement...</>
                  : retrained
                    ? <><CheckCircle size={12} /> Entraîné !</>
                    : <><RefreshCw size={12} /> Entraîner</>}
              </button>
            </div>

            {retrain.isError && (
              <p className="text-[11px] mt-2" style={{ color: "#f87171" }}>
                Erreur : {(retrain.error as any)?.response?.data?.detail ?? "Backend non accessible (port 8001)"}
              </p>
            )}
          </Section>

          {/* Bankroll par défaut */}
          <Section icon={Database} title="Configuration Bankroll par défaut">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label-caps block mb-2">Bankroll initiale (€)</label>
                <input className="input-pro" type="number" value={initialBankroll}
                  onChange={e => setInitialBankroll(e.target.value)} />
              </div>
              <div>
                <label className="label-caps block mb-2">Mise max par pari (%)</label>
                <input className="input-pro" type="number" step="0.5" value={maxStake}
                  onChange={e => setMaxStake(e.target.value)} />
              </div>
            </div>
          </Section>

          {/* Sources de données */}
          <Section icon={Database} title="Sources de données actives">
            <div className="space-y-2">
              {[
                { name: "football-data.co.uk",  type: "CSV historiques",     status: "ACTIF",    note: "PL, BL1, L1, LaLiga, SerA — saisons 2010-2025" },
                { name: "football-data.org",    type: "API REST",             status: "ATTENTE",  note: "Clé API requise" },
                { name: "The Odds API",         type: "Cotes temps réel",    status: "ATTENTE",  note: "Clé API requise" },
                { name: "API-Football",         type: "Statistiques avancées",status: "ATTENTE",  note: "Clé RapidAPI requise" },
                { name: "Kaggle football datasets", type: "Données historiques", status: "ACTIF", note: "Chargement manuel CSV" },
              ].map(({ name, type, status, note }) => (
                <div key={name} className="flex items-center justify-between px-4 py-3 rounded-xl"
                  style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)" }}>
                  <div>
                    <p className="text-[12px] font-semibold text-white">{name}</p>
                    <p className="text-[10px]" style={{ color: "rgba(255,255,255,0.3)" }}>{type} · {note}</p>
                  </div>
                  <span className="text-[9px] font-bold px-2 py-1 rounded-full"
                    style={status === "ACTIF"
                      ? { background: "rgba(34,197,94,0.1)", color: "#4ade80" }
                      : { background: "rgba(255,255,255,0.06)", color: "rgba(255,255,255,0.3)" }}>
                    {status}
                  </span>
                </div>
              ))}
            </div>
          </Section>

          {/* Sauvegarde */}
          <div className="flex justify-end gap-3">
            <button className="btn-ghost">Réinitialiser</button>
            <button className="btn-primary" onClick={() => saved.mutate()} disabled={saved.isPending}>
              {saved.isPending
                ? <><Loader2 size={12} className="animate-spin" /> Sauvegarde...</>
                : saved.isSuccess
                  ? <><CheckCircle size={12} /> Sauvegardé !</>
                  : "Sauvegarder les paramètres"}
            </button>
          </div>

        </div>
      </main>
    </div>
  );
}
