'use client';

import React from 'react';

export function LayerTable({ layers }: { layers: any }) {
  if (!layers) return null;

  return (
    <div className="bg-parasite-surface border border-parasite-border rounded">
      <div className="px-3 py-2 border-b border-parasite-border text-[10px] text-muted uppercase tracking-wider">
        Layers
      </div>
      <table className="w-full text-[10px]">
        <thead>
          <tr className="text-muted border-b border-parasite-border">
            <th className="text-left px-3 py-1.5">LAYER</th>
            <th className="text-right px-2 py-1.5">TRADES</th>
            <th className="text-right px-2 py-1.5">WR</th>
            <th className="text-right px-2 py-1.5">R</th>
            <th className="text-right px-3 py-1.5">AVG</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(layers).map(([name, stats]: [string, any]) => (
            <tr key={name} className="border-b border-parasite-border">
              <td className="px-3 py-1.5">{name.replace(/_/g, ' ').toUpperCase()}</td>
              <td className="text-right px-2 py-1.5">{stats.total_trades?.toLocaleString()}</td>
              <td className={`text-right px-2 py-1.5 ${stats.win_rate >= 0.55 ? 'text-win' : stats.win_rate >= 0.45 ? 'text-amber' : 'text-loss'}`}>
                {(stats.win_rate * 100).toFixed(1)}%
              </td>
              <td className={`text-right px-2 py-1.5 ${stats.total_r >= 0 ? 'text-win' : 'text-loss'}`}>
                {stats.total_r >= 0 ? '+' : ''}{stats.total_r?.toFixed(1)}
              </td>
              <td className={`text-right px-3 py-1.5 ${stats.avg_r >= 0 ? 'text-win' : 'text-loss'}`}>
                {stats.avg_r >= 0 ? '+' : ''}{stats.avg_r?.toFixed(3)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}