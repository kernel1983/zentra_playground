"""Claim a timeout win in an active chess game.

Usage:
    python local_chess_claim_timeout.py <game_id> [account_index]
"""

import json
import sys

import requests

import setting

from local_chess_init import transaction

PROVIDER_HOST = 'http://127.0.0.1:8545'


def main():
    if len(sys.argv) not in (2, 3):
        raise SystemExit(
            'Usage: python local_chess_claim_timeout.py <game_id> '
            '[account_index]'
        )

    game_id = str(sys.argv[1])
    account_index = int(sys.argv[2]) if len(sys.argv) == 3 else 0
    if account_index < 0 or account_index >= len(setting.accounts):
        raise ValueError('account index is out of range')

    account = setting.accounts[account_index]
    call = json.dumps({
        'p': 'zentest3',
        'f': 'chess_claim_timeout',
        'a': [game_id],
    })
    print('account:', account_index, account.address)
    print(call)
    print(transaction(account, call))

    try:
        prefix = 'chess-chess_state:%s' % game_id
        resp = requests.get('%s/api/get_latest_state' % PROVIDER_HOST, params={'prefix': prefix}, timeout=30)
        data = resp.json()
        val = data.get('result')
        if isinstance(val, dict):
            print('status:', val.get('chess_status'))
            print('result:', val.get('chess_result'))
            print('winner:', val.get('chess_winner'))
    except Exception as e:
        print('fetch_err', e)


if __name__ == '__main__':
    main()
