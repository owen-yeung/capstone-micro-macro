"""Expand explicitly authored tabular judgments; never infer semantic scores.

Column order: D1=[label, exact quote, reason]; factors=[id, rating, quote,
reason]; D3/D4=[score, quote, reason]. Every row includes its own action and
same-author evidence-recheck reason. Metadata is explicit at bundle level.
"""
import argparse
import json
from pathlib import Path
from review_capstone_all_20261113 import ROOT,read,save,sha,ingest,source,locate
from recheck_capstone_authored_evidence_20261113 import main as recheck

ALLOWED_IDENTITIES = {
    # Legacy author-assisted bundles (pre-Cursor pipeline participant).
    'explicitly_authored_initial_and_same_assistant_recheck',
    # Cursor / independent second LLM provider adjudication (GV20261117+).
    'explicitly_authored_initial_and_independent_second_llm_provider_recheck',
}


def main(path):
    path=path.resolve()
    bundle=read(path)
    cohort,repeat,attempt=[bundle[k] for k in ['cohort','repeat','attempt']]
    assert bundle['identity'] in ALLOWED_IDENTITIES
    rows=[];notes=[]
    for authored in bundle['rows']:
        assert len(authored['D1'])==3 and authored['recheck_reason'].strip()
        label,quote,reason=authored['D1']
        row={'cohort':cohort,'window_id':authored['window_id'],'arm':authored['arm'],
             'repeat':repeat,'attempt':attempt,'action':authored['action'],
             'D1':dict(label=label,quote=quote,reason=reason),'factors':[]}
        for factor in authored['factors']:
            assert len(factor)==4
            fid,rating,quote,reason=factor
            row['factors'].append(dict(id=fid,rating=rating,quote=quote,reason=reason))
        for metric in ['D3','D4']:
            if metric in authored:
                assert len(authored[metric])==3
                score,quote,reason=authored[metric]
                row[metric]=dict(score=score,quote=quote,reason=reason)
        rows.append(row)
        notes.append({'cohort':cohort,'window_id':authored['window_id'],'arm':authored['arm'],
                      'repeat':repeat,'attempt':attempt,'conclusion':'no_change',
                      'reason':authored['recheck_reason']})
    assert rows
    quote_errors=[]
    for row in rows:
        raw_path,_,payload=source(cohort,row['window_id'],row['arm'],repeat,attempt)
        assert payload is not None
        judgments=[('D1',row['D1']),*[(f['id'],f) for f in row['factors']],
                   *[(k,row[k]) for k in ['D3','D4'] if k in row]]
        for metric,value in judgments:
            if value.get('quote'):
                if not locate(payload,value['quote']):
                    quote_errors.append({'window_id':row['window_id'],'arm':row['arm'],
                        'metric_or_factor':metric,'quote':value['quote'],
                        'exact_source_path':str(raw_path.relative_to(ROOT))})
    assert not quote_errors, json.dumps({'all_exact_quote_errors_before_any_write':quote_errors},ensure_ascii=False)
    labels=path.with_name(path.stem+'_expanded_labels.json')
    checks=path.with_name(path.stem+'_expanded_rechecks.json')
    save(labels,rows);save(checks,notes)
    ingest(labels);recheck(checks)
    save(path.with_name(path.stem+'_lineage.json'),{
        'authored_compact_path':str(path.relative_to(ROOT)),'authored_compact_sha256':sha(path),
        'expanded_labels_sha256':sha(labels),'expanded_rechecks_sha256':sha(checks),
        'compiler_code_sha256':sha(__file__),'new_semantic_labels_inferred':0,
        'new_provider_calls':0,'rows':len(rows),
        'identity':'Mechanical schema conversion of each explicit author-supplied judgment, not automatic grading or independent review.'})
    print({'explicit_authored_rows_saved':len(rows),'new_provider_calls':0})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('bundle',type=Path);main(p.parse_args().bundle)
