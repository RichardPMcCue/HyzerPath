import heapq

def dijkstra(edges: list, start_id: int, end_id: int, node_map: dict = None) -> list:
    graph = {}
    for from_id, to_id, weight in edges:
        if from_id not in graph:
            graph[from_id] = []
        graph[from_id].append((to_id, weight))

    heap = [(0, start_id)]
    costs = {start_id: 0}
    previous = {}

    while heap:
        current_cost, current_node = heapq.heappop(heap)

        if current_cost > costs.get(current_node, float("inf")):
            continue

        if current_node == end_id:
            path = []
            node = end_id
            while node in previous:
                path.append(node)
                node = previous[node]
            path.append(start_id)
            path.reverse()
            return path

        for neighbor, weight in graph.get(current_node, []):
            new_cost = current_cost + weight
            if new_cost < costs.get(neighbor, float("inf")):
                costs[neighbor] = new_cost
                previous[neighbor] = current_node
                heapq.heappush(heap, (new_cost, neighbor))

    return []

def compute_edge_weight(edge, to_node=None, centerline_distance=None, fairway_width=None) -> float:
    base = 1.0  # one throw = base cost of 1

    # Prefer explicitly computed values (dynamic centerline/width), fall back
    # to what's stored on the node/edge.
    if centerline_distance is None and to_node is not None:
        centerline_distance = to_node.centerline_distance
    if fairway_width is None:
        fairway_width = edge.fairway_width

    centerline_penalty = 0.0
    if centerline_distance is not None:
        if fairway_width:
            centerline_penalty = centerline_distance / fairway_width
        else:
            centerline_penalty = centerline_distance / 100.0

    return base + centerline_penalty
