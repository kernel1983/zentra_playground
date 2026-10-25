

import code
import rlcompleter
import sys
import threading
try:
    import readline
except:
    pass

import json
import tornado.web
import tornado.ioloop
import tornado.websocket

try:
    from eth_utils import keccak
except ImportError:
    keccak = None

import space
import rpc
import func


func.load_all_zips()

GLOBAL_FUNCTIONS = func.namespace


class BaseHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.set_header("Access-Control-Allow-Headers", "Content-Type")

    def options(self):
        self.set_status(204)
        self.finish()


class GetLatestStateAPIHandler(BaseHandler):
    def get(self):
        from urllib.parse import unquote
        prefix = unquote(self.get_argument('prefix'))
        print('get_latest_state:', prefix)

        if prefix.startswith('base-'):
            prefix = prefix[5:]

        # format: asset-var:key (e.g., BTC-balance:0xabc...)
        if '-' not in prefix:
            self.finish({'result': None})
            return
        
        idx = prefix.index('-')
        asset = prefix[:idx]
        rest = prefix[idx+1:]
        
        if ':' in rest:
            var, key = rest.split(':', 1)
        else:
            var = rest
            key = None
        
        value, owner = space.get(asset, var, None, key)
        print('value:', value, 'owner:', owner)
        self.finish({'result': value, 'owner': owner})

class QueryRecentStateAPIHandler(BaseHandler):
    def get(self):
        prefix = self.get_argument('prefix')
        print(prefix)


class OrderbookAPIHandler(BaseHandler):
    def get(self):
        base = self.get_argument('base').upper()
        quote = self.get_argument('quote').upper()
        pair = f'{base}_{quote}'

        buys = []
        sells = []

        buy_start, _ = space.get('trade', f'{pair}_buy_start', 1)
        sell_start, _ = space.get('trade', f'{pair}_sell_start', 1)

        buy_id = buy_start
        while buy_id:
            buy, _ = space.get('trade', f'{pair}_buy', None, str(buy_id))
            if buy:
                buys.append({
                    'id': buy_id,
                    'owner': buy[0],
                    'base': str(buy[1]),
                    'quote': str(buy[2]),
                    'price': str(buy[3]),
                    'next': buy[4]
                })
                buy_id = buy[4]
            else:
                break

        sell_id = sell_start
        while sell_id:
            sell, _ = space.get('trade', f'{pair}_sell', None, str(sell_id))
            if sell:
                sells.append({
                    'id': sell_id,
                    'owner': sell[0],
                    'base': str(sell[1]),
                    'quote': str(sell[2]),
                    'price': str(sell[3]),
                    'next': sell[4]
                })
                sell_id = sell[4]
            else:
                break

        self.finish({'buys': buys, 'sells': sells, 'pair': pair})


class PredictOrderbookAPIHandler(BaseHandler):
    def get(self):
        slug = self.get_argument('slug', 'btc_5min')

        def side_book(token, side):
            new, _ = space.get('predict', f'{slug}_{token}_{side}_new', None)
            orders = []
            if new is None:
                return orders
            for oid in range(1, int(new)):
                order, _ = space.get('predict', f'{slug}_{token}_{side}', None, str(oid))
                if not order or len(order) < 4:
                    continue
                if order[1] == 0:
                    continue
                price = int(order[3])
                if price <= 0:
                    continue
                orders.append({
                    'id': oid,
                    'owner': order[0],
                    'base': str(order[1]),
                    'quote': str(order[2]),
                    'price': str(price),
                })
            return orders

        result = {}
        for token in ['yes', 'no']:
            sells = sorted(side_book(token, 'sell'), key=lambda o: int(o['price']))
            buys = sorted(side_book(token, 'buy'), key=lambda o: -int(o['price']))
            result[token] = {
                'bestAsk': str(int(sells[0]['price']) / 10**18) if sells else None,
                'bestBid': str(int(buys[0]['price']) / 10**18) if buys else None,
                'asks': sells,
                'bids': buys,
            }

        self.finish({'slug': slug, 'result': result})


