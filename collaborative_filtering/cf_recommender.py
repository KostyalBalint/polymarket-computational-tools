import numpy as np
import pandas as pd
from collections import defaultdict
from implicit.als import AlternatingLeastSquares
import pickle
import scipy.sparse as sparse
from collaborative_filtering.utils import load_trade_tags
from collaborative_filtering.utils import load_events_with_tags


model = None
user_to_id = {}
tag_to_id = {}
event_tags = defaultdict(list)
event_titles = {}
tag_labels = {}
loaded = False


def load_cf_model(train_df: pd.DataFrame,
                  factors=64,
                  regularization=1.0, 
                  iterations=50,      
                  alpha=40,           
                  force_reload=False, 
                  model_path="models/collaborative_filtering_model.npz",
                  mappings_path="models/cf_mappings.pkl"):
    """
    Loads or trains the Collaborative Filtering (ALS) model.
    Supports force_reload to update hyperparameters on the fly.
    """
    global model, user_to_id, tag_to_id, event_tags, event_titles, tag_labels, loaded, matrix

    # Only return existing model if we are NOT forcing a reload
    if loaded and matrix is not None and not force_reload:
        density = matrix.nnz / (matrix.shape[0] * matrix.shape[1])
        sparsity = 1 - density
        print(f"CF Model already loaded with Factors={model.factors}, Reg={model.regularization}, Iterations={model.iterations}")
        print(f"Sparsity: {sparsity:.4f} ({sparsity*100:.2f}%)")
        return model

    if force_reload:
        print("Forcing model reload and retraining with new parameters.")

    print(f"Loading/Training CF model with: Factors={factors}, Reg={regularization}, Iterations={iterations}...")

    train_agg = train_df.groupby(['user_id', 'tag_id', 'tag_label'])['trade_count'].sum().reset_index()
    print(f"  {len(train_agg):,} user-tag pairs")
    
    # build indexes
    users_cat = train_agg['user_id'].astype('category')
    tags_cat = train_agg['tag_id'].astype('category')
    
    user_to_id = {u: i for i, u in enumerate(users_cat.cat.categories)}
    tag_to_id = {t: i for i, t in enumerate(tags_cat.cat.categories)}
    
    n_users = len(user_to_id)
    n_tags = len(tag_to_id)
    print(f"  matrix: {n_users} x {n_tags}")
    
    # build sparse matrix (Confidence matrix C = 1 + alpha * R)
    row_id = users_cat.cat.codes.values
    col_id = tags_cat.cat.codes.values
    
    # Using confidence weighting for implicit feedback
    confidence = 1 + alpha * np.log1p(train_agg['trade_count'].values)
    
    matrix = sparse.csr_matrix((confidence, (row_id, col_id)), shape=(n_users, n_tags))
    
    # train model
    model = AlternatingLeastSquares(
        factors=factors,
        regularization=regularization,
        iterations=iterations,
        random_state=42
    )
    
    model.fit(matrix, show_progress=True)
    
    
    if event_tags and event_titles:
        print("Skipping event mapping (already loaded).")
    else:
        # build event-tag mappings only if empty
        print("Mapping events...")
        event_tags.clear() # ensure clean start if partially filled
        train_event_ids = set(train_df['event_id'].unique())

        events_df = load_events_with_tags()
        for _, row in events_df .iterrows():
            event_id = row['event_id']

            if event_id not in train_event_ids:  # skip if not in train
                continue

            tag_id = row['tag_id']
            
            if tag_id in tag_to_id:
                t_id = tag_to_id[tag_id]
                event_tags[event_id].append(t_id)
                tag_labels[t_id] = row['tag_label']
            
            event_titles[event_id] = row['title']
    
    print(f"  {len(event_tags)} events mapped")
    density = matrix.nnz / (matrix.shape[0] * matrix.shape[1])
    sparsity = 1 - density
    print(f"sparsity: {sparsity:.4f} ({sparsity*100:.2f}%)")

    loaded = True
    return model


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
