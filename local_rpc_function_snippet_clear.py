"""Directly call function_snippet_clear (no governance proposal).

Always sends a transaction: it uses the digest given on the command line, else
the latest snippet digest found in the proposals, else the demo snippet's
digest. A snippet produced by function_vote is written with its functions
BEFORE funcs_reload is called (and funcs_reload is missing here), so such a
snippet is non-empty: the clear fails the `functions == []` assertion, changes
no state, and emits no RemoveFunctionSnippet event.

Usage: python local_rpc_function_snippet_clear.py [snippet_digest]
"""

import hashlib
import sys

import setting
from local_rpc_init import call, next_block, state
from local_rpc_function_deploy import DEMO_SNIPPET


def discover_digest():
    try:
        count = state('function-proposal_count')
        digest = None
        for i in range(1, int(count or 0) + 1):
            proposal = state(f'function-proposal:{i}')
            if proposal and proposal.get('snippets'):
                digest = proposal['snippets'][-1]
        return digest
    except Exception:
        return None


def main():
    digest = sys.argv[1] if len(sys.argv) > 1 else None
    if not digest:
        digest = discover_digest()
    if not digest:
        digest = hashlib.sha256(DEMO_SNIPPET.encode('utf8')).hexdigest()
        print('No snippet found in proposals; using the demo snippet digest.')

    print(f'function_snippet_clear({digest})')
    print(f'  before: {state(f"function-snippet:{digest}")}')
    call(setting.accounts[0], 'function_snippet_clear', [digest],
         label='function_snippet_clear')
    print(f'  after:  {state(f"function-snippet:{digest}")}')
    next_block()


if __name__ == '__main__':
    main()