class HistoryAPIHandler(BaseHandler):
    def get(self):
        base = self.get_argument('base').upper()
        quote = self.get_argument('quote').upper()
        interval = self.get_argument('interval', '1s')
        target_pair = f'{base}_{quote}'

        interval_seconds = {
            '1s': 1, '1m': 60, '5m': 300, '15m': 900, '1h': 3600, '1d': 86400
        }
        if interval not in interval_seconds:
            interval = '1s'
        interval_sec = interval_seconds[interval]

        start_time_arg = self.get_argument('start_time', None)
        if start_time_arg:
            start_time = int(start_time_arg)
        else:
            start_time = 0

        buckets = {}
        last_trade_before_start = None
        boundary_scanned = False

        for block_num in sorted(space.events.keys()):
            block_events = space.events[block_num]
            timestamp = space.block_times.get(block_num, block_num)

            if timestamp < start_time:
                if boundary_scanned:
                    continue
                boundary_scanned = True

            for evt in block_events:
                if evt['event'] not in ('TradeLimitTake', 'TradeMarketTake'):
                    continue
                if evt['args'][0] != target_pair:
                    continue

                price = int(evt['args'][4])
                if price == 0:
                    side = evt['args'][1]
                    if len(evt['args']) > 5:
                        order_id = evt['args'][5]
                        order, _ = space.get('trade', f'{target_pair}_{side}', None, str(order_id))
                        if order and len(order) >= 4:
                            price = int(order[3])
                if price == 0:
                    continue

                base_amount = int(evt['args'][3])
                price_display = price / 10**6

                if timestamp < start_time:
                    last_trade_before_start = {
                        'time': timestamp,
                        'price': price_display,
                        'amount': base_amount,
                        'side': side,
                    }
                else:
                    bucket = (timestamp // interval_sec) * interval_sec
                    if bucket not in buckets:
                        buckets[bucket] = {
                            'time': bucket,
                            'open': price_display,
                            'high': price_display,
                            'low': price_display,
                            'close': price_display,
                            'volume': base_amount,
                        }
                    else:
                        b = buckets[bucket]
                        b['high'] = max(b['high'], price_display)
                        b['low'] = min(b['low'], price_display)
                        b['close'] = price_display
                        b['volume'] += base_amount

        candles = list(buckets.values())
        candles.sort(key=lambda x: x['time'])

        result = {'candles': candles, 'pair': target_pair}
        if last_trade_before_start:
            result['last_trade_before_start'] = last_trade_before_start
        self.finish(result)


class WSHandler(tornado.websocket.WebSocketHandler):
    def open(self):
        space.connected_clients.add(self)
        print(f'WS client connected, total: {len(space.connected_clients)}')

    def on_close(self):
        space.connected_clients.discard(self)
        print(f'WS client disconnected, total: {len(space.connected_clients)}')

    def check_origin(self, origin):
        return True


class EventsAPIHandler(BaseHandler):
    def get(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "x-requested-with")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')

        chain = self.get_argument('chain', 'base')

        block_number = self.get_argument('blockno', None)
        if block_number is not None:
            block_number = int(block_number)
            block_hash = space.block_hashes.get(block_number, '')
            tx_hashes = space.blocks.get(block_number, [])

            block_events = space.events.get(block_number, [])

            events_with_tx = []
            for i, evt in enumerate(block_events):
                evt_with_tx = dict(evt)
                evt_with_tx['tx_index'] = i
                evt_with_tx['tx_hash'] = tx_hashes[i] if i < len(tx_hashes) else ''
                events_with_tx.append(evt_with_tx)

            self.finish({
                'tx_hashes': tx_hashes,
                'events': events_with_tx,
                'blockno': block_number,
                'block_hash': block_hash,
                'chain': chain
            })
            return

        tx_hash = self.get_argument('txhash', '')
        tx_hash = tx_hash.replace('0x', '')

        if tx_hash in space.transactions:
            tx = space.transactions[tx_hash]
            block_number = tx.get('blockNumber', 0)
            block_events = space.events.get(block_number, [])

            events_with_tx = []
            for i, evt in enumerate(block_events):
                evt_with_tx = dict(evt)
                evt_with_tx['tx_index'] = i
                evt_with_tx['tx_hash'] = tx_hash
                events_with_tx.append(evt_with_tx)

            self.finish({'tx_hash': tx_hash, 'blockno': block_number, 'events': events_with_tx, 'chain': chain})
        else:
            self.finish({'tx_hash': tx_hash, 'events': [], 'chain': chain})


# === Debug Pages ===

def decode_call(tx_hash):
    """Decode the calldata (input hex -> utf-8 JSON call) that produced a tx."""
    tx = space.transactions.get(tx_hash, {})
    raw = tx.get('input', '0x').replace('0x', '')
    if not raw:
        return ""
    try:
        call = json.loads(bytes.fromhex(raw).decode('utf-8'))
        return json.dumps(call, indent=2)
    except Exception:
        return ""

class DebugBaseHandler(tornado.web.RequestHandler):
    def render_debug_page(self, template_name, **kwargs):
        self.render(f"debug/{template_name}", **kwargs)


def _latest_content_block():
    """Highest block that actually holds state writes, transactions or events.
    Trailing blocks opened by nextblock() without any content don't count."""
    for block_num in range(space.latest_block_number, -1, -1):
        if (space.states.get(block_num) or space.blocks.get(block_num)
                or space.events.get(block_num)):
            return block_num
    return 0


class DebugOverviewHandler(DebugBaseHandler):
    def get(self):
        total_state_entries = sum(len(s) for s in space.states.values())
        total_events = sum(len(v) for v in space.events.values())
        total_txs = len(space.transactions)

        self.render_debug_page("overview.html",
            title="Overview",
            page="overview",
            latest_block=_latest_content_block(),
            total_blocks=len(space.blocks),
            total_txs=total_txs,
            total_events=total_events,
            total_state_entries=total_state_entries
        )


class DebugBlocksHandler(DebugBaseHandler):
    def get(self):
        blocks = []
        for blk_num in sorted(space.blocks.keys(), reverse=True)[:100]:
            blk_hash = space.block_hashes.get(blk_num, None)
            tx_count = len(space.blocks.get(blk_num, []))
            evt_count = len(space.events.get(blk_num, []))
            hash_str = (str(blk_hash)[:16] + "...") if blk_hash else "None"
            blocks.append({
                "num": blk_num,
                "hash": hash_str,
                "time": "N/A",
                "tx_count": tx_count,
                "evt_count": evt_count
            })
        self.render_debug_page("blocks.html", title="Blocks", page="blocks", blocks=blocks)


class DebugBlockHandler(DebugBaseHandler):
    def get(self, block_num):
        blk_num = int(block_num)
        blk_hash = space.block_hashes.get(blk_num, None)
        txs = space.blocks.get(blk_num, [])
        evts = space.events.get(blk_num, [])

        existing = sorted(set(space.blocks.keys()) | set(space.block_hashes.keys()) | set(space.states.keys()))
        prev_candidates = [b for b in existing if b < blk_num]
        next_candidates = [b for b in existing if b > blk_num]
        prev_block = prev_candidates[-1] if prev_candidates else None
        next_block = next_candidates[0] if next_candidates else None
        can_prev = prev_block is not None
        can_next = next_block is not None

        tx_list = []
        for tx in txs:
            tx_hash = tx[1] if isinstance(tx, tuple) else tx
            tx_record = space.transactions.get(tx_hash, {})
            tx_events = tx_record.get('events')
            if tx_events is None:
                # Older transactions predate per-tx event tracking; only a
                # single-tx block can be attributed unambiguously.
                tx_events = list(evts) if len(txs) == 1 else []
            tx_list.append({
                "hash": str(tx_hash),
                "data": decode_call(tx_hash),
                "events": [{"event": str(e.get("event")),
                            "args": json.dumps(e.get("args"), indent=2)}
                           for e in tx_events],
            })

        hash_str = str(blk_hash) if blk_hash else "None"

        self.render_debug_page("block.html",
            title="Block " + str(blk_num),
            page="block",
            blk_num=blk_num,
            blk_hash=hash_str,
            blk_time="N/A",
            txs=tx_list,
            prev_block=prev_block,
            next_block=next_block,
            can_prev=can_prev,
            can_next=can_next
        )


class DebugEventsHandler(DebugBaseHandler):
    def get(self):
        blocks = []
        for blk_num in sorted(space.events.keys(), reverse=True):
            evts = space.events[blk_num]
            tx_hashes = space.blocks.get(blk_num, [])
            evt_list = []
            for i, evt in enumerate(evts):
                tx_hash = tx_hashes[i] if i < len(tx_hashes) else ''
                evt_list.append({"event": str(evt.get("event")),
                                 "args": json.dumps(evt.get("args"), indent=2),
                                 "call": decode_call(tx_hash),
                                 "tx_hash": tx_hash})
            blocks.append({"num": blk_num, "count": len(evts), "events": evt_list})
        self.render_debug_page("events.html", title="Events", page="events", blocks=blocks)


class DebugStateHandler(DebugBaseHandler):
    def get(self):
        prefix = self.get_argument("prefix", "")
        block_arg = self.get_argument("block", "")
        max_entries = 500

        state_blocks = sorted(space.states.keys())
        latest_block = _latest_content_block()

        if block_arg:
            try:
                target_block = int(block_arg)
            except ValueError:
                target_block = latest_block
        else:
            target_block = latest_block

        if state_blocks:
            target_block = max(state_blocks[0], min(target_block, state_blocks[-1]))

        first_block = state_blocks[0] if state_blocks else 0
        prev_block = max(first_block, target_block - 1)
        next_block = min(latest_block, target_block + 1)
        can_prev = target_block > first_block
        can_next = target_block < latest_block

        # Replay every block's writes from the earliest one; later writes overwrite
        # earlier ones, so each key appears exactly once with its last-write block.
        effective = {}
        prev_values = {}
        for block_num in state_blocks:
            if block_num > target_block:
                break
            for key, (addr, value) in space.states[block_num].items():
                if key in effective:
                    prev_values[key] = effective[key][1]
                effective[key] = (addr, value, block_num)

        entries = []
        count = 0
        for key in sorted(effective.keys()):
            if prefix and not key.startswith(prefix):
                continue
            addr, value, block_num = effective[key]
            prev_value = prev_values.get(key)
            entries.append({"key": str(key), "owner": str(addr), "value": str(value),
                            "prev_value": "" if prev_value is None else str(prev_value),
                            "block_num": block_num})
            count += 1
            if count >= max_entries:
                break

        self.render_debug_page("state.html",
            title="State Browser",
            page="state",
            prefix=prefix,
            block=target_block,
            latest_block=latest_block,
            is_latest=(block_arg == "" or target_block == latest_block),
            entries=entries,
            count=count,
            unique=len(effective),
            max_entries=max_entries,
            first_block=first_block,
            prev_block=prev_block,
            next_block=next_block,
            can_prev=can_prev,
            can_next=can_next
        )


class DebugTransactionsHandler(DebugBaseHandler):
    def get(self):
        transactions = []
        for tx_hash, tx_data in space.transactions.items():
            transactions.append({"hash": str(tx_hash),
                                 "block": tx_data.get("blockNumber", 0),
                                 "data": json.dumps(tx_data, indent=2)})
        transactions.sort(key=lambda t: (t["block"], t["hash"]))
        self.render_debug_page("transactions.html", title="Transactions", page="transactions", transactions=transactions)


# class EventsAPIHandler(tornado.web.RequestHandler):
#     def get(self):
#         self.set_header("Access-Control-Allow-Origin", "*")
#         self.set_header("Access-Control-Allow-Headers", "x-requested-with")
#         self.set_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')

#         global global_input
#         chain = self.get_argument('chain', 'base')
#         assert chain in setting.chains
#         it1 = global_input.iteritems()
#         events = []
#         try:
#             block_number = int(self.get_argument('blockno', None))
#         except:
#             tx_hash = self.get_argument('txhash', '')
#             tx_hash = tx_hash.replace('0x', '')
#             k = ('%s-tx-%s-' % (chain, tx_hash) ).encode('utf8')
#             it1.seek(k)
#             for key1, value_json1 in it1:
#                 print('key1', key1)
#                 if not key1.startswith(k):
#                     break
#                 tx = json.loads(value_json1)
#                 events.append([tx_hash, tx['events']])

#             self.finish({'events': events, 'tx_hash': tx_hash, 'chain':chain})
#             return

#         it = global_input.iteritems()
#         reversed_height = str(setting.REVERSED_NO - block_number).zfill(16)
#         k = ('%s-block-%s-' % (chain, reversed_height)).encode('utf8')
#         it.seek(k)

#         for key, value_json in it:
#             # print('block', block_number, key)
#             if not key.startswith(k):
#                 break

#             _, _, _, block_hash = key.decode('utf8').split('-')
#             block = json.loads(value_json)
#             tx_hashes = block.get('transactions', [])
#             # chain = block['chain']
#             for tx_hash in tx_hashes:
#                 k = ('%s-tx-%s-' % (chain, tx_hash) ).encode('utf8')
#                 it1.seek(k)
#                 for key1, value_json1 in it1:
#                     print('key1', key1)
#                     if not key1.startswith(k):
#                         break
#                     tx = json.loads(value_json1)
#                     events.append([tx_hash, tx['events']])
#                     break

#             break
#         self.finish({'events': events, 'blockno': block_number, 'block_hash': block_hash, 'chain':chain})


def start_server():
    space._init_block_mode()
    app = tornado.web.Application([
        # (r'/(favicon\.ico)', tornado.web.StaticFileHandler, {'path': 'static/'}),
        (r'/static/(.*)', tornado.web.StaticFileHandler, {'path': 'static/'}),
        # (r"/state", StateHandler),
        (r'/debug', DebugOverviewHandler),
        (r'/debug/blocks', DebugBlocksHandler),
        (r'/debug/block/(\d+)', DebugBlockHandler),
        (r'/debug/events', DebugEventsHandler),
        (r'/debug/state', DebugStateHandler),
        (r'/debug/transactions', DebugTransactionsHandler),
        (r"/", rpc.RPCHandler),
        (r'/api/get_latest_state', GetLatestStateAPIHandler),
        (r'/api/query_recent_state', QueryRecentStateAPIHandler),
        (r'/api/orderbook', OrderbookAPIHandler),
        (r'/api/predict_orderbook', PredictOrderbookAPIHandler),
        (r'/api/history', HistoryAPIHandler),
        (r'/api/events', EventsAPIHandler),
        (r'/ws', WSHandler),
    ], template_path="templates")
    app.listen(8545)
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    server_thread = threading.Thread(target=start_server)
    server_thread.daemon = True  # Thread will close when main program exits
    server_thread.start()
    try:
        readline.parse_and_bind("tab: complete")
    except:
        pass

    print("Server started at http://127.0.0.1:8545")
    print("Debug page: http://127.0.0.1:8545/debug")
    print()

    code.interact(banner="""
    Zentra Interactive python console
    Available commands:
    - put(owner, asset, var, value, key=None)  # Store state
    - get(asset, var, default=None, key=None)  # Access state
    - blocknumber()  # Current block number
    - nextblock()  # Start next block
    - setsender()  # Set sender
    - states  # View all states
    - sender  # Current sender

    Example:
    >>> put('alice', 'USDC', 'balance', 100, 'alice')
    >>> get('USDC', 'balance', 0, 'alice')
    100
    >>> states
    {0: {'asset-balance': ('alice', 100)}}
    >>> nextblock()
    >>> setsender(a[0])
    >>> asset_create('USDC')
    Ok, let's start!
    """, local=func.namespace)

