import { ethers } from "https://cdnjs.cloudflare.com/ajax/libs/ethers/6.13.2/ethers.min.js";

const rc = React.createElement;
const LightweightCharts = window.LightweightCharts;

const TESTNET_INDEXER_URL = 'http://127.0.0.1:8545';
const ANVIL_RPC_URL = 'http://127.0.0.1:8545';
const ANVIL_CHAIN_ID = 31337;
const USE_METAMASK = false; // true → sign via MetaMask; false → local node test accounts

const ZEN_ADDR = '0x00000000000000000000000000000000007a656e';
const PREDICT_SLUG = 'btc_5min';

const showToast = (message, type = 'info') => {
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  document.body.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add('toast-visible'));
  setTimeout(() => {
    toast.classList.remove('toast-visible');
    setTimeout(() => toast.remove(), 300);
  }, 3000);
};

const parseJsonWithBigInt = (data_json) => JSON.parse(
  data_json,
  (key, value, { source }) => (
    Number.isInteger(value) && !Number.isSafeInteger(value) ? BigInt(source) : value
  )
);

const toBigInt = (value) => {
  if (typeof value === 'bigint') return value;
  if (typeof value === 'string') return BigInt(value);
  if (typeof value === 'number') return BigInt(String(Math.trunc(value)));
  return 0n;
};

