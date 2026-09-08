import sys
import time
import datetime
import requests

PROVIDER_HOST = 'http://127.0.0.1:8545'

PERIOD = 300


def current_slug():
    now = int(time.time())
    p_start = (now // PERIOD) * PERIOD
    dt = datetime.datetime.utcfromtimestamp(p_start)
    return 'btc_5min_%04d%02d%02d%02d%02d' % (
        dt.year, dt.month, dt.day, dt.hour, dt.minute)


def get_state(key):
    resp = requests.get(f'{PROVIDER_HOST}/api/get_latest_state?prefix={key}')
    data = resp.json()
    return data.get('result')


def walk_linked(prefix):
    start = get_state(f'{prefix}_start')
    if start is None:
        return []
    seq = []
    oid = int(start)
    seen = set()
    while oid is not None and oid not in seen:
        seen.add(oid)
        order = get_state(f'{prefix}:{oid}')
        if not isinstance(order, list) or len(order) < 6:
            break
        seq.append((oid, order))
        oid = order[5]
    return seq


def list_predict_orders(slug):
    print(f'=== predict orders: {slug} (linked list, sorted) ===')
    total = 0
    for token in ['yes', 'no']:
        for side in ['sell', 'buy']:
            prefix = f'predict-{slug}_{token}_{side}'
            seq = walk_linked(prefix)
            if not seq:
                continue
            if side == 'buy':
                seq = seq[::-1]
            print(f'  --- {token} {side} ---')
            for oid, order in seq:
                total += 1
                maker = order[0]
                base_remain = abs(order[1])
                quote_remain = abs(order[2])
                price_k = order[3]
                print(
                    f'  #{oid:<4} '
                    f'price={price_k / 10**16:6.2f}¢  '
                    f'tokens={base_remain / 10**6:10.2f}  '
                    f'quote={quote_remain / 10**6:10.2f}  '
                    f'{maker[:10]}'
                )
    if total == 0:
        print('  (no orders)')
    return total


def list_spot_orders(base_tick, quote_tick):
    pair = f'{base_tick}_{quote_tick}'
    print(f'=== spot orders: {pair} (linked list, sorted) ===')
    total = 0
    for side in ['sell', 'buy']:
        prefix = f'trade-{pair}_{side}'
        seq = walk_linked(prefix)
        if not seq:
            continue
        if side == 'buy':
            seq = seq[::-1]
        print(f'  --- {side} ---')
        for oid, order in seq:
            total += 1
            maker = order[0]
            base_remain = abs(order[1])
            quote_remain = abs(order[2])
            price_k = order[3]
            print(
                f'  #{oid:<4} '
                f'price={price_k / 10**16:10.2f}  '
                f'base={base_remain / 10**18:12.6f}  '
                f'quote={quote_remain / 10**6:10.2f}  '
                f'{maker[:10]}'
            )
    if total == 0:
        print('  (no orders)')
    return total


if __name__ == '__main__':
    args = sys.argv[1:]
    while True:
        print('\033[2J\033[H', end='')  # clear screen
        if args and args[0] == '--spot':
            base_tick = args[1] if len(args) > 1 else 'BTC'
            quote_tick = args[2] if len(args) > 2 else 'USDC'
            list_spot_orders(base_tick, quote_tick)
        else:
            slug = args[0] if args else current_slug()
            list_predict_orders(slug)
        time.sleep(1)
