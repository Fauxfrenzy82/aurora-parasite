'use client';

import React from 'react';

export function StatusBar({ status }: { status: any }) {
  if (!status) return null;

  const dd = status.total_r < 0 ? Math.abs(status.total_r) / 100 : 0;
  const wr = status.total_trades > 0
    ? (status.layers ? Object.values(status.layers).reduce((acc: number, l: any) => acc + l.wins, 0) / status.total_trades * 100 : 0)
    : 0;

  return (
    <div className="fixed top-0 left-0 right-0 z-50 bg-black border-b border-parasite-border px-3 py-1.5 flex items-center justify-between text-[11px]">
      <div className="flex items-center gap-4">
        <span className="text-parasite-green font-bold">🦠 PARASITE</span>
        <span className={status.halted ? 'text-parasite-red' : 'text-parasite-green'}>
          {status.halted ? '■ HALTED' : '▲ LIVE'}
        </span>
        <span className="text-muted">
          {Math.floor(status.uptime_seconds / 3600)}h {Math.floor((status.uptime_seconds % 3600) / 60)}m
        </span>
      </div>
      <div className="flex items-center gap-3">
        <span>{status.total_trades?.toLocaleString()} trades</span>
        <span className={status.total_r >= 0 ? 'text-win' : 'text-loss'}>
          R: {status.total_r >= 0 ? '+' : ''}{status.total_r?.toFixed(1)}
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