import sys
import requests

from testnet_rpc_init import state

INDEXER_URL = 'https://testnet3.zentra.dev'  # Base Sepolia indexer (state/events)


def get_balance(addr, slug):
    checks = {
        'USDC': ('USDC-balance', 6),
        f'YES ({slug})': (f'predict-{slug}_yes_balance', 6),
        f'NO ({slug})': (f'predict-{slug}_no_balance', 6),
    }
    balances = {}
    for label, (prefix, decimals) in checks.items():
        value = state(f'{prefix}:{addr}')
        if isinstance(value, list):
            value = value[0] if value else 0
        balances[label] = int(value or 0) / 10 ** decimals
    return balances


def holders(slug, tick):
    addrs = []
    a = state(f'predict-{slug}_{tick}_balance_new')
    seen = set()
    while a and a not in seen:
        seen.add(a)
        addrs.append(a)
        balance = state(f'predict-{slug}_{tick}_balance:{a}')
        if not isinstance(balance, list) or len(balance) < 2:
            break
        a = balance[1]
    return addrs


if __name__ == '__main__':
    slug = sys.argv[1] if len(sys.argv) > 1 else 'btc_5min'

    addresses = []
    for tick in ['yes', 'no']:
        for a in holders(slug, tick):
            if a not in addresses:
                addresses.append(a)

    total_usdc = 0.0
    total_yes = 0.0
    total_no = 0.0

    print(f'=== balances: {slug} ({len(addresses)} holders) ===')
    for addr in addresses:
        b = get_balance(addr, slug)
        usdc = b['USDC']
        yes = b[f'YES ({slug})']
        no = b[f'NO ({slug})']
        total_usdc += usdc
        total_yes += yes
        total_no += no
        if usdc or yes or no:
            print(f'{addr}')
            print(f'  USDC: {usdc}')
            print(f'  YES : {yes}')
            print(f'  NO  : {no}')

    print('---')
    print(f'Total USDC: {total_usdc}')
    print(f'Total YES : {total_yes}')
    print(f'Total NO  : {total_no}')