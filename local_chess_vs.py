"""Two AI engines (Stockfish) play an on-chain chess game against each other.

Usage:
    python local_chess_vs.py [stake] [tick]

Skill levels are chosen randomly (0..20) for each new game.
stake                      : escrow per player in raw quote units (default 0).
tick                       : quote token ticker (default USDC).

Both engines run locally; account 0 plays white, account 1 plays black.
The script creates the game, joins as black, then alternates moves, sleeping
5 seconds between plies, until the game ends.
"""

import json
import os
import sys
import time
import math
import random

import requests
import web3

import setting
from stockfish import Stockfish

PROVIDER_HOST = 'http://127.0.0.1:8545'
ZEN_ADDR = '0x00000000000000000000000000000000007A656e'
MOVE_SLEEP = 15
MOVE_TIME_MS = 300

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
        timeout=30,
    )
    response.raise_for_status()
    print('tx=%s %s %s' % (tx_hash, function, args))
    return tx_hash


def latest(prefix):
    response = requests.get(
        '%s/api/get_latest_state' % PROVIDER_HOST,
        params={'prefix': prefix},
        timeout=30,
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


def make_engine(skill):
    skill = max(0, min(20, int(skill)))
    sf = Stockfish(path=find_stockfish())
    try:
        sf.set_skill_level(skill)
    except Exception:
        pass
    try:
        sf.set_depth(12 if skill >= 15 else (8 if skill >= 8 else 4))
    except Exception:
        pass
    return sf




def init_if_needed():
    if latest('chess-chess_game_count') is not None:
        return
    print('No chess init found; initializing...')
    creator = setting.accounts[0]
    commit(creator, 'asset_create', ['USDC'])
    commit(creator, 'token_create', ['USDC', 'Mock USDC', 6])
    for account in setting.accounts:
        commit(account, 'token_mint_free', ['USDC', 1000 * 10 ** 6])
    commit(creator, 'chess_init', [['USDC']])
    print('Init done')




def win_chance(cp):
    """Approximate white win probability (%) from a centipawn score."""
    return 100.0 / (1.0 + math.exp(-0.00368208 * cp))


def eval_line(sf, board, turn):
    try:
        sf.set_fen_position(board_to_fen(board, turn))
        ev = sf.get_evaluation()
    except Exception:
        return ''
    if ev.get('type') == 'cp':
        cp = ev.get('value', 0)
        return 'eval: %+.2f  white win chance: %.1f%%' % (cp / 100.0, win_chance(cp))
    if ev.get('type') == 'mate':
        return 'mate in %d' % ev.get('value', 0)
    return str(ev)

def main():
    stake = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    tick = sys.argv[2] if len(sys.argv) > 2 else 'USDC'

    white = setting.accounts[0]
    black = setting.accounts[1]

    init_if_needed()

    while True:
        white_skill = random.randint(0, 20)
        black_skill = random.randint(0, 20)

        next_game_id = latest('chess-chess_game_count') or 1
        game_id = str(next_game_id)
        print('Creating game %s: white skill=%d black skill=%d stake=%s %s' % (
            game_id, white_skill, black_skill, stake, tick))

        commit(white, 'chess_create_game', [tick, stake])
        state = game_state(game_id)
        assert state['chess_status'] == 'chess_waiting_for_opponent'

        commit(black, 'chess_join_game', [game_id])
        state = game_state(game_id)
        assert state['chess_status'] == 'chess_active'

        sf_white = make_engine(white_skill)
        sf_black = make_engine(black_skill)
        sf_eval = make_engine(20)

        last_seen = None
        while True:
            state = game_state(game_id)
            status = state.get('chess_status')
            marker = (state.get('chess_move_count'), state.get('chess_turn'), status)
            if marker != last_seen:
                last_seen = marker
                print_board(state['chess_board'], state.get('chess_turn'), status, state.get('chess_result'))
                line = eval_line(sf_eval, state['chess_board'], state.get('chess_turn') or 'w')
                if line:
                    print(line)

            if status != 'chess_active':
                print('game over: %s (%s)' % (status, state.get('chess_result')))
                if state.get('chess_winner'):
                    print('winner: %s' % state.get('chess_winner'))
                break

            turn = state.get('chess_turn')
            if turn == 'w':
                account = white
                sf = sf_white
                label = 'white'
                skill = white_skill
            else:
                account = black
                sf = sf_black
                label = 'black'
                skill = black_skill

            fen = board_to_fen(state['chess_board'], turn)
            sf.set_fen_position(fen)
            move = sf.get_best_move_time(MOVE_TIME_MS)
            if not move:
                # Fall back to first legal move if engine returns nothing.
                move = sf.get_best_move()
            assert move, 'engine returned no move for %s' % label
            print('%s (skill %d) plays: %s' % (label, skill, move))

            commit(account, 'chess_make_move', [game_id, move])
            time.sleep(MOVE_SLEEP)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, RuntimeError, requests.RequestException, ValueError) as error:
        print('FAIL:', error, file=sys.stderr)
        sys.exit(1)
