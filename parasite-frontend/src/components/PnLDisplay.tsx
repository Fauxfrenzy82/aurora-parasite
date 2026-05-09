'use client';

import React from 'react';

export function PnLDisplay({ totalR, avgR }: { totalR: number; avgR: number }) {
  const pnl = (totalR * 0.01).toFixed(2);
  const isPositive = totalR >= 0;

  return (
    <div className="text-center py-8">
      <div className={`text-6xl font-bold tracking-tighter ${isPositive ? 'text-win' : 'text-loss'}`}>
        {isPositive ? '+' : ''}{pnl}
      </div>
      <div className="text-muted text-xs mt-1">
        avg {avgR >= 0 ? '+' : ''}{avgR?.toFixed(3)}R / trade
      </div>
    </div>
  );
}