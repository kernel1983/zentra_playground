"""A minimal SLH-DSA (SPHINCS+ / FIPS 205) wallet.

The wallet keeps a single SLH-DSA-SHA2-128s key pair in a local JSON file.
If the file does not exist yet, a new key pair is generated and stored. The
secret key is stored in plain hex (not encrypted) on purpose, as this is a
playground wallet.

Usage as a library:

    import wallet_slhdsa
    w = wallet_slhdsa.Wallet()          # loads or creates wallet_slhdsa.json
    print(w.address)
    raw = w.sign_tx(nonce=0, to='0x...', value=0, data='0x7b7d')

Usage from the command line:

    python wallet_slhdsa.py                       # load or create, print address
    python wallet_slhdsa.py --new                 # force a fresh key pair
    python wallet_slhdsa.py --send '{"p":"zen"}'  # sign and send a tx to the RPC node
    python wallet_slhdsa.py --send '{"p":"zen","f":"committee_init","a":[]}' --to 0x...
"""

import argparse
import json
import os

import pq
import wallet_common


DEFAULT_KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wallet_slhdsa.json')

KEY_TYPE = 'slh-dsa-sha2-128s'
RPC_METHOD = 'eth_sendRawPQTransaction'


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
        return self.key.pubkey.digest()

    @property
    def secret_key(self):
        return self.key.digest()

    @property
    def address(self):
        return pq.address_from_pubkey(self.public_key)

    # -- persistence ----------------------------------------------------
    def load(self):
        with open(self.path, 'r') as f:
            data = json.load(f)
        if data.get('type') != KEY_TYPE:
            raise ValueError(f"unsupported key type: {data.get('type')}")
        self.key = pq.SecretKey.from_digest(bytes.fromhex(data['secret_key']), pq.PARAM)
        return self.key

    def create(self):
        self.key = pq.keygen().sec
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
        return pq.sign_raw_tx(chain_id, nonce, gas_price, gas, to, value, data, self.key)

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
        return f'<WalletSLHDSA {self.address} file={self.path}>'


def main():
    parser = argparse.ArgumentParser(description='SLH-DSA wallet')
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
