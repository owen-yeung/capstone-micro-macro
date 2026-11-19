"""Evidence packets and persistence for explicitly authored content judgments.

No provider, automatic semantic label, keyword score, or default grade.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from capstone_cp_common_20261112 import ROOT, CP00, CP01, read, save, sha
from review_capstone_phase1_20261112 import cards as old_cards, locate

BASE = ROOT / 'Capstone报告/验证体系'
MASTER = BASE / '实验/2026-11-13_总实验收尾'
PACKS = {'CP08': BASE / '实验/2026-11-13_CP08全量微观扩样',
         'CP07': BASE / '实验/2026-11-13_CP07组织质量对照'}


def content_view(data):
    """Read outward text without converting invalid output into acceptance.

    One retained response consists of a thoughts-only JSON object followed by
    one complete business JSON object. A unique public object can be read for
    semantic review; multiple public answers are left ambiguous, never merged.
    """
    private = {'thoughts', 'company_assessment'}
    payload = data.get('parsed')
    if isinstance(payload, dict):
        return {k: v for k, v in payload.items() if k not in private}, {'mode': 'original_parsed_public_fields'}
    raw = data.get('raw_content', '')
    if not isinstance(raw, str) or not raw.strip():
        return None, {'mode': 'no_raw_answer'}
    decoder, offset, objects = json.JSONDecoder(), 0, []
    try:
        while offset < len(raw):
            while offset < len(raw) and raw[offset].isspace():
                offset += 1
            if offset == len(raw):
                break
            start = offset
            obj, offset = decoder.raw_decode(raw, offset)
            if not isinstance(obj, dict):
                return None, {'mode': 'non_object_or_ambiguous_raw'}
            public = {k: v for k, v in obj.items() if k not in private}
            objects.append({'public': public, 'start': start, 'end': offset})
    except (ValueError, TypeError):
        return None, {'mode': 'unparsed_raw_needs_manual_review'}
    candidates = [(i, obj) for i, obj in enumerate(objects) if obj['public']]
    if len(candidates) != 1:
        return None, {'mode': 'multiple_or_no_public_objects_not_merged', 'top_level_object_count': len(objects)}
    index, selected = candidates[0]
    return selected['public'], {'mode': 'unique_public_object_content_read_only',
        'top_level_object_count': len(objects), 'selected_object_index': index,
        'raw_object_start': selected['start'], 'raw_object_end': selected['end'],
        'original_program_status_unchanged': True}


def source(cohort, window_id, arm, repeat=1, attempt=1):
    assert cohort in {'CP00', 'CP01', 'CP08', 'CP07'}
    if cohort == 'CP07':
        assert arm in {'S', 'D3', 'S4'} and repeat == attempt == 1
        path = PACKS[cohort] / 'run/jobs' / f'{window_id}-{arm}-r1/step-4.json'
        for version in ['continuation-001', 'continuation-002']:
            continuation = PACKS[cohort] / version / 'run/jobs' / f'{window_id}-{arm}-r1/step-4.json'
            if continuation.exists():
                if path.exists():
                    assert sha(path) == sha(continuation), 'Original/continuation duplicate final differs'
                path = continuation
    else:
        assert arm in {'v2_4', 'v2_5'}
        root = {'CP00': CP00, 'CP01': CP01, **PACKS}[cohort]
        path = root / 'run/jobs' / f'{window_id}-{arm}-r{repeat}' / f'attempt-{attempt}.json'
        continuation = root / 'continuation-001/run/jobs' / f'{window_id}-{arm}-r{repeat}' / f'attempt-{attempt}.json'
        if cohort in {'CP01', 'CP08'} and continuation.exists():
            if path.exists():
                assert sha(path) == sha(continuation), 'Original/continuation duplicate differs'
            path = continuation
    data = read(path)
    payload, view = content_view(data)
    return path, {**data, 'content_review_read_view': view}, payload


def cards(cohort):
    if cohort in {'CP00', 'CP01'}:
        return old_cards(cohort)
    path = PACKS[cohort] / 'task_cards.json'
    return path, {r['window_id']: r for r in read(path)}


def needs_detailed(cohort, card, repeat):
    if cohort == 'CP07':
        return True
    if cohort == 'CP01':
        return repeat == 1
    if cohort == 'CP08':
        return card['project_group'] in read(PACKS['CP08'] / 'detailed_score_groups.json')
    return False


def packet(cohort, wid, attempt, selected_arm=None, selected_repeat=None, response_only=False):
    path, by_id = cards(cohort)
    card = by_id[wid]
    if not response_only:
        print(json.dumps({'cohort': cohort, 'input': card}, ensure_ascii=False))
    arms = [selected_arm] if selected_arm else (['S', 'D3', 'S4'] if cohort == 'CP07' else ['v2_4', 'v2_5'])
    repeats = [selected_repeat] if selected_repeat else ([1, 2] if cohort in {'CP00', 'CP01'} else [1])
    for arm in arms:
        for repeat in repeats:
            try:
                response, data, outward = source(cohort, wid, arm, repeat, attempt)
            except FileNotFoundError:
                print(json.dumps({'arm': arm, 'repeat': repeat, 'state': 'not_present'}))
                continue
            print(json.dumps({'arm': arm, 'repeat': repeat, 'attempt': attempt, 'status_retained': data['status'],
                 'response_path': str(response.relative_to(ROOT)).replace('\\', '/'), 'sha256': sha(response),
                 'outward': outward, 'readable_json': isinstance(outward, dict),
                 'content_review_read_view': data['content_review_read_view'],
                 'detailed_scoring_required': needs_detailed(cohort, card, repeat)}, ensure_ascii=False))


def evidence(payload, judgment, *, permit_absence=False):
    assert judgment['reason'].strip()
    quote = judgment.get('quote')
    if not quote:
        assert permit_absence, 'An exact outward quote is required'
        return None
    position = locate(payload, quote)
    assert position, 'Not an exact outward quote: ' + quote
    return position


def ingest(path):
    assert (MASTER / 'calibration/six_block_calibration.json').exists()
    rows = read(path)
    prepared = []
    for row in rows:
        cohort, wid, arm, repeat = (row[k] for k in ['cohort', 'window_id', 'arm', 'repeat'])
        attempt = row.get('attempt', 1)
        card_path, by_id = cards(cohort)
        card = by_id[wid]
        response, data, outward = source(cohort, wid, arm, repeat, attempt)
        assert isinstance(outward, dict), 'Missing/unreadable responses receive no synthetic grade'
        assert row['D1']['label'] in {'appropriate', 'inappropriate', 'not_judgable'}
        d1 = {**row['D1'], 'evidence': evidence(outward, row['D1'])}
        assert len(row['factors']) == len(card['factors'])
        factors = []
        for authored, criterion in zip(row['factors'], card['factors']):
            assert authored['id'] == criterion['factor_id'] and authored['rating'] in criterion['states']
            factors.append({**deepcopy(authored),
                'evidence': evidence(outward, authored, permit_absence=authored['rating'] in {'missing', 'not_judgable'}),
                'criterion': criterion['adequate_handling'],
                'defer_decline_criterion': criterion['handling_for_supported_defer_or_decline'],
                'input_pointers': criterion['input_pointers']})
        detailed = {}
        for metric in ['D3', 'D4']:
            value = row.get(metric)
            if needs_detailed(cohort, card, repeat):
                assert value is not None, 'Frozen detailed scoring required: ' + metric
            if value is not None:
                assert (type(value['score']) is int and value['score'] in {0, 1, 2}) or value['score'] == 'not_judgable'
                detailed[metric] = {**deepcopy(value), 'evidence': evidence(outward, value)}
        record = {'cohort': cohort, 'window_id': wid, 'arm': arm, 'repeat': repeat, 'attempt': attempt,
            'project_group': card['project_group'], 'role': card['role'], 'annotated_action': row['action'],
            'response_path': str(response.relative_to(ROOT)).replace('\\', '/'), 'response_sha256': sha(response),
            'call_id': data['call_id'], 'program_status_retained': data['status'], 'D1': d1, 'factor_ratings': factors,
            'content_review_read_view': data['content_review_read_view'],
            'D2_correct_coverage': sum(f['rating'] == 'correct' for f in factors) / len(factors),
            'detailed': detailed, 'input_card_path': str(card_path.relative_to(ROOT)).replace('\\', '/'),
            'input_card_sha256': sha(card_path),             'authored_labels_path': str(path.resolve().relative_to(ROOT)).replace('\\', '/'),
            'authored_labels_sha256': sha(path), 'initial_review_complete': True, 'evidence_recheck': None,
            'reviewer': (
                '独立第二LLM提供方评阅；非原管线设计参与者，非人类外部专家，非盲评'
                if 'GV20261117' in str(path) or 'independent_second_llm_provider' in str(path)
                else '作者辅助AI评阅；参与设计，同一助手，非独立专业评阅，非盲评'
            ),
            'evaluation_identity': 'exploratory_old_material' if cohort == 'CP00' else 'fixed_cohort_content_review'}
        prepared.append((MASTER / 'business_review' / cohort / f'{wid}-{arm}-r{repeat}-a{attempt}.json', record))
    for destination, record in prepared:
        save(destination, record)
    print(json.dumps({'explicitly_authored_reviews_saved': len(rows), 'new_model_calls': 0}))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--packet', nargs=2, metavar=('COHORT', 'WINDOW'))
    p.add_argument('--attempt', type=int, default=1)
    p.add_argument('--arm')
    p.add_argument('--repeat', type=int)
    p.add_argument('--response-only', action='store_true')
    p.add_argument('--ingest', type=Path)
    a = p.parse_args()
    if a.packet:
        packet(*a.packet, a.attempt, a.arm, a.repeat, a.response_only)
    elif a.ingest:
        ingest(a.ingest)
    else:
        p.error('Choose a source packet or explicitly authored labels')
