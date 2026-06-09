export type DiscType = 'putter' | 'midrange' | 'fairway_driver' | 'distance_driver';

export interface Disc {
	disc_id: number;
	name: string;
	manufacturer: string;
	disc_type: DiscType | null;
	color: string | null;
	speed: number | null;
	glide: number | null;
	turn: number | null;
	fade: number | null;
	wear: number | null;
	weight: number | null;
}

export interface DiscStat {
	stat_id: number;
	disc_id: number;
	avg_distance: number;
	max_distance: number | null;
	sample_size: number | null;
}

export interface RoundHoleScore {
	hole_id: number;
	score: number;
}

export interface Round {
	round_id: number;
	course_id: number;
	bag_id: number;
	played_at: string;
	total_score: number | null;
	round_holes: RoundHoleScore[];
}

export interface ThrowMeasurement {
	throw_id: number;
	session_id: number;
	disc_id: number | null;
	end_latitude: number;
	end_longitude: number;
	distance_ft: number;
	created_at: string;
}

export interface ThrowSession {
	session_id: number;
	label: string | null;
	start_latitude: number;
	start_longitude: number;
	created_at: string;
	throws: ThrowMeasurement[];
}

export interface DiscItResult {
	name: string;
	brand: string;
	category: string;
	disc_type: DiscType | null;
	speed: string;
	glide: string;
	turn: string;
	fade: string;
	stability: string;
	background_color: string;
}

export interface Hole {
	hole_id: number;
	course_id: number;
	hole_number: number;
	par: number;
	distance: number;
	elevation: number;
	is_approved: boolean;
}

export interface Course {
	course_id: number;
	name: string;
	city: string;
	state: string;
	address: string;
	total_par: number;
	is_approved: boolean;
	holes: Hole[];
}

export type NodeType = 'tee' | 'landing_zone' | 'mando' | 'dogleg' | 'basket';

export interface HoleNode {
	hole_node_id: number;
	hole_id: number;
	node_type: NodeType;
	sequence: number;
	label: string | null;
	latitude: number | null;
	longitude: number | null;
	centerline_distance: number | null;
	is_fairway: boolean;
}

export interface HoleEdge {
	hole_edge_id: number;
	from_node_id: number;
	to_node_id: number;
	distance: number;
	fairway_width: number | null;
}

export type ShotShape = 'straight' | 'hyzer' | 'anhyzer' | 'spike_hyzer' | 'flex';
export type ThrowType = 'drive' | 'placement' | 'approach' | 'putt';
export type CaddieMode = 'conservative' | 'balanced' | 'aggressive';

export interface SegmentRecommendation {
	disc: string;
	disc_id: number | null;
	distance: number;
	effective_distance: number;
	shot_shape: ShotShape;
	throw_type: ThrowType;
	from_node_id: number;
	to_node_id: number;
	hazards: string[];
	skipped_node_ids: number[];
}

export interface HolePath {
	nodes: HoleNode[];
	edges: HoleEdge[];
	total_distance: number;
	node_count: number;
	recommendations: SegmentRecommendation[];
	/** Closed ring of [lat, lon] pairs tracing the fairway corridor */
	fairway_polygon: [number, number][];
}
