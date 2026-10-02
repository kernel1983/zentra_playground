K = 10**18

def _insert_order(addr, pair, order_type, order_start, order_new, quote_value, base_value):
    assert order_type in ['buy', 'sell']
    price = - quote_value * K // base_value
    order_id = order_start
    while True:
        order, _ = get('options', f'{pair}_{order_type}', None, str(order_id))

        if order is None:
            put(addr, 'options', f'{pair}_{order_type}',
                [addr, base_value, quote_value, price, None, None], str(order_new))
            order_new += 1
            put(addr, 'options', f'{pair}_{order_type}_new', order_new)
            break

        if order_type == 'buy':
            cond = price > order[3]
        else:
            cond = price < order[3]

        if cond:
            next_order_id = order[5]
            put(addr, 'options', f'{pair}_{order_type}',
                [addr, base_value, quote_value, price, order_id, next_order_id], str(order_new))
            if next_order_id is None:
                order_start = order_new
                put(addr, 'options', f'{pair}_{order_type}_start', order_new)
            order[5] = order_new
            order_new += 1
            put(addr, 'options', f'{pair}_{order_type}_new', order_new)

            put(addr, 'options', f'{pair}_{order_type}', order, str(order_id))
            if next_order_id is not None:
                next_order, _ = get('options', f'{pair}_{order_type}', None, str(next_order_id))
                if next_order is not None:
                    next_order[4] = order[5]
                    put(addr, 'options', f'{pair}_{order_type}', next_order, str(next_order_id))
            break

        if order[4] is None:
            put(addr, 'options', f'{pair}_{order_type}',
                [addr, base_value, quote_value, price, None, order_id], str(order_new))
            put(addr, 'options', f'{pair}_{order_type}',
                [order[0], order[1], order[2], order[3], order_new, order[5]], str(order_id))
            order_new += 1
            put(addr, 'options', f'{pair}_{order_type}_new', order_new)
            break

        order_id = order[4]
    return order_start, order_new


def _remove_order(addr, pair, order, order_start, buy_or_sell):
    assert buy_or_sell in ['buy', 'sell']
    if order[4]:
        prev_order, _ = get('options', f'{pair}_{buy_or_sell}', None, str(order[4]))
        prev_order[5] = order[5]
        put(prev_order[0], 'options', f'{pair}_{buy_or_sell}', prev_order, str(order[4]))

    if order[5]:
        next_order, _ = get('options', f'{pair}_{buy_or_sell}', None, str(order[5]))
        next_order[4] = order[4]
        put(next_order[0], 'options', f'{pair}_{buy_or_sell}', next_order, str(order[5]))

    if order[4] is not None and order[5] is None:
        order_start = order[4]
        put(addr, 'options', f'{pair}_{buy_or_sell}_start', order_start)

    elif order[4] is None and order[5] is None:
        order_new, _ = get('options', f'{pair}_{buy_or_sell}_new', 1)
        order_start = order_new
        put(addr, 'options', f'{pair}_{buy_or_sell}_start', order_start)

    return order_start

def _update_slug_balance(addr, slug, tick, delta):
    prev, manager = get('options', f'{slug}_{tick}_balance_new', None)
    balance_tuple, _ = get('options', f'{slug}_{tick}_balance', None, addr)
    if balance_tuple is None:
        balance = 0
        put(manager, 'options', f'{slug}_{tick}_balance_new', addr)
    else:
        balance = balance_tuple[0]
        prev = balance_tuple[1]
    balance += delta
    assert balance >= 0
    put(addr, 'options', f'{slug}_{tick}_balance', [balance, prev], addr)

def _update_quote_balance(addr, quote_tick, delta):
    balance, _ = get(quote_tick, 'balance', 0, addr)
    balance += delta
    assert balance >= 0
    put(addr, quote_tick, 'balance', balance, addr)


