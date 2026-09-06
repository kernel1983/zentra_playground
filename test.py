
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

    call_zip_func('asset_create', '0x002', ['USDC'])
    call_zip_func('token_create', '0x002', ['USDC', 'mock', 6])
    call_zip_func('token_mint_once', '0x002', ['USDC', 1000 * 10**6])
    call_zip_func('token_transfer', '0x002', ['USDC', '0x001', 50 * 10**6])
    call_zip_func('token_transfer', '0x002', ['USDC', '0x003', 50 * 10**6])

    call_zip_func('predict_vote_manager', '0x002', ['0x002'])
    call_zip_func('predict_set_quote_token', '0x002', [['USDC']])
    call_zip_func('predict_create', '0x002', ['btc_5min', 'USDC'])
    call_zip_func('predict_mint', '0x002', ['btc_5min', 15 * 10**6])


def test():
    prepare()


def test1():
    prepare()

    # limit orders + market orders
    print('=test1 1 predict_limit_order')
    call_zip_func('predict_limit_order', '0x002', ['btc_5min', 10 * 10**6, 'yes', -10 * 50 * 10**4]) # buy 10 yes at 50 cents

    print('=test1 2 predict_limit_order')
    call_zip_func('predict_limit_order', '0x002', ['btc_5min', -10 * 10**6, 'yes', 10 * 51 * 10**4]) # sell 10 yes at 51 cents

    print('=test1 3 predict_market_order')
    call_zip_func('predict_market_order', '0x001', ['btc_5min', None, 'yes', -2 * 10**6]) # pay 2U to get yes at market price

    print('=test1 4 predict_market_order')
    call_zip_func('predict_market_order', '0x001', ['btc_5min', -3 * 10**6, 'yes', None])
    return

    print('=test1 5 predict_limit_order')
    call_zip_func('predict_limit_order', '0x002', ['btc_5min', 10, 'USDC', -10])

    print('=test1 6 predict_limit_order')
    call_zip_func('predict_limit_order', '0x002', ['btc_5min', 11, 'USDC', -11])


def test1b():
    prepare()

    print('=test1b 1 predict_limit_order')
    call_zip_func('predict_limit_order', '0x002', ['BTC', -10, 'USDT', 10])


    print('=test1b 2 predict_limit_order')
    call_zip_func('predict_limit_order', '0x002', ['BTC', -11, 'USDT', 11])


    print('=test1b 3 predict_market_order')
    call_zip_func('predict_market_order', '0x002', ['BTC', -22, 'USDT', None])


    print('=test1b 4 predict_market_order')
    call_zip_func('predict_market_order', '0x001', ['BTC', None, 'USDT', -20])


    print('=test1b 5 predict_market_order')
    call_zip_func('predict_market_order', '0x001', ['BTC', None, 'USDT', -10])


    print('=test1b 6 predict_limit_order')
    call_zip_func('predict_limit_order', '0x002', ['BTC', -10, 'USDT', 10])


    print('=test1b 7 predict_limit_order')
    call_zip_func('predict_limit_order', '0x002', ['BTC', -11, 'USDT', 11])


def test2():
    prepare()

    call_zip_func('predict_mint', '0x001', ['btc_5min', 20 * 10**6])
    call_zip_func('predict_mint', '0x003', ['btc_5min', 30 * 10**6])
    call_zip_func('predict_mint', '0x002', ['btc_5min', 6 * 10**6])

    call_zip_func('predict_limit_order', '0x002', ['btc_5min', -10 * 10**6, 'yes', 10 * 50 * 10**4])
    call_zip_func('predict_limit_order', '0x002', ['btc_5min', -10 * 10**6, 'yes', 10 * 50 * 10**4])
    #call_zip_func('predict_limit_order', '0x001', ['btc_5min', 10 * 10**6, 'yes', -10 * 50 * 10**4])
    call_zip_func('predict_limit_order', '0x002', ['btc_5min', -10 * 10**6, 'no', 10 * 50 * 10**4])
    call_zip_func('predict_limit_order', '0x001', ['btc_5min', 10 * 10**6, 'no', -10 * 50 * 10**4])

    call_zip_func('predict_limit_order', '0x002', ['btc_5min', 10 * 10**6, 'yes', -10 * 49 * 10**4])
    call_zip_func('predict_limit_order', '0x002', ['btc_5min', 10 * 10**6, 'yes', -10 * 49 * 10**4])

    call_zip_func('predict_submit', '0x002', ['btc_5min', 'yes'])


