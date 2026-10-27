
"""
zip101.py - Onchain chess state transition prototype
All functions and states must be prefixed with `chess_`
Move format: like "g4d7" or "g7g8q" (from+to, optional promotion)
"""

# ==================== Constants ====================

CHESS_START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

CHESS_PIECE_TYPES = set(['p','n','b','r','q','k','P','N','B','R','Q','K'])
_CHESS_KNIGHT_DIRS = [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]
_CHESS_KING_DIRS = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
_CHESS_DIAG_DIRS = [(-1,-1),(-1,1),(1,-1),(1,1)]
_CHESS_STRAIGHT_DIRS = [(-1,0),(0,-1),(0,1),(1,0)]
_CHESS_SLIDE_DIRS = _CHESS_DIAG_DIRS + _CHESS_STRAIGHT_DIRS

# ==================== Helpers ====================

def _chess_side_of(p):
    if not p or p == '.':
        return None
    if p in ['P','N','B','R','Q','K']:
        return 'w'
    if p in ['p','n','b','r','q','k']:
        return 'b'
    return None

def _chess_on_board(r, c):
    return 0 <= r < 8 and 0 <= c < 8

def _chess_square_to_rc(sq):
    assert isinstance(sq, str) and len(sq) == 2, "chess_bad_square"
    f = sq[0]
    rnk = sq[1]
    assert f in 'abcdefgh', "chess_bad_file"
    assert rnk in '12345678', "chess_bad_rank"
    c = ord(f) - ord('a')
    r = 8 - int(rnk)
    return r, c

def _chess_rc_to_square(r, c):
    assert _chess_on_board(r, c)
    f = chr(ord('a') + c)
    rnk = str(8 - r)
    return f + rnk

def _chess_empty_board():
    return [['.' for _ in range(8)] for _ in range(8)]

def _chess_clone_board(board):
    return [list(row) for row in board]

def _chess_fen_to_board(fen):
    parts = fen.split()
    board_fen = parts[0] if len(parts) > 0 else "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
    board = _chess_empty_board()
    r = 0
    c = 0
    for ch in board_fen:
        if ch == '/':
            r += 1
            c = 0
            if r >= 8:
                break
            continue
        if ch.isdigit():
            c += int(ch)
            continue
        if c < 8:
            board[r][c] = ch
            c += 1
    return board

def _chess_find_king(board, side):
    target = 'K' if side == 'w' else 'k'
    for r in range(8):
        for c in range(8):
            if board[r][c] == target:
                return r, c
    return None, None

# ==================== Move generation ====================

def _chess_pseudo_moves(board, r, c):
    p = board[r][c]
    if p == '.' or p not in CHESS_PIECE_TYPES:
        return []
    side = _chess_side_of(p)
    opp = 'b' if side == 'w' else 'w'
    moves = []

    if p in ['N', 'n']:
        for dr, dc in _CHESS_KNIGHT_DIRS:
            nr, nc = r + dr, c + dc
            if not _chess_on_board(nr, nc):
                continue
            tp = board[nr][nc]
            if tp == '.':
                moves.append((nr, nc))
            elif _chess_side_of(tp) == opp:
                moves.append((nr, nc))
        return moves

    if p in ['K', 'k']:
        for dr, dc in _CHESS_KING_DIRS:
            nr, nc = r + dr, c + dc
            if not _chess_on_board(nr, nc):
                continue
            tp = board[nr][nc]
            if tp == '.':
                moves.append((nr, nc))
            elif _chess_side_of(tp) == opp:
                moves.append((nr, nc))
        return moves

    if p in ['B', 'b']:
        dirs = _CHESS_DIAG_DIRS
    elif p in ['R', 'r']:
        dirs = _CHESS_STRAIGHT_DIRS
    elif p in ['Q', 'q']:
        dirs = _CHESS_SLIDE_DIRS
    else:
        dirs = []

    if dirs and p not in ['P', 'p']:
        for dr, dc in dirs:
            nr, nc = r + dr, c + dc
            while _chess_on_board(nr, nc):
                tp = board[nr][nc]
                if tp == '.':
                    moves.append((nr, nc))
                    nr += dr
                    nc += dc
                    continue
                if _chess_side_of(tp) == opp:
                    moves.append((nr, nc))
                break
        return moves

    if p == 'P':
        if _chess_on_board(r - 1, c) and board[r - 1][c] == '.':
            moves.append((r - 1, c))
            if r == 6 and _chess_on_board(r - 2, c) and board[r - 2][c] == '.':
                moves.append((r - 2, c))
        for dc in [-1, 1]:
            nr, nc = r - 1, c + dc
            if not _chess_on_board(nr, nc):
                continue
            tp = board[nr][nc]
            if tp != '.' and _chess_side_of(tp) == 'b':
                moves.append((nr, nc))
        return moves

    if p == 'p':
        if _chess_on_board(r + 1, c) and board[r + 1][c] == '.':
            moves.append((r + 1, c))
            if r == 1 and _chess_on_board(r + 2, c) and board[r + 2][c] == '.':
                moves.append((r + 2, c))
        for dc in [-1, 1]:
            nr, nc = r + 1, c + dc
            if not _chess_on_board(nr, nc):
                continue
            tp = board[nr][nc]
            if tp != '.' and _chess_side_of(tp) == 'w':
                moves.append((nr, nc))
        return moves

    return moves

def _chess_square_attacked(board, r, c, by_side):
    for sr in range(8):
        for sc in range(8):
            p = board[sr][sc]
            if p == '.':
                continue
            if _chess_side_of(p) != by_side:
                continue
            pm = _chess_pseudo_moves(board, sr, sc)
            for mr, mc in pm:
                if mr == r and mc == c:
                    return True
    return False

def _chess_is_in_check(board, side):
    kr, kc = _chess_find_king(board, side)
    if kr is None:
        return True
    opp = 'b' if side == 'w' else 'w'
    return _chess_square_attacked(board, kr, kc, opp)

