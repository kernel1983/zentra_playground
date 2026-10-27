# -*- coding: utf-8 -*-
"""
zip101.py - Onchain chess state transition prototype
All functions and states must be prefixed with `chess_`
Move format: like "g4d7" or "g7g8q" (from+to, optional promotion)
"""

import string
import hashlib

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
    put(addr, 'chess', 'chess_game_count', 1)
    event('ChessInit', [addr])

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

    put(addr, 'chess', 'chess_state', new_state, game_id)
    event('ChessMove', [game_id, addr, mstr.strip().lower(), mp, new_state['chess_turn'], new_state['chess_status'], new_state['chess_result']])
    return {'chess_ok': True, 'chess_move_count': new_state['chess_move_count'], 'chess_status': new_state['chess_status'], 'chess_result': new_state['chess_result'], 'chess_winner': new_state['chess_winner'], 'chess_turn': new_state['chess_turn']}
