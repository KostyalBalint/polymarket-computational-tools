import itertools
import pandas as pd
from apriori import Apriori

def optimize_apriori_parameters(conn):
    PARAM_SPACE = {
        "mode": ["trades", "sessions", "events"],
        "min_items": [1, 2, 3],
        "min_support": [0.01, 0.02, 0.05, 0.1],
        "min_confidence": [0.3, 0.4, 0.5, 0.6],
        "min_lift": [1.1, 1.3, 1.5]
    }

    print("\nAPRIORI PARAMETER OPTIMIZER")

    results = []

    # Generate all combinations of parameters
    keys = list(PARAM_SPACE.keys())
    for values in itertools.product(*PARAM_SPACE.values()):
        params = dict(zip(keys, values))

        print(f"\nTesting params: {params}")

        apr = Apriori(conn)
        try:
            transactions = apr.fetch_user_transactions(
                mode=params["mode"],
                min_items=params["min_items"],
                days_back=60,  # fixed window
                test=False
            )

            if not transactions:
                print("\t-> No transactions, skipping.")
                continue

            apr.generate_frequent_item_sets(
                min_support=params["min_support"],
                test=False
            )

            if len(apr.frequent_item_sets) <= 1:
                print("  -> Only 1-itemsets found, skipping.")
                continue

            apr.generate_association_rules(
                min_confidence=params["min_confidence"],
                min_lift=params["min_lift"],
                test=False
            )

            n_rules = len(apr.association_rules)
            if n_rules == 0:
                print("\t-> No rules.")
                continue

            avg_lift = sum(r['lift'] for r in apr.association_rules) / n_rules
            avg_conf = sum(r['confidence'] for r in apr.association_rules) / n_rules

            print(f"\t-> {n_rules} rules found")

            results.append({
                **params,
                "rules": n_rules,
                "avg_lift": avg_lift,
                "avg_confidence": avg_conf
            })

        except Exception as e:
            print(f"\tERROR: {e}")
            continue

    # No results found
    if not results:
        print("\nNo parameter combination produced rules.")
        return None

    df = pd.DataFrame(results)

    # Sort by rules first, then lift, then confidence
    df = df.sort_values(
        by=["rules", "avg_lift", "avg_confidence"],
        ascending=False
    )

    print("\nOPTIMIZATION COMPLETE")

    print("\nTop results:")
    print(df.head(10).to_string(index=False))

    best_params = df.iloc[0].to_dict()
    print("\nBEST PARAMETER SET:")
    print(best_params)

    # Export results
    df.to_csv("apriori_param_search_results.csv", index=False)
    print("\nFull search results exported to apriori_param_search_results.csv")

    return best_params
