"""
Data classes mirroring the PostgreSQL schema.
Used for type safety and documentation — not ORM models.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


@dataclass
class Transaction:
    """Mirrors the `transactions` table."""
    id: str
    type: str                              # 'income' | 'expense'
    date: date
    amount: Decimal
    property_id: Optional[str] = None      # gnizd | chaika | chaplia | sup
    platform: Optional[str] = None         # Website | Instagram | Booking | HutsHub | AirBnB | Phone | Return
    counterparty: Optional[str] = None     # sender name or vendor
    payment_type: Optional[str] = None     # Передоплата | Доплата | Оплата | Сапи
    account_type: Optional[str] = None     # Account | Cash | Nestor Account
    category: Optional[str] = None         # expense only: Laundry | Utilities | ...
    description: Optional[str] = None      # expense only: free-text expense description
    paid_by: Optional[str] = None          # expense only: Nestor | Ihor | Ira | Other | Account
    checkin_date: Optional[date] = None
    checkout_date: Optional[date] = None
    sup_duration: Optional[str] = None
    notes: Optional[str] = None
    receipt_url: Optional[str] = None
    source: Optional[str] = None           # ocr | manual
    sheets_synced: bool = False
    created_at: Optional[datetime] = None


@dataclass
class BotSession:
    """Mirrors the `bot_sessions` table."""
    chat_id: int
    user_id: Optional[int] = None
    state: Optional[str] = None
    context: dict = field(default_factory=dict)
    updated_at: Optional[datetime] = None

    @classmethod
    def from_record(cls, record) -> "BotSession":
        """Create BotSession from an asyncpg Record."""
        import json
        ctx = record["context"]
        if isinstance(ctx, str):
            ctx = json.loads(ctx)
        return cls(
            chat_id=record["chat_id"],
            user_id=record["user_id"],
            state=record["state"],
            context=ctx if ctx else {},
            updated_at=record["updated_at"],
        )