def _chess_apply_move(board, fr, fc, tr, tc, promo=None):
    nb = _chess_clone_board(board)
    p = nb[fr][fc]
    side = _chess_side_of(p)
    nb[tr][tc] = p
    nb[fr][fc] = '.'
    if promo and p in ['P', 'p'] and (tr == 0 or tr == 7):
        pr = str(promo).lower()
        if pr not in ['q', 'r', 'b', 'n']:
            pr = 'q'
        if side == 'w':
            nb[tr][tc] = pr.upper()
        else:
            nb[tr][tc] = pr
    return nb, p

def _chess_legal_moves_for_side(board, side):
    res = []
    for fr in range(8):
        for fc in range(8):
            p = board[fr][fc]
            if p == '.':
                continue
            if _chess_side_of(p) != side:
                continue
            pm = _chess_pseudo_moves(board, fr, fc)
            for tr, tc in pm:
                nb, mp = _chess_apply_move(board, fr, fc, tr, tc)
                if not _chess_is_in_check(nb, side):
                    res.append((fr, fc, tr, tc))
    return res

def _chess_parse_move_str(mstr):
    s = str(mstr).strip().lower()
    assert len(s) == 4 or len(s) == 5, "chess_bad_move_format"
    frs = s[0:2]
    trs = s[2:4]
    promo = s[4] if len(s) == 5 else None
    fr, fc = _chess_square_to_rc(frs)
    tr, tc = _chess_square_to_rc(trs)
    return fr, fc, tr, tc, promo

# ==================== Onchain functions (all chess_*) ====================

def chess_init(info, args):
    assert args['f'] == 'chess_init'
    sender = info['sender']
    addr = handle_lookup(sender)
    a = args.get('a', [])
    manager = addr
    quote_tokens = a[0] if a else []
    assert isinstance(quote_tokens, list), 'chess_quote_tokens_must_be_list'
    put(addr, 'chess', 'chess_manager', manager)
    put(addr, 'chess', 'chess_quote_tokens', quote_tokens)
    put(addr, 'chess', 'chess_game_count', 1)
    event('ChessInit', [addr, manager, quote_tokens])

def _chess_predict_create_market(slug, quote_tick):
    """Create the YES/NO market attached to a chess game."""
    assert quote_tick, 'chess_quote_token_required'
    manager, _ = get('chess', 'chess_manager', None)
    tokens, _ = get('chess', 'chess_quote_tokens', [])
    assert manager is not None, 'chess_manager_not_set'
    assert quote_tick in tokens, 'chess_quote_token_not_allowed'
    created, _ = get('chess_predict', f'{slug}_quote_token', None)
    assert created is None, 'chess_predict_market_exists'
    put(manager, 'chess_predict', f'{slug}_quote_token', quote_tick)
    for tick in ['yes', 'no']:
        put(manager, 'chess_predict', f'{slug}_{tick}_buy_start', 1)
        put(manager, 'chess_predict', f'{slug}_{tick}_buy_new', 1)
        put(manager, 'chess_predict', f'{slug}_{tick}_sell_start', 1)
        put(manager, 'chess_predict', f'{slug}_{tick}_sell_new', 1)
        put(manager, 'chess_predict', f'{slug}_{tick}_balance_new', None)
    event('ChessPredictCreate', [slug, quote_tick, manager])

def chess_create_game(info, args):
    assert args['f'] == 'chess_create_game'
    sender = info['sender']
    addr = handle_lookup(sender)
    a = args.get('a', [])
    opp = None
    if len(a) > 0 and a[0] is not None:
        opp = str(a[0]).lower()

    game_count, _ = get('chess', 'chess_game_count', 1)
    # The state key is the game ID, so keep it compact and avoid duplicating it
    # inside the state payload.
    game_id = str(game_count)
    put(addr, 'chess', 'chess_game_count', game_count + 1)

    manager, _ = get('chess', 'chess_manager', None)
    assert manager is not None, 'chess_manager_not_set'
    tokens, _ = get('chess', 'chess_quote_tokens', [])
    quote_tick = str(a[1]) if len(a) > 1 else (tokens[0] if len(tokens) == 1 else None)
    _chess_predict_create_market(game_id, quote_tick)

    board = _chess_fen_to_board(CHESS_START_FEN)
    state = {
        'chess_board': board,
        'chess_turn': 'w',
        # Counts completed plies only. Creating or joining a game is not a move.
        'chess_move_count': 0,
        'chess_white': addr,
        'chess_black': opp,
        # An open game cannot be played until a second account joins as black.
        'chess_status': 'chess_active' if opp else 'chess_waiting_for_opponent',
        'chess_result': None,
        'chess_winner': None,
    }
    put(addr, 'chess', 'chess_state', state, game_id)
    event('ChessGameCreated', [game_id, addr, opp])
    return {'chess_ok': True, 'chess_status': state['chess_status'], 'chess_white': addr, 'chess_black': opp}

def chess_join_game(info, args):
    """Join an open chess game as black. Args: [game_id]."""
    assert args['f'] == 'chess_join_game'
    sender = info['sender']
    addr = handle_lookup(sender)
    a = args.get('a', [])
    assert len(a) >= 1, 'chess_game_id_required'
    game_id = str(a[0])

    state, owner = get('chess', 'chess_state', None, game_id)
    assert state is not None, 'chess_game_not_found'
    assert state['chess_status'] == 'chess_waiting_for_opponent', 'chess_game_not_open'
    assert state.get('chess_black') is None, 'chess_black_already_set'
    assert addr != state['chess_white'], 'chess_cannot_join_own_game'

    new_state = dict(state)
    new_state['chess_black'] = addr
    new_state['chess_status'] = 'chess_active'
    # Preserve the original state owner (the white player) for the game record.
    put(owner or state['chess_white'], 'chess', 'chess_state', new_state, game_id)
    event('ChessGameJoined', [game_id, addr])
    return {'chess_ok': True, 'chess_status': new_state['chess_status'], 'chess_white': new_state['chess_white'], 'chess_black': addr}

