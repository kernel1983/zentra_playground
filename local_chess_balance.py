import sys
import requests

import setting
import web3

PROVIDER_HOST = 'http://127.0.0.1:8545'

def get_balance(account_index, game_id, quote_tick='USDC'):
    account = setting.accounts[account_index]
    addr = account.address.lower()

    checks = {
        f'{quote_tick}': (f'base-{quote_tick}-balance', 6),
        f'YES (game {game_id})': (f'chess_predict-{game_id}_yes_balance', 6),
        f'NO (game {game_id})': (f'chess_predict-{game_id}_no_balance', 6),
    }
    balances = {}

    for label, (prefix, decimals) in checks.items():
        resp = requests.get(f'{PROVIDER_HOST}/api/get_latest_state?prefix={prefix}:{addr}')
        data = resp.json()
        balance = data.get('result') or '0'
        if isinstance(balance, list):
            balance = balance[0] if balance else '0'
        if balance and balance != '0':
            formatted = int(balance) / (10 ** decimals)
            balances[label] = formatted
        else:
            balances[label] = 0

    print(f'Account {account_index}: {addr}')
    for label, balance in balances.items():
        print(f'  {label}: {balance}')

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: python local_chess_balance.py <account_index> <game_id> [quote_tick]')
        print('Example: python local_chess_balance.py 1 1')
        sys.exit(1)

    account_index = int(sys.argv[1])
    game_id = int(sys.argv[2])
    get_balance(account_index, game_id)
