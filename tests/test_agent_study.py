from api.agent_study import _session_info, get_agent_study


def test_session_info_has_phase():
    s = _session_info()
    assert "phase" in s
    assert "now_brt" in s


def test_agent_study_structure(monkeypatch):
    import api.agent_study as mod

    def fake_eval(*a, **k):
        return {
            "symbol": "TEST4",
            "market": {"bid": 10.0, "ask": 10.02, "mid": 10.01},
            "indicators": {"atr_pct": 0.5, "bb_width_pct": 1.2, "regime": "vol baixa", "regime_score": 0.2},
            "active_strategy": "volatility",
            "sizing": {"contracts": 100, "label": "100 ações"},
            "strategies": {},
            "recommendation": {"action": "wait", "action_label": "wait"},
        }

    monkeypatch.setattr(mod, "_evaluate_study", fake_eval)
    monkeypatch.setattr(mod, "_last_signal_row", lambda s: None)
    monkeypatch.setattr(mod, "_history_profile", lambda s, b: {"has_data": False, "message": "test"})
    out = get_agent_study("TEST4", 10.0, 10.02)
    assert out["symbol"] == "TEST4"
    assert "session" in out
    assert "history" in out
    assert "candle_patterns" in out
    assert "trade_playbook" in out
    assert "playbook" in out["trade_playbook"]
    assert "summary_chips" in out["trade_playbook"]