const formatPrice = (price) => {
  if (price === null || price === undefined) return '—';
  return Number(price).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

const formatPriceShort = (price) => {
  if (price === null || price === undefined) return '—';
  if (price >= 10000) return Math.round(price).toLocaleString();
  return Number(price).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
};

// ─── Header ─────────────────────────────────────────────
class Header extends React.Component {
  render() {
    const { ethAddress, walletLoading } = this.props.walletState;
    return rc('header', { className: 'header' },
      rc('div', { className: 'logo' },
        rc('span', { className: 'text-xl font-bold' }, 'Prediction Market')
      ),
      rc('span', { className: 'network-badge' }, 'Local Playground'),
      rc('div', { className: 'login' },
        walletLoading ? null :
          (ethAddress ?
            rc('div', { style: { display: 'flex', alignItems: 'center', gap: '8px' } },
              rc('span', { className: 'font-mono text-sm' }, `${ethAddress.substring(0, 6)}...${ethAddress.substring(ethAddress.length - 4)}`),
              rc('button', { onClick: this.props.handleWalletLogout, className: 'logout-btn' }, 'Logout')
            ) :
            rc('button', { onClick: this.props.handleWalletLogin, className: 'connect-btn' }, USE_METAMASK ? 'Connect MetaMask' : 'Connect Wallet')
          )
      )
    );
  }
}

// ─── LivePricePanel ─────────────────────────────────────
class LivePricePanel extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      lastPrice: null,
      prevPrice: null,
    };
    this.chartRef = React.createRef();
    this.chart = null;
    this.lineSeries = null;
    this.targetLine = null;
    this.histData = [];
    this.rtData = [];
    this.autoRefreshTimer = null;
    this.loadedRoundId = null;
    this.roundStartTime = 0;
    this.finalPrice = null;
  }

  componentDidMount() {
    this.initChart();
    this.startAutoRefresh();
    this.loadRoundData();
  }

  componentWillUnmount() {
    if (this.autoRefreshTimer) clearInterval(this.autoRefreshTimer);
    if (this.chart) {
      this.chart.remove();
      this.chart = null;
    }
  }

  componentDidUpdate(prevProps) {
    const rm = this.props.roundManager;
    if (!rm) return;
    const displayRoundId = rm.getDisplayRoundId();

    if (displayRoundId !== null && displayRoundId !== this.loadedRoundId) {
      this.loadedRoundId = displayRoundId;
      this.histData = [];
      this.rtData = [];
      this.finalPrice = null;
      this.roundStartTime = rm.getRoundStart(displayRoundId);
      this.loadRoundData();
    }

    const currentPrice = this.props.currentPrice;
    if (currentPrice !== null && currentPrice !== prevProps.currentPrice
        && rm.getDisplayRoundId() === rm.getCurrentRoundId()) {
      const prev = this.state.lastPrice;
      this.setState({ lastPrice: currentPrice, prevPrice: prev });
      this.appendRealtimePoint(currentPrice);
    }
  }

  async loadRoundData() {
    const { roundManager, onTargetPrice } = this.props;
    if (!roundManager) return;

    const roundId = roundManager.getDisplayRoundId();
    this.loadedRoundId = roundId;
    const roundStartMs = roundManager.getRoundStart(roundId) * 1000;
    const roundEndMs = roundManager.getRoundEnd(roundId) * 1000;
    // For the live round, candles only go up to now; for finished rounds the
    // whole 5-minute window is available.
    const endMs = roundId === roundManager.getCurrentRoundId()
      ? Date.now()
      : roundEndMs;

    try {
      const resp = await fetch('https://api.hyperliquid.xyz/info', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: 'candleSnapshot',
          req: { coin: 'BTC', interval: '1m', startTime: roundStartMs, endTime: endMs },
        }),
      });
      const curCandles = await resp.json();

      console.log('HL round candles:', curCandles.length, curCandles.slice(0, 2));
      const isLive = roundId === roundManager.getCurrentRoundId();

      if (Array.isArray(curCandles) && curCandles.length > 0) {
        // Backfill 1-second points for each 1m candle's window using the
        // candle's open price as a placeholder. Live WS trades then overwrite
        // the current round's seconds with real prices. For the live round we
        // cap at "now" (so we don't draw into the future); finished rounds fill
        // the full candle window.
        this.rtData = [];
        const nowSec = Math.floor(Date.now() / 1000);
        const isLastCandle = (idx) => idx === curCandles.length - 1;
        for (let idx = 0; idx < curCandles.length; idx++) {
          const c = curCandles[idx];
          const candleTimeSec = Math.floor(c.t / 1000);
          const open = parseFloat(c.o);
          const close = parseFloat(c.c);
          const fillEnd = isLive
            ? Math.min(candleTimeSec + 60, nowSec)
            : candleTimeSec + 60;
          for (let s = candleTimeSec; s < fillEnd; s++) {
            // For finished rounds, the very last second of the round uses the
            // final candle's close (the settlement price) so the winner is easy
            // to judge against the target.
            let value = open;
            if (!isLive && isLastCandle(idx) && s === fillEnd - 1) {
              value = close;
            }
            this.rtData.push({ time: s, value });
          }
        }
        this.rtData.sort((a, b) => a.time - b.time);
        this.histData = this.rtData;
        console.log('rtData backfilled:', this.rtData.length, 'points');
      } else {
        this.histData = [];
        console.log('No candles returned');
      }

      if (curCandles.length > 0 && onTargetPrice && !roundManager.getTargetPrice(roundId)) {
        const openPrice = parseFloat(curCandles[0].o);
        console.log('Target set to:', openPrice);
        onTargetPrice(roundId, openPrice);
      }

      // Capture the settlement (final close) price for finished rounds so we can
      // show the result and UP/DOWN next to the target.
      this.finalPrice = null;
      if (!isLive && Array.isArray(curCandles) && curCandles.length > 0) {
        const last = curCandles[curCandles.length - 1];
        this.finalPrice = parseFloat(last.c);
      }
    } catch (e) {
      console.error('Failed to load candle data:', e);
    }

    this.renderChart();
  }

  appendRealtimePoint(price) {
    if (!price) return;
    const now = Math.floor(Date.now() / 1000);

    if (this.rtData.length > 0) {
      const last = this.rtData[this.rtData.length - 1];
      if (now === last.time) {
        last.value = price;
      } else if (now > last.time) {
        this.rtData.push({ time: now, value: price });
      }
    } else {
      this.rtData.push({ time: now, value: price });
    }

    this.renderChart();
  }

  renderChart() {
    if (!this.lineSeries) return;
    const combined = [...this.rtData];
    if (combined.length > 0) {
      this.lineSeries.setData(combined);
      if (this.chart && this.chart.timeScale) {
        this.chart.timeScale().scrollToRealTime();
      }
    }

    // Update target line
    const { roundManager } = this.props;
    if (roundManager && this.targetLine) {
      const roundId = roundManager.getDisplayRoundId();
      const target = roundManager.getTargetPrice(roundId);
      if (target !== null) {
        this.targetLine.applyOptions({
          price: target,
          color: '#f59e0b',
          lineWidth: 1,
          lineStyle: LightweightCharts.LineStyle.Dashed,
          axisLabelVisible: true,
          title: 'Target',
        });
      }
    }
  }

  initChart() {
    if (!this.chartRef.current) return;
    this.chart = LightweightCharts.createChart(this.chartRef.current, {
      width: this.chartRef.current.offsetWidth || 600,
      height: 220,
      layout: {
        background: { type: 'solid', color: '#ffffff' },
        textColor: '#6b7280',
        fontSize: 10,
      },
      grid: {
        vertLines: { color: '#f3f4f6' },
        horzLines: { color: '#f3f4f6' },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: true,
        tickMarkFormatter: (time) => {
          const d = new Date(time * 1000);
          return `${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`;
        },
      },
      rightPriceScale: {
        borderColor: '#e5e7eb',
      },
    });
    this.lineSeries = this.chart.addLineSeries({
      color: '#2563eb',
      lineWidth: 2,
      priceLineVisible: true,
      lastValueVisible: true,
      priceLineColor: '#2563eb',
    });

    this.targetLine = this.lineSeries.createPriceLine({
      price: 0,
      color: '#f59e0b',
      lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Dashed,
      axisLabelVisible: true,
      title: 'Target',
    });

    setTimeout(() => {
      if (this.chart && this.chartRef.current) {
        this.chart.applyOptions({ width: this.chartRef.current.offsetWidth });
      }
    }, 100);
  }

  startAutoRefresh() {
    this.autoRefreshTimer = setInterval(() => {
      if (!this.chartRef.current || !this.chart) return;
      const w = this.chartRef.current.offsetWidth;
      if (w > 0) {
        this.chart.applyOptions({ width: w });
      }
    }, 2000);
  }

  render() {
    const { lastPrice, prevPrice } = this.state;
    const { roundManager } = this.props;
    const displayRoundId = roundManager ? roundManager.getDisplayRoundId() : null;
    const isLive = roundManager ? displayRoundId === roundManager.getCurrentRoundId() : false;
    const target = roundManager ? roundManager.getTargetPrice(displayRoundId) : null;
    const hasDiff = lastPrice !== null && target !== null;
    const diff = hasDiff ? lastPrice - target : 0;
    const diffClass = diff >= 0 ? 'price-up' : 'price-down';
    const diffSign = diff >= 0 ? '+' : '';

    // For finished rounds, show the settlement result (final close vs target).
    let resultBadge = null;
    if (!isLive && this.finalPrice !== null && target !== null) {
      const won = this.finalPrice > target;
      resultBadge = rc('span', {
        className: `round-result ${won ? 'result-yes' : 'result-no'}`,
      }, `End ${won ? 'YES' : 'NO'} · ${won ? 'UP' : 'DOWN'} $${formatPrice(this.finalPrice)}`);
    }

    return rc('div', { className: 'panel', style: { marginBottom: '8px' } },
      rc('div', { className: 'live-price-panel' },
        rc('div', { style: { flex: 1 } },
          rc('div', { className: 'live-price-panel price-display' },
            rc('span', { className: 'price-label' }, 'BTC / USDC'),
            rc('span', { className: 'price-value' },
              !isLive && this.finalPrice !== null ? formatPrice(this.finalPrice) :
              (lastPrice !== null ? formatPrice(lastPrice) : '—')),
            hasDiff && diff !== 0 && isLive ?
              rc('span', { className: `price-change ${diffClass}` },
                `${diffSign}${formatPrice(Math.abs(diff))}`
              ) : null,
            target !== null ?
              rc('span', {
                style: { fontSize: '10px', color: '#f59e0b', marginLeft: '8px' },
              }, `Target: $${formatPrice(target)}`) : null,
            resultBadge
          ),
          rc('span', { className: 'hl-badge' }, 'Hyperliquid')
        )
      ),
      rc('div', { ref: this.chartRef, style: { width: '100%' } })
    );
  }
}

