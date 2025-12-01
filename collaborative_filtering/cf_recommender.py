# cf_recommender.py
# recommender using collaborative filtering on tags
# had to use tags instead of events directly bc polymarket events expire too fast

import os
import numpy as np
import pandas as pd
from collections import defaultdict
from implicit.als import AlternatingLeastSquares
from dotenv import load_dotenv
from sqlalchemy import create_engine

from collaborative_filtering.utils import load_trade_tags
from collaborative_filtering.utils import load_events_with_tags


# gonna store these globally after loading so we dont have to pass them around everywhere
_model = None
_user2idx = {}
_tag2idx = {}
_event_to_tags = defaultdict(list)
_event_titles = {}
_tag_names = {}
_loaded = False


def _load_event_tags(cache_path):
    """load or create event-to-tag mappings (ALL events, not just active)"""

    events_df = load_events_with_tags()

    return events_df


def load_cf_model(model_path="models/collaborative_filtering_model.npz",
                  trade_cache="collaborative_filtering/df_trade_tags_cache",
                  event_tags_path="collaborative_filtering/events_tag_cache"):
    """
    load the cf model and all the mappings we need
    call this once before using the other functions
    """
    global _model, _user2idx, _tag2idx, _event_to_tags, _event_titles, _tag_names, _loaded

    if _loaded:
        print("already loaded")
        return

    print("loading cf model...")

    # load trained model
    _model = AlternatingLeastSquares(factors=64)
    _model = _model.load(model_path)

    # need to rebuild the user/tag mappings from training data
    # kinda annoying but we need the same indices as when we trained
    df = load_trade_tags(trade_cache)

    # do the same preprocessing as training
    df = df.sort_values(['user_id', 'timestamp'])
    df['idx'] = df.groupby('user_id').cumcount()
    df['total'] = df.groupby('user_id')['timestamp'].transform('size')
    df['cutoff'] = (df['total'] * 0.8).astype(int)
    df['cutoff'] = df['cutoff'].clip(lower=1, upper=df['total']-1)
    df = df[df['total'] >= 2]

    train_df = df[df['idx'] < df['cutoff']].copy()
    train_agg = train_df.groupby(['user_id', 'tag_id', 'tag_label'])['trade_count'].sum().reset_index()

    # build the mappings
    users = train_agg['user_id'].astype('category')
    tags = train_agg['tag_id'].astype('category')

    _user2idx = {u: i for i, u in enumerate(users.cat.categories)}
    _tag2idx = {t: i for i, t in enumerate(tags.cat.categories)}

    print(f"  {len(_user2idx)} users, {len(_tag2idx)} tags")

    # load event tags (creates cache if missing)
    events_df = _load_event_tags(event_tags_path)

    for _, row in events_df.iterrows():
        eid = row['event_id']
        tid = row['tag_id']

        if tid in _tag2idx:
            tidx = _tag2idx[tid]
            _event_to_tags[eid].append(tidx)
            _tag_names[tidx] = row['tag_label']

        _event_titles[eid] = row['title']

    print(f"  {len(_event_to_tags)} events with tags")

    _loaded = True
    print("done!")


def get_user_tag_scores(user_id):
    """get predicted scores for all tags for this user"""
    if not _loaded:
        load_cf_model()

    if user_id not in _user2idx:
        return {}

    uidx = _user2idx[user_id]
    user_vec = _model.user_factors[uidx]
    scores = _model.item_factors.dot(user_vec)

    return {i: float(scores[i]) for i in range(len(scores))}


def get_cf_scores_for_events(user_id):
    """
    score all events for a user based on their tag preferences
    returns dict of event_id -> score
    """
    if not _loaded:
        load_cf_model()

    tag_scores = get_user_tag_scores(user_id)
    if not tag_scores:
        return {}

    # for each event, avg the scores of its tags
    scores = {}
    for eid, tidxs in _event_to_tags.items():
        if tidxs:
            scores[eid] = np.mean([tag_scores[t] for t in tidxs])

    return scores


def recommend_events_cf(user_id, n=10):
    """
    get top n recommendations for a user

    returns list of dicts with id, title, score, tags
    """
    scores = get_cf_scores_for_events(user_id)
    if not scores:
        return []

    # sort and take top n
    sorted_events = sorted(scores.items(), key=lambda x: -x[1])

    results = []
    for eid, score in sorted_events[:n]:
        results.append({
            'id': eid,
            'title': _event_titles.get(eid, f"Event {eid}"),
            'score': score,
            'tags': [_tag_names.get(t, str(t)) for t in _event_to_tags[eid]]
        })

    return results


# helper to check if a user exists in the model
def user_in_cf(user_id):
    if not _loaded:
        load_cf_model()
    return user_id in _user2idx


def get_cf_users():
    """get set of all users in the cf model"""
    if not _loaded:
        load_cf_model()
    return set(_user2idx.keys())


# for getting event titles when combining with topic-based
def get_event_title(event_id):
    return _event_titles.get(event_id)
