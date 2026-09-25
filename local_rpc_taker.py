import sys
import time
import random
import json
import requests

from local_rpc_init import transaction, next_block
import setting

PROVIDER_HOST = 'http://127.0.0.1:8545'
PERIOD = 300
TAKER_COUNT = 3
MINT_USDC = 10000 * 10**6
MINT_QTY = 5000 * 10**6

def state(key):
    resp = requests.get(f'{PROVIDER_HOST}/api/get_latest_state?prefix={key}')
    return resp.json().get('result')

def make_slug(period_start):
    import datetime
    dt = datetime.datetime.utcfromtimestamp(period_start)
    return 'btc_5min_%04d%02d%02d%02d%02d' % (
        dt.year, dt.month, dt.day, dt.hour, dt.minute)

def current_slug():
    now = int(time.time())
    p_start = (now // PERIOD) * PERIOD
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

def best_prices(slug):
    """Get best bid/ask for YES and NO from the orderbook."""
    prices = {}
    for token in ['yes', 'no']:
        prices[token] = {'bid': 0, 'ask': 100}
        for side in ['buy', 'sell']:
            prefix = f'predict-{slug}_{token}_{side}'
            seq = walk_linked(prefix)
            if side == 'buy':
                seq = seq[::-1]
            for oid, order in seq:
                pc = int(order[3]) / 1e16
                if side == 'buy' and pc > prices[token]['bid']:
                    prices[token]['bid'] = pc
                if side == 'sell' and pc < prices[token]['ask']:
                    prices[token]['ask'] = pc
    return prices

def bootstrap():
    if state('committee-members') is None:
        transaction(setting.accounts[0], '{"p":"zentest3","f":"committee_init","a":[]}')
        next_block()
    if state('predict-manager') is None:
        transaction(setting.accounts[0],
                    '{"p":"zentest3","f":"predict_vote_manager","a":["%s"]}' % setting.accounts[0].address.lower())
        next_block()
    qt = state('predict-quote_tokens') or []
    if 'USDC' not in qt:
        transaction(setting.accounts[0],
                    '{"p":"zentest3","f":"predict_set_quote_token","a":[["USDC"]]}')
        next_block()

def taker_setup(takers):
    """Mint USDC for each taker (tokens are only bought from the maker)."""
    for acct in takers:
        addr = acct.address.lower()
        existing = state(f'USDC-balance:{addr}')
        if existing is not None and int(existing) >= MINT_USDC // 2:
            continue
        print(f'  Setup taker {addr[:10]}...')
        transaction(acct, json.dumps({"p": "zentest3", "f": "token_mint_free", "a": ["USDC", MINT_USDC]}))
        next_block()

def holdings(addr, slug):
    """Returns (yes, no) token balance for this taker."""
    bal = state(f'predict-{slug}_yes_balance:{addr}')
    yes = int(bal[0]) if bal else 0
    bal = state(f'predict-{slug}_no_balance:{addr}')
    no = int(bal[0]) if bal else 0
    return yes, no

def market_order(acct, slug, buy_or_sell, token, cost_usdc):
    """Place a market order."""
    base = 1e6  # 1e6 quote units == 1 share == 1 USDC of mint

    if buy_or_sell == 'buy':
        base_value = int(cost_usdc * base * 2)  # ~50c avg fill: 2 shares per USDC
        quote_value = None
    else:
        base_value = None
        quote_value = int(cost_usdc * base)

    call = {"p": "zentest3", "f": "predict_market_order",
            "a": [slug, base_value, token, quote_value]}
    tx = transaction(acct, json.dumps(call))
    next_block()
    return tx

def limit_order(acct, slug, buy_or_sell, token, cents, cost_usdc):
    """Place a limit order at a specific price."""
    base = 1e6  # 1e6 quote units == 1 share == 1 USDC of mint

    if buy_or_sell == 'buy':
        base_value = int(cost_usdc * base * 100 / cents)
        quote_value = -int(cost_usdc * base)
    else:
        base_value = -int(cost_usdc * base * 100 / cents)
        quote_value = int(cost_usdc * base)

    call = {"p": "zentest3", "f": "predict_limit_order",
            "a": [slug, base_value, token, quote_value]}
    tx = transaction(acct, json.dumps(call))
    next_block()
    return tx


if __name__ == '__main__':
    bootstrap()

    takers = setting.accounts[1:1 + TAKER_COUNT]
    print(f'Takers: {[a.address.lower()[:10] for a in takers]}')

    print('Taker running (Ctrl+C to stop)')
    while True:
        slug = current_slug()
        quote_token = state(f'predict-{slug}_quote_token')
        if quote_token is None:
            print(f'[{time.strftime("%H:%M:%S")}] Waiting for market {slug}...')
            time.sleep(5)
            continue

        taker_setup(takers)

        acct = random.choice(takers)
        addr = acct.address.lower()
        yes_bal, no_bal = holdings(addr, slug)
        token = random.choice(['yes', 'no'])
        side = random.choice(['buy', 'sell'])
        have = yes_bal if token == 'yes' else no_bal
        if side == 'sell' and have <= 0:
            side = 'buy'
        cost = random.uniform(5, 50)

        prices = best_prices(slug)
        best_ask = prices[token]['ask']
        best_bid = prices[token]['bid']

        if side == 'buy' and best_ask < 100:
            cents = min(99, int(best_ask) + random.randint(0, 3))
        elif side == 'sell' and best_bid > 0:
            cents = max(1, int(best_bid) - random.randint(0, 3))
        else:
            side = 'buy'
            cents = random.randint(30, 70)

        print(f'[{time.strftime("%H:%M:%S")}] {acct.address.lower()[:10]} '
              f'{side} {token} @ {cents}c  cost={cost:.1f} USDC')

        try:
            tx = market_order(acct, slug, side, token, cost)
            print(f'  tx: {tx}')
        except Exception as e:
            print(f'  failed: {e}')

        time.sleep(random.uniform(2, 8))
