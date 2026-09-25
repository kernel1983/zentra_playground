import sys
import json

import setting
from local_rpc_init import transaction, next_block

if __name__ == '__main__':
    if len(sys.argv) < 4:
        print('Usage: python local_rpc_mint.py <account_index> <slug> <usdc_amount>')
        print('Example: python local_rpc_mint.py 0 btc_5min_202609090120 100')
        sys.exit(1)

    account = setting.accounts[int(sys.argv[1])]
    slug = sys.argv[2]
    usdc_amount = float(sys.argv[3])

    print(f'Account: {account.address.lower()}')
    print(f'Mint {usdc_amount} USDC -> YES + NO for {slug}')

    call = {"p": "zentest3", "f": "predict_mint", "a": [slug, int(usdc_amount * 10**6)]}
    print(f'Call: {call}')

    tx_hash = transaction(account, json.dumps(call))
    print(f'Tx: {tx_hash}')

    print('=== next block ===')
    next_block()