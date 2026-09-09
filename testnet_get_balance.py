import sys
import json
import requests

from testnet_rpc_init import load_accounts

INDEXER_URL = 'https://testnet3.zentra.dev'  # Base Sepolia indexer (state/events)


def _normalize_addr(addr):
    addr = str(addr).lower()
    if not addr.startswith('0x'):
        addr = '0x' + addr
    return addr


def resolve_account(arg):
    if arg.startswith('0x'):
        return {'source': 'address', 'addr': _normalize_addr(arg)}
    with open(arg) as f:
        data = json.load(f)
    if isinstance(data, dict) and ('crypto' in data or 'Crypto' in data):
        addr = data.get('address')
        if addr:
            return {'source': arg, 'addr': _normalize_addr(addr)}
    account = load_accounts(arg)[0]
    return {'source': arg, 'addr': account.address.lower()}


def get_balance(addr, slug='btc_5min'):
    checks = {
        'USDC': ('USDC-balance', 6),
        f'YES ({slug})': (f'predict-{slug}_yes_balance', 6),
        f'NO ({slug})': (f'predict-{slug}_no_balance', 6),
    }
    balances = {}

    for label, (prefix, decimals) in checks.items():
        resp = requests.get(f'{INDEXER_URL}/api/get_latest_state?prefix=base-{prefix}:{addr}')
        data = resp.json()
        balance = data.get('result', '0')
        if isinstance(balance, list):
            balance = balance[0] if balance else '0'
        if balance and balance != '0':
            formatted = int(balance) / (10 ** decimals)
            balances[label] = formatted
        else:
            balances[label] = 0
    return balances


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python testnet_get_balance.py <address|accounts.json> [--slug <slug>]')
        print('Example: python testnet_get_balance.py 0x04cf...e316e59b3')
        print('Example: python testnet_get_balance.py m3.json --slug btc_5min')
        sys.exit(1)

    slug = 'btc_5min'
    if '--slug' in sys.argv:
        slug = sys.argv[sys.argv.index('--slug') + 1]

    acct = resolve_account(sys.argv[1])
    addr = acct['addr']
    balances = get_balance(addr, slug)

    print(f'Account ({acct["source"]}): {addr}')
    for label, balance in balances.items():
        print(f'  {label}: {balance}')