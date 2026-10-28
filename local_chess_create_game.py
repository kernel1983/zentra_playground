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


if __name__ == '__main__':
    # Optional first argument is the black player's test-account index.
    # Without it, the game remains open until another account joins.
    opponent_index = None
    if len(sys.argv) > 1:
        opponent_index = int(sys.argv[1])
        if opponent_index < 0 or opponent_index >= len(setting.accounts):
            raise ValueError('opponent account index is out of range')

    if opponent_index is not None:
        opponent = setting.accounts[opponent_index].address
        call = '{"p": "zentest3", "f": "chess_create_game", "a": ["%s"]}' % opponent
        print('white account: 0')
        print('black account: %s (%s)' % (opponent_index, opponent))
    else:
        call = '{"p": "zentest3", "f": "chess_create_game", "a": []}'
        print('white account: 0')
        print('black account: open game')
    print(call)
    tx_hash = transaction(setting.accounts[0], call)
    print(tx_hash)
