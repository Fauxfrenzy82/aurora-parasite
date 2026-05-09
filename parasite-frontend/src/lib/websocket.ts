const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'wss://aurora-parasite.onrender.com/ws';

type Callback = (data: any) => void;

class ParasiteWebSocket {
  private ws: WebSocket | null = null;
  private listeners: Map<string, Set<Callback>> = new Map();
  private reconnectTimer: any = null;

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    try {
      this.ws = new WebSocket(WS_URL);

      this.ws.onopen = () => {
        console.log('[WS] Connected');
        this.emit('connected', {});
      };

      this.ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          this.emit(msg.type, msg.data);
          this.emit('*', msg);
        } catch {}
      };

      this.ws.onclose = () => {
        console.log('[WS] Disconnected — reconnecting in 5s');
        this.reconnectTimer = setTimeout(() => this.connect(), 5000);
      };

      this.ws.onerror = () => {};
    } catch {}
  }

  on(event: string, cb: Callback) {
    if (!this.listeners.has(event)) this.listeners.set(event, new Set());
    this.listeners.get(event)!.add(cb);
  }

  off(event: string, cb: Callback) {
    this.listeners.get(event)?.delete(cb);
  }

  private emit(event: string, data: any) {
    this.listeners.get(event)?.forEach(cb => cb(data));
  }

  disconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.ws?.close();
  }
}

export const ws = new ParasiteWebSocket();