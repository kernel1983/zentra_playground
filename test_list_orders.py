import sys
import requests

PROVIDER_HOST = 'http://127.0.0.1:8545'


def get_state(key):
    resp = requests.get(f'{PROVIDER_HOST}/api/get_latest_state?prefix={key}')
    data = resp.json()
    return data.get('result')


def load_book(prefix):
    new = get_state(f'{prefix}_new')
    if new is None:
        return {}
    new = int(new)
    orders = {}
    for oid in range(1, new):
        raw = get_state(f'{prefix}:{oid}')
        if isinstance(raw, list) and len(raw) >= 6:
            orders[oid] = raw
    return orders


def sorted_linked(orders):
    heads = [oid for oid, o in orders.items() if o[4] is None]
    if not heads:
        return []
    cur = heads[0]
    seq = []
    seen = set()
    while cur is not None and cur not in seen:
        seen.add(cur)
        seq.append(cur)
        cur = orders[cur][5]
    return seq


def list_predict_orders(slug):
    print(f'=== predict orders: {slug} (linked list, sorted) ===')
    total = 0
    for token in ['yes', 'no']:
        for side in ['sell', 'buy']:
            prefix = f'predict-{slug}_{token}_{side}'
            orders = load_book(prefix)
            seq = sorted_linked(orders)
            if not seq:
                continue
            print(f'  --- {token} {side} ---')
            for oid in seq:
                order = orders[oid]
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
        orders = load_book(prefix)
        seq = sorted_linked(orders)
        if not seq:
            continue
        print(f'  --- {side} ---')
        for oid in seq:
            order = orders[oid]
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
    if args and args[0] == '--spot':
        base_tick = args[1] if len(args) > 1 else 'BTC'
        quote_tick = args[2] if len(args) > 2 else 'USDC'
        list_spot_orders(base_tick, quote_tick)
    else:
        slug = args[0] if args else 'btc_5min'
        list_predict_orders(slug)