def options_limit_buy(info, args):
    assert args['f'] == 'options_limit_buy'
    sender = info['sender']
    addr = handle_lookup(sender)

    slug = args['a'][0]
    call_or_put = args['a'][2]
    assert set(slug) <= set(string.ascii_lowercase+string.digits+'_')
    assert call_or_put in set(['call', 'put'])

    pair = f'{slug}_{call_or_put}'
    base_value = int(args['a'][1])
    quote_value = int(args['a'][3])
    assert base_value * quote_value < 0

    quote_tick, _ = get('options', f'{slug}_quote_token', None)
    assert quote_tick, "Slug not exists"

    options_buy_start, _ = get('options', f'{pair}_buy_start', 1)
    options_buy_new, _ = get('options', f'{pair}_buy_new', 1)
    options_sell_start, _ = get('options', f'{pair}_sell_start', 1)
    options_sell_new, _ = get('options', f'{pair}_sell_new', 1)

    if base_value < 0 and quote_value > 0:
        buy_or_sell = 'sell'
        _update_slug_balance(addr, slug, call_or_put, base_value)
        make_base = - base_value

        order_id = options_sell_new
        options_sell_start, options_sell_new = _insert_order(addr, pair, 'sell', options_sell_start, options_sell_new, quote_value, base_value)

    elif base_value > 0 and quote_value < 0:
        buy_or_sell = 'buy'
        _update_quote_balance(addr, quote_tick, quote_value)
        make_base = base_value

        order_id = options_buy_new
        options_buy_start, options_buy_new = _insert_order(addr, pair, 'buy', options_buy_start, options_buy_new, quote_value, base_value)

    options_sell_id = options_sell_start
    highest_buy_price = None

    take_base = 0
    take_quote = 0
    while True:
        sell, _ = get('options', f'{pair}_sell', None, str(options_sell_id))
        if not sell:
            break
        sell_price = sell[3]
        if highest_buy_price and sell_price > highest_buy_price:
            break

        options_buy_id = options_buy_start
        while True:
            buy, _ = get('options', f'{pair}_buy', None, str(options_buy_id))
            if not buy:
                break
            buy_price = buy[3]
            if highest_buy_price is None:
                highest_buy_price = buy_price
            if sell_price > buy_price:
                options_buy_id = buy[4]
                continue

            matched_price = sell_price
            dx_base = min(-sell[1], buy[1])
            dx_quote = dx_base * matched_price // K
            sell[1] += dx_base
            sell[2] -= dx_quote
            buy[1] -= dx_base
            buy[2] += dx_quote
            take_base += dx_base
            take_quote += dx_quote

            _update_slug_balance(buy[0], slug, call_or_put, dx_base)
            _update_quote_balance(sell[0], quote_tick, dx_quote)
            if buy[1] == 0:
                options_buy_start = _remove_order(addr, pair, buy, options_buy_start, 'buy')
                if buy[2] < 0:
                    _update_quote_balance(buy[0], quote_tick, -buy[2])

                put(buy[0], 'options', f'{pair}_buy', None, str(options_buy_id))
            else:
                put(buy[0], 'options', f'{pair}_buy', buy, str(options_buy_id))

            if sell[1] == 0:
                break
            if buy[4] is None:
                break
            options_buy_id = buy[4]

        if sell[1] == 0:
            options_sell_start = _remove_order(addr, pair, sell, options_sell_start, 'sell')
            if sell[1] < 0:
                _update_slug_balance(sell[0], slug, call_or_put, -sell[1])

            put(sell[0], 'options', f'{pair}_sell', None, str(options_sell_id))
        else:
            put(sell[0], 'options', f'{pair}_sell', sell, str(options_sell_id))

        if sell[4] is None:
            break
        options_sell_id = sell[4]

    make_base -= take_base
    assert make_base >= 0
    make_price = - quote_value * K // base_value
    event('OptionsLimitMake', [pair, buy_or_sell, addr, make_base, make_price, order_id])
    if take_base > 0:
        take_price = take_quote * K // take_base
        event('OptionsLimitTake', [pair, buy_or_sell, addr, take_base, take_price, order_id])


