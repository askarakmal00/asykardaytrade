from abc import ABC, abstractmethod
import pandas as pd
from typing import List, Dict, Any, Optional

class MarketDataProvider(ABC):

    @abstractmethod
    def get_symbols(self) -> List[str]:
        pass

    @abstractmethod
    def get_daily_data(self, symbol: str, period: str = "1y") -> pd.DataFrame:
        """
        Returns historical DAILY OHLCV candles.
        Index: DatetimeIndex (timezone-aware, Asia/Jakarta)
        Columns: Open, High, Low, Close, Volume
        NOTE: The last row's Close is the PREVIOUS SESSION DAILY CLOSE,
              NOT the current market price.
        """
        pass

    @abstractmethod
    def get_intraday_data(
        self,
        symbol: str,
        interval: str = "15m",
        period: str = "5d"
    ) -> pd.DataFrame:
        """
        Returns intraday OHLCV candles for the given interval.
        Index: DatetimeIndex (timezone-aware, Asia/Jakarta)
        Columns: Open, High, Low, Close, Volume
        """
        pass

    @abstractmethod
    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """
        Returns a real-time or near-real-time price quote snapshot.
        Always separate from candle history.
        Keys returned:
            symbol          - str
            current_price   - float | None  (fast_info.last_price)
            previous_close  - float | None  (fast_info.previous_close)
            day_open        - float | None
            day_high        - float | None
            day_low         - float | None
            volume          - int | None
            market_state    - str  ('REGULAR' | 'CLOSED' | 'PRE' | 'POST')
            data_source     - str  (always 'Yahoo Finance')
            data_note       - str  (delay disclaimer)
            quote_timestamp - str  (WIB formatted string)
        """
        pass
