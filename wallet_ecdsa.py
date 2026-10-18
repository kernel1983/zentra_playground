"""A minimal ECDSA (secp256k1) wallet.

The wallet keeps a single secp256k1 private key in a local JSON file. If the
file does not exist yet, a new key is generated and stored. The secret key is
stored in plain hex (not encrypted) on purpose, as this is a playground wallet.

Signed transactions are legacy EIP-155 transactions and are sent through the
standard `eth_sendRawTransaction` RPC method.

Usage as a library:

    import wallet_ecdsa
    w = wallet_ecdsa.Wallet()           # loads or creates wallet_ecdsa.json
    print(w.address)
    raw = w.sign_tx(nonce=0, to='0x...', value=0, data='0x7b7d')

Usage from the command line:

    python wallet_ecdsa.py                        # load or create, print address
    python wallet_ecdsa.py --new                  # force a fresh key
    python wallet_ecdsa.py --send '{"p":"zen"}'   # sign and send a tx to the RPC node
    python wallet_ecdsa.py --send '{"p":"zen","f":"committee_init","a":[]}' --to 0x...
"""

import argparse
import json
import os

from eth_account import Account
from eth_keys import keys
from eth_utils import to_checksum_address

import wallet_common


DEFAULT_KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wallet_ecdsa.json')

KEY_TYPE = 'ecdsa-secp256k1'
RPC_METHOD = 'eth_sendRawTransaction'


class Wallet:
    def __init__(self, path=DEFAULT_KEY_FILE, force_new=False):
        self.path = path
        self.key = None
        if force_new or not os.path.exists(self.path):
            self.create()
        else:
            self.load()

    # -- key material ---------------------------------------------------
    @property
    def public_key(self):
        return keys.PrivateKey(self.key).public_key.to_bytes()

    @property
    def secret_key(self):
        return self.key

    @property
    def address(self):
        return keys.PrivateKey(self.key).public_key.to_checksum_address().lower()

    @property
    def checksum_address(self):
        return keys.PrivateKey(self.key).public_key.to_checksum_address()

    # -- persistence ----------------------------------------------------
    def load(self):
        with open(self.path, 'r') as f:
            data = json.load(f)
        if data.get('type') != KEY_TYPE:
            raise ValueError(f"unsupported key type: {data.get('type')}")
        self.key = bytes.fromhex(data['secret_key'].replace('0x', ''))
        return self.key

    def create(self):
        self.key = os.urandom(32)
        self.save()
        return self.key

    def save(self):
        data = {
            'type': KEY_TYPE,
            'address': self.address,
            'public_key': self.public_key.hex(),
            'secret_key': self.secret_key.hex(),
        }
        with open(self.path, 'w') as f:
            json.dump(data, f, indent=2)
        return self.path

    # -- signing --------------------------------------------------------
    def sign_tx(self, nonce, to=None, value=0, data='0x', gas=21000, gas_price=0, chain_id=None):
        if chain_id is None:
            chain_id = wallet_common.DEFAULT_CHAIN_ID
        tx = {
            'nonce': nonce,
            'gasPrice': gas_price,
            'gas': gas,
            'value': value,
            'data': data,
            'chainId': chain_id,
        }
        if to is not None:
            # eth_account only accepts EIP-55 checksummed addresses here.
            tx['to'] = to_checksum_address(to)
        signed = Account.sign_transaction(tx, self.key)
        return '0x' + bytes(signed.raw_transaction).hex()

    def send_raw(self, rpc_url, raw):
        return wallet_common.rpc(rpc_url, RPC_METHOD, [raw])

    def sign_and_send(self, rpc_url, nonce=None, to=None, value=0, data='0x', gas=21000,
                      gas_price=0, chain_id=None):
        """Sign (filling in nonce/chain id from the node when omitted) and broadcast."""
        if chain_id is None:
            chain_id = wallet_common.get_chain_id(rpc_url)
        if nonce is None:
            nonce = wallet_common.get_nonce(rpc_url, self.address)
        raw = self.sign_tx(nonce, to=to, value=value, data=data, gas=gas,
                           gas_price=gas_price, chain_id=chain_id)
        return self.send_raw(rpc_url, raw)

    def __repr__(self):
        return f'<WalletECDSA {self.address} file={self.path}>'


def main():
    parser = argparse.ArgumentParser(description='ECDSA wallet')
    wallet_common.add_send_arguments(parser, DEFAULT_KEY_FILE)
    args = parser.parse_args()

    wallet = Wallet(args.keyfile, force_new=args.new)
    print('key file :', wallet.path)
    print('type     :', KEY_TYPE)
    print('address  :', wallet.address)
    print('publickey:', wallet.public_key.hex())

    if args.send is not None:
        tx_hash = wallet.sign_and_send(
            args.rpc, nonce=args.nonce, to=wallet_common.to_from_args(args),
            value=args.value, data=wallet_common.tx_data_from_args(args),
            gas=args.gas, gas_price=args.gas_price, chain_id=args.chain_id,
        )
        print('tx hash  :', tx_hash)


if __name__ == '__main__':
    main()
