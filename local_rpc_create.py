import sys
import datetime
import requests

from local_rpc_init import transaction, next_block
import setting

PROVIDER_HOST = 'http://127.0.0.1:8545'
ME = setting.accounts[0].address.lower()

def state(key):
    resp = requests.get(f'{PROVIDER_HOST}/api/get_latest_state?prefix={key}')
    return resp.json().get('result')

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

def make_slug(dt):
    return 'btc_5min_%04d%02d%02d%02d%02d' % (
        dt.year, dt.month, dt.day, dt.hour, dt.minute)

if __name__ == '__main__':
    accounts = setting.accounts
    ME = accounts[0].address.lower()
    print('accounts:', [a.address.lower() for a in accounts])
    bootstrap()

    if len(sys.argv) >= 2:
        slug = sys.argv[1]
    else:
        slug = make_slug(datetime.datetime.utcnow())
        print(f'No slug given, using current UTC time: {slug}')
    create_market(slug)