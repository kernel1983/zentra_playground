"""Mint free USDC to a local test account.

Usage:
    python local_token_mint.py [account_index] [usdc_amount]
"""

import json
import sys

import setting

from local_predict_init import transaction


def main():
    account_index = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    usdc_amount = float(sys.argv[2]) if len(sys.argv) > 2 else 1000
    if account_index < 0 or account_index >= len(setting.accounts):
        raise ValueError('account index is out of range')
    if usdc_amount <= 0:
        raise ValueError('USDC amount must be positive')

    account = setting.accounts[account_index]
    raw_amount = int(usdc_amount * 10**6)
    call = json.dumps({
        'p': 'zentest3',
        'f': 'token_mint_free',
        'a': ['USDC', raw_amount],
    })
    print('account:', account_index, account.address)
    print('mint:', usdc_amount, 'USDC')
    print(call)
    print(transaction(account, call))


if __name__ == '__main__':
    main()