def test2b():
    prepare()

    call_zip_func('predict_mint', '0x001', ['btc_5min', 20 * 10**6])
    call_zip_func('predict_mint', '0x003', ['btc_5min', 30 * 10**6])
    call_zip_func('predict_mint', '0x002', ['btc_5min', 6 * 10**6])

    call_zip_func('predict_limit_order', '0x002', ['btc_5min', -10 * 10**6, 'yes', 10 * 50 * 10**4])
    call_zip_func('predict_market_order', '0x001', ['btc_5min', 3 * 10**6, 'yes', None])
    call_zip_func('predict_market_order', '0x003', ['btc_5min', 4 * 10**6, 'yes', None])

    call_zip_func('predict_submit', '0x002', ['btc_5min', 'yes'])


def test3():
    prepare()

    # limit orders buy and sell
    print('=test3 1 predict_limit_order')
    call_zip_func('predict_limit_order', '0x002', ['BTC', 10, 'USDT', -10])
    print(space.states.get(space.latest_block_number - 1, {}))


    print('=test3 2 predict_limit_order')
    call_zip_func('predict_limit_order', '0x001', ['BTC', -11, 'USDT', 10])
    print(space.states.get(space.latest_block_number - 1, {}))


    print('=test3 3 predict_limit_order')
    call_zip_func('predict_limit_order', '0x002', ['BTC', 1, 'USDT', -1])
    print(space.states.get(space.latest_block_number - 1, {}))


# def test3b():
#     prepare()

#     # limit orders buy and sell
#     print('1======predict_limit_order')
#     funcs.predict_limit_order({'sender':'0x002'}, {'p': 'zen', 'f': 'predict_limit_order', 'a':['BTC', -10, 'USDT', 10]})
#     print(space.states.get(space.latest_block_number - 1, {}))
#

#     print('2======predict_limit_order')
#     funcs.predict_limit_order({'sender':'0x001'}, {'p': 'zen', 'f': 'predict_limit_order', 'a':['BTC', 11, 'USDT', -10]})
#     print(space.states.get(space.latest_block_number - 1, {}))
#

#     print('3======predict_limit_order')
#     funcs.predict_limit_order({'sender':'0x002'}, {'p': 'zen', 'f': 'predict_limit_order', 'a':['BTC', -1, 'USDT', 1]})
#     print(space.states.get(space.latest_block_number - 1, {}))
#


def test4():
    prepare()

    print('=test4 1 predict_limit_order')
    call_zip_func('predict_limit_order', '0x002', ['BTC', 10, 'USDT', -10])
    print(space.states.get(space.latest_block_number - 1, {}))


    print('=test4 2 predict_limit_order')
    call_zip_func('predict_limit_order', '0x002', ['BTC', 11, 'USDT', -10])
    print(space.states.get(space.latest_block_number - 1, {}))


    print('=test4 3 predict_limit_order')
    call_zip_func('predict_limit_order', '0x002', ['BTC', 14, 'USDT', -10])
    print(space.states.get(space.latest_block_number - 1, {}))


    print('=test4 4 predict_limit_order')
    call_zip_func('predict_limit_order', '0x002', ['BTC', 13, 'USDT', -10])
    print(space.states.get(space.latest_block_number - 1, {}))


    print('=test4 5 predict_limit_order')
    call_zip_func('predict_limit_order', '0x002', ['BTC', 110, 'USDT', -100])
    print(space.states.get(space.latest_block_number - 1, {}))



def test5():
    prepare()

    print('=test5 1 predict_limit_order')
    call_zip_func('predict_limit_order', '0x001', ['BTC', -10, 'USDT', 50])
    print(space.states.get(space.latest_block_number - 1, {}))


    print('=test5 2 predict_limit_order')
    call_zip_func('predict_limit_order', '0x001', ['BTC', -10, 'USDT', 60])
    print(space.states.get(space.latest_block_number - 1, {}))


    print('=test5 3 predict_limit_order')
    call_zip_func('predict_limit_order', '0x001', ['BTC', -10, 'USDT', 70])
    print(space.states.get(space.latest_block_number - 1, {}))


    print('=test5 4 predict_limit_order')
    call_zip_func('predict_limit_order', '0x001', ['BTC', -10, 'USDT', 80])
    print(space.states.get(space.latest_block_number - 1, {}))


    print('=test5 5 predict_limit_order')
    call_zip_func('predict_limit_order', '0x001', ['BTC', -10, 'USDT', 60])
    print(space.states.get(space.latest_block_number - 1, {}))



# def test6():
#     prepare()