def chess_make_move(info, args):
    assert args['f'] == 'chess_make_move'
    sender = info['sender']
    addr = handle_lookup(sender)
    a = args.get('a', [])
    game_id = str(a[0])
    mstr = str(a[1])

    state, owner = get('chess', 'chess_state', None, game_id)
    assert state is not None, "chess_game_not_found"
    assert state['chess_status'] == 'chess_active', "chess_game_not_active"

    turn = state['chess_turn']
    if turn == 'w':
        assert addr == state['chess_white'], "chess_not_white_to_move"
    else:
        assert addr == state['chess_black'], "chess_not_black_to_move"

    fr, fc, tr, tc, promo = _chess_parse_move_str(mstr)
    board = state['chess_board']
    p = board[fr][fc]
    assert p != '.', "chess_empty_from"
    assert _chess_side_of(p) == turn, "chess_wrong_side"

    # Promotion is explicit for all non-queen choices.  A missing promotion
    # piece keeps the traditional default-to-queen behavior, while rook,
    # bishop, and knight are also supported (for example: g7g8n).
    reaches_promotion_rank = p in ['P', 'p'] and tr in [0, 7]
    if reaches_promotion_rank:
        promo = promo or 'q'
        assert promo in ['q', 'r', 'b', 'n'], "chess_bad_promotion"
    else:
        assert promo is None, "chess_promotion_not_allowed"

    legal = _chess_legal_moves_for_side(board, turn)
    found = False
    for lm in legal:
        if lm[0] == fr and lm[1] == fc and lm[2] == tr and lm[3] == tc:
            found = True
            break
    assert found, "chess_illegal_move"

    nb, mp = _chess_apply_move(board, fr, fc, tr, tc, promo=promo)
    assert not _chess_is_in_check(nb, turn), "chess_illegal_move_leaves_check"

    new_state = dict(state)
    new_state['chess_board'] = nb
    new_state['chess_turn'] = 'b' if turn == 'w' else 'w'
    new_state['chess_move_count'] = int(state.get('chess_move_count', 0)) + 1

    opp_side = new_state['chess_turn']
    opp_legal = _chess_legal_moves_for_side(nb, opp_side)
    opp_in_check = _chess_is_in_check(nb, opp_side)
    if len(opp_legal) == 0:
        if opp_in_check:
            new_state['chess_status'] = 'chess_checkmate'
            if opp_side == 'b':
                new_state['chess_result'] = 'chess_white_wins'
                new_state['chess_winner'] = new_state.get('chess_white')
            else:
                new_state['chess_result'] = 'chess_black_wins'
                new_state['chess_winner'] = new_state.get('chess_black')
        else:
            new_state['chess_status'] = 'chess_stalemate'
            new_state['chess_result'] = 'chess_draw'
            new_state['chess_winner'] = None
    else:
        new_state['chess_status'] = 'chess_active'
        new_state['chess_result'] = None
        new_state['chess_winner'] = None

    if new_state['chess_result'] is not None:
        result = 'draw'
        if new_state['chess_result'] == 'chess_white_wins':
            result = 'yes'
        elif new_state['chess_result'] == 'chess_black_wins':
            result = 'no'
        _chess_predict_submit(game_id, result)

    put(addr, 'chess', 'chess_state', new_state, game_id)
    event('ChessMove', [game_id, addr, mstr.strip().lower(), mp, new_state['chess_turn'], new_state['chess_status'], new_state['chess_result']])
    return {'chess_ok': True, 'chess_move_count': new_state['chess_move_count'], 'chess_status': new_state['chess_status'], 'chess_result': new_state['chess_result'], 'chess_winner': new_state['chess_winner'], 'chess_turn': new_state['chess_turn']}


def _decimal(tick):
    """On-chain token decimals, used to scale quote raw amounts back to units."""
    dec, _ = get(tick, 'decimal', None)
    assert dec is not None, f'{tick} has no registered decimals'
    return int(dec)

def _insert_order(addr, pair, order_type, order_start, order_new, quote_value, base_value, quote_scale):
    assert order_type in ['buy', 'sell']
    price = - quote_value * quote_scale // base_value
    assert 0 < price < quote_scale, "price must be between 0 and 1"
    order_id = order_start
    while True:
        order, _ = get('chess_predict', f'{pair}_{order_type}', None, str(order_id))

        if order is None:
            put(addr, 'chess_predict', f'{pair}_{order_type}',
                [addr, base_value, quote_value, price, None, None], str(order_new))
            order_new += 1
            put(addr, 'chess_predict', f'{pair}_{order_type}_new', order_new)
            break

        if order_type == 'buy':
            cond = price > order[3]
        else:
            cond = price < order[3]

        if cond:
            next_order_id = order[5]
            put(addr, 'chess_predict', f'{pair}_{order_type}',
                [addr, base_value, quote_value, price, order_id, next_order_id], str(order_new))
            if next_order_id is None:
                order_start = order_new
                put(addr, 'chess_predict', f'{pair}_{order_type}_start', order_new)
            order[5] = order_new
            order_new += 1
            put(addr, 'chess_predict', f'{pair}_{order_type}_new', order_new)

            put(addr, 'chess_predict', f'{pair}_{order_type}', order, str(order_id))
            if next_order_id is not None:
                next_order, _ = get('chess_predict', f'{pair}_{order_type}', None, str(next_order_id))
                if next_order is not None:
                    next_order[4] = order[5]
                    put(addr, 'chess_predict', f'{pair}_{order_type}', next_order, str(next_order_id))
            break

        if order[4] is None:
            put(addr, 'chess_predict', f'{pair}_{order_type}',
                [addr, base_value, quote_value, price, None, order_id], str(order_new))
            put(addr, 'chess_predict', f'{pair}_{order_type}',
                [order[0], order[1], order[2], order[3], order_new, order[5]], str(order_id))
            order_new += 1
            put(addr, 'chess_predict', f'{pair}_{order_type}_new', order_new)
            break

        order_id = order[4]
    return order_start, order_new

