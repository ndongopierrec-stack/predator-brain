/**
 * Predator Brain API Client
 * Tous les appels vers le backend FastAPI (port 8001)
 */
import axios from "axios";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001/api/v1";

const api = axios.create({ baseURL: BASE, timeout: 30_000 });

// ─── Types ────────────────────────────────────────────────────────────────────

export interface MatchAnalysisRequest {
  home_team: string;
  away_team: string;
  league?: string;
  match_date?: string;
  bookmaker_odds?: Record<string, Record<string, number>>;
  form_home?: number;
  form_away?: number;
  injuries_home?: number;
  injuries_away?: number;
  is_important_match?: boolean;
}

export interface AnalysisResult {
  // Champs de haut niveau (alias pratiques utilisés dans les pages)
  home_team: string;
  away_team: string;
  // Structure réelle du backend
  match: { home_team: string; away_team: string; league?: string };
  prediction: {
    prob_home: number; prob_draw: number; prob_away: number;
    prob_over_15: number; prob_over_25: number; prob_over_35: number;
    prob_under_15: number; prob_under_25: number; prob_under_35: number;
    prob_btts_yes: number; prob_btts_no: number;
    lambda_home: number; lambda_away: number;
    most_likely_score: string;
    score_matrix: number[][];
    confidence: number;
    dc_known: boolean;
  };
  fair_odds: Record<string, number>;
  value_bets: ValueBet[];
  ai_analysis: {
    decision: string; confidence: string;
    ou_recommendation: string; btts_recommendation: string;
    narrative: string;
  };
  model_meta: { dc_known: boolean; is_fallback: boolean };
}

export interface ValueBet {
  market: string;
  selection: string;
  bookmaker: string;
  bookmaker_odds: number;
  prob_model: number;
  fair_odds: number;
  edge_pct: number;
  value_rating: "FORT" | "BON" | "FAIBLE";
  confidence: number;
  kelly_stake_pct: number;
  reasons: string[];
  warnings: string[];
}

export interface BacktestResult {
  strategy_name: string;
  // Champs à plat utilisés par les pages
  total_bets: number;
  bets_won: number;
  win_rate: number;
  roi_pct: number;
  profit: number;
  final_bankroll: number;
  max_drawdown_pct: number;
  sharpe_ratio?: number;
  verdict?: string;
  equity_curve: number[];
  // Structure imbriquée du backend
  results?: {
    total_matches: number; total_bets: number; bets_won: number;
    win_rate: number; roi_pct: number; total_profit: number;
    final_bankroll: number; max_drawdown: number; sharpe_ratio: number;
  };
}

export interface ModelStatus {
  is_trained: boolean;
  n_matches: number;
  n_teams: number;
  training_leagues: string[];
  gamma: number;
  rho: number;
  status: string;
  message: string;
}

export interface BankrollSnapshot {
  total: number; available: number; reserved: number;
  daily_profit: number; weekly_profit: number; monthly_profit: number;
  drawdown_current: number;
  /** Retourné par le backend sous ce nom */
  drawdown_max: number;
  peak: number;
  open_bets: number;
  // Extensions frontend
  initial?: number;
  max_drawdown_pct?: number;  // alias de drawdown_max
  exposure_pct?: number;
  equity_curve?: number[];
}

export interface CLVSummary {
  total_bets: number; settled: number; with_clv: number;
  avg_clv_pct: number; median_clv_pct?: number;
  roi_actual: number; win_rate: number;
  pct_positive?: number;
}

// ─── API calls ────────────────────────────────────────────────────────────────

export const predictionsApi = {
  modelStatus:  ()                => api.get<ModelStatus>("/predictions/model-status"),
  retrain:      (csv_dir?: string) => api.post("/predictions/retrain", { csv_dir }),
  analyze:      (req: MatchAnalysisRequest) => api.post<AnalysisResult>("/predictions/analyze", req),
  scanValueBets:(matches: any[], min_edge = 0.03, top_n = 20) =>
    api.post("/predictions/value-bets", { matches, min_edge, top_n }),
  generateTicket:(params: { ticket_type: string; n_tickets?: number; bankroll?: number; available_bets?: any[] }) =>
    api.post("/predictions/ticket", { available_bets: params.available_bets ?? [], ...params }),
};

export const backtestApi = {
  run: (params: {
    from_date?: string; to_date?: string; leagues?: string[];
    min_confidence?: number; min_edge?: number;
    kelly_fraction?: number; max_stake_pct?: number;
    initial_bankroll?: number; strategy_name?: string;
    league?: string; market?: string;
  }) => api.post<BacktestResult>("/backtest/run", {
    from_date: params.from_date ?? "2020-08-01",
    to_date:   params.to_date   ?? new Date().toISOString().slice(0, 10),
    ...params,
  }),

  walkForward: (params: any) => api.post("/backtest/walk-forward", params),
  strategies:  ()            => api.get("/backtest/strategies"),
};

export const bankrollApi = {
  calculateStake: (params: {
    edge_pct: number; odds: number; prob_model: number; bankroll: number;
    strategy?: string; league?: string; n_legs?: number;
  }) => api.post("/bankroll/calculate-stake", params),
  snapshot:    () => api.get<BankrollSnapshot>("/bankroll/snapshot"),
  performance: () => api.get("/bankroll/performance"),
  alerts:      () => api.get("/bankroll/alerts"),
};

export const clvApi = {
  summary:    () => api.get<CLVSummary>("/clv/summary"),
  report:     (from_date?: string, to_date?: string) =>
    api.post("/clv/report", { from_date, to_date }),
  recordBet:  (data: any)                  => api.post("/clv/record-bet", data),
  updateClosing:(bet_id: string, closing_odds: number) =>
    api.post("/clv/update-closing", { bet_id, closing_odds }),
  settle:     (bet_id: string, won: boolean) => api.post("/clv/settle", { bet_id, won }),
  projectRoi: (avg_clv: number, avg_odds = 2.5, n = 500) =>
    api.post(`/clv/project-roi?avg_clv_pct=${avg_clv}&avg_odds=${avg_odds}&n_bets=${n}`),
};

export const healthApi = {
  // /health est à la racine, pas sous /api/v1
  check: () =>
    axios
      .get((BASE || "http://localhost:8001/api/v1").replace("/api/v1", "") + "/health", { timeout: 5000 })
      .catch(() => ({ data: { status: "offline" } })),
};

export default api;
