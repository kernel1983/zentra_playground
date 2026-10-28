"""Mint YES/NO shares for a chess game's prediction market.

Usage:
    python local_chess_mint.py <game_id> <quote_amount> [account_index]
"""

import json
import sys

import setting

from local_chess_init import transaction


def main():
    if len(sys.argv) not in (3, 4):
        raise SystemExit(
            'Usage: python local_chess_mint.py <game_id> <quote_amount> '
            '[account_index]'
        )

    game_id = str(sys.argv[1])
    quote_amount = int(sys.argv[2])
    if quote_amount <= 0:
        raise ValueError('quote amount must be positive')

    account_index = int(sys.argv[3]) if len(sys.argv) == 4 else 0
    if account_index < 0 or account_index >= len(setting.accounts):
        raise ValueError('account index is out of range')

    account = setting.accounts[account_index]
    call = json.dumps({
        'p': 'zentest3',
        'f': 'chess_predict_mint',
        'a': [game_id, quote_amount],
    })
    print('account:', account_index, account.address)
    print(call)
    print(transaction(account, call))


if __name__ == '__main__':
    main()
