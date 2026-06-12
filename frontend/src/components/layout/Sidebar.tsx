"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, Zap, TrendingUp, Ticket,
  FlaskConical, Wallet, History, Target, Settings, Brain,
  Activity, ShieldCheck, FileSearch, TestTube2, BarChart2, DollarSign,
} from "lucide-react";

const NAV = [
  { href: "/dashboard",         icon: LayoutDashboard, label: "Dashboard",         tag: null },
  { href: "/value-bets",        icon: Zap,             label: "Value Bets",        tag: "LIVE" },
  { href: "/predictions",       icon: Brain,           label: "Prédictions",       tag: null },
  { href: "/odds-comparison",   icon: TrendingUp,      label: "Cotes",             tag: null },
  { href: "/ticket-builder",    icon: Ticket,          label: "Tickets",           tag: null },
  null,
  { href: "/backtesting",       icon: FlaskConical,    label: "Backtesting",       tag: null },
  { href: "/strategy-lab",      icon: TestTube2,       label: "Strategy Lab",      tag: "WF" },
  { href: "/model-comparison",  icon: BarChart2,       label: "Comparaison V2",    tag: "NEW" },
  { href: "/profitability",     icon: DollarSign,      label: "Audit Rentabilité", tag: "NEW" },
  { href: "/bankroll",          icon: Wallet,          label: "Bankroll",          tag: null },
  { href: "/clv",               icon: Target,          label: "CLV",               tag: "PRO" },
  { href: "/history",           icon: History,         label: "Historique",        tag: null },
  null,
  { href: "/model-quality",     icon: ShieldCheck,     label: "Qualité Modèle",    tag: null },
  { href: "/audit",             icon: FileSearch,      label: "Audit Fonctionnel", tag: null },
  { href: "/settings",          icon: Settings,        label: "Paramètres",        tag: null },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside
      className="fixed left-0 top-0 h-screen w-56 flex-shrink-0 flex flex-col z-20"
      style={{
        background: "linear-gradient(180deg, #04070d 0%, #060a12 100%)",
        borderRight: "1px solid rgba(255,255,255,0.05)",
      }}
    >
      {/* Ambient glow top */}
      <div className="absolute top-0 left-0 right-0 h-48 pointer-events-none"
        style={{ background: "radial-gradient(ellipse 120% 60% at 50% -20%, rgba(99,102,241,0.12) 0%, transparent 70%)" }} />

      {/* Logo */}
      <div className="relative px-5 pt-5 pb-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl flex items-center justify-center relative"
            style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)", boxShadow: "0 0 16px rgba(99,102,241,0.5)" }}>
            <Brain size={14} className="text-white" />
            <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full pulse-dot"
              style={{ background: "#22c55e", border: "1.5px solid #04070d" }} />
          </div>
          <div>
            <p className="text-[13px] font-black text-white leading-none">Predator Brain</p>
            <p className="text-[9px] mt-0.5 font-semibold tracking-widest"
              style={{ color: "rgba(99,102,241,0.7)" }}>VALUE BETTING AI</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="relative flex-1 px-3 overflow-y-auto space-y-0.5">
        {NAV.map((item, i) => {
          if (!item) {
            return <div key={`sep-${i}`} className="my-2 mx-2 h-px" style={{ background: "rgba(255,255,255,0.05)" }} />;
          }

          const isActive = pathname === item.href || (pathname?.startsWith(item.href + "/") ?? false);
          const Icon = item.icon;

          return (
            <Link key={item.href} href={item.href}
              className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-[12.5px] font-medium transition-all group relative"
              style={isActive ? {
                background: "rgba(99,102,241,0.12)",
                color: "#fff",
                borderLeft: "2px solid #6366f1",
              } : {
                color: "rgba(255,255,255,0.45)",
                borderLeft: "2px solid transparent",
              }}>
              <Icon size={13} className="flex-shrink-0"
                style={{ color: isActive ? "#a5b4fc" : "rgba(255,255,255,0.35)" }} />
              <span className="flex-1 truncate">{item.label}</span>
              {item.tag && (
                <span className="text-[8px] font-black tracking-widest px-1.5 py-0.5 rounded-md flex-shrink-0"
                  style={item.tag === "LIVE"
                    ? { background: "rgba(6,182,212,0.15)", color: "#67e8f9" }
                    : { background: "rgba(139,92,246,0.15)", color: "#c4b5fd" }}>
                  {item.tag}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Footer — Model status */}
      <ModelStatusFooter />
    </aside>
  );
}

function ModelStatusFooter() {
  return (
    <div className="relative px-3 pb-4">
      <div className="px-3 py-2.5 rounded-xl"
        style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.05)" }}>
        <div className="flex items-center gap-2">
          <Activity size={10} style={{ color: "#22c55e" }} />
          <p className="text-[10px] font-semibold" style={{ color: "rgba(255,255,255,0.5)" }}>
            Dixon-Coles
          </p>
          <span className="ml-auto text-[9px] font-bold" style={{ color: "#4ade80" }}>ACTIF</span>
        </div>
        <p className="text-[9px] mt-0.5" style={{ color: "rgba(255,255,255,0.2)" }}>
          Modèle statistique professionnel
        </p>
      </div>
    </div>
  );
}
