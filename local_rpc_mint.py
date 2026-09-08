import sys
import hashlib
import json

import web3

import setting

from test_rpc_init import *
from setting import accounts

if __name__ == '__main__':
    call = '{"p": "zen", "f": "token_mint_once", "a": ["USDC", 8595000000000000]}'
    print(call)
    tx_hash = transaction(accounts[0], call)
    print(tx_hash)

    call = '{"p": "zen", "f": "token_mint_once", "a": ["BTC", 2100000000000000000000]}'
    print(call)
    tx_hash = transaction(accounts[0], call)
    print(tx_hash)
