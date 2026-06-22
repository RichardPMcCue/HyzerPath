export interface Me {
	user_id: number;
	email: string;
	name: string | null;
	username: string | null;
	is_admin: boolean | null;
}

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

export type ThrowStyle = 'backhand' | 'forehand';
export type Hand = 'right' | 'left';

export interface ThrowStyleRow {
	throw_type: ThrowStyle;
	hand: Hand;
	priority: number;
}

export interface DiscStat {
	stat_id: number;
	disc_id: number;
	throw_style: ThrowStyle;
	avg_distance: number;
	max_distance: number | null;
	sample_size: number | null;
}

export interface RoundHoleScore {
	hole_id: number;
	score: number;
}

export type TrackingMode = 'discs' | 'lies' | 'detail' | 'score';
export type RoundLayout = 'full' | 'front9' | 'back9';

export interface Round {
	round_id: number;
	course_id: number;
	bag_id: number;
	played_at: string;
	total_score: number | null;
	tracking_mode: TrackingMode;
	layout: RoundLayout;
	round_holes: RoundHoleScore[];
}

export interface RoundStats {
	holes_with_throws: number;
	c1_putts_made: number;
	c1_putts_attempted: number;
	c2_putts_made: number;
	c2_putts_attempted: number;
	fairway_hits: number;
	fairway_attempts: number;
	parked: number;
}

export interface LifetimeStats {
	rounds_played: number;
	holes_with_throws: number;
	c1_putts_made: number;
	c1_putts_attempted: number;
	c1x_putts_made: number;
	c1x_putts_attempted: number;
	c2_putts_made: number;
	c2_putts_attempted: number;
	fairway_hits: number;
	fairway_attempts: number;
	parked: number;
	gir_c1: number;
	gir_c2: number;
	gir_attempts: number;
}

export interface ThrowMeasurement {
	throw_id: number;
	session_id: number;
	disc_id: number | null;
	throw_style: ThrowStyle | null;
	end_latitude: number;
	end_longitude: number;
	distance_ft: number;
	created_at: string;
}

export interface ThrowSession {
	session_id: number;
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

/** A fairway waypoint between tee and basket in the mapper. */
export interface MapperWaypoint {
	lat: number;
	lng: number;
	/** Set when the waypoint exists on the server (edit mode) */
	nodeId?: number;
	moved?: boolean;
}

/** One hole being placed/edited in the course mapper UI. */
export interface MapperHole {
	holeNumber: number;
	par: number;
	tee: { lat: number; lng: number } | null;
	pin: { lat: number; lng: number } | null;
	/** Fairway waypoints (landing zones), in play order — defines doglegs */
	fairway: MapperWaypoint[];
	/** Set when the hole already exists on the server (edit mode) */
	holeId?: number;
	teeNodeId?: number;
	pinNodeId?: number;
	/** Dirty flags so edit mode only PATCHes what changed */
	teeMoved?: boolean;
	pinMoved?: boolean;
	parChanged?: boolean;
	/** Waypoints added/removed — edges need a rebuild on save */
	fairwayChanged?: boolean;
	/** Persisted waypoint nodes removed via undo, deleted on save */
	removedNodeIds?: number[];
	/** Hazard/OB areas drawn for this hole */
	hazards: MapperHazard[];
	/** Persisted hazards removed in the editor, deleted on save */
	removedHazardIds?: number[];
}

/** A hazard area drawn in the mapper. */
export interface MapperHazard {
	hazard_type: string;
	polygon: { lat: number; lng: number }[];
	/** Set when the hazard exists on the server (edit mode) */
	hazardId?: number;
}

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

export type ShotShape =
	| 'straight'
	| 'hyzer'
	| 'anhyzer'
	| 'spike_hyzer'
	| 'flex'
	| 'hyzer_flip'
	| 'turnover';
export type ThrowType = 'drive' | 'placement' | 'approach' | 'putt';
export type LandingZone = 'fairway' | 'c1' | 'c2' | 'c3' | 'basket';
export type CaddieMode = 'conservative' | 'balanced' | 'aggressive';

export interface SegmentRecommendation {
	disc: string;
	disc_id: number | null;
	distance: number;
	effective_distance: number;
	shot_shape: ShotShape;
	throw_style: ThrowStyle;
	throw_type: ThrowType;
	landing_zone: LandingZone;
	rationale: string;
	// Flight numbers of the recommended disc (distinguishes copies of a mold)
	speed: number | null;
	glide: number | null;
	turn: number | null;
	fade: number | null;
	wear: number | null;
	from_node_id: number;
	to_node_id: number;
	hazards: string[];
	skipped_node_ids: number[];
}

export interface Hazard {
	hazard_id: number;
	hole_id: number;
	hazard_type: string;
	/** Ring of [lat, lon] pairs */
	polygon: [number, number][];
}

export interface HolePath {
	nodes: HoleNode[];
	edges: HoleEdge[];
	total_distance: number;
	node_count: number;
	recommendations: SegmentRecommendation[];
	/** Closed ring of [lat, lon] pairs tracing the fairway corridor */
	fairway_polygon: [number, number][];
	/** Hazard/OB areas drawn by course editors */
	hazards: Hazard[];
}
