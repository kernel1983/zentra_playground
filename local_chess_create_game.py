import sys
import hashlib
import json
import requests

import web3

import setting

PROVIDER_HOST = 'http://127.0.0.1:8545'

w3 = web3.Web3(web3.Web3.HTTPProvider(PROVIDER_HOST))

ZEN_ADDR = '0x00000000000000000000000000000000007A656e'


def transaction(account, call):
    nonce = w3.eth.get_transaction_count(account.address)
    transaction = {
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

    signed = w3.eth.account.sign_transaction(transaction, account.key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return tx_hash.hex()


def next_block():
    resp = requests.post(PROVIDER_HOST, json={'jsonrpc': '2.0', 'method': 'zentra_nextBlock', 'id': 1})
    return resp.json()


if __name__ == '__main__':
    opp = None
    if len(sys.argv) > 1:
        opp = sys.argv[1]
    if opp:
        call = '{"p": "zentest3", "f": "chess_create_game", "a": ["%s"]}' % opp
    else:
        call = '{"p": "zentest3", "f": "chess_create_game", "a": []}'
    print(call)
    tx_hash = transaction(setting.accounts[0], call)
    print(tx_hash)
    result = next_block()
    print(result)