// ─── RoundNavigator ─────────────────────────────────────
class RoundNavigator extends React.Component {
  constructor(props) {
    super(props);
    this.state = { tick: 0 };
    this.tickTimer = null;
  }

  componentDidMount() {
    this.tickTimer = setInterval(() => this.setState({ tick: this.state.tick + 1 }), 1000);
  }

  componentWillUnmount() {
    if (this.tickTimer) clearInterval(this.tickTimer);
  }

  render() {
    const { roundManager, targetPrice, onTargetChange, currentPrice } = this.props;
    const roundId = roundManager.getDisplayRoundId();
    const state = roundManager.getRoundState(roundId);
    const remaining = roundManager.getTimeRemaining(roundId);
    const progress = roundManager.getProgress(roundId);
    const isCurrent = roundManager.isViewingCurrentRound();
    const target = roundManager.getTargetPrice(roundId);

    const stateLabel = state === RoundState.ACTIVE ? 'Active'
      : state === RoundState.SETTLING ? 'Settling...' : 'Resolved';

    const stateClass = state === RoundState.ACTIVE ? 'state-active'
      : state === RoundState.SETTLING ? 'state-settling' : 'state-resolved';

    const timerClass = remaining <= 30 ? 'timer urgent' : 'timer';
    const progressClass = remaining <= 30 ? 'progress-bar-fill urgent' : 'progress-bar-fill';

    return rc('div', { className: 'panel', style: { marginBottom: '8px' } },
      rc('div', { className: 'round-navigator' },
        rc('div', { className: 'round-info' },
          rc('span', { className: 'round-id' }, `Round ${roundManager.formatRoundId(roundId)}`),
          rc('span', { className: `round-state ${stateClass}` }, stateLabel)
        ),
        state === RoundState.ACTIVE ?
          rc('span', { className: timerClass }, roundManager.formatTime(remaining)) :
          state === RoundState.SETTLING ?
            rc('span', { className: 'timer', style: { color: '#d97706' } }, '...') :
            null,
        rc('div', { className: 'progress-bar-container', style: { flex: 1 } },
          rc('div', { className: progressClass, style: { width: `${progress * 100}%` } })
        ),
        rc('div', { className: 'nav-buttons' },
          rc('button', {
            className: 'nav-btn',
            onClick: () => roundManager.goToPreviousRound(),
          }, '\u2190'),
          !isCurrent ?
            rc('button', {
              className: 'nav-btn',
              onClick: () => roundManager.goToCurrentRound(),
              style: { fontSize: '10px', color: '#2563eb' },
            }, 'Current') :
            rc('button', {
              className: 'nav-btn',
              onClick: () => roundManager.goToNextRound(),
              disabled: true,
            }, '\u2192'),
          isCurrent ?
            rc('button', {
              className: 'nav-btn',
              disabled: true,
            }, '\u2192') : null
        ),
        rc('div', { className: 'target-input-group' },
          rc('span', { className: 'target-label' }, 'Target:'),
          rc('span', { className: 'target-value' },
            target !== null ? `$${formatPrice(target)}` : '--'
          ),
          currentPrice !== null && target !== null ?
            rc('span', {
              style: {
                fontSize: '10px',
                color: currentPrice > target ? '#059669' : '#dc2626',
                fontWeight: 600,
              }
            }, currentPrice > target ? 'BTC > Target (YES)' : 'BTC <= Target (NO)') :
            null
        )
      )
    );
  }
}

