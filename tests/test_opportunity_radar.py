"""Regression tests for the long-running opportunity research seat."""
from datetime import datetime
from pathlib import Path

import pytest

from investment_os import radar_store
from investment_os.upstream_radar import evaluate_packet, load_objective, write_outputs
from investment_os.upstream_radar_preflight import build_preflight
from test_upstream_radar_repair import AS_OF, _packet, _qualifying_item

CONFIG = Path('configs/upstream_radar.sample.yaml')


def test_omitted_catchup_is_blocked_at_normal_cli(tmp_path):
    import json
    from investment_os.upstream_radar import main
    db = tmp_path / 'index.sqlite'
    conn = radar_store.open_db(db)
    initial = _packet(tmp_path, [])
    initial['as_of'] = '2026-09-04T07:15:00+08:00'
    # Store historical empty success without pretending it is fresh verified evidence.
    radar_store.ingest_run(conn, initial, dict(status='pass', outcome='no_push', as_of=initial['as_of']), tmp_path)
    fresh = _packet(tmp_path, [])
    fresh['run_id'] = 'after-gap'
    path = tmp_path / 'packet.json'
    path.write_text(json.dumps(fresh))
    assert main(['--packet', str(path), '--db', str(db), '--out', str(tmp_path/'output')]) == 1
    assert radar_store.latest_success_as_of(conn) == datetime.fromisoformat(initial['as_of'])


def test_due_omission_blocks_and_overwrites_previous_silent_files(tmp_path):
    import json
    objective = load_objective(CONFIG)
    db = tmp_path / 'index.sqlite'
    conn = radar_store.open_db(db)
    first = _packet(tmp_path, [_qualifying_item('due:a')])
    radar_store.ingest_run(conn, first, evaluate_packet(first, objective, run_dir=tmp_path), tmp_path)
    out = tmp_path / 'output'
    out.mkdir()
    (out/'run-receipt.json').write_text('{"status":"pass"}')
    (out/'delivery-final.md').write_text('[SILENT]')
    quiet = _packet(tmp_path, [])
    quiet.update(run_id='omitted', as_of='2026-09-08T08:00:00+08:00')
    with pytest.raises(ValueError, match='due followups'):
        write_outputs(evaluate_packet(quiet, objective, run_dir=tmp_path), objective, out,
                      packet=quiet, run_dir=tmp_path, db_path=db)
    assert json.loads((out/'run-receipt.json').read_text())['status'] == 'fail'
    assert '[SILENT]' not in (out/'delivery-final.md').read_text()
    assert conn.execute("SELECT 1 FROM runs WHERE run_id='omitted'").fetchone() is None


@pytest.mark.parametrize('state', ['open', 'closed', 'superseded'])
def test_due_question_review_through_normal_writer(state, tmp_path):
    objective = load_objective(CONFIG)
    db = tmp_path/'index.sqlite'
    conn = radar_store.open_db(db)
    p = _packet(tmp_path, [_qualifying_item('due:a')])
    radar_store.ingest_run(conn, p, evaluate_packet(p, objective, run_dir=tmp_path), tmp_path)
    quiet = _packet(tmp_path, [])
    quiet.update(run_id='reviewed', as_of='2026-09-08T08:00:00+08:00')
    quiet['followup_updates'] = [dict(tracking_key='due:a', status=state,
        next_check_at='2026-09-10T07:15:00+08:00' if state=='open' else None,
        reason='本轮来源支持该复核结论。', source_ids=['cov-0'])]
    result = evaluate_packet(quiet, objective, run_dir=tmp_path)
    paths = write_outputs(result, objective, tmp_path/'output', packet=quiet, run_dir=tmp_path, db_path=db)
    assert paths['delivery_final'].read_text() == '[SILENT]'
    quiet.pop('followup_updates')
    write_outputs(result, objective, tmp_path/'output', packet=quiet, run_dir=tmp_path, db_path=db)
    rows = radar_store.readback_followups(conn, datetime.fromisoformat(quiet['as_of']), include_closed=True)
    assert rows[0]['status'] == state
    assert rows[0]['due'] is False


def test_same_run_final_only_replay_preserves_closed_review(tmp_path):
    objective = load_objective(CONFIG)
    conn = radar_store.open_db(tmp_path / 'index.sqlite')
    p = _packet(tmp_path, [_qualifying_item('question:a')])
    p['followup_updates'] = [dict(tracking_key='question:a', status='closed', reason='已失效。', source_ids=['cov-0'])]
    result = evaluate_packet(p, objective, run_dir=tmp_path)
    radar_store.ingest_run(conn, p, result, tmp_path)
    p.pop('followup_updates')
    p['delivery_artifact'] = {'text': '最终文本'}
    radar_store.ingest_run(conn, p, result, tmp_path)
    assert not radar_store.readback_followups(conn, AS_OF)
    assert radar_store.readback_run(conn, p['run_id'])['followup_updates'][0]['status'] == 'closed'


