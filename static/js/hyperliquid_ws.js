const HL_WS_URL = 'wss://api.hyperliquid.xyz/ws';
const HL_HEARTBEAT_INTERVAL = 25000;
const HL_RECONNECT_BASE_DELAY = 1000;
const HL_RECONNECT_MAX_DELAY = 30000;

class HyperliquidWS {
  constructor() {
    this.ws = null;
    this.listeners = { price: [], candle: [], connected: [], disconnected: [] };
    this.lastPrice = null;
    this.reconnectDelay = HL_RECONNECT_BASE_DELAY;
    this.reconnectTimer = null;
    this.heartbeatTimer = null;
    this.candleIntervals = {};
    this.candleBuffers = {};
    this.connected = false;
    this._intentionalClose = false;
  }

  on(event, callback) {
    if (this.listeners[event]) this.listeners[event].push(callback);
  }

  off(event, callback) {
    if (this.listeners[event]) {
      this.listeners[event] = this.listeners[event].filter(cb => cb !== callback);
    }
  }

  _emit(event, data) {
    (this.listeners[event] || []).forEach(cb => {
      try { cb(data); } catch (e) { console.error('HL WS listener error:', e); }
    });
  }

  connect() {
    if (this.ws) return;
    this._intentionalClose = false;

    try {
      this.ws = new WebSocket(HL_WS_URL);
    } catch (e) {
      console.error('HL WS connect failed:', e);
      this._scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      console.log('Hyperliquid WS connected');
      this.connected = true;
      this.reconnectDelay = HL_RECONNECT_BASE_DELAY;
      this._startHeartbeat();
      this._emit('connected', true);
      this._resubscribe();
    };

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        this._handleMessage(msg);
      } catch (e) {
        console.error('HL WS parse error:', e);
      }
    };

    this.ws.onerror = (err) => {
      console.error('HL WS error:', err);
    };

    this.ws.onclose = () => {
      console.log('HL WS disconnected');
      this.connected = false;
      this._stopHeartbeat();
      this._emit('disconnected', true);
      if (!this._intentionalClose) {
        this._scheduleReconnect();
      }
    };
  }

  disconnect() {
    this._intentionalClose = true;
    this._stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.onopen = null;
      this.ws.onclose = null;
      this.ws.onmessage = null;
      this.ws.onerror = null;
      try { this.ws.close(); } catch (_) {}
      this.ws = null;
    }
    this.connected = false;
  }

  _send(msg) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  _startHeartbeat() {
    this._stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      this._send({ method: 'ping' });
    }, HL_HEARTBEAT_INTERVAL);
  }

  _stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  _scheduleReconnect() {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, HL_RECONNECT_MAX_DELAY);
      this.connect();
    }, this.reconnectDelay);
  }

  _ensureSubscribed(sub) {
    this._activeSubscriptions = this._activeSubscriptions || [];
    const exists = this._activeSubscriptions.some(
      s => JSON.stringify(s.subscription) === JSON.stringify(sub.subscription)
    );
    if (exists) return;
    this._activeSubscriptions.push(sub);
    this._send(sub);
  }

  subscribeTrades(coin = 'BTC') {
    this._ensureSubscribed({ method: 'subscribe', subscription: { type: 'trades', coin } });
  }

  subscribeAllMids() {
    this._ensureSubscribed({ method: 'subscribe', subscription: { type: 'allMids' } });
  }

  subscribeCandle(coin = 'BTC', interval = '5m') {
    const key = `${coin}:${interval}`;
    this.candleBuffers[key] = [];
    this._ensureSubscribed({ method: 'subscribe', subscription: { type: 'candle', coin, interval } });
  }

  unsubscribe(subscription) {
    this._send({ method: 'unsubscribe', subscription });
    if (this._activeSubscriptions) {
      this._activeSubscriptions = this._activeSubscriptions.filter(
        s => JSON.stringify(s.subscription) !== JSON.stringify(subscription)
      );
    }
  }

  _resubscribe() {
    if (this._activeSubscriptions) {
      this._activeSubscriptions.forEach(sub => this._send(sub));
    }
  }

  _handleMessage(msg) {
    if (!msg || !msg.channel) return;

    if (msg.channel === 'trades' && Array.isArray(msg.data)) {
      for (const trade of msg.data) {
        const price = parseFloat(trade.px);
        if (!isNaN(price)) {
          this.lastPrice = price;
          this._emit('price', { price, size: parseFloat(trade.sz), side: trade.side, time: trade.time });
        }
      }
    }

    if (msg.channel === 'allMids' && msg.data) {
      const btcMid = msg.data.BTC || msg.data['BTC'];
      if (btcMid) {
        const price = parseFloat(btcMid);
        if (!isNaN(price)) {
          this.lastPrice = price;
          this._emit('price', { price, size: 0, side: null, time: Date.now() });
        }
      }
    }

    if (msg.channel === 'candle' && msg.data) {
      const c = msg.data;
      const key = `${c.coin}:${c.interval}`;
      const candle = {
        time: Math.floor(c.t / 1000),
        open: parseFloat(c.o),
        high: parseFloat(c.h),
        low: parseFloat(c.l),
        close: parseFloat(c.c),
        volume: parseFloat(c.v)
      };
      this._emit('candle', { key, candle });
    }

    if (msg.channel === 'subscriptionResponse') {
      console.log('HL WS subscription confirmed:', msg.data);
    }

    if (msg.channel === 'error') {
      console.error('HL WS subscription error:', msg.data);
    }
  }

  getLastPrice() {
    return this.lastPrice;
  }

  isConnected() {
    return this.connected;
  }
}

window.HyperliquidWS = HyperliquidWS;