// ─── PredictionMarketPanel ──────────────────────────────
class PredictionMarketPanel extends React.Component {
  render() {
    const { roundManager, currentPrice } = this.props;
    const roundId = roundManager.getDisplayRoundId();
    const state = roundManager.getRoundState(roundId);
    const target = roundManager.getTargetPrice(roundId);
    const result = roundManager.getRoundResult(roundId);

    let yesRatio = 50;
    if (target !== null && currentPrice !== null) {
      const diff = currentPrice - target;
      const absDiff = Math.abs(diff);
      const maxOffset = target * 0.02;
      const normalized = Math.min(absDiff / (maxOffset || 1), 1);
      yesRatio = currentPrice > target ? 50 + normalized * 45 : 50 - normalized * 45;
    }

    const noRatio = 100 - yesRatio;
    const yesPrice = (yesRatio / 100).toFixed(2);
    const noPrice = (noRatio / 100).toFixed(2);

    return rc('div', { className: 'panel prediction-panel', style: { marginBottom: '8px' } },
      rc('div', { style: { fontWeight: 700, marginBottom: '8px', color: '#374151' } }, 'Market'),

      state === RoundState.SETTLING || state === RoundState.RESOLVED ?
        rc(SettlementStatus, {
          roundManager,
          roundId,
          currentPrice,
        }) :

        rc(React.Fragment, null,
          rc('div', { className: 'token-row' },
            rc('span', { className: 'token-name yes' }, 'YES'),
            rc('span', { className: 'token-price yes' }, `$${yesPrice}`)
          ),
          rc('div', { className: 'yes-no-bar' },
            rc('div', { className: 'yes-bar', style: { width: `${yesRatio}%` } }, `${Math.round(yesRatio)}%`),
            rc('div', { className: 'no-bar', style: { width: `${noRatio}%` } }, `${Math.round(noRatio)}%`)
          ),
          rc('div', { className: 'token-row' },
            rc('span', { className: 'token-name no' }, 'NO'),
            rc('span', { className: 'token-price no' }, `$${noPrice}`)
          ),
          rc('div', { className: 'orderbook-placeholder' },
            'Orderbook will be available when on-chain trading is live'
          )
        )
    );
  }
}

