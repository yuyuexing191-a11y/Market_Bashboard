from app.models import Base, DailyQuote, MinuteQuote, Stock


def test_market_models_define_expected_tables_and_composite_keys() -> None:
    assert set(Base.metadata.tables) == {"stocks", "daily_quotes", "minute_quotes"}
    assert Stock.__tablename__ == "stocks"
    assert DailyQuote.__tablename__ == "daily_quotes"
    assert MinuteQuote.__tablename__ == "minute_quotes"
    assert {column.name for column in DailyQuote.__table__.primary_key} == {
        "symbol",
        "trade_date",
    }
    assert {column.name for column in MinuteQuote.__table__.primary_key} == {
        "symbol",
        "trade_time",
    }
