"""Test that re-deploying a function unbinds it from the old snippet.

Scenario (single function `hello`):
  1. deploy `hello` from snippet A (v1)
  2. deploy `hello` from snippet B (v2, a different implementation)
  3. old snippet A must end up with functions == [] and function-code:hello
     must point at snippet B
  4. function_snippet_clear(A) must then succeed

Usage: python local_rpc_function_redeploy.py
"""

import hashlib

import setting
from local_rpc_init import call, state
from local_rpc_function_deploy import DEMO_SNIPPET, deploy

FUNCTION = 'hello'

NEW_SNIPPET = '''\
def hello(info, args):
    sender = info['sender']
    addr = handle_lookup(sender)
    put(addr, 'demo', 'greeting', 'hello v2 from %s' % addr)
    put(addr, 'demo', 'version', 2)
    event('DemoHelloV2', [addr])
'''


def digest(snippet):
    return hashlib.sha256(snippet.encode('utf8')).hexdigest()


def main():
    old_digest = digest(DEMO_SNIPPET)
    new_digest = digest(NEW_SNIPPET)

    print('=== 1. deploy hello (v1) ===')
    deploy(FUNCTION, DEMO_SNIPPET)

    print('=== 2. deploy hello (v2) ===')
    deploy(FUNCTION, NEW_SNIPPET)

    old_snippet = state(f'function-snippet:{old_digest}')
    new_snippet = state(f'function-snippet:{new_digest}')
    code = state(f'function-code:{FUNCTION}')

    old_functions = old_snippet and old_snippet.get('functions')
    new_functions = new_snippet and new_snippet.get('functions')
    code_snippets = code and code.get('snippets')
    print()
    print(f'  old snippet functions = {old_functions}')
    print(f'  new snippet functions = {new_functions}')
    print(f'  code snippets         = {code_snippets}')

    assert old_functions == [], 'old snippet was not unbound'
    assert FUNCTION in (new_functions or []), 'new snippet was not bound'
    assert code_snippets == [new_digest], 'function-code does not point at new snippet'
    assert old_snippet['snippet'] != new_snippet['snippet'], 'snippets are identical'
    print(f'  old snippet source    = {old_snippet["snippet"]!r}')
    print(f'  new snippet source    = {new_snippet["snippet"]!r}')

    print('=== 3. clear old snippet ===')
    call(setting.accounts[0], 'function_snippet_clear', [old_digest],
         label='function_snippet_clear(old)')
    cleared = state(f'function-snippet:{old_digest}')
    print(f'  old snippet after clear = {cleared}')
    assert cleared is None, 'old snippet was not cleared'

    print()
    print('OK: old snippet unbound and cleared')


if __name__ == '__main__':
    main()