// ─── SettlementStatus ───────────────────────────────────
class SettlementStatus extends React.Component {
  render() {
    const { roundManager, roundId, currentPrice } = this.props;
    const state = roundManager.getRoundState(roundId);
    const result = roundManager.getRoundResult(roundId);
    const target = roundManager.getTargetPrice(roundId);

    if (state === RoundState.RESOLVED && result) {
      const isYes = result === 'YES';
      return rc('div', { className: 'settlement-overlay' },
        rc('div', { className: `settlement-result ${isYes ? 'result-yes' : 'result-no'}` },
          `${result} Won`
        ),
        currentPrice !== null ?
          rc('div', { style: { fontSize: '11px', color: '#6b7280' } },
            `Final: $${formatPrice(currentPrice)} ${target !== null ? `vs Target $${formatPrice(target)}` : ''}`
          ) : null
      );
    }

    return rc('div', { className: 'settlement-overlay' },
      rc('div', { className: 'spinner' }),
      rc('div', { className: 'settlement-text' }, 'Settling... Waiting for result'),
      currentPrice !== null ?
        rc('div', { style: { fontSize: '10px', color: '#9ca3af' } },
          `Current: $${formatPrice(currentPrice)} ${target !== null ? `| Target: $${formatPrice(target)}` : ''}`
        ) : null
    );
  }
}

// ─── TradePanel (One-Tap Buy) ───────────────────────────
class TradePanel extends React.Component {
  constructor(props) {
    super(props);
    this.state = { selection: 'up', amount: '5', pending: null };
  }

  selectSide = (side) => {
    this.setState({ selection: side });
  }

  setQuickAmount = (n) => {
    this.setState({ amount: String(n) });
  }

  handleAmountChange = (e) => {
    this.setState({ amount: e.target.value });
  }

  placeMarketOrder = async (side, buy) => {
    const { signer } = this.props;
    if (!signer) {
      showToast('Please connect your wallet first.', 'error');
      return;
    }
    const amount = parseFloat(this.state.amount);
    if (!amount || amount <= 0) {
      showToast('Please enter a valid amount', 'error');
      return;
    }
    if (this.state.pending) return;

    const raw = ethers.parseUnits(this.state.amount, 6).toString();
    const quoteValue = buy ? `-${raw}` : `+${raw}`;
    const calldata = {
      'p': 'zentest3',
      'f': 'predict_market_order',
      'a': [PREDICT_SLUG, null, side, quoteValue],
    };

    const key = `${buy ? 'buy' : 'sell'}_${side}`;
    this.setState({ pending: key });
    try {
      const tx = await signer.sendTransaction({
        to: ZEN_ADDR,
        data: ethers.hexlify(new TextEncoder().encode(JSON.stringify(calldata)))
      });
      showToast(`Market ${buy ? 'buy' : 'sell'} ${side.toUpperCase()} sent: ${tx.hash}`, 'success');
      if (this.props.onTrade) this.props.onTrade();
    } catch (error) {
      console.error('Market order failed:', error);
      showToast('Market order failed.', 'error');
    } finally {
      this.setState({ pending: null });
    }
  }

  render() {
    const { selection, amount, pending } = this.state;
    const { balance, roundManager, currentPrice } = this.props;
    const usdc = parseFloat(balance) || 0;

    const roundId = roundManager.getDisplayRoundId();
    const target = roundManager.getTargetPrice(roundId);

    let yesPrice = 0.50;
    if (target !== null && currentPrice !== null) {
      const diff = currentPrice - target;
      const maxOffset = target * 0.02;
      const normalized = Math.min(Math.abs(diff) / (maxOffset || 1), 1);
      yesPrice = currentPrice > target ? 0.50 + normalized * 0.45 : 0.50 - normalized * 0.45;
    }
    const noPrice = 1 - yesPrice;

    const upBtn = (side, label, price) => rc('button', {
      className: `updown-btn ${side} ${selection === side ? 'selected' : ''}`,
      onClick: () => this.selectSide(side),
    },
      rc('span', { className: 'ud-label' }, label),
      rc('span', { className: 'ud-price' }, `$${price.toFixed(2)}`)
    );

    const side = selection === 'up' ? 'yes' : 'no';
    const isUp = selection === 'up';

    return rc('div', { className: 'panel trade-panel' },
      rc('div', { style: { fontWeight: 700, marginBottom: '4px', color: '#374151' } }, '1-Tap Buy'),

      rc('div', { className: 'balance-info' },
        rc('span', null, 'Available USDC'),
        rc('span', { style: { fontWeight: 600 } }, `$${formatPrice(usdc)}`)
      ),

      rc('div', { className: 'updown-toggle' },
        upBtn('up', 'UP', yesPrice),
        upBtn('down', 'DOWN', noPrice)
      ),

      rc('div', { className: 'one-tap-label' }, 'One-Tap Buy'),

      rc('div', { className: 'amt-chips' },
        [1, 5, 10].map((n) =>
          rc('button', {
            key: n,
            className: `amt-chip ${parseFloat(amount) === n ? 'selected' : ''}`,
            onClick: () => this.setQuickAmount(n),
          }, `${n}U`)
        )
      ),

      rc('div', { className: 'input-group' },
        rc('input', {
          type: 'number',
          name: 'amount',
          value: amount,
          onChange: this.handleAmountChange,
          placeholder: '0.00',
          min: '0',
          step: '0.01',
        })
      ),

      rc('button', {
        className: `onetap-buy-btn ${isUp ? 'up' : 'down'}`,
        disabled: pending !== null || !amount || parseFloat(amount) <= 0,
        onClick: () => this.placeMarketOrder(side, true),
      }, `Buy ${isUp ? 'UP' : 'DOWN'} $${amount}`)
    );
  }
}