def test_catchup_requires_trusted_database_boundary_and_explicit_label(tmp_path):
    objective = load_objective(CONFIG)
    item = _qualifying_item('catchup:a', publication_time='2026-09-04T12:00:00+08:00',
        event_time='2026-09-04T12:00:00+08:00', discovery_status='catchup')
    packet = _packet(tmp_path, [item])
    for source in packet['sources']:
        if source['source_id'] == 'item-src':
            source['publication_time'] = item['publication_time']
            source['event_time'] = item['event_time']
    packet['catchup_since'] = '2026-09-04T07:15:00+08:00'
    assert evaluate_packet(packet, objective, run_dir=tmp_path).outcome == 'blocked'
    boundary = datetime.fromisoformat(packet['catchup_since'])
    good = evaluate_packet(packet, objective, run_dir=tmp_path, catchup_since=boundary)
    assert good.outcome == 'push'
    assert good.selected[0].discovery_status == 'catchup'
    packet['items'][0].pop('discovery_status')
    assert not evaluate_packet(packet, objective, run_dir=tmp_path, catchup_since=boundary).selected
    packet['items'][0]['discovery_status'] = 'catchup'
    packet['catchup_since'] = '2026-09-01T07:15:00+08:00'
    assert evaluate_packet(packet, objective, run_dir=tmp_path, catchup_since=boundary).outcome == 'blocked'


def test_followup_cannot_close_on_unverified_source(tmp_path):
    objective = load_objective(CONFIG)
    conn = radar_store.open_db(tmp_path / 'index.sqlite')
    p = _packet(tmp_path, [_qualifying_item('question:a')])
    p['sources'].append(dict(source_id='x', kind='locator', url='https://example.com/x'))
    p['followup_updates'] = [dict(tracking_key='question:a', status='closed', reason='no proof', source_ids=['x'])]
    with pytest.raises(ValueError, match='verified source_ids'):
        radar_store.ingest_run(conn, p, evaluate_packet(p, objective, run_dir=tmp_path), tmp_path)
    assert conn.execute('SELECT count(*) FROM runs').fetchone()[0] == 0


def test_push_cannot_smuggle_silent_suppression_marker(tmp_path):
    objective = load_objective(CONFIG)
    p = _packet(tmp_path, [_qualifying_item('question:a')])
    p['delivery_artifact'] = {'text': '实质变化 [SILENT]'}
    assert evaluate_packet(p, objective, run_dir=tmp_path).outcome == 'blocked'


def test_live_scope_accepts_company_earnings_and_demands_media_coverage(tmp_path):
    objective = load_objective(CONFIG)
    assert 'company_events' in objective.required_checks
    assert 'market_interpretation' in objective.required_checks
    item = _qualifying_item('company:leader-earnings', domain='company_events', themes=['earnings'])
    packet = _packet(tmp_path, [item])
    assert evaluate_packet(packet, objective, run_dir=tmp_path).selected
    packet['coverage'] = [x for x in packet['coverage'] if x['domain'] != 'market_interpretation']
    gapped = evaluate_packet(packet, objective, run_dir=tmp_path)
    assert gapped.outcome == 'push' and any('market_interpretation' in g for g in gapped.gaps)
    packet['items'] = []
    assert evaluate_packet(packet, objective, run_dir=tmp_path).outcome == 'blocked'


def test_same_theme_keeps_parallel_company_questions_until_explicit_review(tmp_path):
    objective = load_objective(CONFIG)
    conn = radar_store.open_db(tmp_path / 'index.sqlite')
    p = _packet(tmp_path, [
        _qualifying_item('power:plant-a', thesis_key='ai:power'),
        _qualifying_item('power:plant-b', thesis_key='ai:power'),
    ])
    result = evaluate_packet(p, objective, run_dir=tmp_path)
    radar_store.ingest_run(conn, p, result, tmp_path)
    rows = radar_store.readback_followups(conn, AS_OF)
    assert {x['tracking_key'] for x in rows} == {'power:plant-a', 'power:plant-b'}
    quiet = _packet(tmp_path, [])
    quiet.update(run_id='quiet', as_of='2026-09-08T08:00:00+08:00')
    quiet['followup_updates'] = [dict(tracking_key='power:plant-a', status='closed',
        reason='原假设已由当前披露推翻。', source_ids=['cov-0'])]
    radar_store.ingest_run(conn, quiet, evaluate_packet(quiet, objective, run_dir=tmp_path), tmp_path)
    rows = radar_store.readback_followups(conn, datetime.fromisoformat(quiet['as_of']))
    assert {x['tracking_key'] for x in rows} == {'power:plant-b'}
    radar_store.ingest_run(conn, p, result, tmp_path)  # old replay cannot reopen closed question
    assert {x['tracking_key'] for x in radar_store.readback_followups(conn, AS_OF)} == {'power:plant-b'}


