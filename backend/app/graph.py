import heapq

def dijkstra(edges: list, start_id: int, end_id: int) -> list:
    # edges is a list of (from_node_id, to_node_id, weight)
    
    # Build adjacency list from edges
    graph = {}
    for from_id, to_id, weight in edges:
        if from_id not in graph:
            graph[from_id] = []
        graph[from_id].append((to_id, weight))

    # Priority queue: (cost, node_id)
    heap = [(0, start_id)]
    
    # Track lowest cost to reach each node
    costs = {start_id: 0}
    
    # Track the path
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
            
        
        # For each neighbor of current_node
        # Calculate new_cost = current_cost + edge_weight
        # If new_cost < costs.get(neighbor, infinity)
        # Update costs, previous, push to heap
        for neighbor, weight in graph.get(current_node, []):
            new_cost = current_cost + weight
            if new_cost < costs.get(neighbor, float("inf")):
                costs[neighbor] = new_cost
                previous[neighbor] = current_node
                heapq.heappush(heap, (new_cost, neighbor))
    
    return []  # return ordered list of node_ids