import sys
import time
import datetime
import concurrent.futures
import requests

import setting

PROVIDER_HOST = 'http://127.0.0.1:8545'
ME = setting.accounts[0].address.lower()
PERIOD = 300

def state(key):
    resp = requests.get(f'{PROVIDER_HOST}/api/get_latest_state?prefix={key}')
    return resp.json().get('result')

def mint_events():
    resp = requests.get(f'{PROVIDER_HOST}/api/events?event=PredictMint')
    return resp.json().get('events', [])

def minted_per_addr(slug=None):
    total = {}
    block_from = created_block(slug) if slug is not None else None
    for evt in mint_events():
        if block_from is not None and evt.get('blockno', 0) < block_from:
            continue
        s, addr, qty = evt['args'][0], evt['args'][1].lower(), int(evt['args'][2])
        if slug is None or s == slug:
            total[addr] = total.get(addr, 0) + qty
    return total

def trade_events():
    out = []
    for name in ['PredictLimitTake', 'PredictMarketTake']:
        resp = requests.get(f'{PROVIDER_HOST}/api/events?event={name}')
        out.extend(resp.json().get('events', []))
    return out

def created_block(slug):
    """Block number at which the slug's predict market was created (PredictCreate).
    Returns None if the event isn't recorded yet."""
    resp = requests.get(f'{PROVIDER_HOST}/api/events?event=PredictCreate')
    for evt in resp.json().get('events', []):
        if evt['args'][0] == slug:
            return evt['blockno']
    return None

def trades_per_addr(slug=None):
    """addr -> {token: {buy: [n, base, base_cents], sell: [n, base, base_cents]}}
    Assumes all active traders only hit ME's resting limit orders (ME is the
    unique maker). So:
      - PredictMarketTake (non-ME): taker market order filled against ME -> ME is
        the passive side -> reverse direction into ME.
      - PredictLimitTake (addr==ME): ME's own placing limit order filled
        immediately -> active -> count into ME directly.
    taker-vs-taker cross fills would break this assumption.
    If the slug was created on-chain after this local node started, only trades
    in blocks >= the creation block are counted."""
    stats = {}
    block_from = created_block(slug) if slug is not None else None
    for evt in trade_events():
        name = evt['event']
        if block_from is not None and evt.get('blockno', 0) < block_from:
            continue
        pair, direction, addr, take_base, price = evt['args'][0], evt['args'][1], \
            evt['args'][2].lower(), int(evt['args'][3]), int(evt['args'][4])
        s, token = pair.rsplit('_', 1)
        if slug is not None and s != slug:
            continue
        if direction not in ('buy', 'sell'):
            continue
        if not (0 < int(price) < 10**18):
            continue
        base = abs(take_base)
        base_cents = base * price // (10**16)
        if name == 'PredictMarketTake' and addr != ME:
            # passive fill for ME: taker buy -> ME sell, taker sell -> ME buy
            direction = 'sell' if direction == 'buy' else 'buy'
            addr = ME
        elif name == 'PredictLimitTake' and addr != ME:
            # taker placed a limit order and it crossed; only keep if MY assumption
            # holds that its counterpart was ME. That is actually a passive fill
            # too, handled the same way:
            direction = 'sell' if direction == 'buy' else 'buy'
            addr = ME
        a = stats.setdefault(addr, {}).setdefault(token, {'buy': [0, 0, 0], 'sell': [0, 0, 0]})
        side = a[direction]
        side[0] += 1
        side[1] += base
        side[2] += base_cents
    return stats


def make_slug(period_start):
    dt = datetime.datetime.utcfromtimestamp(period_start)
    return 'btc_5min_%04d%02d%02d%02d%02d' % (
        dt.year, dt.month, dt.day, dt.hour, dt.minute)

def current_slug():
    now = int(time.time())
    return current_slug_at(now)