def options_limit_sell(info, args):
    assert args['f'] == 'options_limit_sell'
    sender = info['sender']
    addr = handle_lookup(sender)

    slug = args['a'][0]
    call_or_put = args['a'][2]
    assert set(slug) <= set(string.ascii_lowercase+string.digits+'_')
    assert call_or_put in set(['call', 'put'])

    pair = f'{slug}_{call_or_put}'
    base_value = int(args['a'][1])
    quote_value = int(args['a'][3])
    assert base_value * quote_value < 0

    quote_tick, _ = get('options', f'{slug}_quote_token', None)
    assert quote_tick, "Slug not exists"

    options_buy_start, _ = get('options', f'{pair}_buy_start', 1)
    options_buy_new, _ = get('options', f'{pair}_buy_new', 1)
    options_sell_start, _ = get('options', f'{pair}_sell_start', 1)
    options_sell_new, _ = get('options', f'{pair}_sell_new', 1)

    if base_value < 0 and quote_value > 0:
        buy_or_sell = 'sell'
        _update_slug_balance(addr, slug, call_or_put, base_value)
        make_base = - base_value

        order_id = options_sell_new
        options_sell_start, options_sell_new = _insert_order(addr, pair, 'sell', options_sell_start, options_sell_new, quote_value, base_value)

    elif base_value > 0 and quote_value < 0:
        buy_or_sell = 'buy'
        _update_quote_balance(addr, quote_tick, quote_value)
        make_base = base_value

        order_id = options_buy_new
        options_buy_start, options_buy_new = _insert_order(addr, pair, 'buy', options_buy_start, options_buy_new, quote_value, base_value)

    options_sell_id = options_sell_start
    highest_buy_price = None

    take_base = 0
    take_quote = 0
    while True:
        sell, _ = get('options', f'{pair}_sell', None, str(options_sell_id))
        if not sell:
            break
        sell_price = sell[3]
        if highest_buy_price and sell_price > highest_buy_price:
            break

        options_buy_id = options_buy_start
        while True:
            buy, _ = get('options', f'{pair}_buy', None, str(options_buy_id))
            if not buy:
                break
            buy_price = buy[3]
            if highest_buy_price is None:
                highest_buy_price = buy_price
            if sell_price > buy_price:
                options_buy_id = buy[4]
                continue

            matched_price = sell_price
            dx_base = min(-sell[1], buy[1])
            dx_quote = dx_base * matched_price // K
            sell[1] += dx_base
            sell[2] -= dx_quote
            buy[1] -= dx_base
            buy[2] += dx_quote
            take_base += dx_base
            take_quote += dx_quote

            _update_slug_balance(buy[0], slug, call_or_put, dx_base)
            _update_quote_balance(sell[0], quote_tick, dx_quote)
            if buy[1] == 0:
                options_buy_start = _remove_order(addr, pair, buy, options_buy_start, 'buy')
                if buy[2] < 0:
                    _update_quote_balance(buy[0], quote_tick, -buy[2])

                put(buy[0], 'options', f'{pair}_buy', None, str(options_buy_id))
            else:
                put(buy[0], 'options', f'{pair}_buy', buy, str(options_buy_id))

            if sell[1] == 0:
                break
            if buy[4] is None:
                break
            options_buy_id = buy[4]

        if sell[1] == 0:
            options_sell_start = _remove_order(addr, pair, sell, options_sell_start, 'sell')
            if sell[1] < 0:
                _update_slug_balance(sell[0], slug, call_or_put, -sell[1])

            put(sell[0], 'options', f'{pair}_sell', None, str(options_sell_id))
        else:
            put(sell[0], 'options', f'{pair}_sell', sell, str(options_sell_id))

        if sell[4] is None:
            break
        options_sell_id = sell[4]

    make_base -= take_base
    assert make_base >= 0
    make_price = - quote_value * K // base_value
    event('OptionsLimitMake', [pair, buy_or_sell, addr, make_base, make_price, order_id])
    if take_base > 0:
        take_price = take_quote * K // take_base
        event('OptionsLimitTake', [pair, buy_or_sell, addr, take_base, take_price, order_id])


