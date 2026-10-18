"""Shared helpers for the playground wallets.

Only depends on the standard library, so it can be imported by both
`wallet_ecdsa.py` and `wallet_slhdsa.py` without pulling in web3.
"""

import json
import urllib.request


DEFAULT_RPC_URL = 'http://127.0.0.1:8545'
DEFAULT_CHAIN_ID = 31337

# Default recipient for playground transactions: the hex of b'zen'.
ZEN_ADDRESS = '0x00000000000000000000000000000000007a656e'

# Accepted by --to to mean "no recipient" (contract creation).
NO_RECIPIENT = ('', '-', 'none', 'None', 'null')


def rpc(url, method, params=None):
    """Perform a single JSON-RPC call and return its `result`."""
    payload = json.dumps({
        'jsonrpc': '2.0',
        'method': method,
        'params': params or [],
        'id': 1,
    }).encode('utf8')
    request = urllib.request.Request(url, data=payload,
                                     headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.loads(response.read().decode('utf8'))
    if 'error' in data:
        raise RuntimeError(data['error'].get('message', data['error']))
    return data.get('result')


def get_chain_id(url=DEFAULT_RPC_URL):
    return int(rpc(url, 'eth_chainId'), 16)


def get_nonce(url, address):
    return int(rpc(url, 'eth_getTransactionCount', [address, 'latest']), 16)


def get_gas_price(url=DEFAULT_RPC_URL):
    return int(rpc(url, 'eth_gasPrice'), 16)


def add_send_arguments(parser, keyfile_default):
    """Add the argument set shared by both wallets."""
    parser.add_argument('--keyfile', default=keyfile_default, help='path to the key file')
    parser.add_argument('--new', action='store_true', help='force generating a new key')
    parser.add_argument('--rpc', default=DEFAULT_RPC_URL, help='RPC endpoint')
    parser.add_argument('--send', nargs='?', const='', default=None, metavar='PAYLOAD',
                        help="sign and send a transaction; PAYLOAD is the JSON call payload "
                             "as text, e.g. '{\"p\":\"zen\",\"f\":\"committee_init\",\"a\":[]}' "
                             "(use --data to pass raw hex instead)")
    parser.add_argument('--to', default=ZEN_ADDRESS,
                        help=f'recipient address (default: {ZEN_ADDRESS}; pass "none" for none)')
    parser.add_argument('--value', type=int, default=0, help='value to transfer')
    parser.add_argument('--data', default=None, help='raw hex tx data (alternative to PAYLOAD)')
    parser.add_argument('--nonce', type=int, default=None, help='nonce (default: query the node)')
    parser.add_argument('--gas', type=int, default=21000, help='gas limit')
    parser.add_argument('--gas-price', type=int, default=0, help='gas price')
    parser.add_argument('--chain-id', type=int, default=None, help='chain id (default: query the node)')
    return parser


def tx_data_from_args(args):
    """Resolve the transaction data from `--send PAYLOAD` / `--data`."""
    if args.send:
        return '0x' + args.send.encode('utf8').hex()
    return args.data or '0x'


def to_from_args(args):
    return None if args.to in NO_RECIPIENT else args.to