// ─── DepositPanel ───────────────────────────────────────
class DepositPanel extends React.Component {
  claimMockUSDC = async () => {
    const { signer } = this.props;
    if (!signer) {
      showToast('Please connect your wallet first.', 'error');
      return;
    }
    try {
      const calldata = {
        'p': 'zentest3',
        'f': 'token_mint_free',
        'a': ['USDC', ethers.parseUnits('100', 6).toString()]
      };
      const tx = await signer.sendTransaction({
        to: ZEN_ADDR,
        data: ethers.hexlify(new TextEncoder().encode(JSON.stringify(calldata)))
      });
      showToast(`Mint tx sent: ${tx.hash}`, 'success');
    } catch (error) {
      console.error('Mint USDC failed:', error);
      showToast('Mint USDC failed.', 'error');
    }
  }

  render() {
    return rc('div', { className: 'panel deposit-panel' },
      rc('div', { style: { fontWeight: 700, marginBottom: '8px', color: '#374151' } }, 'Deposit'),
      rc('div', { className: 'deposit-actions' },
        rc('button', {
          className: 'deposit-btn primary',
          onClick: this.claimMockUSDC,
        }, 'Claim 100 Mock USDC'),
        rc('div', { className: 'deposit-note' }, 'No test ETH?'),
        rc('a', {
          href: 'https://www.alchemy.com/faucets/base-sepolia',
          target: '_blank',
          style: { fontSize: '10px', color: '#2563eb', textAlign: 'center', display: 'block', textDecoration: 'underline' }
        }, 'Claim Base Sepolia ETH'),
        rc('div', { style: { marginTop: '8px', borderTop: '1px solid #f3f4f6', paddingTop: '8px' } },
          rc('div', { className: 'deposit-note', style: { marginBottom: '4px' } }, 'Cross-chain deposit'),
          rc('button', {
            className: 'deposit-btn',
            disabled: true,
            style: { opacity: 0.5, cursor: 'not-allowed' },
          }, 'Bridge (Coming Soon)')
        )
      )
    );
  }
}

// ─── AssetsPanel ────────────────────────────────────────
class AssetsPanel extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      USDC: '0',
      loading: false,
    };
  }

  componentDidMount() {
    this.fetchAssets();
  }

  componentDidUpdate(prevProps) {
    if (this.props.address !== prevProps.address && this.props.address) {
      this.fetchAssets();
    }
  }

  fetchAssets = async () => {
    if (!this.props.address) return;
    this.setState({ loading: true });
    try {
      const addr = this.props.address.toLowerCase();
      const prefix = `base-USDC-balance:${addr}`;
      const response = await fetch(`${TESTNET_INDEXER_URL}/api/get_latest_state?prefix=${prefix}`);
      const data = await response.json();
      const val = data.result;
      this.setState({
        USDC: val && val !== '0' ? ethers.formatUnits(toBigInt(val), 6) : '0',
        loading: false,
      });
    } catch (e) {
      this.setState({ USDC: '0', loading: false });
    }
  }

  render() {
    const { balance } = this.props;
    return rc('div', { className: 'panel assets-panel' },
      rc('div', { style: { fontWeight: 700, marginBottom: '8px', color: '#374151' } }, 'My Assets'),
      rc('div', { className: 'asset-row' },
        rc('span', { className: 'asset-name' }, 'USDC'),
        rc('span', { className: 'asset-amount' }, `$${formatPrice(parseFloat(balance) || 0)}`)
      ),
      rc('div', { className: 'asset-row' },
        rc('span', { className: 'asset-name', style: { color: '#059669' } }, 'YES'),
        rc('span', { className: 'asset-amount' }, '—')
      ),
      rc('div', { className: 'asset-row' },
        rc('span', { className: 'asset-name', style: { color: '#dc2626' } }, 'NO'),
        rc('span', { className: 'asset-amount' }, '—')
      )
    );
  }
}

