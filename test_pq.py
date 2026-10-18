import hashlib
import json

import pytest

from eth_utils import keccak

import func
import pq
import rpc
import space

CHAIN_ID = rpc.CHAIN_ID

KEY = pq.from_seed(b'zentra-pq-test')
PK = KEY.pubkey.digest()
ADDR = pq.address_from_pubkey(PK)


def _reset():
    space.states = {0: {}}
    space.latest_block_number = 0
    space.blocks = {}
    space.block_hashes = {}
    space.block_times = {}
    space.transactions = {}
    space.events = {}
    space.nonces = {}
    space.sender = None
    func.load_all_zips()


def _request(method, params):
    handler = rpc.RPCHandler.__new__(rpc.RPCHandler)
    return handler.process_request({'jsonrpc': '2.0', 'method': method, 'params': params, 'id': 1})


def _data_hex(f='committee_init', a=None):
    payload = json.dumps({'p': 'zen', 'f': f, 'a': a if a is not None else []})
    return '0x' + payload.encode('utf8').hex()


def test_build_decode_roundtrip():
    to = '0x' + 'ab' * 20
    raw = pq.sign_raw_tx(CHAIN_ID, 3, 7, 50000, to, 123, _data_hex(), KEY)
    info = pq.decode_and_verify(raw, CHAIN_ID)

    assert info['chain_id'] == CHAIN_ID
    assert info['nonce'] == 3
    assert info['gas_price'] == 7
    assert info['gas'] == 50000
    assert info['to'] == to
    assert info['value'] == 123
    assert info['data'] == _data_hex()
    assert info['tx_from'] == ADDR
    assert info['tx_hash_hex'] == keccak(info['raw']).hex()
    assert info['pubkey'] == PK


def test_send_raw_pq_transaction():
    _reset()
    raw = pq.sign_raw_tx(CHAIN_ID, 0, 1, 21000, None, 0, _data_hex(), KEY)
    resp = _request('eth_sendRawPQTransaction', [raw])

    assert 'error' not in resp, resp
    tx_hash = resp['result']
    assert tx_hash.startswith('0x')

    tx_hash_hex = tx_hash[2:]
    assert space.nonces[ADDR] == 1

    tx = space.transactions[tx_hash_hex]
    assert tx['from'] == ADDR
    assert tx['nonce'] == 0
    assert tx['events'] == [{'event': 'CommitteeInit', 'args': [ADDR]}]

    by_hash = _request('eth_getTransactionByHash', [tx_hash])
    assert by_hash['result']['from'] == ADDR

    receipt = _request('eth_getTransactionReceipt', [tx_hash])
    assert receipt['result']['status'] == hex(1)


def test_bad_signature_rejected():
    _reset()
    raw = pq.sign_raw_tx(CHAIN_ID, 0, 1, 21000, None, 0, _data_hex(), KEY)
    tampered = bytearray(bytes.fromhex(raw[2:]))
    tampered[-1] ^= 0x01

    resp = _request('eth_sendRawPQTransaction', ['0x' + tampered.hex()])

    assert 'error' in resp
    assert 'signature' in resp['error']['message']
    assert space.nonces.get(ADDR, 0) == 0


def test_wrong_chain_id_rejected():
    _reset()
    raw = pq.sign_raw_tx(CHAIN_ID + 1, 0, 1, 21000, None, 0, _data_hex(), KEY)
    resp = _request('eth_sendRawPQTransaction', [raw])

    assert 'error' in resp
    assert 'chain id' in resp['error']['message']


def test_nonce_mismatch_rejected():
    _reset()
    raw = pq.sign_raw_tx(CHAIN_ID, 5, 1, 21000, None, 0, _data_hex(), KEY)
    resp = _request('eth_sendRawPQTransaction', [raw])

    assert 'error' in resp
    assert 'nonce mismatch' in resp['error']['message']
    assert space.nonces.get(ADDR, 0) == 0


def test_eth_send_raw_transaction_still_works():
    from eth_account import Account

    _reset()
    acct = Account.from_key(hashlib.sha256(b'brownie0').digest())
    tx = {
        'nonce': 0,
        'gasPrice': 1,
        'gas': 21000,
        'to': acct.address,
        'value': 0,
        'data': _data_hex(),
        'chainId': CHAIN_ID,
    }
    signed = acct.sign_transaction(tx)
    raw = getattr(signed, 'rawTransaction', None) or signed.raw_transaction
    resp = _request('eth_sendRawTransaction', ['0x' + bytes(raw).hex()])

    assert 'error' not in resp, resp
    tx_hash_hex = resp['result'][2:]
    sender = acct.address.lower()
    assert space.nonces[sender] == 1
    assert space.transactions[tx_hash_hex]['from'] == sender
    assert space.transactions[tx_hash_hex]['events'] == [{'event': 'CommitteeInit', 'args': [sender]}]


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-v']))
