export interface ParasiteStatus {
  running: boolean;
  halted: boolean;
  halt_reason: string;
  uptime_seconds: number;
  total_trades: number;
  total_r: number;
  avg_r_per_trade: number;
  nervous_system: {
    running: boolean;
    symbols: number;
    total_ticks: number;
    signal_queue_size: number;
  };
  cortex: {
    total_branches: number;
    promoted: number;
    testing: number;
    top_branches: BranchInfo[];
  };
  memory: {
    total_laws: number;
  };
  exposure: {
    current_exposure: number;
    max_exposure: number;
    regime: string;
  };
  layers: {
    spread_capture: LayerStats;
    tick_momentum: LayerStats;
    fade_engine: LayerStats;
    news_scalper: LayerStats;
    cross_instrument: LayerStats;
  };
}

export interface LayerStats {
  active: boolean;
  total_trades: number;
  wins: number;
  win_rate: number;
  total_r: number;
  avg_r: number;
}

export interface BranchInfo {
  id: string;
  symbol: string;
  feature: string;
  wr: number;
  avg_r: number;
  sharpe: number;
  trades: number;
  status: string;
}

export interface TradeRecord {
  trade_id: string;
  instrument: string;
  layer: string;
  direction: string;
  r_multiple: number;
  profit_currency: number;
  duration_ms: number;
  created_at: string;
}

export interface WSEvent {
  type: string;
  data: any;
  timestamp: string;
}