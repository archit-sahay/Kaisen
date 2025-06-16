from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ItemResponse(BaseModel):
    id: int
    name: str
    examine: Optional[str] = None
    members: bool = False
    lowalch: Optional[int] = None
    highalch: Optional[int] = None
    limit_value: Optional[int] = None
    value: Optional[int] = None
    icon: Optional[str] = None
    high_price: Optional[int] = None
    low_price: Optional[int] = None
    high_time: Optional[int] = None
    low_time: Optional[int] = None
    price_last_updated: Optional[datetime] = None

class ItemsResponse(BaseModel):
    items: List[ItemResponse]
    count: int
    timestamp: datetime
    source: str 