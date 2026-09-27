"""Run: python -m app.evaluate evaluation.jsonl [--output evaluation-results.json]."""
import argparse
import json
from pathlib import Path
from app.arabic import tokens, skeleton, ending


def score(reference: str, prediction: str) -> dict:
    ref, hyp = tokens(reference), tokens(prediction)
    if not ref:
        raise ValueError('Each reference must contain Arabic words.')
    # Align by spelling first; ending agreement breaks spelling-alignment ties.
    # Unlike zip(), insertions/deletions cannot shift all subsequent endings.
    n, m = len(ref), len(hyp)
    dp = [[(0, 0)] * (m+1) for _ in range(n+1)]
    back = {}
    for i in range(1, n+1): dp[i][0] = (i, i); back[i, 0] = 'delete'
    for j in range(1, m+1): dp[0][j] = (j, j); back[0, j] = 'insert'
    for i in range(1, n+1):
        for j in range(1, m+1):
            mismatch = int(skeleton(ref[i-1]) != skeleton(hyp[j-1]))
            mark_error = int(ending(ref[i-1]) != ending(hyp[j-1]))
            options = [((dp[i-1][j-1][0]+mismatch, dp[i-1][j-1][1]+mark_error), 'pair'),
                       ((dp[i-1][j][0]+1, dp[i-1][j][1]+1), 'delete'),
                       ((dp[i][j-1][0]+1, dp[i][j-1][1]+1), 'insert')]
            dp[i][j], back[i, j] = min(options, key=lambda p:p[0])
    i, j = n, m
    correct = matched = ending_correct = insertions = 0
    details = []
    while i or j:
        op = back[i, j]
        if op == 'pair':
            r, h = ref[i-1], hyp[j-1]
            same_word = skeleton(r) == skeleton(h)
            same_ending = ending(r) == ending(h)
            matched += same_word
            ending_correct += same_word and same_ending
            correct += same_word and same_ending
            details.append({'reference':r, 'prediction':h, 'correct':same_word and same_ending})
            i -= 1; j -= 1
        elif op == 'delete':
            details.append({'reference':ref[i-1], 'prediction':None, 'correct':False}); i -= 1
        else:
            insertions += 1
            details.append({'reference':None, 'prediction':hyp[j-1], 'correct':False}); j -= 1
    denominator = n + insertions
    return {'reference_words':n, 'insertions':insertions, 'correct_words_and_endings':correct,
            'matched_words':matched, 'correct_endings_on_matched_words':ending_correct,
            'strict_final_word_accuracy':correct/denominator,
            'ending_accuracy_on_matched_words':ending_correct/matched if matched else None,
            'word_error_rate':dp[n][m][0]/n, 'alignment':list(reversed(details))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--output', type=Path, default=Path('evaluation-results.json'))
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.manifest.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    if not rows: parser.error('The evaluation manifest is empty.')
    results = []
    for row in rows:
        if 'prediction' in row:
            prediction = row['prediction']
        else:
            from app.audio import decode_audio, split_at_silence
            from app.engine import engine
            audio = decode_audio((args.manifest.parent / row['audio']).read_bytes())
            prediction = ' '.join(engine.transcribe(audio[a:b]) for a,b in split_at_silence(audio))
        results.append({'id':row.get('id', row.get('audio')), 'prediction':prediction,
                        **score(row['reference'], prediction)})
    correct = sum(r['correct_words_and_endings'] for r in results)
    total = sum(r['reference_words']+r['insertions'] for r in results)
    accuracy = correct / total
    report = {'clips':len(results), 'strict_final_word_accuracy':accuracy,
              'above_90_percent_on_this_dataset':accuracy > .90,
              'note':'This result applies only to the supplied references. Use held-out human recordings and audit their labels.',
              'results':results}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Strict word + ending accuracy: {accuracy:.2%} ({correct}/{total}); report: {args.output}')


if __name__ == '__main__': main()
