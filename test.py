
# import code
# import readline
# import rlcompleter

import space
from play import GLOBAL_FUNCTIONS

def call_zip_func(name, sender, args):
    print(space.latest_block_number, sender, name, args)
    space.sender = sender
    func = GLOBAL_FUNCTIONS[name]
    res = func(*args)
    for k, v in space.states[space.latest_block_number].items():
        print(k, v)
    print('')
    space.nextblock()
    return res

def prepare():
    space.states = {0: {}}
    call_zip_func('committee_init', '0x002', [])

    call_zip_func('asset_create', '0x002', ['BTC'])
    call_zip_func('token_create', '0x002', ['BTC', 'mock', 6])
    call_zip_func('token_mint_once', '0x002', ['BTC', 1000 * 10**6])
    call_zip_func('token_transfer', '0x002', ['BTC', '0x001', 50 * 10**6])
    call_zip_func('token_transfer', '0x002', ['BTC', '0x003', 50 * 10**6])

    call_zip_func('asset_create', '0x002', ['USDC'])
    call_zip_func('token_create', '0x002', ['USDC', 'mock', 6])
    call_zip_func('token_mint_once', '0x002', ['USDC', 1000 * 10**6])
    call_zip_func('token_transfer', '0x002', ['USDC', '0x001', 50 * 10**6])
    call_zip_func('token_transfer', '0x002', ['USDC', '0x003', 50 * 10**6])

    call_zip_func('options_vote_manager', '0x002', ['0x002'])
    call_zip_func('options_set_quote_token', '0x002', [['USDC']])
    call_zip_func('options_create', '0x002', ['btc_5min', 'USDC'])
    call_zip_func('options_mint', '0x002', ['btc_5min', 15 * 10**6])


def test():
    prepare()


def test1():
    prepare()

    # limit orders + market orders
    call_zip_func('options_limit_buy', '0x002', ['btc_5min', 10 * 10**6, 'call', -10 * 50 * 10**4]) # buy 10 yes at 50 cents
    call_zip_func('options_limit_buy', '0x002', ['btc_5min', -10 * 10**6, 'call', 10 * 51 * 10**4]) # sell 10 yes at 51 cents
    call_zip_func('options_market_order', '0x001', ['btc_5min', None, 'call', -2 * 10**6]) # pay 2U to get yes at market price
    call_zip_func('options_market_order', '0x001', ['btc_5min', -3 * 10**6, 'call', None])
    return

    print('=test1 5 options_limit_order')
    call_zip_func('options_limit_order', '0x002', ['btc_5min', 10, 'USDC', -10])

    print('=test1 6 options_limit_order')
    call_zip_func('options_limit_order', '0x002', ['btc_5min', 11, 'USDC', -11])


def test1b():
    prepare()

    print('=test1b 1 options_limit_order')
    call_zip_func('options_limit_order', '0x002', ['BTC', -10, 'USDT', 10])

    print('=test1b 2 options_limit_order')
    call_zip_func('options_limit_order', '0x002', ['BTC', -11, 'USDT', 11])

    print('=test1b 3 options_market_order')
    call_zip_func('options_market_order', '0x002', ['BTC', -22, 'USDT', None])

    print('=test1b 4 options_market_order')
    call_zip_func('options_market_order', '0x001', ['BTC', None, 'USDT', -20])

    print('=test1b 5 options_market_order')
    call_zip_func('options_market_order', '0x001', ['BTC', None, 'USDT', -10])

    print('=test1b 6 options_limit_order')
    call_zip_func('options_limit_order', '0x002', ['BTC', -10, 'USDT', 10])

    print('=test1b 7 options_limit_order')
    call_zip_func('options_limit_order', '0x002', ['BTC', -11, 'USDT', 11])


def test2():
    prepare()

    call_zip_func('options_mint', '0x001', ['btc_5min', 20 * 10**6])
    call_zip_func('options_mint', '0x003', ['btc_5min', 30 * 10**6])
    call_zip_func('options_mint', '0x002', ['btc_5min', 6 * 10**6])

    call_zip_func('options_limit_order', '0x002', ['btc_5min', -10 * 10**6, 'yes', 10 * 50 * 10**4])
    call_zip_func('options_limit_order', '0x002', ['btc_5min', -10 * 10**6, 'yes', 10 * 50 * 10**4])
    #call_zip_func('options_limit_order', '0x001', ['btc_5min', 10 * 10**6, 'yes', -10 * 50 * 10**4])
    call_zip_func('options_limit_order', '0x002', ['btc_5min', -10 * 10**6, 'no', 10 * 50 * 10**4])
    call_zip_func('options_limit_order', '0x001', ['btc_5min', 10 * 10**6, 'no', -10 * 50 * 10**4])

    call_zip_func('options_limit_order', '0x002', ['btc_5min', 10 * 10**6, 'yes', -10 * 49 * 10**4])
    call_zip_func('options_limit_order', '0x002', ['btc_5min', 10 * 10**6, 'yes', -10 * 49 * 10**4])

    call_zip_func('options_submit', '0x002', ['btc_5min', 'yes'])


def test2b():
    prepare()

    call_zip_func('options_mint', '0x001', ['btc_5min', 20 * 10**6])
    call_zip_func('options_mint', '0x003', ['btc_5min', 30 * 10**6])
    call_zip_func('options_mint', '0x002', ['btc_5min', 6 * 10**6])

    call_zip_func('options_limit_order', '0x002', ['btc_5min', -10 * 10**6, 'yes', 10 * 50 * 10**4])
    call_zip_func('options_market_order', '0x001', ['btc_5min', 3 * 10**6, 'yes', None])
    call_zip_func('options_market_order', '0x003', ['btc_5min', 4 * 10**6, 'yes', None])

    call_zip_func('options_submit', '0x002', ['btc_5min', 'yes'])


def test3():
    prepare()

    # limit orders buy and sell
    call_zip_func('options_limit_order', '0x002', ['BTC', 10, 'USDT', -10])
    print(space.states.get(space.latest_block_number - 1, {}))

    call_zip_func('options_limit_order', '0x001', ['BTC', -11, 'USDT', 10])
    print(space.states.get(space.latest_block_number - 1, {}))

    call_zip_func('options_limit_order', '0x002', ['BTC', 1, 'USDT', -1])
    print(space.states.get(space.latest_block_number - 1, {}))


#test()

test1()
#test1b()
#test2()
#test2b()
#test3()
# test3b()
#test4()
#test5()
# test6()
#test7()
#test8()

