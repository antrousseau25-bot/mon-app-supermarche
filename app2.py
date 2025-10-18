from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import heapq
import json
import firebase_admin
from firebase_admin import credentials, firestore
import math

app = Flask(__name__)
CORS(app) 

# --- 1. INITIALISATION DE FIREBASE ---
try:
    CRED = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(CRED)
    db = firestore.client()
except Exception as e:
    print(f"Erreur FATALE lors de l'initialisation de Firebase : {e}")

# --- 2. FONCTIONS DE L'ALGORITHME ---
def dijkstra(graph, start_node, end_node):
    distances = {node: float('inf') for node in graph}
    distances[start_node] = 0
    previous_nodes = {node: None for node in graph}
    priority_queue = [(0, start_node)]
    while priority_queue:
        current_distance, current_node = heapq.heappop(priority_queue)
        if current_distance > distances[current_node]: continue
        if current_node == end_node:
            path = []
            while current_node is not None:
                path.append(current_node)
                current_node = previous_nodes[current_node]
            return distances[end_node], path[::-1]
        if current_node in graph:
            for neighbor, weight in graph[current_node].items():
                weight = float(weight) 
                distance = current_distance + weight
                if distance < distances[neighbor]:
                    distances[neighbor] = distance
                    previous_nodes[neighbor] = current_node 
                    heapq.heappush(priority_queue, (distance, neighbor))
    return float('inf'), []

def dijkstra_with_avoidance(graph, start_node, end_node, used_edges):
    distances = {node: float('inf') for node in graph}
    distances[start_node] = 0
    previous_nodes = {node: None for node in graph}
    priority_queue = [(0, start_node)]
    while priority_queue:
        current_distance, current_node = heapq.heappop(priority_queue)
        if current_distance > distances[current_node]: continue
        if current_node == end_node:
            path = []
            while current_node is not None:
                path.append(current_node)
                current_node = previous_nodes[current_node]
            return distances[end_node], path[::-1]
        if current_node in graph:
            for neighbor, weight in graph[current_node].items():
                if (current_node, neighbor) in used_edges or (neighbor, current_node) in used_edges: continue
                weight = float(weight)
                distance = current_distance + weight
                if distance < distances[neighbor]:
                    distances[neighbor] = distance
                    previous_nodes[neighbor] = current_node
                    heapq.heappush(priority_queue, (distance, neighbor))
    return float('inf'), []

def calculer_distance_entre_noeuds(node_a, node_b, graphe):
    distance, _ = dijkstra(graphe, node_a, node_b)
    return distance

def calculer_distance_totale_destinations(sequence_destinations, graphe):
    if len(sequence_destinations) < 2: return 0
    total_distance = 0
    for i in range(len(sequence_destinations) - 1):
        total_distance += calculer_distance_entre_noeuds(sequence_destinations[i], sequence_destinations[i+1], graphe)
    return total_distance

def trouver_chemin_initial_glouton(destinations_nodes, graphe):
    current_node = 'E' 
    ordered_destinations = [] 
    remaining_destinations = set(destinations_nodes)
    while remaining_destinations:
        min_distance = float('inf')
        next_destination = None
        for dest in remaining_destinations:
            if dest in graphe:
                distance = calculer_distance_entre_noeuds(current_node, dest, graphe)
                if distance < min_distance:
                    min_distance = distance
                    next_destination = dest
        if next_destination:
            ordered_destinations.append(next_destination)
            current_node = next_destination
            remaining_destinations.remove(next_destination)
        else: break
    return ordered_destinations

def two_opt_swap(sequence, i, k):
    return sequence[:i] + sequence[i:k+1][::-1] + sequence[k+1:]

def ameliorer_parcours_two_opt(destinations_only, graphe):
    best_destination_sequence = trouver_chemin_initial_glouton(destinations_only, graphe)
    if not best_destination_sequence:
        return ['E']
    full_sequence_for_calc = ['E'] + best_destination_sequence
    best_distance = calculer_distance_totale_destinations(full_sequence_for_calc, graphe)
    improved = True
    iteration_count = 0 
    while improved and iteration_count < 50:
        improved = False
        iteration_count += 1
        for i in range(len(best_destination_sequence)):
            for k in range(i + 1, len(best_destination_sequence)): 
                candidate_destinations = two_opt_swap(best_destination_sequence, i, k)
                candidate_full_sequence = ['E'] + candidate_destinations
                new_distance = calculer_distance_totale_destinations(candidate_full_sequence, graphe)
                if new_distance < best_distance:
                    best_distance = new_distance
                    best_destination_sequence = candidate_destinations
                    improved = True
                    break 
            if improved: break
    return ['E'] + best_destination_sequence