def current_slug_at(t):
    p_start = (int(t) // PERIOD) * PERIOD
    return make_slug(p_start)

def walk_linked(prefix):
    start = state(f'{prefix}_start')
    if start is None:
        return []
    seq = []
    oid = int(start)
    seen = set()
    while oid is not None and oid not in seen:
        seen.add(oid)
        order = state(f'{prefix}:{oid}')
        if not isinstance(order, list) or len(order) < 6:
            break
        seq.append((oid, order))
        oid = order[5]
    return seq

def collect_orders(slug):
    """Collect all orders for a slug. Returns dict: {addr: {token: {side: [(oid, base, quote, price)]}}}"""
    orders_by_addr = {}
    for token in ['yes', 'no']:
        for side in ['sell', 'buy']:
            prefix = f'predict-{slug}_{token}_{side}'
            for oid, order in walk_linked(prefix):
                addr = order[0].lower()
                base = int(order[1])
                quote = int(order[2])
                price = int(order[3])
                orders_by_addr.setdefault(addr, {}).setdefault(token, {}).setdefault(side, [])
                orders_by_addr[addr][token][side].append((oid, base, quote, price))
    return orders_by_addr

def holders(slug, tick):
    addrs = []
    a = state(f'predict-{slug}_{tick}_balance_new')
    seen = set()
    while a and a not in seen:
        seen.add(a)
        addrs.append(a)
        balance = state(f'predict-{slug}_{tick}_balance:{a}')
        if not isinstance(balance, list) or len(balance) < 2:
            break
        a = balance[1]
    return addrs

def get_balance(addr, slug):
    checks = {
        'USDC': ('USDC-balance', 6),
        f'YES ({slug})': (f'predict-{slug}_yes_balance', 6),
        f'NO ({slug})': (f'predict-{slug}_no_balance', 6),
    }
    balances = {}
    for label, (prefix, decimals) in checks.items():
        value = state(f'{prefix}:{addr}')
        if isinstance(value, list):
            value = value[0] if value else 0
        balances[label] = int(value or 0) / 10 ** decimals
    return balances

def get_btc_price():
    resp = requests.post('https://api.hyperliquid.xyz/info',
                         json={'type': 'allMids'})
    return float(resp.json()['BTC'])

def calc_fair_price(current_price, target_price, start_time, end_time):
    now = time.time()
    if end_time <= start_time:
        return 50.0
    time_remaining = max(0.0, min(1.0, (end_time - now) / (end_time - start_time)))
    decay = 1.0 - time_remaining
    price_diff_pct = (current_price - target_price) / target_price * 100
    if current_price >= target_price:
        fair = 50.0 + 49.0 * decay + price_diff_pct * time_remaining
    else:
        fair = 50.0 - 49.0 * decay + price_diff_pct * time_remaining
    return max(1.0, min(99.0, fair))


def analyze(slug):
    addresses = set()
    for a in setting.accounts:
        addresses.add(a.address.lower())
    for tick in ['yes', 'no']:
        for a in holders(slug, tick):
            addresses.add(a)
    orders_by_addr = collect_orders(slug)
    addresses.update(orders_by_addr.keys())

    rows = []
    for addr in sorted(addresses):
        b = get_balance(addr, slug)
        usdc = b['USDC']
        yes_hand = b[f'YES ({slug})']
        no_hand = b[f'NO ({slug})']

        yes_sell_tok = 0.0
        yes_buy_tok = 0.0
        no_sell_tok = 0.0
        no_buy_tok = 0.0
        usdc_locked = 0.0

        my = orders_by_addr.get(addr, {})
        for oid, base, quote, price in my.get('yes', {}).get('sell', []):
            yes_sell_tok += abs(base) / 1e6
        for oid, base, quote, price in my.get('yes', {}).get('buy', []):
            yes_buy_tok += abs(base) / 1e6
            usdc_locked += abs(quote) / 1e6
        for oid, base, quote, price in my.get('no', {}).get('sell', []):
            no_sell_tok += abs(base) / 1e6
        for oid, base, quote, price in my.get('no', {}).get('buy', []):
            no_buy_tok += abs(base) / 1e6
            usdc_locked += abs(quote) / 1e6

        # Chain balance already deducts base locked by open SELL orders
        # (zip24 predict_limit_order updates balance with negative base_value).
        # To show true holdings (mint + filled buys - filled sells), add the
        # locked sell quantity back.
        yes_delta = yes_hand + yes_sell_tok
        no_delta = no_hand + no_sell_tok
        net_usdc = usdc - usdc_locked

        rows.append({
            'addr': addr,
            'usdc': usdc, 'usdc_locked': usdc_locked, 'net_usdc': net_usdc,
            'yes_hand': yes_hand, 'yes_sell': yes_sell_tok, 'yes_buy': yes_buy_tok,
            'yes_delta': yes_delta,
            'no_hand': no_hand, 'no_sell': no_sell_tok, 'no_buy': no_buy_tok,
            'no_delta': no_delta,
            'my_orders': my,
        })

    return rows

def print_book(slug):
    print(f'\n=== orderbook: {slug} ===')
    for side in ['sell', 'buy']:
        for token in ['yes', 'no']:
            prefix = f'predict-{slug}_{token}_{side}'
            seq = walk_linked(prefix)
            if side == 'buy':
                seq = seq[::-1]
            if not seq:
                continue
            print(f'  {side.upper():>4} {token.upper():>3}')
            for oid, order in seq:
                maker = order[0][:10]
                base = abs(int(order[1])) / 1e6
                quote = abs(int(order[2])) / 1e6
                price = int(order[3]) / 1e16
                print(f'    #{oid:<4} {price:6.2f}c  {base:10.2f} tok  {quote:10.2f} USDC  {maker}')

def print_delta(rows, slug):
    print(f'\n=== delta: {slug} ({len(rows)} holders) ===')
    minted = minted_per_addr(slug)
    t = trades_per_addr(slug)
    tot = {'usdc': 0, 'net_usdc': 0, 'yes_hand': 0, 'yes_sell': 0, 'yes_buy': 0, 'yes_delta': 0,
           'no_hand': 0, 'no_sell': 0, 'no_buy': 0, 'no_delta': 0}
    for r in rows:
        if r['addr'] != ME:
            continue
        if not (r['usdc'] or r['yes_hand'] or r['no_hand'] or r['yes_sell'] or r['yes_buy']
                or r['no_sell'] or r['no_buy']):
            continue
        tag = ''
        yes_delta = r['yes_delta']
        no_delta = r['no_delta']
        held = yes_delta + no_delta
        diff = yes_delta - no_delta
        if diff > 0:
            bias = f'MORE YES +{diff:.0f}'
        elif diff < 0:
            bias = f'MORE NO {diff:.0f}'
        else:
            bias = 'BALANCED'
        mint = minted.get(r['addr'], 0) / 1e6
        print(f'\n  {r["addr"]}{tag}')
        print(f'    USDC: hand={r["usdc"]:10.2f}  buy_locked={r["usdc_locked"]:10.2f}  total={r["usdc"] + r["usdc_locked"]:10.2f}')
        print(f'    minted: {mint:12.2f}')
        tr = t.get(r['addr'], {})
        my = r['my_orders']
        for token in ['yes', 'no']:
            t = tr.get(token, {})
            parts = []
            for side in ['buy', 'sell']:
                n, base, base_cents = t.get(side, [0, 0, 0])
                if base:
                    avg = base_cents / base
                    parts.append(f'{side} {n}x {base/1e6:.0f} tok @ {avg:.1f}c')
            obuy = sum(abs(int(o[1])) / 1e6 for o in my.get(token, {}).get('buy', []))
            osell = sum(abs(int(o[1])) / 1e6 for o in my.get(token, {}).get('sell', []))
            if osell:
                parts.append(f'openSell {osell:.0f}')
            if parts:
                print(f'    {token.upper()}: ' + '  '.join(parts))
            _ = obuy
        sales_yes = (tr.get('yes', {}).get('sell', [0, 0, 0])[2]
                     - tr.get('yes', {}).get('buy', [0, 0, 0])[2]) / 1e8
        sales_no = (tr.get('no', {}).get('sell', [0, 0, 0])[2]
                    - tr.get('no', {}).get('buy', [0, 0, 0])[2]) / 1e8
        if diff == 0:
            print(f'    YES/NO: {yes_delta:10.2f} each  (balanced)  sales YES {sales_yes:+.2f}  NO {sales_no:+.2f}')
        else:
            print(f'    YES: {yes_delta:10.2f}  NO: {no_delta:10.2f}  sales YES {sales_yes:+.2f}  NO {sales_no:+.2f}')
        print(f'    >> {bias}')
        n_orders = sum(len(v2) for v in r['my_orders'].values() for v2 in v.values())
        if n_orders:
            print(f'    orders: {n_orders}')
        for tok in r['my_orders']:
            for sd in r['my_orders'][tok]:
                for oid, base, quote, price in r['my_orders'][tok][sd]:
                    pc = price / 1e16
                    print(f'      {tok.upper():>3} {sd.upper():>4} #{oid:<4} '
                          f'{pc:6.2f}c  {abs(base)/1e6:10.2f} tok  {abs(quote)/1e6:10.2f} USDC')
        for k in tot:
            tot[k] += r[k]

    tot_diff = tot['yes_delta'] - tot['no_delta']
    if tot_diff > 0:
        tot_bias = f'MORE YES +{tot_diff:.0f}'
    elif tot_diff < 0:
        tot_bias = f'MORE NO {tot_diff:.0f}'
    else:
        tot_bias = 'BALANCED'
    tot_held = tot['yes_delta'] + tot['no_delta']

def mm_suggest(slug, rows, fair):
    print(f'\n=== MM suggestion (fair={fair:.1f}c) ===')

    best_yes_bid = 0
    best_yes_ask = 100
    best_no_bid = 0
    best_no_ask = 100

    for r in rows:
        for tok in r['my_orders']:
            for sd in r['my_orders'][tok]:
                for oid, base, quote, price in r['my_orders'][tok][sd]:
                    pc = price / 1e16
                    if tok == 'yes':
                        if sd == 'buy' and pc > best_yes_bid:
                            best_yes_bid = pc
                        if sd == 'sell' and pc < best_yes_ask:
                            best_yes_ask = pc
                    else:
                        if sd == 'buy' and pc > best_no_bid:
                            best_no_bid = pc
                        if sd == 'sell' and pc < best_no_ask:
                            best_no_ask = pc

    print(f'  current book:  YES bid={best_yes_bid:.0f}c ask={best_yes_ask:.0f}c  '
          f'NO bid={best_no_bid:.0f}c ask={best_no_ask:.0f}c')
    print(f'  spread: YES {best_yes_ask - best_yes_bid:.0f}c  NO {best_no_ask - best_no_bid:.0f}c')

    spread = 1
    suggest_yes_ask = max(2, min(99, int(fair + spread)))
    suggest_yes_bid = max(1, min(98, int(fair - spread)))
    suggest_no_ask = 100 - suggest_yes_bid
    suggest_no_bid = 100 - suggest_yes_ask

    print(f'\n  suggested new orders (spread={spread}c):')
    print(f'    YES BUY  @ {suggest_yes_bid}c   (fair {fair:.1f} - {spread})')
    print(f'    YES SELL @ {suggest_yes_ask}c   (fair {fair:.1f} + {spread})')
    print(f'    NO  BUY  @ {suggest_no_bid}c')
    print(f'    NO  SELL @ {suggest_no_ask}c')

    if best_yes_bid >= suggest_yes_bid and best_yes_ask <= suggest_yes_ask:
        print(f'\n  => existing orders already cover suggested range, no action needed')
    else:
        print(f'\n  => consider cancelling & re-quoting at new levels')


if __name__ == '__main__':
    args = sys.argv[1:]
    refresh = int(args[0]) if args and args[0].isdigit() else 5
    slug_arg = args[1] if len(args) > 1 else None

    print(f'ME: {ME}')
    print(f'refresh: every {refresh}s (Ctrl+C to stop)')

    last_slug = None
    while True:
        slug = slug_arg or current_slug()
        print('\033[2J\033[H', end='')  # clear screen
        print(f'target: {slug}')
        if slug != last_slug:
            last_slug = slug
            try:
                btc = get_btc_price()
            except Exception:
                btc = None
        try:
            now = time.time()
            p_start = (int(now) // PERIOD) * PERIOD
            if btc is None:
                btc = get_btc_price()
            target_raw = state(f'predict-{slug}_target_price')
            target = float(target_raw) if target_raw else btc
            fair = calc_fair_price(btc, target, p_start, p_start + PERIOD)
            label = 'on-chain' if target_raw else 'approx (current BTC)'
            print(f'BTC=${btc:,.2f}  target=${target:,.2f} ({label})  fair={fair:.1f}c  '
                  f'time_left={max(0, p_start + PERIOD - now):.0f}s')
        except Exception:
            fair = 50.0

        rows = analyze(slug)
        print_delta(rows, slug)
        print_book(slug)
        mm_suggest(slug, rows, fair)

        time.sleep(refresh)
