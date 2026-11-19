"""Persist explicitly authored recheck conclusions, no judging API."""
import argparse
from decimal import Decimal
from pathlib import Path

from capstone_cp_common_20261112 import ROOT, read, save, sha
from review_capstone_all_20261113 import MASTER, source, locate


def main(path):
    notes = read(path)
    for note in notes:
        cohort, wid, arm, repeat, attempt = (note[k] for k in ['cohort', 'window_id', 'arm', 'repeat', 'attempt'])
        assert note['conclusion'] == 'no_change' and note['reason'].strip()
        name = f'{wid}-{arm}-r{repeat}-a{attempt}.json'
        initial_path = MASTER / 'business_review' / cohort / name
        initial = read(initial_path)
        response, data, payload = source(cohort, wid, arm, repeat, attempt)
        assert sha(response) == initial['response_sha256']
        positions = [initial['D1']['evidence'], *[f['evidence'] for f in initial['factor_ratings']],
                     *[v['evidence'] for v in initial['detailed'].values()]]
        for position in positions:
            if position:
                assert locate(payload, position['quote']) == position
        numeric = None
        if isinstance(payload.get('quotation_breakdown'), list):
            total = sum((Decimal(str(row['amount'])) for row in payload['quotation_breakdown']), Decimal(0))
            reported = Decimal(str(payload['quotation']))
            numeric = {'parts_sum': str(total), 'reported_total': str(reported),
                       'difference_parts_minus_reported': str(total - reported), 'original_tolerance': '1 MOP'}
        authored_hint = str(initial.get('authored_labels_path') or path)
        if 'GV20261117' in authored_hint or 'independent_second_llm_provider' in authored_hint:
            reviewer = (
                'Independent second LLM provider evidence recheck; '
                'not original pipeline design participant; not external human expert; not blinded'
            )
        else:
            reviewer = 'Same author-assisting AI evidence recheck, not independent or blinded'
        record = {**note, 'reviewer': reviewer,
            'initial_record_path': str(initial_path.relative_to(ROOT)).replace('\\', '/'),
            'initial_record_sha256': sha(initial_path), 'response_sha256': sha(response),
            'task_card_sha256': initial['input_card_sha256'],
            'authored_recheck_notes_sha256': sha(path), 'all_stored_outward_quotes_offsets_verified': True,
            'content_review_read_view': data['content_review_read_view'], 'numeric_recalculation': numeric,
            'complete': True, 'new_provider_calls': 0}
        save(MASTER / 'business_recheck' / cohort / name, record)
    print(f'{len(notes)} explicitly authored rechecks saved; original grades retained; no model calls')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('authored_notes', type=Path)
    main(parser.parse_args().authored_notes)