def construire_chemin_final_sans_retour(ordered_stops, graphe):
    final_path_nodes = []
    total_distance = 0
    used_edges = set()
    for i in range(len(ordered_stops) - 1):
        start_node = ordered_stops[i]
        end_node = ordered_stops[i+1]
        dist_segment, path_segment = dijkstra_with_avoidance(graphe, start_node, end_node, used_edges)
        if not path_segment:
             dist_segment, path_segment = dijkstra(graphe, start_node, end_node)
             if not path_segment:
                 return float('inf'), [], {"error": f"Impossible de trouver un chemin entre {start_node} et {end_node}."}
        for j in range(len(path_segment) - 1):
            u, v = path_segment[j], path_segment[j+1]
            used_edges.add((u, v))
            used_edges.add((v, u))
        if not final_path_nodes:
            final_path_nodes.extend(path_segment)
        else:
            final_path_nodes.extend(path_segment[1:])
        total_distance += dist_segment
    return total_distance, final_path_nodes, None

# --- 3. LOGIQUE DE RÉCUPÉRATION DES DONNÉES ---
def graphe_to_arêtes(graphe):
    aretes = set()
    for start_node, neighbors in graphe.items():
        for end_node, _ in neighbors.items():
            if start_node < end_node:
                aretes.add(json.dumps({'start': start_node, 'end': end_node}))
    return [json.loads(a) for a in aretes]
def get_magasin_data(magasin_id):
    try:
        magasin_doc = db.collection('magasins').document(magasin_id).get()
        if not magasin_doc.exists: return None, None, None, None, {"error": "Magasin non trouvé."}
        magasin_data = magasin_doc.to_dict()
        graphe_magasin = magasin_data.get('graphe_data', {})
        coordonnees_dessin = magasin_data.get('coordonnees_dessin', {})
        emplacements_ref = db.collection('emplacements_produits').where('magasin_id', '==', magasin_id).stream()
        emplacements_produits = {}
        for doc in emplacements_ref:
            data = doc.to_dict()
            emplacements_produits[data['nom_produit']] = data.get('noeud_localisation')
        aretes_dessin = graphe_to_arêtes(graphe_magasin)
        return graphe_magasin, coordonnees_dessin, emplacements_produits, aretes_dessin, None
    except Exception as e:
        return None, None, None, None, {"error": f"Erreur de base de données Firestore: {e}"}

# --- 4. ROUTES API ---
@app.route('/', methods=['GET'])
def index_page():
    return render_template('index2.html')

@app.route('/service-worker.js')
def serve_sw():
    return send_from_directory('.', 'service-worker.js')

@app.route('/api/v1/magasin_data/<magasin_id>', methods=['GET'])
def get_magasin_plan(magasin_id):
    graphe, coordonnees, emplacements, aretes, error = get_magasin_data(magasin_id)
    if error: return jsonify(error), 500
    response = { "magasin_id": magasin_id, "coordonnees_dessin": coordonnees, "arêtes_dessin": aretes, "emplacements_produits": emplacements }
    return jsonify(response)

@app.route('/api/v1/optimize_route', methods=['POST'])
def optimize_route():
    data = request.json
    if not data or 'liste_produits' not in data or 'magasin_id' not in data:
        return jsonify({"error": "Données manquantes"}), 400
    
    liste_courses = data['liste_produits']
    magasin_id = data['magasin_id']
    nombre_articles = len(liste_courses)
    CAISSES_REGULIERES = ('C1', 'C2', 'C3')
    CAISSE_AUTO = 'CA'

    graphe, _, emplacements, _, error_db = get_magasin_data(magasin_id)
    if error_db: return jsonify(error_db), 500 

    destinations_nodes = []
    for produit in liste_courses:
        emplacement = emplacements.get(produit) 
        if emplacement and emplacement not in destinations_nodes:
            destinations_nodes.append(emplacement)
            
    if not destinations_nodes:
        parcours_final_ordonne = ['E', CAISSE_AUTO]
    else:
        parcours_produits_ordonne = ameliorer_parcours_two_opt(destinations_nodes, graphe)
        dernier_point_avant_caisse = parcours_produits_ordonne[-1]

        if nombre_articles <= 5:
            destination_finale = CAISSE_AUTO
            message = "Itinéraire via la caisse automatique."
        else:
            meilleure_caisse = min(CAISSES_REGULIERES, key=lambda c: calculer_distance_entre_noeuds(dernier_point_avant_caisse, c, graphe))
            destination_finale = meilleure_caisse
            message = "Itinéraire via la caisse la plus proche."

        parcours_final_ordonne = parcours_produits_ordonne + [destination_finale]

    distance_reelle, parcours_final_noms, error_path = construire_chemin_final_sans_retour(parcours_final_ordonne, graphe)
    if error_path: return jsonify(error_path), 500
    response = { "magasin_id": magasin_id, "liste_fournie": liste_courses, "distance_optimale": round(distance_reelle, 2), "parcours_optimise_noms": parcours_final_noms, "message": message }
    return jsonify(response)

# --- LANCEMENT DE L'APPLICATION ---
if __name__ == '__main__':
    app.run(debug=True, port=5000)