"""Deploy a demo function through the on-chain governance flow.

Flow: function_snippet -> function_proposal -> function_vote (enough votes).

The final vote reaches the committee threshold and therefore calls
funcs_reload, which is not implemented in this playground. That vote returns
a JSON-RPC error, but the code/snippet state has already been written - check
it on /debug (or with local_rpc_function_state.py).
"""

import hashlib

import setting
from local_rpc_init import (bootstrap_committee, call, next_block, state,
                            votes_needed)

COMMITTEE_SIZE = 3

DEMO_FUNCTION = 'hello'

DEMO_SNIPPET = '''\
def hello(info, args):
    sender = info['sender']
    addr = handle_lookup(sender)
    put(addr, 'demo', 'greeting', 'hello from %s' % addr)
    event('DemoHello', [addr])
'''


def deploy(func_name=DEMO_FUNCTION, snippet=DEMO_SNIPPET):
    digest = hashlib.sha256(snippet.encode('utf8')).hexdigest()
    print(f'Deploying function "{func_name}"')
    print(f'  snippet digest: {digest}')

    members = bootstrap_committee(COMMITTEE_SIZE)
    print(f'  committee ({len(members)}): {members}')

    call(setting.accounts[0], 'function_snippet', [snippet], label='function_snippet')
    call(setting.accounts[0], 'function_proposal', [[func_name], [digest]],
         label='function_proposal')

    proposal_id = state('function-proposal_count')
    print(f'  proposal id: {proposal_id}')

    needed = votes_needed(members)
    print(f'  votes needed: {needed}')
    for i in range(needed):
        voter = setting.accounts[i]
        call(voter, 'function_vote', [proposal_id],
             label=f'function_vote(#{proposal_id} by {voter.address[:10]}...)')

    # The deciding vote aborts at funcs_reload, so no nextblock() happens;
    # advance one block so the deploy is committed to a block on /debug.
    next_block()

    return func_name, digest, proposal_id


if __name__ == '__main__':
    name, digest, proposal_id = deploy()
    print()
    print('State to check on /debug:')
    print(f'  function-code:{name} = {state(f"function-code:{name}")}')
    print(f'  function-proposal:{proposal_id} = {state(f"function-proposal:{proposal_id}")}')
