# Import all models here for Alembic
from app.db.base_class import Base
from app.models.user import User
from app.models.trader import Trader
from app.models.trade import Trade
from app.models.copy_relationship import CopyRelationship
from app.models.notification import Notification, UserBalance
from app.models.user_preferences import UserPreferences, BillingHistory

__all__ = [
    "Base",
    "User",
    "Trader",
    "Trade",
    "CopyRelationship",
    "Notification",
    "UserBalance",
    "UserPreferences",
    "BillingHistory"
]
