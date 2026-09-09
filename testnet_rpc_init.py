import sys
import json
import time
import getpass
import requests

import web3

RPC_URL = 'https://sepolia.base.org'  # public Base Sepolia RPC
INDEXER_URL = 'https://testnet3.zentra.dev'  # indexer: read state/events
CHAIN_ID = 84532  # Base Sepolia

w3 = web3.Web3(web3.Web3.HTTPProvider(RPC_URL))

ZEN_ADDR = '0x00000000000000000000000000000000007A656e'  # hex of 'zen'


def transaction(account, call):
    nonce = w3.eth.get_transaction_count(account.address)
    print(account.address, nonce)
    transaction = {
        'from': account.address,
        'to': ZEN_ADDR,
        'value': 0,
        'nonce': nonce,
        'data': call.encode('utf8'),
        'gas': 210000,
        'maxFeePerGas': w3.eth.gas_price,
        'maxPriorityFeePerGas': 0,
        'chainId': CHAIN_ID,
    }

    signed = w3.eth.account.sign_transaction(transaction, account.key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return tx_hash.hex()


def state(key):
    resp = requests.get(f'{INDEXER_URL}/api/get_latest_state?prefix=base-{key}')
    return resp.json().get('result')


def next_block():
    # Base Sepolia can't be manually advanced (zentra_nextBlock is anvil-only).
    # Wait until a new block appears (Base Sepolia produces blocks every ~2s).
    start = w3.eth.block_number
    while w3.eth.block_number == start:
        time.sleep(1)
    return w3.eth.block_number


def load_account_entry(entry, password=None):
    if isinstance(entry, dict) and ('crypto' in entry or 'Crypto' in entry):
        if password is None:
            while True:
                password = getpass.getpass('keystore password: ')
                try:
                    key = web3.Account.decrypt(entry, password)
                    break
                except ValueError:
                    print('Wrong password, try again.')
        else:
            key = web3.Account.decrypt(entry, password)
        account = web3.Account.from_key(key)
        expected = str(entry.get('address', '')).lower().replace('0x', '')
        if expected and account.address.lower().replace('0x', '') != expected:
            raise ValueError(
                f'decrypted address {account.address} != keystore address {entry.get("address")}')
        return account, password
    return web3.Account.from_key(entry), password


def load_accounts(path):
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, dict) and ('crypto' in data or 'Crypto' in data):
        entries = [data]
    elif isinstance(data, dict):
        entries = list(data.values())
    else:
        entries = data
    accounts = []
    password = None
    for entry in entries:
        account, password = load_account_entry(entry, password)
        accounts.append(account)
    return accounts


def predict_init(account):
    me = account.address.lower()
    steps = []
    if not state('committee-members'):
        transaction(account, '{"p":"zentest3","f":"committee_init","a":[]}')
        steps.append('committee_init')
        next_block()
    if state('predict-manager') is None:
        transaction(account,
                    '{"p":"zentest3","f":"predict_vote_manager","a":["%s"]}' % me)
        steps.append('predict_vote_manager')
        next_block()
    qt = state('predict-quote_tokens') or []
    if 'USDC' not in qt:
        transaction(account,
                    '{"p":"zentest3","f":"predict_set_quote_token","a":[["USDC"]]}')
        steps.append('predict_set_quote_token')
        next_block()
    return steps


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python testnet_rpc_init.py <accounts.json>')
        print('Example: python testnet_rpc_init.py m3.json')
        sys.exit(1)

    account = load_accounts(sys.argv[1])[0]
    print('init account:', account.address.lower())
    print('committee-members:', state('committee-members'))
    print('predict-manager   :', state('predict-manager'))
    print('predict-quote_tokens:', state('predict-quote_tokens'))

    steps = predict_init(account)
    print('\ninit done:', steps if steps else '(nothing needed)')
    print('committee-members:', state('committee-members'))
    print('predict-manager   :', state('predict-manager'))
    print('predict-quote_tokens:', state('predict-quote_tokens'))