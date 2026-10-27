"""Play an on-chain chess game as test account 1 using Stockfish.

Waits for the game to become active, joins as black if the game is still
open, then polls the chain and plays the Stockfish best move whenever it
is account 1's turn, until the game ends.
"""

import json
import os
import sys
import time

import requests
import web3

import setting
from stockfish import Stockfish

PROVIDER_HOST = 'http://127.0.0.1:8545'
ZEN_ADDR = '0x00000000000000000000000000000000007A656e'
ACCOUNT_INDEX = 1
POLL_SECONDS = 2
MOVE_TIME_MS = 500

w3 = web3.Web3(web3.Web3.HTTPProvider(PROVIDER_HOST))


def transaction(account, call):
    nonce = w3.eth.get_transaction_count(account.address)
    tx = {
        'from': account.address,
        'to': ZEN_ADDR,
        'value': 0,
        'nonce': nonce,
        'data': json.dumps(call).encode('utf8'),
        'gas': 210000,
        'maxFeePerGas': 1000000000,
        'maxPriorityFeePerGas': 0,
        'chainId': setting.CHAIN_ID,
    }
    signed = w3.eth.account.sign_transaction(tx, account.key)
    return w3.eth.send_raw_transaction(signed.raw_transaction).hex()


def commit(account, function, args):
    call = {'p': 'zentest3', 'f': function, 'a': args}
    tx_hash = transaction(account, call)
    response = requests.post(
        PROVIDER_HOST,
        json={'jsonrpc': '2.0', 'method': 'zentra_nextBlock', 'id': 1},
        timeout=5,
    )
    response.raise_for_status()
    print('tx=%s %s %s' % (tx_hash, function, args))


def latest(prefix):
    response = requests.get(
        '%s/api/get_latest_state' % PROVIDER_HOST,
        params={'prefix': prefix},
        timeout=5,
    )
    response.raise_for_status()
    return response.json().get('result')


def game_state(game_id):
    state = latest('chess-chess_state:%s' % game_id)
    assert isinstance(state, dict), 'missing chess state for game %s' % game_id
    assert isinstance(state.get('chess_board'), list), 'missing chess board'
    return state


def print_board(board, turn=None, status=None, result=None):
    print('')
    print('  +---+---+---+---+---+---+---+---+')
    for r in range(8):
        row_str = '  |'
        for c in range(8):
            p = board[r][c]
            if p == '.':
                row_str += '   |'
            else:
                row_str += ' %s |' % p
        print('%s %d' % (row_str, 8 - r))
        print('  +---+---+---+---+---+---+---+---+')
    print('    a   b   c   d   e   f   g   h')
    if turn is not None:
        print('  turn: %s' % turn)
    if status is not None:
        print('  status: %s' % status)
    if result is not None:
        print('  result: %s' % result)
    print('')


def board_to_fen(board, turn):
    rows = []
    for r in range(8):
        row = ''
        empty = 0
        for c in range(8):
            p = board[r][c]
            if p == '.':
                empty += 1
            else:
                if empty:
                    row += str(empty)
                    empty = 0
                row += p
        if empty:
            row += str(empty)
        rows.append(row)
    return '%s %s - - 0 1' % ('/'.join(rows), turn)


def find_stockfish():
    candidates = [
        os.path.expanduser('~/bin/stockfish'),
        '/usr/local/bin/stockfish',
        '/usr/games/stockfish',
        '/usr/bin/stockfish',
    ]
    for path in candidates:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    raise RuntimeError('stockfish binary not found in %s' % candidates)


def main():
    if len(sys.argv) < 2:
        print('Usage: python local_chess_fish.py <game_id>')
        sys.exit(1)
    game_id = str(sys.argv[1])

    me = setting.accounts[ACCOUNT_INDEX]
    print('account: index %d %s' % (ACCOUNT_INDEX, me.address))

    sf = Stockfish(path=find_stockfish())

    my_color = None
    last_seen = None
    while True:
        state = game_state(game_id)
        status = state.get('chess_status')
        white = (state.get('chess_white') or '').lower()
        black = (state.get('chess_black') or '').lower()
        if my_color is None:
            if white == me.address.lower():
                my_color = 'w'
            elif black == me.address.lower():
                my_color = 'b'
            elif status == 'chess_waiting_for_opponent' and not black:
                print('game %s is open, joining as black...' % game_id)
                commit(me, 'chess_join_game', [game_id])
                continue
            else:
                raise RuntimeError('account %s is not a player of game %s' % (me.address, game_id))
            print('playing %s (%s)' % ('white' if my_color == 'w' else 'black', game_id))

        marker = (state.get('chess_move_count'), state.get('chess_turn'), status)
        if marker != last_seen:
            last_seen = marker
            print_board(state['chess_board'], state.get('chess_turn'), status, state.get('chess_result'))

        if status != 'chess_active':
            print('game over: %s (%s)' % (status, state.get('chess_result')))
            break

        if state.get('chess_turn') != my_color:
            time.sleep(POLL_SECONDS)
            continue

        fen = board_to_fen(state['chess_board'], my_color)
        sf.set_fen_position(fen)
        move = sf.get_best_move_time(MOVE_TIME_MS)
        assert move, 'stockfish returned no move'
        print('fish move (%s): %s' % ('white' if my_color == 'w' else 'black', move))
        commit(me, 'chess_make_move', [game_id, move])


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, RuntimeError, requests.RequestException) as error:
        print('FAIL:', error, file=sys.stderr)
        sys.exit(1)
