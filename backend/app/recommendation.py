from pydantic import BaseModel
from typing import Optional
from app.models import Disc, HoleEdge

class SegmentRecommendation(BaseModel):
    disc: str
    distance: int
    shot_shape: str
    to_node_id: int
    hazards: list[str]

def recommend_path(
    edges: list,
    discs: list,
    disc_distances: dict,  # {disc_id: avg_distance}
    wind_speed: float = 0.0,
    wind_direction: str = "N"
) -> list[SegmentRecommendation]:
    recommendations = []

    for edge in edges:
        # 1. Filter discs that can cover the distance
        capable_discs = [d for d in discs if (edge.distance - 10) <= disc_distances.get(d.disc_id, 0)]
        
        if not capable_discs:
            # No disc can reach — pick the longest one
            capable_discs = [max(discs, key=lambda d: disc_distances.get(d.disc_id, 0))]
        
        # 2. Pick best disc (for now: closest to required distance)
        best_disc = min(capable_discs, key=lambda d: abs(disc_distances.get(d.disc_id, 0) - edge.distance))
        
        # 3. Get hazards for this edge
        hazard_names = [h.hazard_type for h in edge.edge_hazards]
        
        recommendations.append(SegmentRecommendation(
            disc=f"{best_disc.manufacturer} {best_disc.name}",
            distance=edge.distance,
            shot_shape="straight",
            to_node_id=edge.to_node_id,
            hazards=hazard_names
        ))
    
    return recommendations