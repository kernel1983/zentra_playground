"""Exercise the complete on-chain chess lifecycle with Fool's Mate.

Runs the shortest possible checkmate (four plies):
    1. f3 e5 2. g4 Qh4#

The script creates an open game with test account 0 staking USDC, has test
account 1 join as black (staking the same amount), performs every move, and
validates the persisted state, stake escrow pot and history after each
transition.  The stake can be overridden with the first argument.
"""

import json
import sys

import requests
import web3

import setting

PROVIDER_HOST = 'http://127.0.0.1:8545'
ZEN_ADDR = '0x00000000000000000000000000000000007A656e'
QUOTE_TICK = 'USDC'
DEFAULT_STAKE = 1000000
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
    print('%-18s tx=%s' % (function, tx_hash))


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


def quote_balance(quote_tick, account):
    balance = latest('%s-balance:%s' % (quote_tick, account))
    if balance in (None, '', 'None'):
        return 0
    return int(balance)


def stake_pot_balance(quote_tick, game_id):
    balance = latest('%s-balance:pot_chess_stake:%s' % (quote_tick, game_id))
    if balance in (None, '', 'None'):
        return 0
    return int(balance)


def assert_state(state, turn, status, result=None, move_count=0):
    assert state['chess_turn'] == turn, (state['chess_turn'], turn)
    assert state['chess_status'] == status, (state['chess_status'], status)
    assert state['chess_result'] == result, (state['chess_result'], result)
    assert state['chess_move_count'] == move_count, (state['chess_move_count'], move_count)


def main():
    stake = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_STAKE
    assert stake >= 0, 'stake must be non-negative'
    white = setting.accounts[0]
    black = setting.accounts[1]

    # chess_game_count is the ID assigned to the next game. It is unset on a
    # fresh chain, where chess_create_game defaults it to 1.
    next_game_id = latest('chess-chess_game_count') or 1
    game_id = str(next_game_id)
    print(
        'Creating chess game %s: white=test account 0, black=test account 1, '
        'stake=%s %s' % (game_id, stake, QUOTE_TICK)
    )

    white_bal_before = quote_balance(QUOTE_TICK, white.address)
    commit(white, 'chess_create_game', [QUOTE_TICK, stake])
    state = game_state(game_id)
    assert_state(state, 'w', 'chess_waiting_for_opponent')
    assert state['chess_white'].lower() == white.address.lower()
    assert state['chess_black'] is None
    assert state['chess_stake'] == stake, (state['chess_stake'], stake)
    assert stake_pot_balance(QUOTE_TICK, game_id) == stake
    assert quote_balance(QUOTE_TICK, white.address) == white_bal_before - stake
    if stake > 0:
        print('  stake escrowed from white: pot=%s' % stake)

    black_bal_before = quote_balance(QUOTE_TICK, black.address)
    commit(black, 'chess_join_game', [game_id])
    state = game_state(game_id)
    assert_state(state, 'w', 'chess_active')
    assert state['chess_black'].lower() == black.address.lower()
    assert stake_pot_balance(QUOTE_TICK, game_id) == 2 * stake
    assert quote_balance(QUOTE_TICK, black.address) == black_bal_before - stake
    if stake > 0:
        print('  matching stake escrowed from black: pot=%s' % (2 * stake))

    # Fool's Mate: the shortest possible checkmate in chess.
    moves = [
        (white, 'f2f3', 'b', 'chess_active', None, 1),
        (black, 'e7e5', 'w', 'chess_active', None, 2),
        (white, 'g2g4', 'b', 'chess_active', None, 3),
        (black, 'd8h4', 'w', 'chess_checkmate', 'chess_black_wins', 4),
    ]
    for account, move, turn, status, result, move_count in moves:
        commit(account, 'chess_make_move', [game_id, move])
        state = game_state(game_id)
        assert_state(state, turn, status, result, move_count)
        print('  %s -> %s' % (move, status))

    assert state['chess_winner'].lower() == black.address.lower()
    # The winner sweeps both stakes out of the escrow pot.
    assert stake_pot_balance(QUOTE_TICK, game_id) == 0
    assert quote_balance(QUOTE_TICK, black.address) == black_bal_before + stake
    if stake > 0:
        print('  black swept the stake pot: pot=0, black=+%s' % (2 * stake))
    response = requests.get(
        '%s/api/query_recent_state' % PROVIDER_HOST,
        params={'prefix': 'chess-chess_state:%s' % game_id},
        timeout=5,
    )
    response.raise_for_status()
    history = response.json().get('result', [])
    assert len(history) == 6, 'expected 6 state snapshots, got %s' % len(history)
    assert [entry['block_number'] for entry in history] == sorted(entry['block_number'] for entry in history)
    print('PASS: game %s ended in Fool\'s Mate; %s state snapshots verified.' % (game_id, len(history)))


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, requests.RequestException, ValueError) as error:
        print('FAIL:', error, file=sys.stderr)
        sys.exit(1)
