from typing import Optional
from app.schemas import DiscType

def map_discit_category(category: str) -> Optional[DiscType]:
    mapping = {
        "Distance Driver": DiscType.distance_driver,
        "Hybrid Driver": DiscType.fairway_driver,
        "Control Driver": DiscType.fairway_driver,
        "Midrange": DiscType.midrange,
        "Putter": DiscType.putter
    }
    return mapping.get(category)