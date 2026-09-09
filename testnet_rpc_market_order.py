import sys
import json

from testnet_rpc_init import transaction, next_block, load_accounts

if __name__ == '__main__':
    if len(sys.argv) < 7:
        print('Usage: python testnet_rpc_market_order.py <accounts.json> <slug> <buy|sell> <yes|no> <cents> <cost>')
        print('  cents: target price per share (1-99)')
        print('  cost: total USDC to spend/receive')
        print('Example: python testnet_rpc_market_order.py accounts.json btc_5min_202609090120 buy yes 50 100')
        sys.exit(1)

    accounts = load_accounts(sys.argv[1])
    slug = sys.argv[2]
    buy_or_sell = sys.argv[3]
    yes_or_no = sys.argv[4]
    cents = int(sys.argv[5])
    cost = float(sys.argv[6])

    assert buy_or_sell in ['buy', 'sell']
    assert yes_or_no in ['yes', 'no']
    assert 1 <= cents <= 99, "cents must be 1-99"

    shares = cost * 100 / cents

    if buy_or_sell == 'buy':
        base_value = int(shares * 1e18)
        quote_value = None
    else:
        base_value = None
        quote_value = int(cost * 1e6)

    print(f'Account: {accounts[0].address.lower()}')
    print(f'Slug: {slug}, {buy_or_sell} {yes_or_no} @ {cents} cents, cost {cost} USDC, shares {shares:.2f}')

    call = {"p": "zentest3", "f": "predict_market_order", "a": [slug, base_value, yes_or_no, quote_value]}
    print(f'Call: {call}')

    tx_hash = transaction(accounts[0], json.dumps(call))
    print(f'Tx: {tx_hash}')

    print('=== next block ===')
    next_block()