def test_invalid_followup_update_rolls_back_entire_run(tmp_path):
    objective = load_objective(CONFIG)
    conn = radar_store.open_db(tmp_path / 'index.sqlite')
    p = _packet(tmp_path, [_qualifying_item('question:a')])
    radar_store.ingest_run(conn, p, evaluate_packet(p, objective, run_dir=tmp_path), tmp_path)
    p = dict(p, run_id='invalid', followup_updates=[dict(tracking_key='unknown', status='closed', reason='x', source_ids=['cov-0'])])
    with pytest.raises(ValueError, match='unknown tracking_key'):
        radar_store.ingest_run(conn, p, evaluate_packet(p, objective, run_dir=tmp_path), tmp_path)
    assert conn.execute("SELECT 1 FROM runs WHERE run_id='invalid'").fetchone() is None


def test_deferred_followup_remains_indexed_but_not_due(tmp_path):
    objective = load_objective(CONFIG)
    conn = radar_store.open_db(tmp_path / 'index.sqlite')
    p = _packet(tmp_path, [_qualifying_item('question:a')])
    p['followup_updates'] = [dict(tracking_key='question:a', status='open',
        next_check_at='2026-10-01T07:15:00+08:00', reason='等待已公布的后续节点。', source_ids=['cov-0'])]
    radar_store.ingest_run(conn, p, evaluate_packet(p, objective, run_dir=tmp_path), tmp_path)
    rows = radar_store.readback_followups(conn, AS_OF)
    assert len(rows) == 1 and rows[0]['due'] is False
    assert rows[0]['next_check_at'].startswith('2026-10-01')


def test_successful_no_push_persists_native_silent_delivery(tmp_path):
    objective = load_objective(CONFIG)
    p = _packet(tmp_path, [])
    p['delivery_artifact'] = {'text': '不要把无变化播报给读者'}
    result = evaluate_packet(p, objective, run_dir=tmp_path)
    paths = write_outputs(result, objective, tmp_path / 'output', packet=p, run_dir=tmp_path)
    assert paths['delivery_final'].read_text() == '[SILENT]'
    p['coverage'] = []
    blocked = evaluate_packet(p, objective, run_dir=tmp_path)
    paths = write_outputs(blocked, objective, tmp_path / 'output', packet=p, run_dir=tmp_path)
    assert '[SILENT]' not in paths['delivery_final'].read_text()


def test_opportunity_context_cannot_be_only_risk_monitoring(tmp_path):
    objective = load_objective(CONFIG)
    p = _packet(tmp_path, [_qualifying_item('idea:a')])
    p['items'][0].pop('expectation_gap', None)
    result = evaluate_packet(p, objective, run_dir=tmp_path)
    assert not result.selected
    assert 'missing_expectation_gap' in result.rejected[0]['reasons']


def test_preflight_exposes_source_plan_and_gap_without_hiding_old_questions(tmp_path):
    objective = load_objective(CONFIG)
    db = tmp_path / 'index.sqlite'
    conn = radar_store.open_db(db)
    p = _packet(tmp_path, [_qualifying_item('question:a'), _qualifying_item('question:b')])
    radar_store.ingest_run(conn, p, evaluate_packet(p, objective, run_dir=tmp_path), tmp_path)
    payload = build_preflight(objective, datetime.fromisoformat('2026-09-15T07:15:00+08:00'), None, db_path=db)
    assert payload['catchup_since'] == AS_OF.isoformat()
    assert len(payload['open_followups']) == 2
    assert 'Reuters' in str(payload['research_sources'])
    assert 'Bloomberg' in str(payload['research_sources'])
    assert 'NVIDIA' in str(payload['research_sources'])


