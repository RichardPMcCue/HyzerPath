import heapq

def dijkstra(edges: list, start_id: int, end_id: int) -> list:
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
