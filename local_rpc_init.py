import json

import requests
import web3

import setting

PROVIDER_HOST = 'http://127.0.0.1:8545'

# address that the playground treats as the "zen" system contract
ZEN_ADDR = '0x00000000000000000000000000000000007A656e'  # hex of 'zen'

w3 = web3.Web3(web3.Web3.HTTPProvider(PROVIDER_HOST))


def rpc(method, params=None):
    payload = {'jsonrpc': '2.0', 'method': method, 'params': params or [], 'id': 1}
    return requests.post(PROVIDER_HOST, json=payload).json()


def next_block():
    return rpc('zentra_nextBlock')


def state(key):
    resp = requests.get(f'{PROVIDER_HOST}/api/get_latest_state', params={'prefix': key})
    return resp.json().get('result')


def send(account, data):
    """Sign `data` (a zentest3 call dict or a raw JSON string) with `account`
    and push it through eth_sendRawTransaction.

    Returns the raw JSON-RPC response dict. The playground writes state before
    it runs funcs_reload, so a call can return an error while still having
    changed state (this is expected here: funcs_reload is not implemented).
    """
    if isinstance(data, dict):
        data = json.dumps(data)
    tx = {
        'from': account.address,
        'to': ZEN_ADDR,
        'value': 0,
        'nonce': w3.eth.get_transaction_count(account.address),
        'data': data.encode('utf8'),
        'gas': 210000,
        'maxFeePerGas': 1000000000,
        'maxPriorityFeePerGas': 0,
        'chainId': setting.CHAIN_ID,
    }
    signed = w3.eth.account.sign_transaction(tx, account.key)
    raw = signed.raw_transaction.hex()
    if not raw.startswith('0x'):
        raw = '0x' + raw
    return rpc('eth_sendRawTransaction', [raw])


def call(account, func_name, args=None, label=None):
    resp = send(account, {'p': 'zentest3', 'f': func_name, 'a': args or []})
    name = label or func_name
    if 'error' in resp:
        err = resp['error']
        msg = err.get('message', err) if isinstance(err, dict) else err
        print(f'  [warn] {name}: {msg}')
    else:
        print(f'  [ok]   {name}: {resp.get("result")}')
    return resp


def committee_members():
    members = state('committee-members')
    return list(members) if members else []


def bootstrap_committee(size=3, proposer_index=0):
    """Make sure the committee exists and has up to `size` members."""
    proposer = setting.accounts[proposer_index]
    if not committee_members():
        call(proposer, 'committee_init', [], label='committee_init')
    members = committee_members()
    for account in setting.accounts:
        if len(members) >= size:
            break
        addr = account.address.lower()
        if addr in members:
            continue
        call(proposer, 'committee_add_member', [addr],
             label=f'committee_add_member({addr[:10]}...)')
        members = committee_members()
    return members


def votes_needed(members):
    return max(len(members) * 2 // 3, 1)
