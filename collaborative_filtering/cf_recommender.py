import numpy as np
import pandas as pd
from collections import defaultdict
from implicit.als import AlternatingLeastSquares
import pickle

from collaborative_filtering.utils import load_trade_tags
from collaborative_filtering.utils import load_events_with_tags


model = None
user_to_id = {}
tag_to_id = {}
event_tags = defaultdict(list)
event_titles = {}
tag_labels = {}
loaded = False


def load_cf_model(model_path="models/collaborative_filtering_model.npz",
                  mappings_path="models/cf_mappings.pkl",):
    global model, user_to_id, tag_to_id, event_tags, event_titles, tag_labels, loaded

    if loaded:
        return

    print("Loading CF model...")

    model = AlternatingLeastSquares(factors=64)
    model = model.load(model_path)

    with open(mappings_path, 'rb') as f:
            mappings = pickle.load(f)
            user_to_id = mappings['user_to_id']
            tag_to_id = mappings['tag_to_id']
            # Convert back to defaultdict
            event_tags = defaultdict(list, mappings['event_tags'])
            event_titles = mappings['event_titles']
            tag_labels = mappings['tag_labels']

    print(f"  {len(user_to_id)} users, {len(tag_to_id)} tags")
    print(f"  {len(event_tags)} events mapped")

    loaded = True
    print("done")


def get_event_scores(user_id):
    if user_id not in user_to_id:
        return {}

    u_id = user_to_id[user_id]
    user_vec = model.user_factors[u_id]
    scores = model.item_factors.dot(user_vec)
    tag_scores = {i: float(scores[i]) for i in range(len(scores))}

    if not tag_scores:
        return {}

    event_scores = {}
    for event_id, t_ids in event_tags.items():
        if t_ids:
            event_scores[event_id] = np.mean([tag_scores[t] for t in t_ids])

    return event_scores


def recommend_events(user_id, n=10):
    scores = get_event_scores(user_id)
    if not scores:
        return []

    sorted_events = sorted(scores.items(), key=lambda x: -x[1])

    results = []
    for event_id, score in sorted_events[:n]:
        results.append({
            'id': event_id,
            'title': event_titles.get(event_id, f"Event {event_id}"),
            'score': score,
            'tags': [tag_labels.get(t, str(t)) for t in event_tags[event_id]]
        })

    return results

#Get all user IDs in the model
def get_cf_users():
    return set(user_to_id.keys())
