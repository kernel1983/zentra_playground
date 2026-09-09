import sys
import json

from testnet_rpc_init import transaction, next_block, load_accounts

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: python testnet_rpc_mint.py <accounts.json> <slug> <usdc_amount>')
        print('Example: python testnet_rpc_mint.py accounts.json btc_5min_202609090120 100')
        sys.exit(1)

    accounts = load_accounts(sys.argv[1])
    slug = sys.argv[2]
    usdc_amount = float(sys.argv[3])

    print(f'Account: {accounts[0].address.lower()}')
    print(f'Mint {usdc_amount} USDC -> YES + NO for {slug}')

    call = {"p": "zentest3", "f": "predict_mint", "a": [slug, int(usdc_amount * 10**6)]}
    print(f'Call: {call}')

    tx_hash = transaction(accounts[0], json.dumps(call))
    print(f'Tx: {tx_hash}')

    print('=== next block ===')
    next_block()
