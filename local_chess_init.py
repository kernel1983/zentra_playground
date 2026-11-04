"""Initialize the on-chain chess + prediction environment.

Creates the USDC asset/token, mints a balance to every test account, and
registers USDC as the only chess quote token.

Usage:
    python local_chess_init.py
"""

import sys
import hashlib
import json

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


if __name__ == '__main__':
    creator = setting.accounts[0]

    call = '{"p": "zen", "f": "asset_create", "a": ["USDC"]}'
    print(call)
    print(transaction(creator, call))

    call = '{"p": "zen", "f": "token_create", "a": ["USDC", "Mock USDC", 6]}'
    print(call)
    print(transaction(creator, call))

    for account in setting.accounts:
        call = '{"p": "zen", "f": "token_mint_free", "a": ["USDC", %d]}' % (1000 * 10 ** 6)
        print(call)
        print(transaction(account, call))

    call = '{"p": "zentest3", "f": "chess_init", "a": [["USDC"]]}'
    print(call)
    print(transaction(creator, call))
