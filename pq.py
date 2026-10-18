"""Post-quantum (SLH-DSA / SPHINCS+ FIPS 205) transaction helpers.

This module is the single source of truth for encoding, signing and verifying
`eth_sendRawPQTransaction` payloads. It is deliberately independent from the
RPC server (no `rpc`/`space` imports) so the same code can be used by clients.

Raw payload layout (mirrors the EIP-typed transaction style, new type byte 0x03):

    raw = 0x03 || rlp([chain_id, nonce, gas_price, gas, to, value, data, pubkey, sig])

Signed message (no type byte, no pubkey/sig):

    msg = rlp([chain_id, nonce, gas_price, gas, to, value, data])

Signature is a FIPS 205 "pure" SLH-DSA signature over `msg` with ctx=b'zentra'.
The parameter set is fixed to SLH-DSA-SHA2-128s.
"""

import binascii
import hashlib

import rlp

import slhdsa
from slhdsa import PublicKey, SecretKey, KeyPair
from slhdsa.lowlevel.wots import WOTSParameter
from slhdsa.lowlevel.xmss import XMSS
from slhdsa.lowlevel.addresses import Address

try:
    from eth_utils import keccak
except ImportError:  # pragma: no cover
    from web3 import Web3
    keccak = web3.Web3.keccak


PARAM = slhdsa.sha2_128s
TYPE_BYTE = 3
CTX = b'zentra'

PK_LEN = PARAM.n * 2
SIG_LEN = (1 + PARAM.k * (PARAM.a + 1) + PARAM.h + PARAM.d * WOTSParameter(PARAM).len) * PARAM.n


def keygen():
    """Generate a fresh SLH-DSA-SHA2-128s key pair."""
    return slhdsa.KeyPair.gen(PARAM)


def from_seed(seed):
    """Derive a deterministic key pair from a seed (playground / testing)."""
    if isinstance(seed, str):
        seed = seed.encode('utf8')

    def derive(label):
        return hashlib.shake_256(seed + label).digest(PARAM.n)

    sk_seed = derive(b'-sk')
    sk_prf = derive(b'-prf')
    pk_seed = derive(b'-pk')
    address = Address(PARAM.d - 1, 0)
    pk_root = XMSS(PARAM).node(sk_seed, 0, PARAM.h_m, pk_seed, address)
    return slhdsa.SecretKey((sk_seed, sk_prf, pk_seed, pk_root), PARAM)


def address_from_pubkey(pubkey):
    """Derive an Ethereum-style 0x address from a SLH-DSA public key."""
    return '0x' + keccak(bytes(pubkey)).hex()[-40:]


def _to_bytes(value):
    if value is None:
        return b''
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, int):
        return value.to_bytes((value.bit_length() + 7) // 8, 'big') if value else b''
    if isinstance(value, str):
        v = value[2:] if value.startswith('0x') else value
        if v == '':
            return b''
        if len(v) % 2:
            v = '0' + v
        return bytes.fromhex(v)
    raise TypeError(f'unsupported value type: {type(value)}')


def build_raw_tx(chain_id, nonce, gas_price, gas, to, value, data, secret_key):
    """Encode and sign a transaction, returning the raw payload bytes."""
    to_bytes = _to_bytes(to)
    data_bytes = _to_bytes(data)

    unsigned = [chain_id, nonce, gas_price, gas, to_bytes, value, data_bytes]
    msg = rlp.encode(unsigned)

    pubkey = secret_key.pubkey.digest()
    sig = secret_key.sign_pure(msg, ctx=CTX)

    raw = rlp.encode(unsigned + [pubkey, sig])
    return b'\x03' + raw


def sign_raw_tx(chain_id, nonce, gas_price, gas, to, value, data, secret_key):
    """Same as build_raw_tx but returns a '0x'-prefixed hex string."""
    return '0x' + build_raw_tx(chain_id, nonce, gas_price, gas, to, value, data, secret_key).hex()


def decode_and_verify(raw_hex, chain_id):
    """Decode and verify a raw PQ transaction.

    Returns a dict with the transaction fields plus `tx_from`, `tx_hash_hex`
    and `raw`. Raises ValueError when the payload is malformed, targets another
    chain, or carries an invalid signature.
    """
    if raw_hex.startswith('0x') or raw_hex.startswith('0X'):
        raw_hex = raw_hex[2:]
    try:
        raw = bytes.fromhex(raw_hex)
    except ValueError:
        raise ValueError('raw transaction is not valid hex')

    if len(raw) == 0 or raw[0] != 3:
        raise ValueError('not a PQ transaction (expected type byte 0x03)')

    try:
        items = rlp.decode(raw[1:])
    except Exception:
        raise ValueError('raw transaction is not valid RLP')

    if len(items) != 9:
        raise ValueError(f'expected 9 fields, got {len(items)}')

    cid = int.from_bytes(items[0], 'big')
    if cid != chain_id:
        raise ValueError(f'wrong chain id: got {cid}, expected {chain_id}')

    pubkey = bytes(items[7])
    sig = bytes(items[8])
    if len(pubkey) != PK_LEN:
        raise ValueError(f'invalid public key length: {len(pubkey)} (expected {PK_LEN})')
    if len(sig) != SIG_LEN:
        raise ValueError(f'invalid signature length: {len(sig)} (expected {SIG_LEN})')

    msg = rlp.encode(items[0:7])
    pk = slhdsa.PublicKey.from_digest(pubkey, PARAM)
    if not pk.verify_pure(msg, sig, ctx=CTX):
        raise ValueError('invalid SLH-DSA signature')

    to_bytes = bytes(items[4])
    data_bytes = bytes(items[6])

    return {
        'chain_id': cid,
        'nonce': int.from_bytes(items[1], 'big'),
        'gas_price': int.from_bytes(items[2], 'big'),
        'gas': int.from_bytes(items[3], 'big'),
        'to': ('0x' + to_bytes.hex()) if to_bytes else None,
        'value': int.from_bytes(items[5], 'big'),
        'data': '0x' + data_bytes.hex(),
        'pubkey': pubkey,
        'sig': sig,
        'tx_from': address_from_pubkey(pubkey),
        'tx_hash_hex': keccak(raw).hex(),
        'raw': raw,
    }
