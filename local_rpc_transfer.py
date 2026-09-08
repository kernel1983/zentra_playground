import sys
import hashlib
import json

import web3

import setting

from test_rpc_init import *
from setting import accounts

if __name__ == '__main__':
    for i in range(1, 10):
        to = accounts[i].address.lower()
        call = '{"p": "zen", "f": "token_transfer", "a": ["USDC", "%s", 15000000000000]}' % to
        print(call)
        tx_hash = transaction(accounts[0], call)
        print(tx_hash)

        call = '{"p": "zen", "f": "token_transfer", "a": ["BTC", "%s", 100000000000000000000]}' % to
        print(call)
        tx_hash = transaction(accounts[0], call)
        print(tx_hash)


    print('=== next block ===')
    next_block()
