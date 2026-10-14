"""Dump the current function governance state for /debug cross-checking.

Discovers function names and snippet digests from the proposal records, so it
also surfaces the leftovers that remain after a delete (the proposal records
and the two counters), alongside the code/snippet entries that should be gone.

Usage: python local_rpc_function_state.py [name ...]
"""

import sys

from local_rpc_init import state


def dump_records(prefix, count):
    for i in range(1, int(count or 0) + 1):
        print(f'  {prefix}:{i} = {state(f"{prefix}:{i}")}')


def main():
    extra_names = sys.argv[1:]

    members = state('committee-members')
    proposal_count = state('function-proposal_count')
    delete_count = state('function-delete_proposal_count')

    names = set(extra_names)
    digests = set()
    for i in range(1, int(proposal_count or 0) + 1):
        proposal = state(f'function-proposal:{i}')
        if proposal:
            names.update(proposal.get('functions', []))
            digests.update(proposal.get('snippets', []))

    print('=== committee ===')
    print(f'  committee-members = {members}')

    print('=== counters ===')
    print(f'  function-proposal_count        = {proposal_count}')
    print(f'  function-delete_proposal_count = {delete_count}')

    print('=== add proposals ===')
    dump_records('function-proposal', proposal_count)

    print('=== delete proposals ===')
    dump_records('function-delete_proposal', delete_count)

    print('=== deployed function code ===')
    for name in sorted(names):
        print(f'  function-code:{name} = {state(f"function-code:{name}")}')

    print('=== snippets ===')
    for digest in sorted(digests):
        print(f'  function-snippet:{digest} = {state(f"function-snippet:{digest}")}')


if __name__ == '__main__':
    main()
