"""Conservative suffix/prefix alignment for transcripts of overlapping audio.

This is text matching, not acoustic forced alignment or word timestamps.
Keep complete predicted words (including marks) from one side of a central
anchor. Never vote on or grammatically correct an ending.
"""
import math
import unicodedata
from app.arabic import WORD, HARAKAT, ending


def key(word):
    return ''.join(c for c in unicodedata.normalize('NFC', word) if c not in HARAKAT)


def align(left, right):
    n, m = len(left), len(right)
    dp = [[0]*(m+1) for _ in range(n+1)]
    for i in range(n+1): dp[i][0] = i
    for j in range(m+1): dp[0][j] = j
    for i in range(1, n+1):
        for j in range(1, m+1):
            dp[i][j] = min(dp[i-1][j-1] + (left[i-1] != right[j-1]),
                           dp[i-1][j]+1, dp[i][j-1]+1)
    i, j, pairs = n, m, []
    while i and j:
        if dp[i][j] == dp[i-1][j-1] + (left[i-1] != right[j-1]):
            if left[i-1] == right[j-1]: pairs.append((i-1, j-1))
            i -= 1; j -= 1
        elif dp[i][j] == dp[i-1][j]+1: i -= 1
        else: j -= 1
    return dp[n][m], list(reversed(pairs))


def merge_pair(left, right, left_duration, right_duration, overlap, left_word_count=None):
    a, b = list(WORD.finditer(left)), list(WORD.finditer(right))
    # Timing bounds limit the search; they are not claimed to be word timestamps.
    cap_a = min(len(a), 40, max(6, math.ceil((left_word_count or len(a))*overlap/left_duration*2)+3))
    cap_b = min(len(b), 40, max(6, math.ceil(len(b)*overlap/right_duration*2)+3))
    ka, kb = [key(x.group()) for x in a], [key(x.group()) for x in b]
    candidates = []
    for n in range(3, cap_a+1):
        for m in range(3, cap_b+1):
            edits, pairs = align(ka[-n:], kb[:m])
            if len(pairs) < 3 or edits/max(n, m) > .3: continue
            if len({ka[len(a)-n+i] for i, _ in pairs}) < 3: continue
            candidates.append((2*len(pairs)-3*edits, n, m, pairs))
    if not candidates:
        return left.rstrip() + '\n' + right.lstrip(), {'status':'unresolved', 'ending_conflicts':0}
    candidates.sort(key=lambda c:c[0], reverse=True)
    best, n, m, pairs = candidates[0]
    # Repeated phrases make text-only joins ambiguous; prefer visible duplication
    # and an explicit warning over silently dropping a potentially spoken repeat.
    matched = [ka[len(a)-n+i] for i, _ in pairs]
    triples = [tuple(matched[i:i+3]) for i in range(len(matched)-2)]
    ambiguous = len(triples) != len(set(triples))
    ambiguous |= any(c[0] >= best-1 and (c[1], c[2]) != (n, m) for c in candidates[1:])
    if ambiguous:
        return left.rstrip() + '\n' + right.lstrip(), {'status':'unresolved', 'ending_conflicts':0}
    # Seam near the middle of the shared speech: avoid both clipped outer edges.
    i, j = min(pairs, key=lambda p:abs((p[0]+.5)/n-.5)+abs((p[1]+.5)/m-.5))
    index = len(a)-n+i
    # Preserve punctuation belonging to the anchor from the left transcript.
    left_end = a[index+1].start() if index+1 < len(a) else len(left)
    right_start = b[j+1].start() if j+1 < len(b) else len(right)
    merged = (left[:left_end].rstrip() + ' ' + right[right_start:].lstrip()).strip()
    conflicts = sum(ending(a[len(a)-n+x].group()) != ending(b[y].group()) for x,y in pairs)
    return merged, {'status':'merged', 'matched_words':len(pairs), 'ending_conflicts':conflicts}


def merge_segments(segments):
    if not segments: return '', []
    text, joins = segments[0]['raw'], []
    for previous, current in zip(segments, segments[1:]):
        overlap = previous['end'] - current['start']
        if overlap <= 0:
            text = (text.rstrip() + ' ' + current['raw'].lstrip()).strip()
            continue
        text, info = merge_pair(text, current['raw'], previous['end']-previous['start'],
                                current['end']-current['start'], overlap,
                                len(list(WORD.finditer(previous['raw']))))
        joins.append({'start':current['start'], 'end':previous['end'], **info})
    return text, joins
