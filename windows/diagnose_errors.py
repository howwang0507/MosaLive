"""Offline replay diagnostics. No service, audio decoder or model imports.

Boundary = first/last two hypothesis words of a final, not an audio diagnosis.
Proper nouns = capitalized reference words except sentence starts and 'I'.
Both are heuristics. Translation chrF is similarity, not semantic accuracy.
"""
import argparse
from array import array
from collections import Counter, defaultdict
import json
from pathlib import Path
import re

import score_eval as score


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def finals_of(events):
    finals = {}
    for event in events:
        if isinstance(event, dict) and event.get('type') == 'final':
            finals.setdefault(event['seq'], event)
    return sorted(finals.values(), key=lambda event: event.get('speech_start_ms', 0))


def align_words(reference, hypothesis):
    """Exact Levenshtein path, scorer's diagonal-first tie break; O(n*m).

    Compact integer rows keep a 2,700-word benchmark to tens of MB, not hundreds.
    """
    table = [array('I', range(len(hypothesis) + 1))]
    for i, word in enumerate(reference, 1):
        previous = table[-1]
        row = array('I', [i])
        for j, other in enumerate(hypothesis, 1):
            row.append(min(previous[j] + 1, row[j - 1] + 1,
                           previous[j - 1] + (word != other)))
        table.append(row)
    i, j = len(reference), len(hypothesis)
    operations = []
    while i or j:
        if i and j and table[i][j] == table[i - 1][j - 1] + (reference[i - 1] != hypothesis[j - 1]):
            operations.append(('C' if reference[i - 1] == hypothesis[j - 1] else 'S', i - 1, j - 1))
            i, j = i - 1, j - 1
        elif i and table[i][j] == table[i - 1][j] + 1:
            operations.append(('D', i - 1, None))
            i -= 1
        else:
            operations.append(('I', None, j - 1))
            j -= 1
    return operations[::-1]


def alignment(segments, finals, normalized):
    reference = [(word, i) for i, segment in enumerate(segments)
                 for word in score.tokens(segment['source'], normalized)]
    hypothesis = [(word, i) for i, final in enumerate(finals)
                  for word in score.tokens(final.get('original', ''), normalized)]
    operations = align_words([word for word, _ in reference], [word for word, _ in hypothesis])
    return reference, hypothesis, operations


def word_errors(segments, finals):
    reference, hypothesis, operations = alignment(segments, finals, True)
    positions = defaultdict(list)
    for j, (_, caption) in enumerate(hypothesis):
        positions[caption].append(j)
    near = {j for indexes in positions.values() for j in indexes[:2] + indexes[-2:]}
    proper = set()
    for segment in segments:
        for sentence in re.split(r'[.!?]\s+', segment['source']):
            words = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", sentence)
            proper.update(word.lower() for word in words[1:] if word[0].isupper() and word != 'I')
    # Deletions have no hypothesis time: use both immediate neighbours, or unknown
    # when they disagree. Unlike the draft, S/I also update the left anchor.
    next_anchor = [None] * len(operations)
    anchor = None
    for k in range(len(operations) - 1, -1, -1):
        next_anchor[k] = anchor
        if operations[k][2] is not None:
            anchor = operations[k][2]
    rows, left = [], None
    for k, (operation, i, j) in enumerate(operations):
        if operation != 'C':
            indexes = [j] if j is not None else [x for x in (left, next_anchor[k]) if x is not None]
            locations = {'boundary' if x in near else 'interior' for x in indexes}
            location = locations.pop() if len(locations) == 1 else 'unknown'
            expected = reference[i][0] if i is not None else ''
            actual = hypothesis[j][0] if j is not None else ''
            kind = ('number' if any(re.fullmatch(r'-?\d+(?:\.\d+)?', x) for x in (expected, actual))
                    else 'proper_noun' if expected in proper or actual in proper else 'other')
            rows.append(dict(operation=operation, reference=expected, hypothesis=actual,
                             reference_index=reference[i][1] if i is not None else None,
                             final_seq=finals[hypothesis[j][1]]['seq'] if j is not None else None,
                             location=location, category=kind))
        if j is not None:
            left = j
    counts = Counter(operation for operation, _, _ in operations)
    return dict(reference_words=len(reference), errors=len(rows),
                wer=round(len(rows) / len(reference), 4) if reference else None,
                operations=dict(counts), locations=dict(Counter(row['location'] for row in rows)),
                categories=dict(Counter(row['category'] for row in rows)),
                boundary_hypothesis_words=len(near), interior_hypothesis_words=len(hypothesis) - len(near),
                details=rows)


