import os
import pandas as pd
import numpy as np
from data.loader import get_ohlcv
from strategies import CrossoverStrategy, RSIStrategy, MACDStrategy, EnsembleStrategy

def verify_strategies():
    print("=== STARTING STRATEGY FRAMEWORK VERIFICATION ===\n")
    
    # 1. Load cached BTC/USDT daily data
    symbol = 'BTC/USDT'
    timeframe = '1d'
    start_date = '2026-04-01'
    end_date = '2026-05-25'
    
    print(f"Loading cached BTC data ({symbol}, {timeframe}) from {start_date} to {end_date}...")
    df = get_ohlcv(symbol, timeframe, start_date, end_date)
    print(f"Loaded {len(df)} candles.\n")
    
    # 2. Test CrossoverStrategy (SMA)
    print("Testing CrossoverStrategy (SMA 20/50)...")
    crossover_sma = CrossoverStrategy(name="SMA_Crossover", params={'fast_window': 20, 'slow_window': 50, 'ma_type': 'sma'})
    df_sma = crossover_sma.generate_signals(df)
    
    # Check output columns
    required_sma_cols = ['fast_ma', 'slow_ma', 'Signal']
    for col in required_sma_cols:
        assert col in df_sma.columns, f"Column '{col}' is missing in CrossoverStrategy output"
        
    print("SMA Columns added successfully.")
    
    # Verify SMA signal logic
    valid_sma = df_sma.dropna(subset=['fast_ma', 'slow_ma'])
    print(f"Total rows: {len(df_sma)}, rows with valid MAs: {len(valid_sma)}")
    
    # Check that signals match our rules
    for idx, row in valid_sma.iterrows():
        expected_signal = 1.0 if row['fast_ma'] > row['slow_ma'] else -1.0
        assert row['Signal'] == expected_signal, f"Signal mismatch at {idx}: fast={row['fast_ma']}, slow={row['slow_ma']}, got Signal={row['Signal']}"
        
    # Check that initial NaN rows have Signal = 0.0
    nan_sma = df_sma[df_sma['slow_ma'].isna()]
    for idx, row in nan_sma.iterrows():
        assert row['Signal'] == 0.0, f"Expected 0.0 Signal for NaN slow_ma at {idx}, got {row['Signal']}"
        
    print("CrossoverStrategy (SMA) validation PASSED.")
    print("Sample Crossover SMA data (Last 5 rows):")
    print(df_sma[required_sma_cols].tail(5))
    print("\n" + "-"*50 + "\n")
    
    # 3. Test CrossoverStrategy (EMA)
    print("Testing CrossoverStrategy (EMA 20/50)...")
    crossover_ema = CrossoverStrategy(name="EMA_Crossover", params={'fast_window': 20, 'slow_window': 50, 'ma_type': 'ema'})
    df_ema = crossover_ema.generate_signals(df)
    assert 'fast_ma' in df_ema.columns and 'slow_ma' in df_ema.columns and 'Signal' in df_ema.columns
    print("CrossoverStrategy (EMA) validation PASSED.")
    print("Sample Crossover EMA data (Last 5 rows):")
    print(df_ema[required_sma_cols].tail(5))
    print("\n" + "-"*50 + "\n")
    
    # 4. Test RSIStrategy
    print("Testing RSIStrategy (14 window, 30/70 thresholds)...")
    rsi_strat = RSIStrategy(name="RSI_14", params={'window': 14, 'overbought': 70, 'oversold': 30})
    df_rsi = rsi_strat.generate_signals(df)
    
    required_rsi_cols = ['rsi', 'Signal']
    for col in required_rsi_cols:
        assert col in df_rsi.columns, f"Column '{col}' is missing in RSIStrategy output"
        
    print("RSI Columns added successfully.")
    
    # Verify RSI signal logic
    valid_rsi = df_rsi.dropna(subset=['rsi'])
    print(f"Total rows: {len(df_rsi)}, rows with valid RSI: {len(valid_rsi)}")
    
    for idx, row in valid_rsi.iterrows():
        if row['rsi'] < 30:
            expected = 1.0
        elif row['rsi'] > 70:
            expected = -1.0
        else:
            expected = 0.0
        assert row['Signal'] == expected, f"Signal mismatch at {idx}: rsi={row['rsi']}, expected Signal={expected}, got {row['Signal']}"
        
    # Check that initial NaN rows have Signal = 0.0
    nan_rsi = df_rsi[df_rsi['rsi'].isna()]
    for idx, row in nan_rsi.iterrows():
        assert row['Signal'] == 0.0, f"Expected 0.0 Signal for NaN RSI at {idx}, got {row['Signal']}"
        
    print("RSIStrategy validation PASSED.")
    print("Sample RSI data (Last 5 rows):")
    print(df_rsi[required_rsi_cols].tail(5))
    print("\n" + "-"*50 + "\n")
    
    # 5. Test MACDStrategy
    print("Testing MACDStrategy (12 fast, 26 slow, 9 signal)...")
    macd_strat = MACDStrategy(name="MACD_12_26_9", params={'fast_period': 12, 'slow_period': 26, 'signal_period': 9})
    df_macd = macd_strat.generate_signals(df)
    
    required_macd_cols = ['macd_line', 'signal_line', 'macd_hist', 'Signal']
    for col in required_macd_cols:
        assert col in df_macd.columns, f"Column '{col}' is missing in MACDStrategy output"
        
    print("MACD Columns added successfully.")
    
    # Verify MACD signal logic
    valid_macd = df_macd.dropna(subset=['macd_line', 'signal_line'])
    print(f"Total rows: {len(df_macd)}, rows with valid MACD: {len(valid_macd)}")
    
    for idx, row in valid_macd.iterrows():
        expected = 1.0 if row['macd_line'] > row['signal_line'] else -1.0
        assert row['Signal'] == expected, f"Signal mismatch at {idx}: macd={row['macd_line']}, signal={row['signal_line']}, expected Signal={expected}, got {row['Signal']}"
        
    # Check that initial NaN rows have Signal = 0.0
    nan_macd = df_macd[df_macd['macd_line'].isna() | df_macd['signal_line'].isna()]
    for idx, row in nan_macd.iterrows():
        assert row['Signal'] == 0.0, f"Expected 0.0 Signal for NaN MACD at {idx}, got {row['Signal']}"
        
    print("MACDStrategy validation PASSED.")
    print("Sample MACD data (Last 5 rows):")
    print(df_macd[required_macd_cols].tail(5))
    print("\n" + "-"*50 + "\n")
    
    # 6. Test EnsembleStrategy
    print("Testing EnsembleStrategy (triple rule)...")
    ensemble_strat = EnsembleStrategy(name="Ensemble_Triple", params={
        'fast_window': 20,
        'slow_window': 50,
        'ma_type': 'ema',
        'rsi_window': 14,
        'rsi_overbought': 70.0,
        'rsi_oversold': 30.0,
        'macd_fast': 12,
        'macd_slow': 26,
        'macd_signal': 9,
        'rules': 'triple'
    })
    df_ens = ensemble_strat.generate_signals(df)
    
    required_ens_cols = ['fast_ma', 'slow_ma', 'rsi', 'macd_line', 'signal_line', 'Signal']
    for col in required_ens_cols:
        assert col in df_ens.columns, f"Column '{col}' is missing in EnsembleStrategy output"
        
    print("Ensemble Columns added successfully.")
    
    valid_ens = df_ens.dropna(subset=required_ens_cols[:-1])
    print(f"Total rows: {len(df_ens)}, rows with valid Ensemble indicators: {len(valid_ens)}")
    
    for idx, row in valid_ens.iterrows():
        expected = 1.0 if (row['macd_line'] > row['signal_line'] and row['fast_ma'] > row['slow_ma'] and row['rsi'] < 70.0) else -1.0
        assert row['Signal'] == expected, f"Signal mismatch at {idx}: expected {expected}, got {row['Signal']}"
        
    print("EnsembleStrategy validation PASSED.")
    print("Sample Ensemble data (Last 5 rows):")
    print(df_ens[required_ens_cols].tail(5))
    print("\n" + "-"*50 + "\n")
    
    # 7. Test Edge Case: Empty DataFrame
    print("Testing edge case: Empty DataFrame...")
    empty_df = pd.DataFrame(columns=['Open', 'High', 'Low', 'Close', 'Volume'])
    empty_df.index = pd.to_datetime([], utc=True)
    empty_df.index.name = 'Timestamp'
    
    res_sma_empty = crossover_sma.generate_signals(empty_df)
    assert len(res_sma_empty) == 0
    assert 'fast_ma' in res_sma_empty.columns
    assert 'slow_ma' in res_sma_empty.columns
    assert 'Signal' in res_sma_empty.columns
    
    res_rsi_empty = rsi_strat.generate_signals(empty_df)
    assert len(res_rsi_empty) == 0
    assert 'rsi' in res_rsi_empty.columns
    assert 'Signal' in res_rsi_empty.columns
    
    res_macd_empty = macd_strat.generate_signals(empty_df)
    assert len(res_macd_empty) == 0
    assert 'macd_line' in res_macd_empty.columns
    assert 'signal_line' in res_macd_empty.columns
    assert 'macd_hist' in res_macd_empty.columns
    assert 'Signal' in res_macd_empty.columns
    
    res_ens_empty = ensemble_strat.generate_signals(empty_df)
    assert len(res_ens_empty) == 0
    assert 'fast_ma' in res_ens_empty.columns
    assert 'rsi' in res_ens_empty.columns
    assert 'macd_line' in res_ens_empty.columns
    assert 'Signal' in res_ens_empty.columns
    print("Empty DataFrame edge case validation PASSED.")
    
    # 8. Test Edge Case: Very short DataFrame
    print("Testing edge case: Very short DataFrame (len=5)...")
    short_df = df.head(5)
    
    res_sma_short = crossover_sma.generate_signals(short_df)
    assert len(res_sma_short) == 5
    assert res_sma_short['fast_ma'].isna().all()
    assert (res_sma_short['Signal'] == 0.0).all()
    
    res_rsi_short = rsi_strat.generate_signals(short_df)
    assert len(res_rsi_short) == 5
    assert res_rsi_short['rsi'].isna().all()
    assert (res_rsi_short['Signal'] == 0.0).all()
    
    res_macd_short = macd_strat.generate_signals(short_df)
    assert len(res_macd_short) == 5
    assert res_macd_short['macd_line'].isna().all()
    assert res_macd_short['signal_line'].isna().all()
    assert res_macd_short['macd_hist'].isna().all()
    assert (res_macd_short['Signal'] == 0.0).all()
    
    res_ens_short = ensemble_strat.generate_signals(short_df)
    assert len(res_ens_short) == 5
    assert res_ens_short['fast_ma'].isna().all()
    assert res_ens_short['rsi'].isna().all()
    assert res_ens_short['macd_line'].isna().all()
    assert (res_ens_short['Signal'] == 0.0).all()
    print("Short DataFrame edge case validation PASSED.\n")
    
    print("=== ALL VERIFICATIONS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    verify_strategies()
