import sys
import json
import requests

PROVIDER_HOST = 'http://127.0.0.1:8545'


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
        print('Usage: python local_chess_show.py <game_id>')
        sys.exit(1)
    game_id = sys.argv[1]
    prefix = 'chess-chess_state:%s' % game_id
    resp = requests.get('%s/api/get_latest_state' % PROVIDER_HOST, params={'prefix': prefix})
    try:
        data = resp.json()
        val = data.get('result')
        if isinstance(val, dict) and val.get('chess_board'):
            print_board(val.get('chess_board'), val.get('chess_turn'), val.get('chess_status'), val.get('chess_result'))
        else:
            print(json.dumps(data, indent=2))
    except Exception as e:
        print(e)
        print(resp.text)
