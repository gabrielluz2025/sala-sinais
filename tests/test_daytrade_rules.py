from shared.daytrade_rules import (
    build_example_levels,
    build_trade_playbook_section,
    get_playbook,
    playbook_breakout,
)


def test_playbook_breakout_has_three_pillars():
    pb = playbook_breakout({"stop_loss_pct": 2.0, "take_profit_pct": 4.0}, "PETR4")
    assert pb.strategy_type == "breakout"
    assert len(pb.pillars) == 3
    stages = [p.stage for p in pb.pillars]
    assert "context_filter" in stages
    assert "entry_trigger" in stages
    assert "exit_management" in stages
    assert "14-tres-pilares-setup" in pb.library_article_ids


def test_example_levels_rr_from_config():
    rec = {"side": "BUY", "entry": 100.0, "stop": 98.0, "target": 104.0}
    ex = build_example_levels(
        "PETR4",
        {"stop_loss_pct": 2.0, "take_profit_pct": 4.0, "strategy_type": "breakout"},
        99.9,
        100.1,
        rec,
        {"levels": {"range_high": 99.5, "range_low": 98.0}},
    )
    assert ex["risk_reward_ratio"] == 2.0
    assert ex["aligned_with_engine"] is True


def test_trade_playbook_section_keys():
    study = {
        "active_strategy": "breakout",
        "indicators": {"regime": "vol moderada", "atr_pct": 0.4, "bb_width_pct": 1.0},
        "recommendation": {
            "side": None,
            "entry": None,
            "stop": None,
            "target": None,
        },
        "strategies": {
            "breakout": {
                "levels": {"range_high": 50.0, "range_low": 49.0},
            }
        },
    }
    cfg = {"strategy_type": "breakout", "stop_loss_pct": 2.0, "take_profit_pct": 3.0}
    section = build_trade_playbook_section("PETR4", cfg, 49.99, 50.01, study)
    assert "playbook" in section
    assert "example_levels" in section
    assert "summary_chips" in section
    assert len(section["summary_chips"]) == 5
    chip_keys = {c["key"] for c in section["summary_chips"]}
    assert chip_keys == {"filtro", "entrada", "stop", "alvo", "rr"}


def test_get_playbook_volatility_regime_in_text():
    pb = get_playbook(
        "volatility",
        {"stop_loss_pct": 2, "take_profit_pct": 3},
        "PETR4",
        regime="vol alta",
        atr_pct=1.2,
        bb_width_pct=4.0,
    )
    assert "vol alta" in pb.pillars[0].rule_pt
    assert "16-volatilidade-atr-stop" in pb.library_article_ids
