'use client';

import React, { useEffect, useState, useRef } from 'react';
import { fetchTrades } from '@/lib/api';

export function TradeFeed() {
  const [trades, setTrades] = useState<any[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const load = async () => {
      const data = await fetchTrades(50);
      setTrades(data || []);
    };
    load();
    const interval = setInterval(load, 3000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [trades]);

  const formatTime = (ts: string) => {
    if (!ts) return '--:--:--';
    return new Date(ts).toLocaleTimeString('en-US', { hour12: false });
  };

  const shortLayer = (l: string) => {
    const m: Record<string, string> = {
      spread_capture: 'SPREAD',
      tick_momentum: 'MOM',
      fade_engine: 'FADE',
      news_scalper: 'NEWS',
      cross_instrument: 'CROSS',
    };
    return m[l] || l.slice(0, 5).toUpperCase();
  };

  const shortSymbol = (s: string) => s?.replace('frx', '').slice(0, 8) || '';

  return (
    <div className="bg-parasite-surface border border-parasite-border rounded">
      <div className="px-3 py-2 border-b border-parasite-border text-[10px] text-muted uppercase tracking-wider">
        Trade Feed
      </div>
      <div className="max-h-64 overflow-y-auto">
        {trades.length === 0 && (
          <div className="text-center text-muted py-8 text-xs">Awaiting trades...</div>
        )}
        {trades.map((t: any, i: number) => (
          <div
            key={t.trade_id || i}
            className={`px-3 py-1.5 flex items-center gap-2 text-[10px] border-b border-parasite-border ${
              (t.r_multiple || 0) >= 0 ? 'text-parasite-green' : 'text-parasite-red'
            }`}
          >
            <span className="text-muted w-16">{formatTime(t.created_at)}</span>
            <span className="w-12">{shortSymbol(t.instrument)}</span>
            <span className="w-12 text-muted">{shortLayer(t.layer)}</span>
            <span className="w-8">{t.direction?.slice(0, 4)}</span>
            <span className="font-bold">{(t.r_multiple || 0) >= 0 ? '+' : ''}{(t.r_multiple || 0)?.toFixed(1)}R</span>
            <span className="text-muted ml-auto">{t.duration_ms ? `${(t.duration_ms / 1000).toFixed(1)}s` : ''}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}