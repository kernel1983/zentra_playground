import sys
import requests

import setting

PROVIDER_HOST = 'http://127.0.0.1:8545'


def get_balance(addr, slug):
    checks = {
        'USDC': ('base-USDC-balance', 6),
        f'YES ({slug})': (f'predict-{slug}_yes_balance', 6),
        f'NO ({slug})': (f'predict-{slug}_no_balance', 6),
    }
    balances = {}
    for label, (prefix, decimals) in checks.items():
        resp = requests.get(f'{PROVIDER_HOST}/api/get_latest_state?prefix={prefix}:{addr}')
        value = resp.json().get('result', '0')
        if isinstance(value, list):
            value = value[0] if value else '0'
        balances[label] = int(value or 0) / 10 ** decimals
    return balances


if __name__ == '__main__':
    args = sys.argv[1:]
    slug = 'btc_5min'
    account_index = None

    i = 0
    while i < len(args):
        if args[i] == '--slug' and i + 1 < len(args):
            slug = args[i + 1]
            i += 2
        else:
            account_index = int(args[i])
            i += 1

    accounts = setting.accounts
    total_usdc = 0.0
    total_yes = 0.0
    total_no = 0.0

    print(f'=== balances: {slug} ===')
    for idx, account in enumerate(accounts):
        if account_index is not None and idx != account_index:
            continue
        addr = account.address.lower()
        b = get_balance(addr, slug)
        usdc = b['USDC']
        yes = b[f'YES ({slug})']
        no = b[f'NO ({slug})']
        total_usdc += usdc
        total_yes += yes
        total_no += no
        if usdc or yes or no:
            print(f'Account {idx}: {addr}')
            print(f'  USDC: {usdc}')
            print(f'  YES : {yes}')
            print(f'  NO  : {no}')

    print('---')
    print(f'Total USDC: {total_usdc}')
    print(f'Total YES : {total_yes}')
    print(f'Total NO  : {total_no}')
