import sys
import json

import setting
from local_rpc_init import transaction, next_block

if __name__ == '__main__':
    if len(sys.argv) < 7:
        print('Usage: python local_rpc_limit_order.py <account_index> <slug> <buy|sell> <yes|no> <price_usdc> <cost_usdc>')
        print('  price_usdc: price per share in USDC (0.01-0.99)')
        print('  cost_usdc: total USDC to spend/receive')
        print('Example: python local_rpc_limit_order.py 0 btc_5min_202609090120 buy yes 0.50 100')
        sys.exit(1)

    account_index = int(sys.argv[1])
    slug = sys.argv[2]
    buy_or_sell = sys.argv[3]
    yes_or_no = sys.argv[4]
    price_usdc = float(sys.argv[5])
    cost_usdc = float(sys.argv[6])

    assert buy_or_sell in ['buy', 'sell']
    assert yes_or_no in ['yes', 'no']
    assert 0.01 <= price_usdc <= 0.99, "price_usdc must be 0.01-0.99"

    shares = cost_usdc / price_usdc

    if buy_or_sell == 'buy':
        base_value = int(shares * 1e6)
        quote_value = -int(cost_usdc * 1e6)
    else:
        base_value = -int(shares * 1e6)
        quote_value = int(cost_usdc * 1e6)

    account = setting.accounts[account_index]
    print(f'Account: {account.address.lower()}')
    print(f'Slug: {slug}, {buy_or_sell} {yes_or_no} @ {price_usdc} USDC, cost {cost_usdc} USDC, shares {shares:.2f}')

    call = {"p": "zentest3", "f": "predict_limit_order", "a": [slug, base_value, yes_or_no, quote_value]}
    print(f'Call: {call}')

    tx_hash = transaction(account, json.dumps(call))
    print(f'Tx: {tx_hash}')

    print('=== next block ===')
    next_block()