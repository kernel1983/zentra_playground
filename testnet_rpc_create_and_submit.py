import sys
import time
import requests

import web3

from testnet_rpc_init import transaction, next_block, load_accounts

INDEXER_URL = 'https://testnet3.zentra.dev'  # Base Sepolia indexer (state/events)
PERIOD = 300  # 5 minutes


def state(key):
    resp = requests.get(f'{INDEXER_URL}/api/get_latest_state?prefix={key}')
    return resp.json().get('result')

def get_btc_price():
    resp = requests.post('https://api.hyperliquid.xyz/info',
                         json={'type': 'allMids'})
    return float(resp.json()['BTC'])

def make_slug(period_start):
    import datetime
    dt = datetime.datetime.utcfromtimestamp(period_start)
    return 'btc_5min_%04d%02d%02d%02d%02d' % (
        dt.year, dt.month, dt.day, dt.hour, dt.minute)

def next_period_start(now):
    return int((now // PERIOD + 1) * PERIOD)

def bootstrap():
    if state('predict-btc_5min_quote_token') is not None:
        return
    print('Bootstrapping...')
    if not state('committee-members'):
        transaction(accounts[0], '{"p":"zentest3","f":"committee_init","a":[]}')
    if state('predict-manager') is None:
        transaction(accounts[0],
                    '{"p":"zentest3","f":"predict_vote_manager","a":["%s"]}' % ME)
    qt = state('predict-quote_tokens') or []
    if 'USDC' not in qt:
        transaction(accounts[0],
                    '{"p":"zentest3","f":"predict_set_quote_token","a":[["USDC"]]}')

def create_market(slug):
    if state(f'predict-{slug}_quote_token') is not None:
        print(f'  Market already exists: {slug}')
        return
    transaction(accounts[0],
                '{"p":"zentest3","f":"predict_create","a":["%s","USDC"]}' % slug)
    next_block()
    print(f'  Created market: {slug}')

def submit_market(slug, winner):
    transaction(accounts[0],
                '{"p":"zentest3","f":"predict_submit","a":["%s","%s"]}' % (slug, winner))
    next_block()
    print(f'  Submitted {slug} -> {winner} wins')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python testnet_rpc_create_and_submit.py <accounts.json>')
        print('Example: python testnet_rpc_create_and_submit.py accounts.json')
        sys.exit(1)

    accounts = load_accounts(sys.argv[1])
    ME = accounts[0].address.lower()
    print('accounts:', [a.address.lower() for a in accounts])
    bootstrap()

    print('Create & submit loop (Ctrl+C to stop)')
    while True:
        now = time.time()
        p_start = next_period_start(now)
        p_end = p_start + PERIOD
        slug = make_slug(p_start)
        next_slug = make_slug(p_end)

        print(f'\n[{time.strftime("%H:%M:%S")}] Current target period: {slug}')

        wait = p_start - time.time()
        if wait > 0:
            print(f'  Waiting {wait:.0f}s for period to start...')
            time.sleep(wait)

        target_price = get_btc_price()
        print(f'  Target BTC = ${target_price:,.2f} (recorded at period start)')

        print(f'  Creating next market: {next_slug}')
        create_market(next_slug)

        wait = p_end - time.time()
        if wait > 0:
            print(f'  Waiting {wait:.0f}s for period to end...')
            time.sleep(wait)

        current_price = get_btc_price()
        winner = 'yes' if current_price >= target_price else 'no'
        print(f'  Period ended. BTC=${current_price:,.2f} vs target=${target_price:,.2f} -> {winner}')
        submit_market(slug, winner)