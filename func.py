import os
import hashlib
import string
import json
import binascii
import collections
import opcode
import types
import importlib.util
import importlib.machinery

import web3
try:
    from eth_utils import keccak
except ImportError:
    keccak = None

import space
import setting

vm = None
codeop = None
try:
    if setting.USE_VM:
        import vm
        import codeop
except ImportError:
    vm = None

# CPython 3.10 bytecode opcodes actually implemented by vm.py (VM.step).
# Any other opcode makes VM.step fall through and silently end execution.
VM_SUPPORTED_OPCODES = set(opcode.opmap[n] for n in (
 "POP_TOP","ROT_TWO","ROT_THREE","DUP_TOP","DUP_TOP_TWO","NOP","UNARY_POSITIVE","UNARY_NEGATIVE",
 "UNARY_NOT","UNARY_INVERT","BINARY_POWER","BINARY_MULTIPLY","BINARY_MODULO","BINARY_ADD","BINARY_SUBTRACT",
 "BINARY_SUBSCR","BINARY_FLOOR_DIVIDE","BINARY_TRUE_DIVIDE","INPLACE_ADD","INPLACE_SUBTRACT",
 "INPLACE_MODULO","STORE_SUBSCR","DELETE_SUBSCR","BINARY_AND","GET_ITER","LOAD_ASSERTION_ERROR",
 "INPLACE_RSHIFT","WITH_CLEANUP_START","WITH_CLEANUP_FINISH","RETURN_VALUE","POP_BLOCK","END_FINALLY",
 "POP_EXCEPT","STORE_NAME","UNPACK_SEQUENCE","FOR_ITER","STORE_GLOBAL","LOAD_CONST","LOAD_NAME",
 "BUILD_TUPLE","BUILD_LIST","BUILD_MAP","LOAD_ATTR","COMPARE_OP","JUMP_FORWARD","JUMP_IF_FALSE_OR_POP",
 "JUMP_IF_TRUE_OR_POP","JUMP_ABSOLUTE","POP_JUMP_IF_FALSE","POP_JUMP_IF_TRUE","LOAD_GLOBAL","IS_OP",
 "CONTAINS_OP","SETUP_FINALLY","LOAD_FAST","STORE_FAST","RAISE_VARARGS","CALL_FUNCTION","MAKE_FUNCTION",
 "BUILD_SLICE","CALL_FUNCTION_KW","CALL_FUNCTION_EX","SETUP_WITH","EXTENDED_ARG","LIST_APPEND",
 "FORMAT_VALUE","BUILD_CONST_KEY_MAP","BUILD_STRING","LOAD_METHOD","CALL_METHOD","LIST_EXTEND",
 "LOAD_CLOSURE","LOAD_DEREF","STORE_DEREF","DELETE_DEREF"
) if n in opcode.opmap)

def _check_vm_code(code, filename):
    """Warn about bytecode ops vm.py does not implement (they silently stop)."""
    unsupported = collections.Counter()
    def walk(c):
        cc = c.co_code
        i = 0
        while i < len(cc):
            op = cc[i]
            if op not in VM_SUPPORTED_OPCODES:
                unsupported[opcode.opname[op]] += 1
            i += 2
        for k in c.co_consts:
            if hasattr(k, 'co_code'):
                walk(k)
    walk(code)
    if unsupported:
        ops = ', '.join('%s x%d' % (n, k) for n, k in unsupported.most_common())
        print(f"Warning: {filename} uses opcodes not implemented by vm.py: {ops}")

class VMNamedFunction:
    def __init__(self, v, name, file):
        self.v = v
        self.name = name
        self.file = file

    def __call__(self, *args):
        if space.sender is None:
            raise Exception('sender is not set')
        info = {'sender': space.sender}
        args = {'p': 'zen', 'a': list(args), 'f': self.name}
        self.v.last_exception = None
        return self.v.run([info, args], function_name=self.name)

    def __str__(self):
        return '<VMFunction %s>' % self.name

    def __repr__(self):
        return '<VMFunction %s>' % self.name

