const ROUND_DURATION = 300;

const RoundState = {
  ACTIVE: 'active',
  SETTLING: 'settling',
  RESOLVED: 'resolved'
};

class RoundManager {
  constructor() {
    this.listeners = [];
    this.viewingRoundId = null;
    this.targetPrices = {};
    this.roundResults = {};
    this._tickTimer = null;
  }

  getCurrentRoundId() {
    return Math.floor(Date.now() / 1000 / ROUND_DURATION);
  }

  getRoundStart(roundId) {
    return roundId * ROUND_DURATION;
  }

  getRoundEnd(roundId) {
    return (roundId + 1) * ROUND_DURATION;
  }

  getTimeRemaining(roundId) {
    if (roundId === undefined) roundId = this.getCurrentRoundId();
    const now = Math.floor(Date.now() / 1000);
    const end = this.getRoundEnd(roundId);
    return Math.max(0, end - now);
  }

  getProgress(roundId) {
    if (roundId === undefined) roundId = this.getCurrentRoundId();
    const now = Math.floor(Date.now() / 1000);
    const start = this.getRoundStart(roundId);
    const elapsed = now - start;
    return Math.min(1, Math.max(0, elapsed / ROUND_DURATION));
  }

  getRoundState(roundId) {
    if (roundId === undefined) roundId = this.getCurrentRoundId();
    const currentId = this.getCurrentRoundId();

    if (roundId < currentId) {
      return this.roundResults[roundId] ? RoundState.RESOLVED : RoundState.SETTLING;
    }
    if (roundId === currentId) {
      const remaining = this.getTimeRemaining(roundId);
      if (remaining <= 0) return RoundState.SETTLING;
      return RoundState.ACTIVE;
    }
    return RoundState.ACTIVE;
  }

  setTargetPrice(roundId, price) {
    this.targetPrices[roundId] = price;
  }

  getTargetPrice(roundId) {
    return this.targetPrices[roundId] || null;
  }

  setRoundResult(roundId, result) {
    this.roundResults[roundId] = result;
  }

  getRoundResult(roundId) {
    return this.roundResults[roundId] || null;
  }

  determineResult(targetPrice, finalPrice) {
    if (targetPrice === null || finalPrice === null) return null;
    return finalPrice > targetPrice ? 'YES' : 'NO';
  }

  formatTime(seconds) {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${String(s).padStart(2, '0')}`;
  }

  formatRoundId(roundId) {
    return this.toSlug(roundId);
  }

  toSlug(roundId) {
    const start = this.getRoundStart(roundId);
    const d = new Date(start * 1000);
    const pad = (n) => String(n).padStart(2, '0');
    const stamp = `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}${pad(d.getUTCHours())}${pad(d.getUTCMinutes())}`;
    return `BTC-5min-${stamp}`;
  }

  parseSlug(slug) {
    if (!slug || typeof slug !== 'string') return null;
    const m = slug.match(/^BTC-5min-(\d{12})$/i);
    if (!m) return null;
    const stamp = m[1];
    const year = parseInt(stamp.slice(0, 4), 10);
    const month = parseInt(stamp.slice(4, 6), 10) - 1;
    const day = parseInt(stamp.slice(6, 8), 10);
    const hour = parseInt(stamp.slice(8, 10), 10);
    const minute = parseInt(stamp.slice(10, 12), 10);
    const utcMs = Date.UTC(year, month, day, hour, minute);
    const startSec = Math.floor(utcMs / 1000);
    const roundId = Math.floor(startSec / ROUND_DURATION);
    // Only accept slugs that are aligned to a round boundary
    if (this.getRoundStart(roundId) !== startSec) return null;
    return roundId;
  }

  getDisplayRoundId() {
    return this.viewingRoundId !== null ? this.viewingRoundId : this.getCurrentRoundId();
  }

  isViewingCurrentRound() {
    return this.viewingRoundId === null || this.viewingRoundId === this.getCurrentRoundId();
  }

  goToPreviousRound() {
    const current = this.getDisplayRoundId();
    this.viewingRoundId = current - 1;
    this._syncHash();
    this._emit();
  }

  goToNextRound() {
    const current = this.getDisplayRoundId();
    const currentRound = this.getCurrentRoundId();
    if (current < currentRound) {
      this.viewingRoundId = current + 1;
      if (this.viewingRoundId > currentRound) {
        this.viewingRoundId = null;
      }
      this._syncHash();
      this._emit();
    }
  }

  goToCurrentRound() {
    this.viewingRoundId = null;
    this._syncHash();
    this._emit();
  }

  _syncHash() {
    if (typeof window === 'undefined') return;
    const currentId = this.getCurrentRoundId();
    const targetId = this.viewingRoundId === null ? currentId : this.viewingRoundId;
    window.history.pushState(null, '', `#${this.toSlug(targetId)}`);
  }

  onChange(callback) {
    this.listeners.push(callback);
  }

  _emit() {
    this.listeners.forEach(cb => {
      try { cb(); } catch (e) { console.error('RoundManager listener error:', e); }
    });
  }

  startTicking(intervalMs = 1000) {
    if (this._tickTimer) return;
    let lastRoundId = this.getCurrentRoundId();
    this._tickTimer = setInterval(() => {
      const newRoundId = this.getCurrentRoundId();
      if (newRoundId !== lastRoundId) {
        lastRoundId = newRoundId;
        // When live-viewing (not browsing history), jump to the new round
        // when the current round's time is up.
        if (this.viewingRoundId === null) {
          this._syncHash();
        }
        this._emit();
      }
    }, intervalMs);
  }

  stopTicking() {
    if (this._tickTimer) {
      clearInterval(this._tickTimer);
      this._tickTimer = null;
    }
  }
}

window.RoundManager = RoundManager;
window.RoundState = RoundState;
window.ROUND_DURATION = ROUND_DURATION;
