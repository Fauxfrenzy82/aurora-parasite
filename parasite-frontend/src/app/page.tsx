'use client';

import React, { useEffect, useState } from 'react';
import { StatusBar } from '@/components/StatusBar';
import { PnLDisplay } from '@/components/PnLDisplay';
import { TradeFeed } from '@/components/TradeFeed';
import { LayerTable } from '@/components/LayerTable';
import { fetchStatus, sendControl } from '@/lib/api';

export default function Home() {
  const [status, setStatus] = useState<any>(null);
  const [loading, setLoading] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const s = await fetchStatus();
        setStatus(s);
      } catch {}
    };
    load();
    const interval = setInterval(load, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleControl = async (action: string) => {
    setLoading(action);
    try {
      await sendControl(action);
    } catch {}
    setTimeout(async () => {
      try {
        setStatus(await fetchStatus());
      } catch {}
      setLoading(null);
    }, 500);
  };

  return (
    <div className="min-h-screen bg-parasite-bg pb-16">
      <StatusBar status={status} />

      <div className="pt-10 px-3 space-y-3">
        {status?.cap_halted && (
          <div className="text-center py-3 bg-amber-500/10 border border-amber-500/30 rounded">
            <span className="text-amber text-sm font-bold">
              💰 BALANCE CAP REACHED: ${status.balance_cap?.toFixed(0)}
            </span>
            <p className="text-amber text-xs mt-1">
              Withdraw from Deriv, then tap RESUME to continue compounding
            </p>
          </div>
        )}

        <PnLDisplay
          totalR={status?.total_r || 0}
          avgR={status?.avg_r_per_trade || 0}
        />

        <div className="grid grid-cols-1 gap-3">
          <TradeFeed />
          <LayerTable layers={status?.layers} />
        </div>

        {status?.cortex && (
          <div className="bg-parasite-surface border border-parasite-border rounded p-3 text-[10px] flex justify-between">
            <span>BRANCHES: <span className="text-parasite-green">{status.cortex.total_branches}</span> ({status.cortex.promoted} promoted)</span>
            <span>LAWS: <span className="text-amber">{status.memory?.total_laws || 0}</span></span>
            <span>TICKS: <span className="text-muted">{(status.nervous_system?.total_ticks || 0).toLocaleString()}</span></span>
          </div>
        )}
      </div>

      <div className="fixed bottom-0 left-0 right-0 bg-black border-t border-parasite-border px-3 py-2 flex gap-2">
        <button
          onClick={() => handleControl('halt')}
          disabled={loading !== null}
          className="flex-1 py-2 bg-parasite-red/20 text-parasite-red border border-parasite-red/30 rounded text-xs font-bold"
        >
          HALT
        </button>
        <button
          onClick={() => handleControl('resume')}
          disabled={loading !== null}
          className="flex-1 py-2 bg-parasite-green/20 text-parasite-green border border-parasite-green/30 rounded text-xs font-bold"
        >
          RESUME
        </button>
        <button
          onClick={() => handleControl('close_all')}
          disabled={loading !== null}
          className="flex-1 py-2 bg-amber-500/20 text-amber border border-amber-500/30 rounded text-xs font-bold"
        >
          CLOSE ALL
        </button>
      </div>
    </div>
  );
}