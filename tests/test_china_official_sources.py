from investment_os.china_official_sources import official_source_targets


def test_china_official_targets_cover_required_authorities():
    targets = official_source_targets()
    assert {target.authority for target in targets} == {"PBOC", "NBS", "CNINFO", "SSE", "SZSE", "HKEX"}
    assert all(target.evidence_status == "source_target_only" for target in targets)
    assert all(target.source_url.startswith("https://") for target in targets)


def test_brittle_or_access_controlled_sources_have_explicit_blockers():
    targets = official_source_targets()
    blocked = [target for target in targets if not target.stable_machine_readable]
    assert blocked
    assert all(target.blocker for target in blocked)
    assert all(target.queue_status == "open" for target in blocked)
