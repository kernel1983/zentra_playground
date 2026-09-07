import time
import requests

import setting
from test_rpc_init import transaction, next_block

PROVIDER_HOST = 'http://127.0.0.1:8545'
ME = setting.accounts[0].address.lower()
SLUG = 'btc_5min'
TOKENS = 10 * 10**6
MINT_QTY = 5000 * 10**6
USDC_MINT = MINT_QTY * 2
SLEEP = 5
SPREAD = 1

def state(key):
    resp = requests.get(f'{PROVIDER_HOST}/api/get_latest_state?prefix={key}')
    return resp.json().get('result')

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

def get_my_orders():
    my_orders = []
    for token in ['yes', 'no']:
        for side in ['sell', 'buy']:
            prefix = f'predict-{SLUG}_{token}_{side}'
            new_id = state(f'{prefix}_new')
            if new_id is None:
                continue
            for oid in range(1, int(new_id)):
                order = state(f'{prefix}:{oid}')
                if isinstance(order, list) and len(order) >= 6 and order[0].lower() == ME:
                    my_orders.append((token, side, oid))
    return my_orders

def cancel_all_orders():
    orders = get_my_orders()
    for token, side, oid in orders:
        call = '{"p":"zentest3","f":"predict_limit_order_cancel","a":["%s","%s","%s",%d]}' % (
            SLUG, token, side, oid)
        print(f'  Cancel {token} {side} #{oid}')
        tx = transaction(accounts[0], call)
        print(f'    tx: {tx}')

if __name__ == '__main__':
    accounts = setting.accounts

    if state(f'predict-{SLUG}_quote_token') is None:
        print('Bootstrapping market...')
        if not state('committee-members'):
            transaction(accounts[0], '{"p":"zentest3","f":"committee_init","a":[]}')
        if state('predict-manager') is None:
            transaction(accounts[0],
                        '{"p":"zentest3","f":"predict_vote_manager","a":["%s"]}' % ME)
        qt = state('predict-quote_tokens') or []
        if 'USDC' not in qt:
            transaction(accounts[0],
                        '{"p":"zentest3","f":"predict_set_quote_token","a":[["USDC"]]}')
        transaction(accounts[0],
                    '{"p":"zentest3","f":"predict_create","a":["%s","USDC"]}' % SLUG)

    print('Minting tokens...')
    for call in [
        '{"p":"zentest3","f":"token_mint_free","a":["USDC",%d]}' % (USDC_MINT),
        '{"p":"zentest3","f":"predict_mint","a":["%s",%d]}' % (SLUG, MINT_QTY),
    ]:
        transaction(accounts[0], call)
    next_block()
    print('Minted %d YES + %d NO + %d USDC' % (
        MINT_QTY // 10**6, MINT_QTY // 10**6, (USDC_MINT - MINT_QTY) // 10**6))

    target_price = None
    period_start = None
    period_end = None
    n = TOKENS // 10**6

    print('Maker running (Ctrl+C to stop)')
    while True:
        now = time.time()

        if target_price is None or now >= period_end:
            target_price = get_btc_price()
            period_start = now
            period_end = now + 300
            print(f'\n[Target] BTC = ${target_price:,.2f}  period: {time.strftime("%H:%M:%S")} - {time.strftime("%H:%M:%S", time.localtime(period_end))}')

        current_price = get_btc_price()
        fair = calc_fair_price(current_price, target_price, period_start, period_end)

        yes_ask = int(max(2, min(99, fair + SPREAD)))
        yes_bid = int(max(1, min(98, fair - SPREAD)))
        no_ask = 100 - yes_bid
        no_bid = 100 - yes_ask

        print(f'BTC=${current_price:,.2f}  fair={fair:.1f}  YES[{yes_bid}-{yes_ask}] NO[{no_bid}-{no_ask}]')

        cancel_all_orders()
        next_block()

        orders = [
            ('yes', -TOKENS, n * yes_ask * 10**4),
            ('yes',  TOKENS, -(n * yes_bid * 10**4)),
            ('no',  -TOKENS, n * no_ask * 10**4),
            ('no',   TOKENS, -(n * no_bid * 10**4)),
        ]

        for token, base, quote in orders:
            side = 'SELL' if base < 0 else 'BUY'
            price_cents = quote / (n * 10**4) if base < 0 else -quote / (n * 10**4)
            call = '{"p":"zentest3","f":"predict_limit_order","a":["%s",%d,"%s",%d]}' % (
                SLUG, base, token, quote)
            print(f'  {token.upper():>3} {side} {n} @ {price_cents:.0f}¢')
            tx = transaction(accounts[0], call)
            print(f'    tx: {tx}')

        next_block()
        time.sleep(SLEEP)
