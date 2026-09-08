import sys
import requests

import setting
import web3

PROVIDER_HOST = 'http://127.0.0.1:8545'

def get_balance(account_index, slug='btc_5min'):
    account = setting.accounts[account_index]
    addr = account.address.lower()

    checks = {
        'USDC': ('base-USDC-balance', 6),
        f'YES ({slug})': (f'predict-{slug}_yes_balance', 6),
        f'NO ({slug})': (f'predict-{slug}_no_balance', 6),
    }
    balances = {}

    for label, (prefix, decimals) in checks.items():
        resp = requests.get(f'{PROVIDER_HOST}/api/get_latest_state?prefix={prefix}:{addr}')
        data = resp.json()
        balance = data.get('result', '0')
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
    if len(sys.argv) < 2:
        print('Usage: python test_get_balance.py <account_index>')
        print('Example: python test_get_balance.py 0')
        sys.exit(1)

    account_index = int(sys.argv[1])
    get_balance(account_index)