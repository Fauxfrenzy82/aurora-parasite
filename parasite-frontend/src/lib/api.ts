const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://aurora-parasite.onrender.com';

export async function fetchStatus(): Promise<any> {
  const res = await fetch(`${API_URL}/api/status`);
  return res.json();
}

export async function fetchTrades(limit = 50): Promise<any> {
  const res = await fetch(`${API_URL}/api/trades?limit=${limit}`);
  return res.json();
}

export async function fetchTradeStats(): Promise<any> {
  const res = await fetch(`${API_URL}/api/trades/stats`);
  return res.json();
}

export async function fetchBranches(): Promise<any> {
  const res = await fetch(`${API_URL}/api/branches`);
  return res.json();
}

export async function fetchLayers(): Promise<any> {
  const res = await fetch(`${API_URL}/api/layers`);
  return res.json();
}

export async function sendControl(action: string): Promise<any> {
  const res = await fetch(`${API_URL}/api/control?action=${action}`, { method: 'POST' });
  return res.json();
}