#     print('1======predict_limit_order')
#     funcs.predict_limit_order({'sender':'0x002'}, {'p': 'zen', 'f': 'predict_limit_order', 'a':['BTC', 10, 'USDT', -10]})
#     print(space.states.get(space.latest_block_number - 1, {}))
#

#     print('2======predict_limit_order')
#     funcs.predict_limit_order({'sender':'0x002'}, {'p': 'zen', 'f': 'predict_limit_order', 'a':['BTC', 20, 'USDT', -20]})
#     print(space.states.get(space.latest_block_number - 1, {}))
#

#     print('3======predict_market_order')
#     funcs.predict_market_order({'sender':'0x002'}, {'p': 'zen', 'f': 'predict_market_order', 'a':['BTC', -5, 'USDT', None]})
#     print(space.states.get(space.latest_block_number - 1, {}))
#

#     print('4======predict_market_order')
#     funcs.predict_market_order({'sender':'0x002'}, {'p': 'zen', 'f': 'predict_market_order', 'a':['BTC', -3, 'USDT', None]})
#     print(space.states.get(space.latest_block_number - 1, {}))
#

#     print('5======predict_market_order')
#     funcs.predict_market_order({'sender':'0x001'}, {'p': 'zen', 'f': 'predict_market_order', 'a':['BTC', -30, 'USDT', None]})
#     print(space.states.get(space.latest_block_number - 1, {}))
#


def test7():
    prepare()

    print('=test7 1 predict_limit_order')
    call_zip_func('predict_limit_order', '0x002', ['BTC', -10, 'USDT', 10])
    print(space.states.get(space.latest_block_number - 1, {}))


    print('=test7 2 predict_limit_order')
    call_zip_func('predict_limit_order', '0x001', ['BTC', -9, 'USDT', 10])
    print(space.states.get(space.latest_block_number - 1, {}))


    print('=test7 3 predict_limit_order')
    call_zip_func('predict_limit_order', '0x001', ['BTC', -17, 'USDT', 20])
    print(space.states.get(space.latest_block_number - 1, {}))



    print('=test7 4 predict_limit_order')
    call_zip_func('predict_limit_order', '0x002', ['BTC', -11, 'USDT', 10])
    print(space.states.get(space.latest_block_number - 1, {}))


    print('=test7 5 predict_limit_order')
    call_zip_func('predict_limit_order', '0x001', ['BTC', -12, 'USDT', 10])
    print(space.states.get(space.latest_block_number - 1, {}))


    print('=test7 6 predict_limit_order')
    call_zip_func('predict_limit_order', '0x001', ['BTC', -25, 'USDT', 20])
    print(space.states.get(space.latest_block_number - 1, {}))

    print('=test7 7 predict_limit_order')
    call_zip_func('predict_limit_order', '0x001', ['BTC', 10, 'USDT', -10])
    print(space.states.get(space.latest_block_number - 1, {}))


def test8():
    prepare()

    print('=test8 1 predict_limit_order')
    call_zip_func('predict_limit_order', '0x002', ['BTC', 10, 'USDT', -10])
    print(space.states.get(space.latest_block_number - 1, {}))


    print('=test8 2 predict_limit_order')
    call_zip_func('predict_limit_order', '0x001', ['BTC', 9, 'USDT', -10])
    print(space.states.get(space.latest_block_number - 1, {}))


    print('=test8 3 predict_limit_order')
    call_zip_func('predict_limit_order', '0x001', ['BTC', 17, 'USDT', -20])
    print(space.states.get(space.latest_block_number - 1, {}))


    print('=test8 4 predict_limit_order')
    call_zip_func('predict_limit_order', '0x002', ['BTC', 11, 'USDT', -10])
    print(space.states.get(space.latest_block_number - 1, {}))


    print('=test8 5 predict_limit_order')
    call_zip_func('predict_limit_order', '0x001', ['BTC', 12, 'USDT', -10])
    print(space.states.get(space.latest_block_number - 1, {}))


    print('=test8 6 predict_limit_order')
    call_zip_func('predict_limit_order', '0x001', ['BTC', 25, 'USDT', -20])
    print(space.states.get(space.latest_block_number - 1, {}))

    print('=test8 7 predict_limit_order')
    call_zip_func('predict_limit_order', '0x001', ['BTC', -10, 'USDT', 10])
    print(space.states.get(space.latest_block_number - 1, {}))


#test()

#test1()
#test1b()
test2()
#test2b()
#test3()
# test3b()
#test4()
#test5()
# test6()
#test7()
#test8()