def translation_subset(segments, finals, max_errors=1):
    """Use RAW document word alignment; do not hide an ASR error with aliases.

    Cross-reference captions are excluded: their Chinese text cannot be split
    reliably between references. A selection is not a representative quality score.
    """
    reference, hypothesis, operations = alignment(segments, finals, False)
    errors = Counter()
    owners = defaultdict(set)
    words = defaultdict(list)
    # Charge insertions to the next reference, matching scorer.sentence_errors.
    next_reference = [None] * len(operations)
    following = len(segments) - 1
    for k in range(len(operations) - 1, -1, -1):
        i = operations[k][1]
        if i is not None:
            following = reference[i][1]
        next_reference[k] = following
    for k, (operation, i, j) in enumerate(operations):
        owner = reference[i][1] if i is not None else next_reference[k]
        if operation != 'C':
            errors[owner] += 1
        if j is not None:
            owners[hypothesis[j][1]].add(owner)
            words[owner].append(hypothesis[j][0])
    selected, excluded = [], Counter()
    for i, segment in enumerate(segments):
        if errors[i] > max_errors:
            excluded['more_than_one_raw_word_error'] += 1
            continue
        captions = [k for k in range(len(finals)) if i in owners[k]]
        if not captions:
            excluded['no_caption'] += 1
            continue
        if any(owners[k] != {i} for k in captions):
            excluded['caption_spans_multiple_references'] += 1
            continue
        if any(finals[k].get('speech_end_ms', 0) <= segment['start_ms'] or
               finals[k].get('speech_start_ms', 0) >= segment['end_ms'] for k in captions):
            excluded['alignment_without_audio_overlap'] += 1
            continue
        translation = ' '.join(finals[k].get('translation', '') for k in captions)
        if not translation.strip():
            excluded['empty_translation'] += 1
            continue
        selected.append(dict(reference_index=i, source=segment['source'],
                             asr=' '.join(finals[k].get('original', '') for k in captions),
                             raw_word_errors=errors[i], final_seqs=[finals[k]['seq'] for k in captions],
                             translation=translation, reference_translation=segment['reference_zh_tw'],
                             chrf=score.chrf(translation, segment['reference_zh_tw'])))
    return dict(selected=len(selected), exact=sum(row['raw_word_errors'] == 0 for row in selected),
                one_error=sum(row['raw_word_errors'] == 1 for row in selected), excluded=dict(excluded),
                rows=selected, lowest_10=sorted(selected, key=lambda row: (row['chrf'], row['reference_index']))[:10])


def agreement_shadow(events, finals):
    """Observed source stability and received translations, NOT actual DOM adoption."""
    previous = {}
    changes, confirmations, missing = [], 0, 0
    finals_by_seq = {event['seq']: event for event in finals}
    pairs = []
    for event in events:
        if not isinstance(event, dict):
            continue
        seq = event.get('seq')
        if event.get('type') == 'partial' and event.get('phase') == 'asr':
            if 'stable_original' not in event:
                missing += 1
                continue
            stable = event['stable_original']
            before = previous.get(seq, '')
            if before and not stable.startswith(before):
                changes.append(dict(seq=seq, speech_end_ms=event.get('speech_end_ms'),
                                    stage='forced_final' if 'commit_samples' in event else 'agreement_update',
                                    before=before, after=stable))
            if stable and stable != before:
                confirmations += 1
            previous[seq] = stable
        if event.get('type') == 'partial' and event.get('phase') == 'stable' and event.get('translation'):
            final = finals_by_seq.get(seq)
            if final:
                preview = score.norm_zh(event['translation'])
                target = score.norm_zh(final.get('translation', ''))
                distance = score.edit_distance(preview, target)
                pairs.append(dict(seq=seq, speech_end_ms=event.get('speech_end_ms'),
                                  stable_original=event.get('stable_original'), original=event.get('original'),
                                  preview=event['translation'], final=final.get('translation', ''),
                                  edit_distance=distance,
                                  normalized_edit_distance=distance / max(len(preview), len(target), 1),
                                  final_starts_with_preview=target.startswith(preview)))
    return dict(observed_confirmations=confirmations, observed_retractions=len(changes),
                retractions_by_stage=dict(Counter(row['stage'] for row in changes)),
                retractions=changes, asr_events_without_stable_original=missing,
                stable_final_pairs=len(pairs),
                edit_distance_p50=score.pct([p['edit_distance'] for p in pairs], .5),
                edit_distance_p95=score.pct([p['edit_distance'] for p in pairs], .95),
                pairs=pairs,
                caveat='Observed received events only. No DOM timestamps or complete internal Agreement update/reset trace; edit distance includes appended tails.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results', nargs='+', type=Path)
    parser.add_argument('--reference', required=True, type=Path)
    parser.add_argument('--save', required=True, type=Path)
    args = parser.parse_args()
    if args.save.exists():
        parser.error('Output exists; choose a new filename')
    reference = read_json(args.reference)
    reports = {}
    for path in args.results:
        for result in read_json(path)['results']:
            metrics = result.get('metrics', {})
            if any(metrics.get(key, 0) for key in
                   ('reconnects', 'dropped_audio_ms', 'playback_reset_count', 'overflow_count')):
                parser.error('Stream restarted/dropped audio: do not claim exact sentence alignment')
            events = result.get('events', [])
            finals = finals_of(events)
            label = f"{path.stem}:{result['id']}"
            reports[label] = dict(result_file=str(path),
                                  word_errors=word_errors(reference['segments'], finals),
                                  translation_subset=translation_subset(reference['segments'], finals),
                                  agreement=agreement_shadow(events, finals))
            report = reports[label]
            print(label, 'D/I/S:', {k: report['word_errors']['operations'].get(k, 0) for k in ['D', 'I', 'S']},
                  'translation subset:', report['translation_subset']['selected'],
                  'observed retractions:', report['agreement']['observed_retractions'])
    output = dict(scorer_version=score.SCORER_VERSION, reference=str(args.reference),
                  timeline_sha256=reference.get('timeline_sha256'), reports=reports,
                  caveats=['Boundary and proper-noun categories are heuristics, not causes.',
                           'Raw-ASR <=1 word-error subset, ambiguous multi-reference captions excluded.',
                           'chrF is character similarity, not human semantic accuracy.',
                           'Received stable events do not prove display adoption.'])
    with args.save.open('x', encoding='utf-8') as stream:
        json.dump(output, stream, ensure_ascii=False, indent=2)
    print('Saved', args.save)


if __name__ == '__main__':
    main()
