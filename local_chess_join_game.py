import sys
import json
import requests

import web3

import setting

PROVIDER_HOST = 'http://127.0.0.1:8545'

ZEN_ADDR = '0x00000000000000000000000000000000007A656e'

w3 = web3.Web3(web3.Web3.HTTPProvider(PROVIDER_HOST))


def transaction(account, call):
    nonce = w3.eth.get_transaction_count(account.address)
    tx = {
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
    signed = w3.eth.account.sign_transaction(tx, account.key)
    return w3.eth.send_raw_transaction(signed.raw_transaction).hex()


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
    if len(sys.argv) < 2:
        print('Usage: python local_chess_join_game.py <game_id> [account_index]')
        print('Example: python local_chess_join_game.py 1 1')
        sys.exit(1)

    game_id = sys.argv[1]
    account_index = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    call = json.dumps({'p': 'zentest3', 'f': 'chess_join_game', 'a': [game_id]})
    print(call)
    tx_hash = transaction(setting.accounts[account_index], call)
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