class NamedFunction:
    def __init__(self, f, name):
        self.f = f
        self.name = name

    def __call__(self, *args):
        a = list(args)
        if space.sender is None:
            raise Exception('sender is not set')
        r = self.f({'sender': space.sender}, {'p': 'zen', 'a': a, 'f': self.name})
        return r

    def __str__(self):
        return self.f.__str__()

    def __repr__(self):
        return self.f.__repr__()

def get_block_number():
    return space.latest_block_number

def set_sender(sender):
    space.sender = sender.lower()
    namespace['sender'] = space.sender


accounts = []
for i in range(10):
    private_key = hashlib.sha256(('brownie%s' % i).encode('utf8')).digest()
    account = web3.Account.from_key(private_key)
    accounts.append(account.address.lower())

namespace = {
    'put': space.put,
    'get': space.get, 
    'blocknumber': get_block_number,
    'nextblock': space.nextblock,
    'setsender': set_sender,
    'states': space.states,
    'sender': space.sender,
    'accounts': accounts,
    'a': accounts,
    '__name__': '__console__',
    '__doc__': None,
    'blocks': space.blocks,
    'events': space.events,
    'transactions': space.transactions,
    'nonces': space.nonces,
}


def _load_zip_vm(logic_path, filename):
    '''Compile a funcs file and execute it inside vm.VM, like testnet3's
    funcs._process loads snippet code (codeop.compile_command -> VM -> run).'''
    src = open(logic_path).read()
    c = codeop.compile_command(src, symbol="exec")
    _check_vm_code(c, filename)

    v = vm.VM()
    v.import_src(c)

    funcs_reload = lambda func_names: None

    v.global_vars['get'] = space.get
    v.global_vars['put'] = space.put
    v.global_vars['event'] = space.event
    v.global_vars['handle_lookup'] = space.handle_lookup
    v.global_vars['funcs_reload'] = funcs_reload
    v.global_vars['hashlib'] = hashlib
    v.global_vars['string'] = string
    v.global_vars['json'] = json
    v.global_vars['binascii'] = binascii
    v.global_vars['print'] = print
    if keccak:
        v.global_vars['keccak'] = keccak

    v.native_vars.add(space.get)
    v.native_vars.add(space.put)
    v.native_vars.add(space.event)
    v.native_vars.add(space.handle_lookup)
    v.native_vars.add(print)
    if keccak:
        v.native_vars.add(keccak)

    v.run([])

    wrapped = []
    for name in v.funcs:
        if name.startswith('_'):
            continue
        function_object = v.global_vars.get(name)
        if type(function_object) is not types.FunctionType:
            continue
        wrapped.append(VMNamedFunction(v, name, filename))
    return wrapped


def load_all_zips():
    funcs_dir = os.path.join(os.path.dirname(__file__), 'funcs')
    if not os.path.exists(funcs_dir):
        print(f"Warning: {funcs_dir} not found.")
        return
    for filename in sorted(os.listdir(funcs_dir)):
        if not filename.endswith('.py') or filename == '__init__.py':
            continue
        logic_path = os.path.join(funcs_dir, filename)

        if vm is not None:
            for wrapped in _load_zip_vm(logic_path, filename):
                namespace[wrapped.name] = wrapped
            continue

        module_name = f'funcs_{filename[:-3]}'
        loader = importlib.machinery.SourceFileLoader(module_name, logic_path)
        spec = importlib.util.spec_from_loader(module_name, loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)

        mod.get = space.get
        mod.put = space.put
        mod.event = space.event
        mod.handle_lookup = space.handle_lookup
        mod.hashlib = hashlib
        mod.string = string
        mod.json = json
        mod.binascii = binascii
        if keccak:
            mod.keccak = keccak

        for attr in dir(mod):
            if attr in ['put', 'get', 'event', 'handle_lookup']:
                continue
            if attr.startswith('_'):
                continue
            func = getattr(mod, attr)
            if callable(func):
                # print(attr)
                wrapped = NamedFunction(func, attr)
                namespace[attr] = wrapped
