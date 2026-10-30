-- Schema Sala de Sinais para Supabase Postgres (gerado a partir de api/database.py)
-- Rode no SQL Editor do Supabase OU deixe a API criar via init_db() na primeira subida.
-- Tabelas legadas do app financasmais.com NÃO são alteradas — use projeto limpo ou prefixo.

CREATE TABLE IF NOT EXISTS signals (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(32) NOT NULL,
    side VARCHAR(8) NOT NULL,
    entry DOUBLE PRECISION NOT NULL,
    stop DOUBLE PRECISION NOT NULL,
    target DOUBLE PRECISION NOT NULL,
    contracts INTEGER NOT NULL,
    strategy_id VARCHAR(64) NOT NULL,
    mode VARCHAR(16) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    note TEXT,
    execution_message TEXT,
    created_at VARCHAR(32) NOT NULL,
    exit_price DOUBLE PRECISION,
    closed_at VARCHAR(32),
    outcome VARCHAR(16),
    gross_pnl_brl DOUBLE PRECISION,
    net_pnl_brl DOUBLE PRECISION,
    strategy_type VARCHAR(16),
    strategy_version VARCHAR(16),
    entry_reason TEXT,
    exit_reason TEXT,
    regime VARCHAR(32)
);

CREATE TABLE IF NOT EXISTS agent_config (
    id INTEGER PRIMARY KEY,
    symbols_json TEXT NOT NULL DEFAULT '["PETR4","VALE3"]',
    active_symbol VARCHAR(16),
    rotate_symbols BOOLEAN NOT NULL DEFAULT FALSE,
    capital_brl DOUBLE PRECISION NOT NULL DEFAULT 10000.0,
    risk_per_trade_pct DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    max_position_brl DOUBLE PRECISION NOT NULL DEFAULT 2000.0,
    shares_per_order INTEGER NOT NULL DEFAULT 100,
    stop_loss_pct DOUBLE PRECISION NOT NULL DEFAULT 2.0,
    take_profit_pct DOUBLE PRECISION NOT NULL DEFAULT 3.0,
    stop_points INTEGER NOT NULL DEFAULT 80,
    target_points INTEGER NOT NULL DEFAULT 120,
    asset_class VARCHAR(16) NOT NULL DEFAULT 'acoes',
    strategy_type VARCHAR(16) NOT NULL DEFAULT 'volatility',
    use_news_filter BOOLEAN NOT NULL DEFAULT TRUE,
    applied_preset VARCHAR(32),
    updated_at VARCHAR(32) NOT NULL
);

CREATE TABLE IF NOT EXISTS system_state (
    id INTEGER PRIMARY KEY,
    engine_paused BOOLEAN NOT NULL DEFAULT FALSE,
    emergency_flatten BOOLEAN NOT NULL DEFAULT FALSE,
    last_heartbeat VARCHAR(32),
    mode VARCHAR(16) NOT NULL DEFAULT 'paper',
    updated_at VARCHAR(32) NOT NULL,
    account_login INTEGER,
    is_demo BOOLEAN,
    account_server VARCHAR(128),
    data_source VARCHAR(32),
    mt5_connected BOOLEAN,
    operating_mode VARCHAR(32)
);
