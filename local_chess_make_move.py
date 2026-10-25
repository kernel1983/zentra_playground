import sys
import hashlib
import json
import requests

import web3

import setting

PROVIDER_HOST = 'http://127.0.0.1:8545'

w3 = web3.Web3(web3.Web3.HTTPProvider(PROVIDER_HOST))

ZEN_ADDR = '0x00000000000000000000000000000000007A656e'


def transaction(account, call):
    nonce = w3.eth.get_transaction_count(account.address)
    transaction = {
        'from': account.address,
        'to': ZEN_ADDR,
        'value': 0,
        'nonce': nonce,
        'data': call.encode('utf8'),
        'gas': 210000,
        'maxFeePerGas': 1000000000,
        'maxPriorityFeePerGas': 0,
        'chainId': setting.CHAIN_ID,
    }

    signed = w3.eth.account.sign_transaction(transaction, account.key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return tx_hash.hex()


def next_block():
    resp = requests.post(PROVIDER_HOST, json={'jsonrpc': '2.0', 'method': 'zentra_nextBlock', 'id': 1})
    return resp.json()


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


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: python local_chess_make_move.py <game_id> <move> [account_index]')
        print('Example: python local_chess_make_move.py chess_game_1 g1f3 0')
        sys.exit(1)
    game_id = sys.argv[1]
    move = sys.argv[2].lower()
    acc_idx = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    call = '{"p": "zentest3", "f": "chess_make_move", "a": ["%s", "%s"]}' % (game_id, move)
    print(call)
    tx_hash = transaction(setting.accounts[acc_idx], call)
    print(tx_hash)
    res = next_block()
    print('next_block:', json.dumps(res))
    try:
        prefix = 'chess-chess_state:%s' % game_id
        resp = requests.get('%s/api/get_latest_state' % PROVIDER_HOST, params={'prefix': prefix})
        data = resp.json()
        val = data.get('result')
        if isinstance(val, dict) and val.get('chess_board'):
            print_board(val.get('chess_board'), val.get('chess_turn'), val.get('chess_status'), val.get('chess_result'))
        else:
            print(json.dumps(data, indent=2))
    except Exception as e:
        print('fetch_err', e)
