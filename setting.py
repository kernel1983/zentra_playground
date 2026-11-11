import hashlib

import eth_account

accounts = []
for i in range(10):
    private_key = hashlib.sha256(('brownie%s' % i).encode('utf8')).digest()
    account = eth_account.Account.from_key(private_key)
    accounts.append(account)
    # print(f'{account.address} < 0x{private_key.hex()}')


CHAIN_ID = 31337

BLOCK_MODE = 5  # 0: manual, 1: auto after tx, >=2: auto with interval (seconds)

USE_VM = True

