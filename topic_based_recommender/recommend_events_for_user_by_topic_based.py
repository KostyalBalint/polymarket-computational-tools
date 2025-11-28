import faiss
import numpy as np


def find_similar_events(id_to_index, normalized_embeddings,index,index_to_id, events_df, event_id, k):
    idx = id_to_index[event_id]
    query = normalized_embeddings[idx:idx+1].astype('float32')

    # Search for k+1 because the event itself will be included
    distances, indices = index.search(query, k + 1)

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        similar_id = index_to_id[idx]
        if similar_id != event_id:  # Exclude the query event itself
            results.append({
                'id': similar_id,
                'title': events_df.loc[similar_id, 'title'],
                'similarity': float(dist)
            })
    return results[:k]





def recommend_events_for_user_by_topic_based(id_to_index, normalized_embeddings,index,index_to_id, user_event_associations_df,events_df, user_address, top_n,  similar_per_event):
    # Get all events the user has betted on and measure their score
    user_events = user_event_associations_df[user_event_associations_df['address'] == user_address]
    user_event_ids = set(user_events['event_id'].astype(str).unique())

    event_scores = {}

    # For each event the user has betted on, find similar events
    for event_id in user_event_ids:
        event_id_int = int(event_id)
        if event_id_int not in events_df.index:
            continue

        similar_events = find_similar_events(id_to_index, normalized_embeddings,index,index_to_id, events_df, event_id, similar_per_event)

        # Add to scores and weight by the similartiy.
        for similar_event in similar_events:
            similar_id = str(similar_event['id'])
            similarity = similar_event['similarity']

            if similar_id in user_event_ids:
                continue

            if similar_id not in event_scores:
                event_scores[similar_id] = {
                    'id': similar_event['id'],
                    'title': similar_event['title'],
                    'score': 0,
                    'count': 0
                }
            event_scores[similar_id]['score'] += similarity
            event_scores[similar_id]['count'] += 1

    recommendations = sorted(event_scores.values(), key=lambda x: x['score'], reverse=True)[:top_n]

    # Format results
    for rec in recommendations:
        rec['avg_similarity'] = rec['score'] / rec['count']
        rec['total_score'] = rec['score']

    return recommendations