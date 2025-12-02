import numpy as np
import pandas as pd
from collections import defaultdict
from implicit.als import AlternatingLeastSquares

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
                  trade_cache="collaborative_filtering/df_trade_tags_cache",
                  events_cache="collaborative_filtering/events_tag_cache"):
    global model, user_to_id, tag_to_id, event_tags, event_titles, tag_labels, loaded

    if loaded:
        return

    print("Loading CF model...")

    model = AlternatingLeastSquares(factors=64)
    model = model.load(model_path)

    # rebuild mappings to match training
    trades_df = load_trade_tags(trade_cache)

    trades_df = trades_df.sort_values(['user_id', 'timestamp'])
    trades_df['row_num'] = trades_df.groupby('user_id').cumcount()
    trades_df['total'] = trades_df.groupby('user_id')['timestamp'].transform('size')
    trades_df['cutoff'] = (trades_df['total'] * 0.8).astype(int)
    trades_df['cutoff'] = trades_df['cutoff'].clip(lower=1, upper=trades_df['total']-1)
    trades_df = trades_df[trades_df['total'] >= 2]

    train_df = trades_df[trades_df['row_num'] < trades_df['cutoff']].copy()
    train_agg = train_df.groupby(['user_id', 'tag_id', 'tag_label'])['trade_count'].sum().reset_index()

    users_cat = train_agg['user_id'].astype('category')
    tags_cat = train_agg['tag_id'].astype('category')

    user_to_id = {u: i for i, u in enumerate(users_cat.cat.categories)}
    tag_to_id = {t: i for i, t in enumerate(tags_cat.cat.categories)}

    print(f"  {len(user_to_id)} users, {len(tag_to_id)} tags")

    # load event-tag mappings
    events_df = load_events_with_tags(events_cache)

    for _, row in events_df.iterrows():
        event_id = int(row['event_id'])
        tag_id = row['tag_id']

        if tag_id in tag_to_id:
            t_id = tag_to_id[tag_id]
            event_tags[event_id].append(t_id)
            tag_labels[t_id] = row['tag_label']

        event_titles[event_id] = row['title']

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
