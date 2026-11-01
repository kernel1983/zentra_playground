"""Cancel a chess game nobody has joined yet and reclaim the stake.

Usage:
    python local_chess_cancel_game.py <game_id> [account_index]

Only the creator (white) can cancel, and only while the game is still
waiting for an opponent.
"""

import json
import sys

import setting

from local_chess_init import transaction


def main():
    if len(sys.argv) not in (2, 3):
        raise SystemExit(
            'Usage: python local_chess_cancel_game.py <game_id> '
            '[account_index]'
        )

    game_id = str(sys.argv[1])
    account_index = int(sys.argv[2]) if len(sys.argv) == 3 else 0
    if account_index < 0 or account_index >= len(setting.accounts):
        raise ValueError('account index is out of range')

    account = setting.accounts[account_index]
    call = json.dumps({
        'p': 'zentest3',
        'f': 'chess_cancel_game',
        'a': [game_id],
    })
    print('account:', account_index, account.address)
    print(call)
    print(transaction(account, call))


if __name__ == '__main__':
    main()