def _remove_order(addr, pair, order, order_start, buy_or_sell):
    assert buy_or_sell in ['buy', 'sell']
    if order[4]:
        prev_order, _ = get('chess_predict', f'{pair}_{buy_or_sell}', None, str(order[4]))
        prev_order[5] = order[5]
        put(prev_order[0], 'chess_predict', f'{pair}_{buy_or_sell}', prev_order, str(order[4]))

    if order[5]:
        next_order, _ = get('chess_predict', f'{pair}_{buy_or_sell}', None, str(order[5]))
        next_order[4] = order[4]
        put(next_order[0], 'chess_predict', f'{pair}_{buy_or_sell}', next_order, str(order[5]))

    if order[4] is not None and order[5] is None:
        order_start = order[4]
        put(addr, 'chess_predict', f'{pair}_{buy_or_sell}_start', order_start)

    elif order[4] is None and order[5] is None:
        order_new, _ = get('chess_predict', f'{pair}_{buy_or_sell}_new', 1)
        order_start = order_new
        put(addr, 'chess_predict', f'{pair}_{buy_or_sell}_start', order_start)

    return order_start

def _update_slug_balance(addr, slug, tick, delta):
    prev, manager = get('chess_predict', f'{slug}_{tick}_balance_new', None)
    balance_tuple, _ = get('chess_predict', f'{slug}_{tick}_balance', None, addr)
    if balance_tuple is None:
        balance = 0
        put(manager, 'chess_predict', f'{slug}_{tick}_balance_new', addr)
    else:
        balance = balance_tuple[0]
        prev = balance_tuple[1]
    balance += delta
    assert balance >= 0
    put(addr, 'chess_predict', f'{slug}_{tick}_balance', [balance, prev], addr)

def _update_quote_balance(addr, quote_tick, delta):
    balance, _ = get(quote_tick, 'balance', 0, addr)
    balance += delta
    assert balance >= 0
    put(addr, quote_tick, 'balance', balance, addr)

def _update_pot(slug, quote_tick, delta):
    """Hold the escrow as a real quote balance parked at `pot_chess_predict:{slug}`.
    The colon keeps the account outside DID/address space, so the pot can never
    be a user of the chain or be claimed by one; the predict manager owns the
    balance entry, mirroring zip25's `pot_options:{slug}`."""
    pot = f'pot_chess_predict:{slug}'
    balance, _ = get(quote_tick, 'balance', 0, pot)
    balance += delta
    assert balance >= 0, "Escrow pot underfunded"
    manager, _ = get('chess', 'chess_manager', None)
    put(manager, quote_tick, 'balance', balance, pot)


def chess_predict_limit_order(info, args):
    assert args['f'] == 'chess_predict_limit_order'
    sender = info['sender']
    addr = handle_lookup(sender)

    slug = args['a'][0]
    yes_or_no = args['a'][2]
    assert set(slug) <= set(string.ascii_lowercase+string.digits+'_')
    assert yes_or_no in set(['yes', 'no'])

    pair = f'{slug}_{yes_or_no}'
    base_value = int(args['a'][1])
    quote_value = int(args['a'][3])
    assert base_value * quote_value < 0

    quote_tick, _ = get('chess_predict', f'{slug}_quote_token', None)
    assert quote_tick, "Slug not exists"
    quote_scale = 10 ** _decimal(quote_tick)

    chess_predict_buy_start, _ = get('chess_predict', f'{pair}_buy_start', 1)
    chess_predict_buy_new, _ = get('chess_predict', f'{pair}_buy_new', 1)
    chess_predict_sell_start, _ = get('chess_predict', f'{pair}_sell_start', 1)
    chess_predict_sell_new, _ = get('chess_predict', f'{pair}_sell_new', 1)

    if base_value < 0 and quote_value > 0:
        buy_or_sell = 'sell'
        _update_slug_balance(addr, slug, yes_or_no, base_value)
        make_base = - base_value

        order_id = chess_predict_sell_new
        chess_predict_sell_start, chess_predict_sell_new = _insert_order(addr, pair, 'sell', chess_predict_sell_start, chess_predict_sell_new, quote_value, base_value, quote_scale)

    elif base_value > 0 and quote_value < 0:
        buy_or_sell = 'buy'
        _update_quote_balance(addr, quote_tick, quote_value)
        make_base = base_value

        order_id = chess_predict_buy_new
        chess_predict_buy_start, chess_predict_buy_new = _insert_order(addr, pair, 'buy', chess_predict_buy_start, chess_predict_buy_new, quote_value, base_value, quote_scale)

    chess_predict_sell_id = chess_predict_sell_start
    highest_buy_price = None

    take_base = 0
    take_quote = 0
    while True:
        sell, _ = get('chess_predict', f'{pair}_sell', None, str(chess_predict_sell_id))
        if not sell:
            break
        sell_price = sell[3]
        if highest_buy_price and sell_price > highest_buy_price:
            break

        chess_predict_buy_id = chess_predict_buy_start
        while True:
            buy, _ = get('chess_predict', f'{pair}_buy', None, str(chess_predict_buy_id))
            if not buy:
                break
            buy_price = buy[3]
            if highest_buy_price is None:
                highest_buy_price = buy_price
            if sell_price > buy_price:
                chess_predict_buy_id = buy[4]
                continue

            matched_price = sell_price
            dx_base = min(-sell[1], buy[1])
            dx_quote = dx_base * matched_price // quote_scale
            sell[1] += dx_base
            sell[2] -= dx_quote
            buy[1] -= dx_base
            buy[2] += dx_quote
            take_base += dx_base
            take_quote += dx_quote

            _update_slug_balance(buy[0], slug, yes_or_no, dx_base)
            _update_quote_balance(sell[0], quote_tick, dx_quote)

            if buy[1] == 0:
                chess_predict_buy_start = _remove_order(addr, pair, buy, chess_predict_buy_start, 'buy')

                if buy[2] < 0:
                    _update_quote_balance(buy[0], quote_tick, -buy[2])

                put(buy[0], 'chess_predict', f'{pair}_buy', None, str(chess_predict_buy_id))
            else:
                put(buy[0], 'chess_predict', f'{pair}_buy', buy, str(chess_predict_buy_id))

            if sell[1] == 0:
                break
            if buy[4] is None:
                break
            chess_predict_buy_id = buy[4]

        if sell[1] == 0:
            chess_predict_sell_start = _remove_order(addr, pair, sell, chess_predict_sell_start, 'sell')

            if sell[1] < 0:
                _update_slug_balance(sell[0], slug, yes_or_no, -sell[1])

            put(sell[0], 'chess_predict', f'{pair}_sell', None, str(chess_predict_sell_id))
        else:
            put(sell[0], 'chess_predict', f'{pair}_sell', sell, str(chess_predict_sell_id))

        if sell[4] is None:
            break
        chess_predict_sell_id = sell[4]

    make_base -= take_base
    assert make_base >= 0
    make_price = - quote_value * quote_scale // base_value
    event('PredictLimitMake', [pair, buy_or_sell, addr, make_base, make_price, order_id])
    if take_base > 0:
        take_price = take_quote * quote_scale // take_base
        event('PredictLimitTake', [pair, buy_or_sell, addr, take_base, take_price, order_id])


