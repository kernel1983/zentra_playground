import sys
import time
import datetime
import requests

from local_rpc_init import transaction, next_block
import setting

PROVIDER_HOST = 'http://127.0.0.1:8545'
ME = setting.accounts[0].address.lower()
PERIOD = 300  # 5 minutes

def state(key):
    resp = requests.get(f'{PROVIDER_HOST}/api/get_latest_state?prefix={key}')
    return resp.json().get('result')

def get_btc_price():
    resp = requests.post('https://api.hyperliquid.xyz/info',
                         json={'type': 'allMids'})
    return float(resp.json()['BTC'])

def make_slug(period_start):
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
        transaction(setting.accounts[0], '{"p":"zentest3","f":"committee_init","a":[]}')
        next_block()
    if state('predict-manager') is None:
        transaction(setting.accounts[0],
                    '{"p":"zentest3","f":"predict_vote_manager","a":["%s"]}' % ME)
        next_block()
    qt = state('predict-quote_tokens') or []
    if 'USDC' not in qt:
        transaction(setting.accounts[0],
                    '{"p":"zentest3","f":"predict_set_quote_token","a":[["USDC"]]}')
        next_block()

def create_market(slug):
    if state(f'predict-{slug}_quote_token') is not None:
        print(f'  Market already exists: {slug}')
        return
    transaction(setting.accounts[0],
                '{"p":"zentest3","f":"predict_create","a":["%s","USDC"]}' % slug)
    next_block()
    print(f'  Created market: {slug}')

def submit_market(slug, winner):
    transaction(setting.accounts[0],
                '{"p":"zentest3","f":"predict_submit","a":["%s","%s"]}' % (slug, winner))
    next_block()
    print(f'  Submitted {slug} -> {winner} wins')

if __name__ == '__main__':
    accounts = setting.accounts
    ME = accounts[0].address.lower()
    print('accounts:', [a.address.lower() for a in accounts])
    bootstrap()

    print('Create & submit loop (Ctrl+C to stop)')

    now = time.time()
    p_start = (int(now) // PERIOD) * PERIOD
    slug = make_slug(p_start)
    print(f'[{time.strftime("%H:%M:%S")}] Ensuring current market: {slug}')
    create_market(slug)

    p_next = p_start + PERIOD
    next_slug = make_slug(p_next)
    print(f'[{time.strftime("%H:%M:%S")}] Creating next market: {next_slug}')
    create_market(next_slug)

    target_price = get_btc_price()
    print(f'[{time.strftime("%H:%M:%S")}] Current period target BTC = ${target_price:,.2f}')

    while True:
        now = time.time()

        if now >= p_start + PERIOD:
            p_end = p_start + PERIOD
            current_price = get_btc_price()
            winner = 'yes' if current_price >= target_price else 'no'
            print(f'[{time.strftime("%H:%M:%S")}] Period {slug} ended. BTC=${current_price:,.2f} vs target=${target_price:,.2f} -> {winner}')
            submit_market(slug, winner)

            p_start = p_end
            slug = next_slug
            p_next = p_start + PERIOD
            next_slug = make_slug(p_next)
            print(f'[{time.strftime("%H:%M:%S")}] Transitioning to market: {slug}')
            target_price = get_btc_price()
            print(f'[{time.strftime("%H:%M:%S")}] Period {slug} started. Target BTC = ${target_price:,.2f}')

        print(f'[{time.strftime("%H:%M:%S")}] Creating next market: {next_slug}')
        create_market(next_slug)
        time.sleep(5)
