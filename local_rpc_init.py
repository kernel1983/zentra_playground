
import sys
import hashlib
import json
import requests

import web3

import setting

PROVIDER_HOST = 'http://127.0.0.1:8545'

w3 = web3.Web3(web3.Web3.HTTPProvider(PROVIDER_HOST))

ZEN_ADDR = '0x00000000000000000000000000000000007A656e'# hex of 'zen'


def transaction(account, call):
    nonce = w3.eth.get_transaction_count(account.address)
    print(account.address, nonce)
    transaction = {
        'from': account.address,
        'to': ZEN_ADDR,
        'value': 0,
        'nonce': w3.eth.get_transaction_count(account.address),
        'data': call.encode('utf8'),
        'gas': 210000,
        'maxFeePerGas': 1000000000,
        'maxPriorityFeePerGas': 0,
        'chainId': setting.CHAIN_ID,
        # 'chainId': 31337,
    }

    signed = w3.eth.account.sign_transaction(transaction, account.key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return tx_hash.hex()

def next_block():
    resp = requests.post(PROVIDER_HOST, json={'jsonrpc': '2.0', 'method': 'zentra_nextBlock', 'id': 1})
    return resp.json()


if __name__ == '__main__':
    call = '{"p": "zen", "f": "asset_create", "a": ["USDC"]}'
    print(call)
    tx_hash = transaction(setting.accounts[0], call)
    print(tx_hash)

    call = '{"p": "zen", "f": "token_create", "a": ["USDC", "Mock USDC", 6]}'
    print(call)
    tx_hash = transaction(setting.accounts[0], call)
    print(tx_hash)


    call = '{"p": "zen", "f": "asset_create", "a": ["BTC"]}'
    print(call)
    tx_hash = transaction(setting.accounts[0], call)
    print(tx_hash)

    call = '{"p": "zen", "f": "token_create", "a": ["BTC", "Mock BTC", 18]}'
    print(call)
    tx_hash = transaction(setting.accounts[0], call)
    print(tx_hash)

    # 手动推进 block
    print('=== 调用 next block ===')
    result = next_block()
    print('next block result:', result)