def chess_predict_market_order(info, args):
    assert args['f'] == 'chess_predict_market_order'
    sender = info['sender']
    addr = handle_lookup(sender)

    slug = args['a'][0]
    yes_or_no = args['a'][2]
    assert set(slug) <= set(string.ascii_lowercase+string.digits+'_')
    assert yes_or_no in set(['yes', 'no'])

    quote_tick, _ = get('chess_predict', f'{slug}_quote_token', None)
    assert quote_tick, "Slug not exists"
    quote_scale = 10 ** _decimal(quote_tick)
    pair = f'{slug}_{yes_or_no}'

    base_value = args['a'][1]
    quote_value = args['a'][3]
    chess_predict_sell_start, _ = get('chess_predict', f'{pair}_sell_start', 1)
    chess_predict_buy_start, _ = get('chess_predict', f'{pair}_buy_start', 1)

    take_base = 0
    take_quote = 0
    if quote_value is None and int(base_value) < 0:
        buy_or_sell = 'sell'
        base_value = int(args['a'][1])
        [base_balance, _], _ = get('chess_predict', f'{pair}_balance', [0, None], addr)

        chess_predict_buy_id = chess_predict_buy_start
        while True:
            buy, _ = get('chess_predict', f'{pair}_buy', None, str(chess_predict_buy_id))
            if buy is None:
                break

            price = buy[3]
            dx_base = min(buy[1], -buy[2] * quote_scale // price, -base_value)
            dx_quote = dx_base * price // quote_scale
            if dx_base == 0 or dx_quote == 0:
                break
            if base_balance - dx_base < 0:
                break
            buy[1] -= dx_base
            buy[2] += dx_quote
            take_base += dx_base
            take_quote += dx_quote
            base_balance -= dx_base

            if buy[1] == 0 or buy[1] * quote_scale // price == 0:
                chess_predict_buy_start = _remove_order(addr, pair, buy, chess_predict_buy_start, 'buy')

                if buy[2] < 0:
                    _update_quote_balance(buy[0], quote_tick, -buy[2])

                put(buy[0], 'chess_predict', f'{pair}_buy', None, str(chess_predict_buy_id))
            else:
                put(buy[0], 'chess_predict', f'{pair}_buy', buy, str(chess_predict_buy_id))

            _update_slug_balance(buy[0], slug, yes_or_no, dx_base)

            base_value += dx_base
            assert base_value <= 0
            _update_quote_balance(addr, quote_tick, dx_quote)

            if buy[4] is None:
                break
            chess_predict_buy_id = buy[4]

        _update_slug_balance(addr, slug, yes_or_no, -take_base)

    elif quote_value is None and int(base_value) > 0:
        buy_or_sell = 'buy'
        base_value = int(args['a'][1])
        quote_balance, _ = get(quote_tick, 'balance', 0, addr)

        chess_predict_sell_id = chess_predict_sell_start
        while True:
            sell, _ = get('chess_predict', f'{pair}_sell', None, str(chess_predict_sell_id))
            if sell is None:
                break

            price = sell[3]
            dx_base = min(-sell[1], quote_balance * quote_scale // price, base_value)
            dx_quote = dx_base * price // quote_scale
            if dx_base == 0 or dx_quote == 0:
                break
            if quote_balance - dx_quote < 0:
                break

            sell[1] += dx_base
            sell[2] -= dx_quote
            take_base += dx_base
            take_quote += dx_quote
            quote_balance -= dx_quote

            if sell[1] == 0 or sell[1] * quote_scale // price == 0:
                chess_predict_sell_start = _remove_order(addr, pair, sell, chess_predict_sell_start, 'sell')
                if sell[1] < 0:
                    _update_slug_balance(sell[0], slug, yes_or_no, -sell[1])

                put(sell[0], 'chess_predict', f'{pair}_sell', None, str(chess_predict_sell_id))
            else:
                put(sell[0], 'chess_predict', f'{pair}_sell', sell, str(chess_predict_sell_id))

            _update_quote_balance(sell[0], quote_tick, dx_quote)
            base_value -= dx_base
            assert base_value >= 0
            _update_slug_balance(addr, slug, yes_or_no, dx_base)

            if sell[4] is None:
                break
            chess_predict_sell_id = sell[4]

        _update_quote_balance(addr, quote_tick, -take_quote)

    elif base_value is None and int(quote_value) < 0:
        buy_or_sell = 'buy'
        quote_value = int(args['a'][3])
        quote_balance, _ = get(quote_tick, 'balance', 0, addr)
        # quote_sum = 0

        chess_predict_sell_id = chess_predict_sell_start
        while True:
            sell, _ = get('chess_predict', f'{pair}_sell', None, str(chess_predict_sell_id))
            if sell is None:
                break

            price = sell[3]
            dx_base = min(-sell[1], -quote_value * quote_scale // price)
            dx_quote = dx_base * price // quote_scale
            if dx_base == 0 or  dx_quote == 0:
                break
            if quote_balance - dx_quote < 0:
                break

            sell[1] += dx_base
            sell[2] -= dx_quote
            take_base += dx_base
            take_quote += dx_quote
            quote_balance -= dx_quote
            # quote_sum += dx_quote

            if sell[1] == 0 or sell[1] * quote_scale // price == 0:
                chess_predict_sell_start = _remove_order(addr, pair, sell, chess_predict_sell_start, 'sell')

                if sell[1] < 0:
                    _update_slug_balance(sell[0], slug, yes_or_no, -sell[1])
                    # balance, _ = get('chess_predict', f'{pair}_balance', 0, sell[0])
                    # balance -= sell[1]
                    # assert balance >= 0
                    # put(sell[0], 'chess_predict', f'{pair}_balance', balance, sell[0])

                put(sell[0], 'chess_predict', f'{pair}_sell', None, str(chess_predict_sell_id))
            else:
                put(sell[0], 'chess_predict', f'{pair}_sell', sell, str(chess_predict_sell_id))

            _update_quote_balance(sell[0], quote_tick, dx_quote)
            # balance, _ = get(quote_tick, 'balance', 0, sell[0])
            # balance += dx_quote
            # assert balance >= 0
            # put(sell[0], quote_tick, 'balance', balance, sell[0])

            quote_value += dx_quote
            assert quote_value <= 0
            _update_slug_balance(addr, slug, yes_or_no, dx_base)
            # balance, _ = get('chess_predict', f'{pair}_balance', 0, addr)
            # balance += dx_base
            # assert balance >= 0
            # put(addr, 'chess_predict', f'{pair}_balance', balance, addr)

            if sell[4] is None:
                break
            chess_predict_sell_id = sell[4]

        _update_quote_balance(addr, quote_tick, -take_quote)
        # balance, _ = get(quote_tick, 'balance', 0, addr)
        # balance -= take_quote
        # assert balance >= 0
        # put(addr, quote_tick, 'balance', balance, addr)

    elif base_value is None and int(quote_value) > 0:
        buy_or_sell = 'sell'
        quote_value = int(args['a'][3])
        [base_balance, _], _ = get('chess_predict', f'{pair}_balance', [0, None], addr)
        # base_sum = 0

        chess_predict_buy_id = chess_predict_buy_start
        while True:
            buy, _ = get('chess_predict', f'{pair}_buy', None, str(chess_predict_buy_id))
            if buy is None:
                break

            price = buy[3]
            dx_base = min(buy[1], base_balance, quote_value * quote_scale // price)
            dx_quote = dx_base * price // quote_scale
            if dx_base == 0 or dx_quote == 0:
                break
            if base_balance - dx_base < 0:
                break

            buy[1] -= dx_base
            buy[2] += dx_quote
            take_base += dx_base
            take_quote += dx_quote
            base_balance -= dx_base
            # base_sum += dx_base

            if buy[1] == 0 or buy[1] * quote_scale // price == 0:
                chess_predict_buy_start = _remove_order(addr, pair, buy, chess_predict_buy_start, 'buy')

                if buy[2] < 0:
                    _update_quote_balance(buy[0], quote_tick, -buy[2])
                    # balance, _ = get(quote_tick, 'balance', 0, buy[0])
                    # balance -= buy[2]
                    # assert balance >= 0
                    # put(buy[0], quote_tick, 'balance', balance, buy[0])

                put(buy[0], 'chess_predict', f'{pair}_buy', None, str(chess_predict_buy_id))
            else:
                put(buy[0], 'chess_predict', f'{pair}_buy', buy, str(chess_predict_buy_id))

            _update_slug_balance(buy[0], slug, yes_or_no, dx_base)
            # balance, _ = get('chess_predict', f'{pair}_balance', 0, buy[0])
            # balance += dx_base
            # assert balance >= 0
            # put(buy[0], 'chess_predict', f'{pair}_balance', balance, buy[0])

            quote_value -= dx_quote
            assert quote_value >= 0
            _update_quote_balance(addr, quote_tick, dx_quote)
            # balance, _ = get(quote_tick, 'balance', 0, addr)
            # balance += dx_quote
            # assert balance >= 0
            # put(addr, quote_tick, 'balance', balance, addr)

            if buy[4] is None:
                break
            chess_predict_buy_id = buy[4]

        _update_slug_balance(addr, slug, yes_or_no, -take_base)
        # balance, _ = get('chess_predict', f'{pair}_balance', 0, addr)
        # balance -= take_base
        # assert balance >= 0
        # put(addr, 'chess_predict', f'{pair}_balance', balance, addr)

    if take_base > 0:
        price = take_quote * quote_scale // take_base
        event('PredictMarketTake', [pair, buy_or_sell, addr, take_base, price])


def chess_predict_limit_order_cancel(info, args):
    assert args['f'] == 'chess_predict_limit_order_cancel'
    sender = info['sender']
    addr = handle_lookup(sender)

    slug = args['a'][0]
    yes_or_no = args['a'][1]
    buy_or_sell = args['a'][2]
    chess_predict_order_id = int(args['a'][3])
    assert set(slug) <= set(string.ascii_lowercase+string.digits+'_')
    assert yes_or_no in set(['yes', 'no'])
    assert buy_or_sell in ['buy', 'sell']
    assert chess_predict_order_id > 0

    pair = f'{slug}_{yes_or_no}'
    order_key = f'{pair}_{buy_or_sell}'
    quote_tick, _ = get('chess_predict', f'{slug}_quote_token', None)
    order, _ = get('chess_predict', order_key, None, str(chess_predict_order_id))

    if order is None:
        return

    assert order[0] == addr, "Sender is not the owner of the order"
    prev_order_id = order[4]
    next_order_id = order[5]

    if prev_order_id is not None:
        prev_order, _ = get('chess_predict', order_key, None, str(prev_order_id))
        if prev_order:
            prev_order[5] = next_order_id
            put(prev_order[0], 'chess_predict', order_key, prev_order, str(prev_order_id))

    if next_order_id is not None:
        next_order, _ = get('chess_predict', order_key, None, str(next_order_id))
        if next_order:
            next_order[4] = prev_order_id
            put(next_order[0], 'chess_predict', order_key, next_order, str(next_order_id))

    start_key = f'{pair}_{buy_or_sell}_start'
    current_start, _ = get('chess_predict', start_key, 1)
    if current_start == chess_predict_order_id:
        if prev_order_id is not None:
            put(addr, 'chess_predict', start_key, prev_order_id)
        else:
            new_start_key = f'{pair}_{buy_or_sell}_new'
            new_start_val, _ = get('chess_predict', new_start_key, 1)
            put(addr, 'chess_predict', start_key, new_start_val)

    if buy_or_sell == 'sell':
        if order[1] < 0:
            _update_slug_balance(addr, slug, yes_or_no, -order[1])
            # balance, _ = get('chess_predict', f'{pair}_balance', 0, addr)
            # balance -= order[1]
            # put(addr, 'chess_predict', f'{pair}_balance', balance, addr)
    elif buy_or_sell == 'buy':
        if order[2] < 0:
            _update_quote_balance(addr, quote_tick, -order[2])
            # balance, _ = get(quote_tick, 'balance', 0, addr)
            # balance -= order[2]
            # put(addr, quote_tick, 'balance', balance, addr)

    put(addr, 'chess_predict', order_key, None, str(chess_predict_order_id))
    event('PredictOrderCancel', [chess_predict_order_id, buy_or_sell, pair])

def chess_predict_create(info, args):
    assert args['f'] == 'chess_predict_create'
    sender = info['sender']
    addr = handle_lookup(sender)

    slug = args['a'][0]
    quote_tick = args['a'][1]
    assert set(slug) <= set(string.ascii_lowercase+string.digits+'_')

    quote_tokens, _ = get('chess', 'chess_quote_tokens', [])
    assert quote_tick in quote_tokens, f'{quote_tick} is not a designated quote token'

    manager, _ = get('chess', 'chess_manager', None)
    assert manager == addr, f"Sender must be the owner of predict system"
    created, _ = get('chess_predict', f'{slug}_quote_token', None)
    assert created is None, "Slug already exists"
    put(addr, 'chess_predict', f'{slug}_quote_token', quote_tick)

    put(addr, 'chess_predict', f'{slug}_yes_buy_start', 1)
    put(addr, 'chess_predict', f'{slug}_yes_buy_new', 1)
    put(addr, 'chess_predict', f'{slug}_yes_sell_start', 1)
    put(addr, 'chess_predict', f'{slug}_yes_sell_new', 1)
    put(addr, 'chess_predict', f'{slug}_yes_balance_new', None)

    put(addr, 'chess_predict', f'{slug}_no_buy_start', 1)
    put(addr, 'chess_predict', f'{slug}_no_buy_new', 1)
    put(addr, 'chess_predict', f'{slug}_no_sell_start', 1)
    put(addr, 'chess_predict', f'{slug}_no_sell_new', 1)
    put(addr, 'chess_predict', f'{slug}_no_balance_new', None)

    event('PredictCreate', [slug, quote_tick, addr])


def chess_predict_mint(info, args):
    assert args['f'] == 'chess_predict_mint'
    sender = info['sender']
    addr = handle_lookup(sender)

    slug = args['a'][0]
    assert set(slug) <= set(string.ascii_lowercase+string.digits+'_')

    quote_tick, _ = get('chess_predict', f'{slug}_quote_token', None)
    assert quote_tick, "Slug is not created"

    quote_value = int(args['a'][1])
    assert quote_value > 0

    _update_quote_balance(addr, quote_tick, -quote_value)
    # The deposit is escrowed per slug. One unit of quote backs one YES plus
    # one NO, and only one side can ever pay out, so payout is capped at the
    # pot by construction. Without this the deposit was simply destroyed and
    # every outstanding claim was unsecured.
    _update_pot(slug, quote_tick, quote_value)

    for tick in ['yes', 'no']:
        _update_slug_balance(addr, slug, tick, quote_value)

    event('PredictMint', [slug, addr, quote_value])


def _chess_predict_submit(slug, yes_or_no):
    manager, _ = get('chess', 'chess_manager', None)
    assert manager is not None, "Manager not set"
    addr = manager
    assert set(slug) <= set(string.ascii_lowercase+string.digits+'_')
    assert yes_or_no in set(['yes', 'no', 'draw'])
    is_draw = yes_or_no == 'draw'
    # A draw pays both outcomes at half value.  Keep YES as the first side
    # processed; the second pass below pays NO as well.
    settle_tick = 'yes' if is_draw else yes_or_no
    lose_tick = 'no' if settle_tick == 'yes' else 'yes'

    quote_tick, _ = get('chess_predict', f'{slug}_quote_token', None)
    assert quote_tick, "Slug not exists"

    win_pair = f'{slug}_{settle_tick}'
    win_sell_start, _ = get('chess_predict', f'{win_pair}_sell_start', 1)
    win_buy_start, _ = get('chess_predict', f'{win_pair}_buy_start', 1)

    chess_predict_sell_id = win_sell_start
    while True:
        sell, _ = get('chess_predict', f'{win_pair}_sell', None, str(chess_predict_sell_id))
        if not sell:
            break
        next_id = sell[4]
        if sell[1] < 0:
            _update_slug_balance(sell[0], slug, settle_tick, -sell[1])
        put(sell[0], 'chess_predict', f'{win_pair}_sell', None, str(chess_predict_sell_id))
        if next_id is None:
            break
        chess_predict_sell_id = next_id

    chess_predict_buy_id = win_buy_start
    while True:
        buy, _ = get('chess_predict', f'{win_pair}_buy', None, str(chess_predict_buy_id))
        if not buy:
            break
        next_id = buy[4]
        if buy[2] < 0:
            _update_quote_balance(buy[0], quote_tick, -buy[2])
        put(buy[0], 'chess_predict', f'{win_pair}_buy', None, str(chess_predict_buy_id))
        if next_id is None:
            break
        chess_predict_buy_id = next_id

    put(addr, 'chess_predict', f'{win_pair}_sell_start', None)
    put(addr, 'chess_predict', f'{win_pair}_sell_new', None)
    put(addr, 'chess_predict', f'{win_pair}_buy_start', None)
    put(addr, 'chess_predict', f'{win_pair}_buy_new', None)

    win_balance_new, _ = get('chess_predict', f'{win_pair}_balance_new', None)
    current_addr = win_balance_new
    while current_addr is not None:
        balance_tuple, _ = get('chess_predict', f'{win_pair}_balance', None, current_addr)
        if balance_tuple is None:
            break
        balance, prev = balance_tuple
        assert balance >= 0
        if is_draw:
            assert balance % 2 == 0, "Draw payout is not representable in quote units"
        payout = balance // 2 if is_draw else balance
        # Pay from escrow, never by minting quote.  On-chain token units are
        # integral, so an odd unit is rounded down consistently.
        _update_pot(slug, quote_tick, -payout)
        _update_quote_balance(current_addr, quote_tick, payout)
        put(current_addr, 'chess_predict', f'{win_pair}_balance', None, current_addr)
        current_addr = prev
    put(addr, 'chess_predict', f'{win_pair}_balance_new', None)

    lose_pair = f'{slug}_{lose_tick}'
    lose_sell_start, _ = get('chess_predict', f'{lose_pair}_sell_start', 1)
    lose_buy_start, _ = get('chess_predict', f'{lose_pair}_buy_start', 1)

    chess_predict_sell_id = lose_sell_start
    while True:
        sell, _ = get('chess_predict', f'{lose_pair}_sell', None, str(chess_predict_sell_id))
        if not sell:
            break
        next_id = sell[4]
        put(sell[0], 'chess_predict', f'{lose_pair}_sell', None, str(chess_predict_sell_id))
        if next_id is None:
            break
        chess_predict_sell_id = next_id

    chess_predict_buy_id = lose_buy_start
    while True:
        buy, _ = get('chess_predict', f'{lose_pair}_buy', None, str(chess_predict_buy_id))
        if not buy:
            break
        next_id = buy[4]
        put(buy[0], 'chess_predict', f'{lose_pair}_buy', None, str(chess_predict_buy_id))
        if next_id is None:
            break
        chess_predict_buy_id = next_id

    put(addr, 'chess_predict', f'{lose_pair}_sell_start', None)
    put(addr, 'chess_predict', f'{lose_pair}_sell_new', None)
    put(addr, 'chess_predict', f'{lose_pair}_buy_start', None)
    put(addr, 'chess_predict', f'{lose_pair}_buy_new', None)

    balance_new, _ = get('chess_predict', f'{lose_pair}_balance_new', None)
    current_addr = balance_new
    while current_addr is not None:
        balance_tuple, _ = get('chess_predict', f'{lose_pair}_balance', None, current_addr)
        if balance_tuple is None:
            break
        balance, prev = balance_tuple
        if is_draw:
            assert balance % 2 == 0, "Draw payout is not representable in quote units"
            payout = balance // 2
            _update_pot(slug, quote_tick, -payout)
            _update_quote_balance(current_addr, quote_tick, payout)
        put(current_addr, 'chess_predict', f'{lose_pair}_balance', None, current_addr)
        current_addr = prev
    put(addr, 'chess_predict', f'{lose_pair}_balance_new', None)

    pot_quote, _ = get(quote_tick, 'balance', 0, f'pot_chess_predict:{slug}')
    assert pot_quote == 0, "Escrow pot not fully drained"

    put(addr, 'chess_predict', f'{slug}_quote_token', None)
    event('PredictSubmit', [slug, yes_or_no])


def chess_predict_set_quote_tokens(info, args):
    assert args['f'] == 'chess_predict_set_quote_tokens'
    sender = info['sender']
    addr = handle_lookup(sender)

    manager, _ = get('chess', 'chess_manager', None)
    assert manager is not None, "Manager not set"
    assert addr == manager, "Only the manager can add quote tokens"

    new_tokens = args['a'][0]
    assert isinstance(new_tokens, list), "Quote tokens must be a list"

    quote_tokens, _ = get('chess', 'chess_quote_tokens', [])

    for token in new_tokens:
        assert isinstance(token, str), "Token ticker must be a string"
        assert len(token) > 0 and len(token) < 42, "Invalid token ticker length"
        assert token[0] in string.ascii_uppercase, "Token ticker must start with an uppercase letter"
        assert set(token) <= set(string.ascii_uppercase+string.digits+'_'), "Invalid characters in token ticker"
        if token not in quote_tokens:
            quote_tokens.append(token)

    put(addr, 'chess', 'chess_quote_tokens', quote_tokens)

def chess_update_manager(info, args):
    """Transfer control of chess markets to another address."""
    assert args['f'] == 'chess_update_manager'
    addr = handle_lookup(info['sender'])
    manager, _ = get('chess', 'chess_manager', None)
    assert manager is not None and addr == manager, 'Only the manager can change manager'
    user = args['a'][0]
    assert isinstance(user, str) and user
    put(addr, 'chess', 'chess_manager', user.lower())
    event('ChessManagerUpdated', [addr, user.lower()])


