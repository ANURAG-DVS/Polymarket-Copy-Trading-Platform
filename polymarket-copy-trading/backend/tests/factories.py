import factory
from factory import Faker
from app.models.user import User, SubscriptionTier
from app.models.trader import Trader
from app.models.trade import Trade, TradeStatus, TradeSide
from app.models.copy_relationship import CopyRelationship, RelationshipStatus

class UserFactory(factory.Factory):
    """Factory for creating test users"""
    
    class Meta:
        model = User
    
    email = Faker("email")
    username = Faker("user_name")
    hashed_password = "$2b$12$test_hashed_password"
    full_name = Faker("name")
    is_active = True
    is_verified = True
    subscription_tier = SubscriptionTier.FREE
    telegram_id = None

class TraderFactory(factory.Factory):
    """Factory for creating test traders"""
    
    class Meta:
        model = Trader
    
    wallet_address = Faker("sha256")
    pnl_7d = Faker("pyfloat", min_value=-1000, max_value=5000)
    pnl_30d = Faker("pyfloat", min_value=-2000, max_value=10000)
    pnl_all_time = Faker("pyfloat", min_value=-5000, max_value=50000)
    win_rate = Faker("pyfloat", min_value=0, max_value=100)
    total_trades = Faker("pyint", min_value=0, max_value=1000)
    winning_trades = Faker("pyint", min_value=0, max_value=500)
    losing_trades = Faker("pyint", min_value=0, max_value=500)
    avg_trade_size = Faker("pyfloat", min_value=10, max_value=1000)
    is_active = True

class TradeFactory(factory.Factory):
    """Factory for creating test trades"""
    
    class Meta:
        model = Trade
    
    market_id = Faker("uuid4")
    market_title = Faker("sentence")
    outcome = "YES"
    side = TradeSide.YES
    entry_price = Faker("pyfloat", min_value=0.1, max_value=0.9)
    current_price = Faker("pyfloat", min_value=0.1, max_value=0.9)
    quantity = Faker("pyfloat", min_value=1, max_value=100)
    amount_usd = Faker("pyfloat", min_value=10, max_value=1000)
    unrealized_pnl = Faker("pyfloat", min_value=-100, max_value=200)
    status = TradeStatus.OPEN

class CopyRelationshipFactory(factory.Factory):
    """Factory for creating test copy relationships"""
    
    class Meta:
        model = CopyRelationship
    
    copy_percentage = Faker("pyfloat", min_value=1, max_value=100)
    max_investment_usd = Faker("pyfloat", min_value=10, max_value=1000)
    total_pnl = Faker("pyfloat", min_value=-500, max_value=1000)
    total_trades_copied = Faker("pyint", min_value=0, max_value=100)
    status = RelationshipStatus.ACTIVE
