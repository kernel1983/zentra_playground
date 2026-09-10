import sys
import time
import requests

import web3

from testnet_rpc_init import transaction, next_block, load_accounts, state

INDEXER_URL = 'https://testnet3.zentra.dev'  # Base Sepolia indexer (state/events)
PERIOD = 300  # 5 minutes


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
    print(state('committee-members'))
    if state('committee-members') is None:
        transaction(accounts[0], '{"p":"zentest3","f":"committee_init","a":[]}')
        next_block()

    if state('predict-manager') is None:
        transaction(accounts[0],
                    '{"p":"zentest3","f":"predict_vote_manager","a":["%s"]}' % ME)
        next_block()

    qt = state('predict-quote_tokens') or []
    if 'USDC' not in qt:
        transaction(accounts[0],
                    '{"p":"zentest3","f":"predict_set_quote_token","a":[["USDC"]]}')
        next_block()

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
    if len(sys.argv) < 3:
        print('Usage: python testnet_rpc_create.py <accounts.json> <slug>')
        print('Example: python testnet_rpc_create.py accounts.json btc_5min_202609090120')
        sys.exit(1)

    accounts = load_accounts(sys.argv[1])
    print('accounts:', [a.address.lower() for a in accounts])
    ME = accounts[0].address.lower()
    bootstrap()

    slug = sys.argv[2]
    create_market(slug)