def test_cli_attaches_reviewed_delivery_file_without_inline_python(tmp_path):
    import json
    from investment_os.upstream_radar import main
    packet = _packet(tmp_path, [_qualifying_item('question:new')])
    packet['followup_updates'] = [dict(
        tracking_key='question:new', status='open',
        next_check_at='2026-10-01T07:15:00+08:00',
        reason='按后续披露节点复核。', source_ids=['item-src'])]
    path = tmp_path / 'packet.json'
    path.write_text(json.dumps(packet))
    draft = tmp_path / 'reviewed.md'
    text = '本轮新增订单改变了收入兑现的观察重点；估值仍未核实。\n'
    draft.write_text(text)
    db = tmp_path / 'index.sqlite'
    radar_store.open_db(db).close()
    assert main(['--packet', str(path), '--db', str(db), '--out', str(tmp_path/'out'),
                 '--delivery-file', str(draft)]) == 0
    saved = json.loads(path.read_text())
    assert saved['delivery_artifact'] == dict(kind='agent_final', text=text, claim_sent=False)
    assert (tmp_path/'out/delivery-final.md').read_text() == text
    with radar_store.open_db(db) as conn:
        rows = radar_store.readback_followups(conn, AS_OF)
        assert len(rows) == 1 and rows[0]['due'] is False
        assert radar_store.readback_run(conn, packet['run_id'])['status'] == 'pass'


def test_cli_delivery_file_rejects_empty_and_preserves_packet(tmp_path):
    import json
    from investment_os.upstream_radar import main
    packet = tmp_path / 'packet.json'
    packet.write_text(json.dumps(_packet(tmp_path, [])))
    before = packet.read_bytes()
    draft = tmp_path / 'empty.md'
    draft.write_text('  \n')
    with pytest.raises(ValueError, match='empty delivery'):
        main(['--packet', str(packet), '--out', str(tmp_path/'out'), '--delivery-file', str(draft)])
    assert packet.read_bytes() == before


def test_unreviewed_due_reported_but_does_not_hold_back_publishable_issue(tmp_path):
    import json
    objective = load_objective(CONFIG)
    db = tmp_path / 'index.sqlite'
    conn = radar_store.open_db(db)
    first = _packet(tmp_path, [_qualifying_item('due:a')])
    radar_store.ingest_run(conn, first, evaluate_packet(first, objective, run_dir=tmp_path), tmp_path)
    nxt = _packet(tmp_path, [_qualifying_item('fresh:b')])
    nxt.update(run_id='next', as_of='2026-09-08T08:00:00+08:00')
    paths = write_outputs(evaluate_packet(nxt, objective, run_dir=tmp_path), objective, tmp_path/'output',
                          packet=nxt, run_dir=tmp_path, db_path=db)
    receipt = json.loads(paths['receipt'].read_text())
    assert receipt['outcome'] == 'push' and receipt['unreviewed_due_followups'] == ['due:a']
    # Not silently advanced: still due next time.
    due = [r for r in radar_store.readback_followups(conn, datetime.fromisoformat('2026-09-09T08:00:00+08:00')) if r['due']]
    assert 'due:a' in {r['tracking_key'] for r in due}


def test_followups_expire_instead_of_accumulating(tmp_path):
    objective = load_objective(CONFIG)
    conn = radar_store.open_db(tmp_path / 'index.sqlite')
    p = _packet(tmp_path, [_qualifying_item('old:q'), _qualifying_item('named:node')])
    radar_store.ingest_run(conn, p, evaluate_packet(p, objective, run_dir=tmp_path), tmp_path)
    later = _packet(tmp_path, [])
    later.update(run_id='later', as_of='2026-09-08T09:00:00+08:00')
    later['followup_updates'] = [dict(tracking_key='named:node', status='open',
        next_check_at='2026-10-10T08:00:00+08:00', reason='等待已公布的10月财报。', source_ids=['cov-0'])]
    radar_store.ingest_run(conn, later, evaluate_packet(later, objective, run_dir=tmp_path), tmp_path)
    day15 = datetime.fromisoformat('2026-09-23T08:00:00+08:00')
    rows = {r['tracking_key']: r for r in radar_store.readback_followups(conn, day15)}
    assert 'old:q' not in rows  # 15 days, no new evidence, no later node: expired
    assert rows['named:node']['due'] is False  # named node keeps it alive
    at_node = {r['tracking_key']: r for r in radar_store.readback_followups(conn, datetime.fromisoformat('2026-10-10T09:00:00+08:00'))}
    assert at_node['named:node']['due'] and not at_node['named:node']['required']
    assert not radar_store.readback_followups(conn, datetime.fromisoformat('2026-10-12T09:00:00+08:00'))