// ─── App ────────────────────────────────────────────────
class App extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      screenWidth: window.innerWidth,
      ethAddress: null,
      provider: null,
      signer: null,
      walletLoading: true,
      currentPrice: null,
      usdcBalance: '0',
      targetPrice: null,
      roundVersion: 0,
    };
    this.hlWS = new HyperliquidWS();
    this.roundManager = new RoundManager();
    this.balanceInterval = null;
  }

  componentDidMount() {
    window.addEventListener('resize', this.handleResize);
    this.applyHashRound();
    window.addEventListener('hashchange', this.applyHashRound);
    window.addEventListener('popstate', this.applyHashRound);
    this.initializeWallet();
    this.initHyperliquidWS();
    this.roundManager.startTicking();
    this.roundManager.onChange(() => {
      this.syncWsConnection();
      this.setState({ roundVersion: this.state.roundVersion + 1 });
    });
    this.syncWsConnection();

    if (USE_METAMASK && window.ethereum) {
      window.ethereum.on('accountsChanged', () => {
        this.initializeWallet();
      });
    }

    this.balanceInterval = setInterval(() => this.fetchBalance(), 5000);
  }

  componentWillUnmount() {
    window.removeEventListener('resize', this.handleResize);
    window.removeEventListener('hashchange', this.applyHashRound);
    window.removeEventListener('popstate', this.applyHashRound);
    this.hlWS.disconnect();
    this.roundManager.stopTicking();
    if (this.balanceInterval) clearInterval(this.balanceInterval);
  }

  applyHashRound = () => {
    const hash = window.location.hash.replace(/^#/, '');
    if (!hash) {
      const currentId = this.roundManager.getCurrentRoundId();
      window.history.replaceState(null, '', `#${this.roundManager.toSlug(currentId)}`);
      this.roundManager.goToCurrentRound();
      return;
    }
    const roundId = this.roundManager.parseSlug(hash);
    if (roundId === null) return;
    this.roundManager.viewingRoundId = roundId;
    this.setState({ roundVersion: this.state.roundVersion + 1 });
  }


  initHyperliquidWS = () => {
    this.hlWS.on('price', (data) => {
      this.setState({ currentPrice: data.price });
    });

    this.hlWS.on('connected', () => {
      console.log('Hyperliquid WS connected');
    });

    this.hlWS.on('disconnected', () => {
      console.log('Hyperliquid WS disconnected');
    });

    this.hlWS.on('candle', ({ key, candle }) => {
      if (!key.startsWith('BTC:1m')) return;
      this.setState({ currentPrice: candle.close });
    });
  }

  // Only run the live WS feed when viewing the current round; historical
  // rounds don't need realtime data, they just fetch their finished history.
  syncWsConnection = () => {
    const viewingCurrent = this.roundManager.viewingRoundId === null;
    if (viewingCurrent) {
      if (!this.hlWS.isConnected()) {
        this.hlWS.connect();
        this.hlWS.subscribeTrades('BTC');
        this.hlWS.subscribeCandle('BTC', '1m');
      }
    } else {
      this.hlWS.disconnect();
    }
  }

  switchToAnvilChain = async () => {
    const chainIdHex = `0x${ANVIL_CHAIN_ID.toString(16)}`;
    try {
      await window.ethereum.request({
        method: 'wallet_switchEthereumChain',
        params: [{ chainId: chainIdHex }],
      });
    } catch (switchError) {
      if (switchError.code === 4902) {
        await window.ethereum.request({
          method: 'wallet_addEthereumChain',
          params: [{
            chainId: chainIdHex,
            chainName: 'Anvil Local',
            nativeCurrency: { name: 'ETH', symbol: 'ETH', decimals: 18 },
            rpcUrls: [ANVIL_RPC_URL],
          }],
        });
      } else {
        throw switchError;
      }
    }
  }

  connectWalletForMode = async () => {
    if (!USE_METAMASK) {
      return { provider: new ethers.JsonRpcProvider(ANVIL_RPC_URL, ANVIL_CHAIN_ID) };
    }
    if (typeof window.ethereum === 'undefined') {
      throw new Error('MetaMask is not installed!');
    }
    await this.switchToAnvilChain();
    const provider = new ethers.BrowserProvider(window.ethereum);
    await provider.send('eth_requestAccounts', []);
    return { provider };
  }

  initializeWallet = async () => {
    try {
      const { provider } = await this.connectWalletForMode();
      const signer = await provider.getSigner();
      const ethAddress = await signer.getAddress();
      this.setState({ ethAddress, provider, signer });
      this.fetchBalance();
    } catch (error) {
      console.error('Error initializing wallet:', error);
    } finally {
      this.setState({ walletLoading: false });
    }
  }

  handleWalletLogin = async () => {
    try {
      const { provider } = await this.connectWalletForMode();
      const signer = await provider.getSigner();
      const ethAddress = await signer.getAddress();
      this.setState({ ethAddress, provider, signer });
      this.fetchBalance();
    } catch (error) {
      console.error('Error logging in:', error);
    }
  }

  handleWalletLogout = async () => {
    this.setState({
      ethAddress: null, provider: null, signer: null, usdcBalance: '0',
    });
  }

  fetchBalance = async () => {
    const { signer } = this.state;
    if (!signer) return;
    try {
      const address = await signer.getAddress();
      const prefix = `base-USDC-balance:${address.toLowerCase()}`;
      const response = await fetch(`${TESTNET_INDEXER_URL}/api/get_latest_state?prefix=${prefix}`);
      const data_json = await response.text();
      const data = parseJsonWithBigInt(data_json);
      const formatted = ethers.formatUnits(BigInt(data.result || 0), 6);
      this.setState({ usdcBalance: formatted });
    } catch (error) {
      console.error('Failed to fetch balance:', error);
    }
  }

  handleResize = () => {
    this.setState({ screenWidth: window.innerWidth });
  }

  handleTargetChange = (roundId, value) => {
    this.roundManager.setTargetPrice(roundId, value);
  }

  render() {
    const { screenWidth, ethAddress, walletLoading, currentPrice, usdcBalance, roundVersion } = this.state;

    const walletState = { ethAddress, walletLoading };

    const header = rc(Header, {
      walletState,
      handleWalletLogin: this.handleWalletLogin,
      handleWalletLogout: this.handleWalletLogout,
    });

    const livePrice = rc(LivePricePanel, {
      currentPrice,
      roundManager: this.roundManager,
      onTargetPrice: this.handleTargetChange,
    });

    const roundNav = rc(RoundNavigator, {
      roundManager: this.roundManager,
      targetPrice: this.state.targetPrice,
      onTargetChange: this.handleTargetChange,
      currentPrice,
    });

    const predictionPanel = rc(PredictionMarketPanel, {
      roundManager: this.roundManager,
      currentPrice,
    });

    const tradePanel = rc(TradePanel, {
      balance: usdcBalance,
      signer: this.state.signer,
      onTrade: this.fetchBalance,
      roundManager: this.roundManager,
      currentPrice,
    });

    const depositPanel = rc(DepositPanel, { signer: this.state.signer });

    const assetsPanel = rc(AssetsPanel, {
      address: ethAddress,
      balance: usdcBalance,
    });

    if (screenWidth < 960) {
      return rc('div', null,
        header,
        rc('main', { style: { padding: '8px' } },
          rc('div', { style: { display: 'flex', flexDirection: 'column', gap: '8px' } },
            livePrice,
            roundNav,
            predictionPanel,
            tradePanel,
            depositPanel,
            assetsPanel
          )
        )
      );
    }

    if (screenWidth < 1400) {
      return rc('div', null,
        header,
        rc('main', { style: { padding: '8px' } },
          rc('div', { style: { display: 'flex', gap: '8px' } },
            rc('div', { style: { flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' } },
              livePrice,
              roundNav,
              predictionPanel,
              assetsPanel
            ),
            rc('div', { style: { width: '320px', display: 'flex', flexDirection: 'column', gap: '8px' } },
              tradePanel,
              depositPanel
            )
          )
        )
      );
    }

    return rc('div', null,
      header,
      rc('main', { style: { padding: '8px' } },
        rc('div', { style: { display: 'flex', gap: '8px' } },
          rc('div', { style: { flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' } },
            livePrice,
            roundNav,
            predictionPanel,
            assetsPanel
          ),
          rc('div', { style: { width: '320px', display: 'flex', flexDirection: 'column', gap: '8px' } },
            tradePanel,
            depositPanel
          )
        )
      )
    );
  }
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(rc(App, null));