def options_market_order(info, args):
    assert args['f'] == 'options_market_order'
    sender = info['sender']
    addr = handle_lookup(sender)

    slug = args['a'][0]
    call_or_put = args['a'][2]
    assert set(slug) <= set(string.ascii_lowercase+string.digits+'_')
    assert call_or_put in set(['call', 'put'])

    quote_tick, _ = get('options', f'{slug}_quote_token', None)
    assert quote_tick, "Slug not exists"
    pair = f'{slug}_{call_or_put}'

    base_value = args['a'][1]
    quote_value = args['a'][3]
    options_sell_start, _ = get('options', f'{pair}_sell_start', 1)
    options_buy_start, _ = get('options', f'{pair}_buy_start', 1)

    take_base = 0
    take_quote = 0
    if quote_value is None and int(base_value) < 0:
        buy_or_sell = 'sell'
        base_value = int(args['a'][1])
        [base_balance, _], _ = get('options', f'{pair}_balance', [0, None], addr)

        options_buy_id = options_buy_start
        while True:
            buy, _ = get('options', f'{pair}_buy', None, str(options_buy_id))
            if buy is None:
                break

            price = buy[3]
            dx_base = min(buy[1], -buy[2] * K // price, -base_value)
            dx_quote = dx_base * price // K
            if dx_base == 0 or dx_quote == 0:
                break
            if base_balance - dx_base < 0:
                break
            buy[1] -= dx_base
            buy[2] += dx_quote
            take_base += dx_base
            take_quote += dx_quote
            base_balance -= dx_base

            if buy[1] == 0 or buy[1] * K // price == 0:
                options_buy_start = _remove_order(addr, pair, buy, options_buy_start, 'buy')
                if buy[2] < 0:
                    _update_quote_balance(buy[0], quote_tick, -buy[2])

                put(buy[0], 'options', f'{pair}_buy', None, str(options_buy_id))
            else:
                put(buy[0], 'options', f'{pair}_buy', buy, str(options_buy_id))

            _update_slug_balance(buy[0], slug, call_or_put, dx_base)
            base_value += dx_base
            assert base_value <= 0

            _update_quote_balance(addr, quote_tick, dx_quote)
            if buy[4] is None:
                break
            options_buy_id = buy[4]

        _update_slug_balance(addr, slug, call_or_put, -take_base)

    elif quote_value is None and int(base_value) > 0:
        buy_or_sell = 'buy'
        base_value = int(args['a'][1])
        quote_balance, _ = get(quote_tick, 'balance', 0, addr)

        options_sell_id = options_sell_start
        while True:
            sell, _ = get('options', f'{pair}_sell', None, str(options_sell_id))
            if sell is None:
                break

            price = sell[3]
            dx_base = min(-sell[1], quote_balance * K // price, base_value)
            dx_quote = dx_base * price // K
            if dx_base == 0 or dx_quote == 0:
                break
            if quote_balance - dx_quote < 0:
                break

            sell[1] += dx_base
            sell[2] -= dx_quote
            take_base += dx_base
            take_quote += dx_quote
            quote_balance -= dx_quote

            if sell[1] == 0 or sell[1] * K // price == 0:
                options_sell_start = _remove_order(addr, pair, sell, options_sell_start, 'sell')
                if sell[1] < 0:
                    _update_slug_balance(sell[0], slug, call_or_put, -sell[1])

                put(sell[0], 'options', f'{pair}_sell', None, str(options_sell_id))
            else:
                put(sell[0], 'options', f'{pair}_sell', sell, str(options_sell_id))

            _update_quote_balance(sell[0], quote_tick, dx_quote)
            base_value -= dx_base
            assert base_value >= 0

            _update_slug_balance(addr, slug, call_or_put, dx_base)
            if sell[4] is None:
                break
            options_sell_id = sell[4]

        _update_quote_balance(addr, quote_tick, -take_quote)

    elif base_value is None and int(quote_value) < 0:
        buy_or_sell = 'buy'
        quote_value = int(args['a'][3])
        quote_balance, _ = get(quote_tick, 'balance', 0, addr)

        options_sell_id = options_sell_start
        while True:
            sell, _ = get('options', f'{pair}_sell', None, str(options_sell_id))
            if sell is None:
                break

            price = sell[3]
            dx_base = min(-sell[1], -quote_value * K // price)
            dx_quote = dx_base * price // K
            if dx_base == 0 or  dx_quote == 0:
                break
            if quote_balance - dx_quote < 0:
                break

            sell[1] += dx_base
            sell[2] -= dx_quote
            take_base += dx_base
            take_quote += dx_quote
            quote_balance -= dx_quote

            if sell[1] == 0 or sell[1] * K // price == 0:
                options_sell_start = _remove_order(addr, pair, sell, options_sell_start, 'sell')
                if sell[1] < 0:
                    _update_slug_balance(sell[0], slug, call_or_put, -sell[1])

                put(sell[0], 'options', f'{pair}_sell', None, str(options_sell_id))
            else:
                put(sell[0], 'options', f'{pair}_sell', sell, str(options_sell_id))

            _update_quote_balance(sell[0], quote_tick, dx_quote)
            quote_value += dx_quote
            assert quote_value <= 0

            _update_slug_balance(addr, slug, call_or_put, dx_base)
            if sell[4] is None:
                break
            options_sell_id = sell[4]

        _update_quote_balance(addr, quote_tick, -take_quote)

    elif base_value is None and int(quote_value) > 0:
        buy_or_sell = 'sell'
        quote_value = int(args['a'][3])
        [base_balance, _], _ = get('options', f'{pair}_balance', [0, None], addr)

        options_buy_id = options_buy_start
        while True:
            buy, _ = get('options', f'{pair}_buy', None, str(options_buy_id))
            if buy is None:
                break

            price = buy[3]
            dx_base = min(buy[1], base_balance, quote_value * K // price)
            dx_quote = dx_base * price // K
            if dx_base == 0 or dx_quote == 0:
                break
            if base_balance - dx_base < 0:
                break

            buy[1] -= dx_base
            buy[2] += dx_quote
            take_base += dx_base
            take_quote += dx_quote
            base_balance -= dx_base

            if buy[1] == 0 or buy[1] * K // price == 0:
                options_buy_start = _remove_order(addr, pair, buy, options_buy_start, 'buy')
                if buy[2] < 0:
                    _update_quote_balance(buy[0], quote_tick, -buy[2])

                put(buy[0], 'options', f'{pair}_buy', None, str(options_buy_id))
            else:
                put(buy[0], 'options', f'{pair}_buy', buy, str(options_buy_id))

            _update_slug_balance(buy[0], slug, call_or_put, dx_base)
            quote_value -= dx_quote
            assert quote_value >= 0
            _update_quote_balance(addr, quote_tick, dx_quote)

            if buy[4] is None:
                break
            options_buy_id = buy[4]

        _update_slug_balance(addr, slug, call_or_put, -take_base)

    if take_base > 0:
        price = take_quote * K // take_base
        event('OptionsMarketTake', [pair, buy_or_sell, addr, take_base, price])


def options_limit_order_cancel(info, args):
    assert args['f'] == 'options_limit_order_cancel'
    sender = info['sender']
    addr = handle_lookup(sender)

    slug = args['a'][0]
    call_or_put = args['a'][1]
    buy_or_sell = args['a'][2]
    options_order_id = int(args['a'][3])
    assert set(slug) <= set(string.ascii_lowercase+string.digits+'_')
    assert call_or_put in set(['call', 'put'])
    assert buy_or_sell in ['buy', 'sell']
    assert options_order_id > 0

    pair = f'{slug}_{call_or_put}'
    order_key = f'{pair}_{buy_or_sell}'
    quote_tick, _ = get('options', f'{slug}_quote_token', None)
    order, _ = get('options', order_key, None, str(options_order_id))

    if order is None:
        return

    assert order[0] == addr, "Sender is not the owner of the order"
    prev_order_id = order[4]
    next_order_id = order[5]

    if prev_order_id is not None:
        prev_order, _ = get('options', order_key, None, str(prev_order_id))
        if prev_order:
            prev_order[5] = next_order_id
            put(prev_order[0], 'options', order_key, prev_order, str(prev_order_id))

    if next_order_id is not None:
        next_order, _ = get('options', order_key, None, str(next_order_id))
        if next_order:
            next_order[4] = prev_order_id
            put(next_order[0], 'options', order_key, next_order, str(next_order_id))

    start_key = f'{pair}_{buy_or_sell}_start'
    current_start, _ = get('options', start_key, 1)
    if current_start == options_order_id:
        if prev_order_id is not None:
            put(addr, 'options', start_key, prev_order_id)
        else:
            new_start_key = f'{pair}_{buy_or_sell}_new'
            new_start_val, _ = get('options', new_start_key, 1)
            put(addr, 'options', start_key, new_start_val)

    if buy_or_sell == 'sell':
        if order[1] < 0:
            _update_slug_balance(addr, slug, call_or_put, -order[1])
    elif buy_or_sell == 'buy':
        if order[2] < 0:
            _update_quote_balance(addr, quote_tick, -order[2])

    put(addr, 'options', order_key, None, str(options_order_id))
    event('OptionsOrderCancel', [options_order_id, buy_or_sell, pair])


def options_create(info, args):
    assert args['f'] == 'options_create'
    sender = info['sender']
    addr = handle_lookup(sender)

    slug = args['a'][0]
    quote_tick = args['a'][1]
    assert set(slug) <= set(string.ascii_lowercase+string.digits+'_')

    quote_tokens, _ = get('options', 'quote_tokens', [])
    assert quote_tick in quote_tokens, f'{quote_tick} is not a designated quote token'

    manager, _ = get('options', 'manager', None)
    assert manager == addr, f"Sender must be the owner of options system"
    created, _ = get('options', f'{slug}_quote_token', None)
    assert created is None, "Slug already exists"
    put(addr, 'options', f'{slug}_quote_token', quote_tick)

    put(addr, 'options', f'{slug}_call_buy_start', 1)
    put(addr, 'options', f'{slug}_call_buy_new', 1)
    put(addr, 'options', f'{slug}_call_sell_start', 1)
    put(addr, 'options', f'{slug}_call_sell_new', 1)
    put(addr, 'options', f'{slug}_call_balance_new', None)

    put(addr, 'options', f'{slug}_put_buy_start', 1)
    put(addr, 'options', f'{slug}_put_buy_new', 1)
    put(addr, 'options', f'{slug}_put_sell_start', 1)
    put(addr, 'options', f'{slug}_put_sell_new', 1)
    put(addr, 'options', f'{slug}_put_balance_new', None)

    event('OptionsMarketCreate', [slug, quote_tick, addr])


def options_mint(info, args):
    assert args['f'] == 'options_mint'
    sender = info['sender']
    addr = handle_lookup(sender)

    slug = args['a'][0]
    assert set(slug) <= set(string.ascii_lowercase+string.digits+'_')

    quote_tick, _ = get('options', f'{slug}_quote_token', None)
    assert quote_tick, "Slug is not created"

    quote_value = int(args['a'][1])
    assert quote_value > 0

    _update_quote_balance(addr, quote_tick, -quote_value)

    #TODO: move the balance to the options slug

    for tick in ['call', 'put']:
        _update_slug_balance(addr, slug, tick, quote_value)

    event('OptionsMint', [slug, addr, quote_value])


def options_submit(info, args):
    assert args['f'] == 'options_submit'
    sender = info['sender']
    addr = handle_lookup(sender)

    manager, _ = get('options', 'manager', None)
    assert manager is not None, "Manager not set"
    assert addr == manager, "Only the manager can submit result"

    slug = args['a'][0]
    call_or_put = args['a'][1]
    assert set(slug) <= set(string.ascii_lowercase+string.digits+'_')
    assert call_or_put in set(['call', 'put'])
    lose_tick = 'put' if call_or_put == 'call' else 'call'

    quote_tick, _ = get('options', f'{slug}_quote_token', None)
    assert quote_tick, "Slug not exists"

    win_pair = f'{slug}_{call_or_put}'
    win_sell_start, _ = get('options', f'{win_pair}_sell_start', 1)
    win_buy_start, _ = get('options', f'{win_pair}_buy_start', 1)

    options_sell_id = win_sell_start
    while True:
        sell, _ = get('options', f'{win_pair}_sell', None, str(options_sell_id))
        if not sell:
            break
        next_id = sell[4]
        if sell[1] < 0:
            _update_slug_balance(sell[0], slug, call_or_put, -sell[1])
        put(sell[0], 'options', f'{win_pair}_sell', None, str(options_sell_id))
        if next_id is None:
            break
        options_sell_id = next_id

    options_buy_id = win_buy_start
    while True:
        buy, _ = get('options', f'{win_pair}_buy', None, str(options_buy_id))
        if not buy:
            break
        next_id = buy[4]
        if buy[2] < 0:
            _update_quote_balance(buy[0], quote_tick, -buy[2])
        put(buy[0], 'options', f'{win_pair}_buy', None, str(options_buy_id))
        if next_id is None:
            break
        options_buy_id = next_id

    put(addr, 'options', f'{win_pair}_sell_start', None)
    put(addr, 'options', f'{win_pair}_sell_new', None)
    put(addr, 'options', f'{win_pair}_buy_start', None)
    put(addr, 'options', f'{win_pair}_buy_new', None)

    win_balance_new, _ = get('options', f'{win_pair}_balance_new', None)
    current_addr = win_balance_new
    while current_addr is not None:
        balance_tuple, _ = get('options', f'{win_pair}_balance', None, current_addr)
        if balance_tuple is None:
            break
        balance, prev = balance_tuple
        assert balance >= 0
        _update_quote_balance(current_addr, quote_tick, balance)
        put(current_addr, 'options', f'{win_pair}_balance', None, current_addr)
        current_addr = prev
    put(addr, 'options', f'{win_pair}_balance_new', None)

    lose_pair = f'{slug}_{lose_tick}'
    lose_sell_start, _ = get('options', f'{lose_pair}_sell_start', 1)
    lose_buy_start, _ = get('options', f'{lose_pair}_buy_start', 1)

    options_sell_id = lose_sell_start
    while True:
        sell, _ = get('options', f'{lose_pair}_sell', None, str(options_sell_id))
        if not sell:
            break
        next_id = sell[4]
        put(sell[0], 'options', f'{lose_pair}_sell', None, str(options_sell_id))
        if next_id is None:
            break
        options_sell_id = next_id

    options_buy_id = lose_buy_start
    while True:
        buy, _ = get('options', f'{lose_pair}_buy', None, str(options_buy_id))
        if not buy:
            break
        next_id = buy[4]
        put(buy[0], 'options', f'{lose_pair}_buy', None, str(options_buy_id))
        if next_id is None:
            break
        options_buy_id = next_id

    put(addr, 'options', f'{lose_pair}_sell_start', None)
    put(addr, 'options', f'{lose_pair}_sell_new', None)
    put(addr, 'options', f'{lose_pair}_buy_start', None)
    put(addr, 'options', f'{lose_pair}_buy_new', None)

    balance_new, _ = get('options', f'{lose_pair}_balance_new', None)
    current_addr = balance_new
    while current_addr is not None:
        balance_tuple, _ = get('options', f'{lose_pair}_balance', None, current_addr)
        if balance_tuple is None:
            break
        _, prev = balance_tuple
        put(current_addr, 'options', f'{lose_pair}_balance', None, current_addr)
        current_addr = prev
    put(addr, 'options', f'{lose_pair}_balance_new', None)

    put(addr, 'options', f'{slug}_quote_token', None)
    event('OptionsSubmit', [slug, call_or_put])


def options_set_quote_token(info, args):
    assert args['f'] == 'options_set_quote_token'
    sender = info['sender']
    addr = handle_lookup(sender)

    manager, _ = get('options', 'manager', None)
    assert manager is not None, "Manager not set"
    assert addr == manager, "Only the manager can add quote tokens"

    new_tokens = args['a'][0]
    assert isinstance(new_tokens, list), "Quote tokens must be a list"

    quote_tokens, _ = get('options', 'quote_tokens', [])

    for token in new_tokens:
        assert isinstance(token, str), "Token ticker must be a string"
        assert set(token) <= set(string.ascii_uppercase+'_'), "Invalid characters in token ticker"
        if token not in quote_tokens:
            quote_tokens.append(token)

    put(addr, 'options', 'quote_tokens', quote_tokens)


def options_update_manager(info, args):
    assert args['f'] == 'options_update_manager'
    sender = info['sender']
    addr = handle_lookup(sender)

    manager, _ = get('options', 'manager', None)
    if manager is not None:
        assert addr == manager, "Only the current manager can change manager"

    user = args['a'][0]
    assert isinstance(user, str), "User address must be a string"
    put(addr, 'options', 'manager', user)
    event('OptionsUpdateManager', [addr, user])


def options_vote_manager(info, args):
    assert args['f'] == 'options_vote_manager'
    sender = info['sender']
    addr = handle_lookup(sender)

    manager, _ = get('options', 'manager', None)
    assert manager is None, "Manager already set, use options_set_manager instead"

    committee_members, _ = get('committee', 'members', [])
    committee_members = set(committee_members)
    assert addr in committee_members, "Only committee members can vote"

    user = args['a'][0]
    assert isinstance(user, str), "User address must be a string"

    proposal_key = f'options_manager:{user}'
    votes, _ = get('committee', 'proposal', [], proposal_key)
    votes = set(votes)
    votes.add(addr)

    if len(votes) >= len(committee_members) * 2 // 3:
        put(addr, 'options', 'manager', user)
        put(addr, 'committee', 'proposal', [], proposal_key)
        event('OptionsUpdateManager', [list(votes), user])
    else:
        put(addr, 'committee', 'proposal', list(votes), proposal_key)

