'use client';

import React from 'react';

export function StatusBar({ status }: { status: any }) {
  if (!status) return null;

  const dd = status.total_r < 0 ? Math.abs(status.total_r) / 100 : 0;
  const wins = status.layers
    ? Object.values(status.layers).reduce((acc: number, l: any) => acc + (l.wins || 0), 0)
    : 0;
  const wr = status.total_trades > 0 ? (wins / status.total_trades) * 100 : 0;

  return (
    <div className="fixed top-0 left-0 right-0 z-50 bg-black border-b border-parasite-border px-3 py-1.5 flex items-center justify-between text-[11px]">
      <div className="flex items-center gap-4">
        <span className="text-parasite-green font-bold">🦠 PARASITE</span>
        <span className={status.halted ? 'text-parasite-red' : 'text-parasite-green'}>
          {status.cap_halted ? '💰 CAP' : status.halted ? '■ HALTED' : '▲ LIVE'}
        </span>
        <span className="text-parasite-green font-bold">
          ${(status.current_balance || 0).toFixed(2)}
        </span>
        <span className="text-muted">
          / ${(status.balance_cap || 500).toFixed(0)} cap
        </span>
        <span className="text-muted">
          {Math.floor((status.uptime_seconds || 0) / 3600)}h {Math.floor(((status.uptime_seconds || 0) % 3600) / 60)}m
        </span>
      </div>
      <div className="flex items-center gap-3">
        <span>{(status.total_trades || 0).toLocaleString()} trades</span>
        <span className={(status.total_r || 0) >= 0 ? 'text-win' : 'text-loss'}>
          R: {(status.total_r || 0) >= 0 ? '+' : ''}{(status.total_r || 0).toFixed(1)}
        </span>
        <span className="text-amber">WR: {wr.toFixed(1)}%</span>
        <span className="text-amber">LAWS: {status.memory?.total_laws || 0}</span>
        <span className={dd > 30 ? 'text-loss' : dd > 15 ? 'text-amber' : 'text-muted'}>
          DD: {dd.toFixed(1)}%
        </span>
      </div>
    </div>
  );
}