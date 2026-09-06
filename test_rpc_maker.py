import random
import time
import requests

import setting
from test_rpc_init import transaction, next_block

PROVIDER_HOST = 'http://127.0.0.1:8545'
ME = setting.accounts[0].address.lower()
SLUG = 'btc_5min'
TOKENS = 10 * 10**6          # per order (10 tokens, 6 decimals)
MINT_QTY = 5000 * 10**6      # 5000 tokens minted at startup
ASK_RANGE = (50, 60)
SPREAD_RANGE = (5, 15)
SLEEP = 5

def state(key):
    resp = requests.get(f'{PROVIDER_HOST}/api/get_latest_state?prefix={key}')
    return resp.json().get('result')

if __name__ == '__main__':
    accounts = setting.accounts

    # --- one-time bootstrap (idempotent) ---
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

    # --- mint tokens (idempotent, just adds) ---
    print('Minting tokens...')
    for call in [
        '{"p":"zentest3","f":"token_mint_free","a":["USDC",%d]}' % MINT_QTY,
        '{"p":"zentest3","f":"predict_mint","a":["%s",%d]}' % (SLUG, MINT_QTY),
    ]:
        transaction(accounts[0], call)
    next_block()
    print('Minted %d YES + %d NO + %d USDC' % (MINT_QTY // 10**6, MINT_QTY // 10**6, MINT_QTY // 10**6))

    # --- two-sided maker loop ---
    print('Maker running (Ctrl+C to stop)')
    while True:
        ask = random.randint(*ASK_RANGE)
        spread = random.randint(*SPREAD_RANGE)
        bid = max(10, ask - spread)
        no_ask = 100 - bid
        no_bid = 100 - ask
        n = TOKENS // 10**6

        orders = [
            ('yes', -TOKENS, n * ask * 10**4),
            ('yes',  TOKENS, -(n * bid * 10**4)),
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