"""Delete a previously deployed function through governance.

Flow: function_delete_proposal -> function_delete_vote (enough votes).

As with deploy, the deciding vote calls funcs_reload, which is not
implemented here, so it returns a JSON-RPC error after the state has already
been updated. Expected result: function-code:<name> and (when empty)
function-snippet:<digest> are removed, while the proposal records and the
counters remain.

Usage: python local_rpc_function_delete.py [name ...]
"""

import sys

import setting
from local_rpc_init import (bootstrap_committee, call, next_block, state,
                            votes_needed)

COMMITTEE_SIZE = 3

DEFAULT_FUNCTIONS = ['hello']


def delete(func_names):
    print(f'Deleting functions: {func_names}')
    for name in func_names:
        if state(f'function-code:{name}') is None:
            print(f'  [skip] function-code:{name} not found')
            return func_names, None

    members = bootstrap_committee(COMMITTEE_SIZE)
    print(f'  committee ({len(members)}): {members}')

    call(setting.accounts[0], 'function_delete_proposal', [func_names],
         label='function_delete_proposal')

    proposal_id = state('function-delete_proposal_count')
    print(f'  delete proposal id: {proposal_id}')

    needed = votes_needed(members)
    print(f'  votes needed: {needed}')
    for i in range(needed):
        voter = setting.accounts[i]
        call(voter, 'function_delete_vote', [proposal_id],
             label=f'function_delete_vote(#{proposal_id} by {voter.address[:10]}...)')

    # The deciding vote aborts at funcs_reload, so no nextblock() happens;
    # advance one block so the delete is committed to a block on /debug.
    next_block()

    return func_names, proposal_id


if __name__ == '__main__':
    func_names = sys.argv[1:] or DEFAULT_FUNCTIONS
    delete(func_names)
    print()
    print('After delete:')
    for name in func_names:
        print(f'  function-code:{name} = {state(f"function-code:{name}")}')
