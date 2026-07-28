from pathlib import Path

from investment_os.cli import main


def test_doctor_passes(capsys):
    assert main(["doctor"]) == 0
    assert '"python_supported": true' in capsys.readouterr().out


def test_offline_demo_writes_complete_artifact_set(tmp_path):
    out = tmp_path / "demo"
    assert main(["demo", "--out", str(out)]) == 0
    expected = {
        "market-metrics.csv",
        "market-report.md",
        "cxo_daily_brief.md",
        "cxo_ranked_candidates.json",
        "cxo_brief_quality_scan.json",
    }
    assert {path.name for path in out.iterdir()} == expected
    assert "不是交易建议" in (out / "cxo_daily_brief.md").read_text(encoding="utf-8")


def test_strict_live_run_fails_when_every_row_is_degraded(monkeypatch, tmp_path):
    def fake_run(_config: Path, out: Path):
        out.mkdir(parents=True, exist_ok=True)
        report = out / "report.md"
        metrics = out / "metrics.csv"
        report.write_text("demo", encoding="utf-8")
        metrics.write_text("symbol,data_quality\nDEMO,missing\n", encoding="utf-8")
        return report, metrics

    monkeypatch.setattr("investment_os.cli.run_pipeline", fake_run)
    assert main(["run", "--config", "unused.yaml", "--out", str(tmp_path / "live"), "--strict"]) == 2


def test_daily_command_supports_exact_offline_contract_and_reports_quiet(tmp_path, capsys):
    state = tmp_path / "topic-state.json"
    command = [
        "daily",
        "--config",
        "configs/watchlist.sample.yaml",
        "--profile",
        "configs/profiles.sample.yaml",
        "--state",
        str(state),
        "--out",
        str(tmp_path / "run-1"),
        "--strict",
        "--offline",
    ]

    assert main(command) == 0
    first_output = capsys.readouterr().out
    assert "daily_run=completed" in first_output
    assert (tmp_path / "run-1" / "cxo_daily_brief.md").exists()
    command[command.index(str(tmp_path / "run-1"))] = str(tmp_path / "run-2")
    assert main(command) == 0
    assert "daily_run=quiet" in capsys.readouterr().out