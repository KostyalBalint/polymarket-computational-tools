from itertools import combinations
from collections import defaultdict
from typing import List, Dict, Set
import pandas as pd

class Apriori:
    def __init__(self, db_connection):
        self.conn = db_connection
        self.transactions = []
        self.frequent_item_sets = {}
        self.association_rules = []

    # STEP 1: FETCH DATA
    # Modes:
    #     - Mode 'positions': All markets a user currently has positions in
    #     - Mode 'trades': All markets a user has ever traded
    #     - Mode 'sessions': Markets traded by a user on the same day
    #     - Mode 'events': Markets in the same event traded by a user
    # Args:
    #   - mode: 'positions', 'trades', 'sessions', or 'events'
    #   - min_items: Minimum number of items per transaction (filter noise)
    #   - days_back: Number of days to look back for historical data
    #   - test: Print all transactions
    # Returns:
    #   - List of transactions
    def fetch_user_transactions(self, mode: str = 'positions', min_items: int = 2, days_back: int = 30, test: bool = False):
        cursor = self.conn.cursor()
        print("STEP 1: FETCHING TRANSACTION DATA")

        if mode == 'positions':
            query = """
            SELECT 
                up."proxyWallet" as transaction_id,
                up.slug || '_' || up.outcome as item
            FROM "UserPosition" up
            WHERE up.size > 0 
                AND (up."endDate" IS NULL 
                     OR up."endDate" = '' 
                     OR up."endDate"::timestamp > NOW())
            ORDER BY up."proxyWallet"
            """
            cursor.execute(query)

        elif mode == 'trades':
            query = """
            SELECT 
                ut."proxyWallet" as transaction_id,
                ut.slug || '_' || ut.outcome as item
            FROM "UserTrade" ut
            WHERE ut.timestamp >= NOW() - INTERVAL '%s days'
            ORDER BY ut."proxyWallet"
            """
            cursor.execute(query, (days_back,))

        elif mode == 'sessions':
            query = """
            SELECT 
                ut."proxyWallet" || '_' || DATE(ut.timestamp) as transaction_id,
                ut.slug || '_' || ut.outcome as item
            FROM "UserTrade" ut
            WHERE ut.timestamp >= NOW() - INTERVAL '%s days'
            ORDER BY transaction_id
            """
            cursor.execute(query, (days_back,))

        elif mode == 'events':
            query = """
            SELECT 
                ut."proxyWallet" || '_' || ut."eventSlug" as transaction_id,
                ut.slug || '_' || ut.outcome as item
            FROM "UserTrade" ut
            WHERE ut.timestamp >= NOW() - INTERVAL '%s days'
                AND ut."eventSlug" IS NOT NULL
            ORDER BY transaction_id
            """
            cursor.execute(query, (days_back,))
        else:
            raise ValueError(f"Invalid mode: {mode}")

        results = cursor.fetchall()
        cursor.close()

        # Group items by transaction
        transaction_dict = defaultdict(set)
        for transaction_id, item in results:
            if item:
                transaction_dict[transaction_id].add(item)

        # Filter transactions with minimum number of items
        self.transactions = [
            items for items in transaction_dict.values()
            if len(items) >= min_items
        ]

        print(f"\n📊 TRANSACTION STATISTICS:")
        print(f"   Total transactions: {len(self.transactions)}")
        if self.transactions:
            avg_items = sum(len(t) for t in self.transactions) / len(self.transactions)
            print(f"   Average items per transaction: {avg_items:.2f}")
            print(f"   Total unique items: {len(set().union(*self.transactions))}")

        if test:
            for t in self.transactions:
                print(f"   Transaction {t}: {list(t)[:5]}" +
                      ("..." if len(t) > 5 else ""))
        return self.transactions

    # STEP 2: CALCULATE SUPPORT
    @staticmethod
    def _calculate_support(item_set: frozenset, transactions: List[Set]) -> float:
        count = sum(1 for transaction in transactions if item_set.issubset(transaction))
        support = count / len(transactions) if transactions else 0
        return support

    # STEP 3: FIND FREQUENT 1-ITEM SETS
    # Args:
    #    - min_support: Minimum support threshold (e.g., 0.02 = 2%)
    #    - test: Print detailed output
    # Returns:
    #   - Dictionary {item_set: support} for frequent 1-item_sets
    def _get_frequent_1_item_sets(self, min_support: float, test: bool = False) -> Dict[frozenset, float]:
        print(f"\nMinimum support threshold: {min_support} ({min_support * 100}%)")

        # Count each individual item
        item_counts = defaultdict(int)
        for transaction in self.transactions:
            for item in transaction:
                item_counts[frozenset([item])] += 1

        if test:
            print(f"Total unique items found: {len(item_counts)}")

        # Calculate support and filter
        n_transactions = len(self.transactions)
        frequent_items = {}

        for item_set, count in item_counts.items():
            support = count / n_transactions
            if support >= min_support:
                frequent_items[item_set] = support

        if test:
            print(f"Items passing support threshold: {len(frequent_items)}")
            print(f"Items filtered out: {len(item_counts) - len(frequent_items)}")

            # Show top items by support
            sorted_items = sorted(frequent_items.items(), key=lambda x: x[1], reverse=True)
            print(f"\n📊 TOP 10 MOST FREQUENT ITEMS:")
            for i, (item_set, sup) in enumerate(sorted_items[:10], 1):
                item = list(item_set)[0]
                print(f"   {i}. {item}: {sup:.3f} ({sup * 100:.1f}%)")

        return frequent_items

    # STEP 4: GENERATE CANDIDATE ITEM SETS
    # Generate candidate k-item_sets from frequent (k-1)-item_sets.
    # Args:
    #     - prev_frequent: List of frequent (k-1)-item_sets
    #     - k: Size of item_sets to generate
    #     - test: Print detailed output
    #
    # Returns:
    #     List of candidate k-item_sets
    @staticmethod
    def _generate_candidates(prev_frequent: List[frozenset], k: int, test: bool = False) -> List[frozenset]:
        if test:
            print(f"\n   Generating candidate {k}-itemsets...")
            print(f"   Starting with {len(prev_frequent)} frequent {k - 1}-itemsets")

        candidates = []
        n = len(prev_frequent)

        # Join step: merge itemsets
        for i in range(n):
            for j in range(i + 1, n):
                # Union of two (k-1)-itemsets
                union = prev_frequent[i] | prev_frequent[j]

                # If union has exactly k items, it's a valid candidate
                if len(union) == k:
                    candidates.append(union)

        # Remove duplicates
        candidates = list(set(candidates))

        if test:
            print(f"\tGenerated {len(candidates)} candidate {k}-itemsets")
            if candidates and len(candidates) <= 5:
                print(f"\tExamples: {[list(c) for c in candidates[:5]]}")

        return candidates

    # STEP 5: GENERATE ALL FREQUENT ITEM SETS
    # 1. Start with frequent 1-item sets (individual items)
    # 2. Use them to generate candidate 2-item sets
    # 3. Test candidates against database, keep frequent ones
    # 4. Use frequent 2-item sets to generate candidate 3-item sets
    # 5. Repeat until no more frequent item sets can be found
    # Args:
    #     - min_support: Minimum support threshold (0-1)
    #     - test: Print detailed progress information
    # Returns:
    #     - Dictionary {k: {item_set: support}} for all frequent k-item_sets
    def generate_frequent_item_sets(self, min_support: float = 0.02, test: bool = True):
        if not self.transactions:
            raise ValueError("No transactions loaded")

        self.frequent_item_sets = {1: self._get_frequent_1_item_sets(min_support, test)}

        if not self.frequent_item_sets[1]:
            print("\n⚠️  No frequent 1-itemsets found. Try lowering min_support.")
            return self.frequent_item_sets

        k = 2
        while self.frequent_item_sets[k - 1]:
            if test:
                print(f"ITERATION {k}: Finding frequent {k}-itemsets")

            candidates = self._generate_candidates(
                list(self.frequent_item_sets[k - 1].keys()),
                k,
                test
            )

            if not candidates:
                if test:
                    print(f"\tNo candidates generated. Stopping.")
                break

            if test:
                print(f"\tTesting {len(candidates)} candidates against {len(self.transactions)} transactions")

            frequent_k = {}
            for candidate in candidates:
                support = self._calculate_support(candidate, self.transactions)
                if support >= min_support:
                    frequent_k[candidate] = support

            if frequent_k:
                self.frequent_item_sets[k] = frequent_k
                if test:
                    print(f"\t✅Found {len(frequent_k)} frequent {k}-item_sets")

                    # Show examples
                    sorted_item_sets = sorted(frequent_k.items(), key=lambda x: x[1], reverse=True)
                    print(f"\n\t📊 TOP 5 FREQUENT {k}-ITEM_SETS:")
                    for i, (item_set, sup) in enumerate(sorted_item_sets[:5], 1):
                        print(f"      {i}. {list(item_set)}: {sup:.3f} ({sup * 100:.1f}%)")
                k += 1
            else:
                if test:
                    print(f"\t❌No frequent {k}-item_sets found. Stopping.")
                break

        if test:
            print("FREQUENT ITEM SET GENERATION COMPLETE")
            total_frequent = sum(len(item_sets) for item_sets in self.frequent_item_sets.values())
            print(f"Total frequent item sets found: {total_frequent}")
            for k, item_sets in self.frequent_item_sets.items():
                print(f"\t{k}-item_sets: {len(item_sets)}")

        return self.frequent_item_sets

    # STEP 6: GENERATE ASSOCIATION RULES
    # "If someone bets on A and B, they will likely also bet on C"
    # Support = 0.08 (8% of users bet on all three)
    # Confidence = 0.65 (65% of users who bet A+B also bet C)
    # Lift = 2.1 (C is 2.1x more likely given A+B)
    #
    # Args:
    #     - min_confidence: Minimum confidence threshold (e.g., 0.3 = 30%)
    #     - min_lift: Minimum lift threshold (typically > 1.0)
    #     - test: Print detailed output
    #
    # Returns:
    #     - List of association rules with metrics

    def generate_association_rules(self, min_confidence: float = 0.3, min_lift: float = 1.0, test: bool = True):
        if not self.frequent_item_sets:
            raise ValueError("No frequent item sets.")

        print("STEP 6: GENERATING ASSOCIATION RULES")
        print(f"\nMinimum confidence: {min_confidence} ({min_confidence * 100}%)")
        print(f"Minimum lift: {min_lift}")

        self.association_rules = []
        rules_tested = 0

        # Generate rules from item sets of size >= 2
        for k in range(2, max(self.frequent_item_sets.keys()) + 1):
            if k not in self.frequent_item_sets:
                continue

            if test:
                print(f"\n\tProcessing {k}-itemsets ({len(self.frequent_item_sets[k])} itemsets)")

            for item_set, support_abc in self.frequent_item_sets[k].items():
                items = list(item_set)
                for i in range(1, len(items)):
                    for antecedent_items in combinations(items, i):
                        antecedent = frozenset(antecedent_items)
                        consequent = item_set - antecedent

                        rules_tested += 1
                        support_a = self.frequent_item_sets[len(antecedent)].get(antecedent, 0)
                        support_c = self.frequent_item_sets[len(consequent)].get(consequent, 0)

                        if support_a == 0:
                            continue

                        confidence = support_abc / support_a
                        lift = support_abc / (support_a * support_c) if support_c > 0 else 0

                        if confidence < 1:
                            conviction = (1 - support_c) / (1 - confidence)
                        else:
                            conviction = float('inf')

                        if confidence >= min_confidence and lift >= min_lift:
                            self.association_rules.append({
                                'antecedent': list(antecedent),
                                'consequent': list(consequent),
                                'support': support_abc,
                                'confidence': confidence,
                                'lift': lift,
                                'conviction': conviction
                            })

        # Sort by lift (descending), then confidence (descending)
        self.association_rules.sort(key=lambda x: (x['lift'], x['confidence']), reverse=True)

        if test:
            print(f"ASSOCIATION RULE GENERATION COMPLETE")
            print(f"Total rules tested: {rules_tested}")
            print(f"Rules passing thresholds: {len(self.association_rules)}")
            print(f"Rules filtered out: {rules_tested - len(self.association_rules)}")

        return self.association_rules

    # STEP 7: USE RULES FOR RECOMMENDATIONS
    # 1. Look at what markets the user currently has
    # 2. Find rules where the user has ALL antecedent items
    # 3. Recommend the consequent items (that user doesn't have yet)
    # 4. Rank by lift and confidence
    #
    # Args:
    #     - user_markets: List of markets user currently has positions in
    #     - top_n: Number of recommendations to return
    #     - test: Print detailed output
    #
    # Returns:
    #     - List of recommendations with metrics
    def get_recommendations(self, user_markets: List[str], top_n: int = 5, test: bool = True) -> List[Dict]:
        print("STEP 7: GENERATING RECOMMENDATIONS")
        print(f"\nUser's current markets: {user_markets}")

        recommendations = []
        previous_consequents = set()
        matching_rules = 0

        user_set = set(user_markets)

        for rule in self.association_rules:
            # Check if user has ALL antecedent items
            antecedent_set = set(rule['antecedent'])
            if antecedent_set.issubset(user_set):
                matching_rules += 1

                # Check if consequent is NOT already in user's markets
                consequent_items = set(rule['consequent'])

                if not consequent_items.intersection(user_set):
                    # Add unique recommendations
                    for item in consequent_items:
                        if item not in previous_consequents:
                            recommendations.append({
                                'recommended_market': item,
                                'based_on': rule['antecedent'],
                                'confidence': rule['confidence'],
                                'lift': rule['lift'],
                                'support': rule['support'],
                                'conviction': rule['conviction']
                            })
                            previous_consequents.add(item)

                            if len(recommendations) >= top_n:
                                if test:
                                    print(f"\n✓ Found {len(recommendations)} recommendations")
                                    print(f"  Matched {matching_rules} rules")
                                return recommendations

        if test:
            print(f"\n✅Found {len(recommendations)} recommendations")
            print(f"\tMatched {matching_rules} rules")

            if recommendations:
                print(f"\n📊 TOP RECOMMENDATIONS:")
                for i, rec in enumerate(recommendations, 1):
                    print(f"\n   {i}. {rec['recommended_market']}")
                    print(f"\tBased on: {rec['based_on']}")
                    print(f"\tConfidence: {rec['confidence']:.1%} (probability)")
                    print(f"\tLift: {rec['lift']:.2f}x (correlation strength)")
                    print(f"\tSupport: {rec['support']:.1%} (frequency)")

        return recommendations

    ############################################################################

    def export_rules_to_dataframe(self) -> pd.DataFrame:
        if not self.association_rules:
            return pd.DataFrame()

        df = pd.DataFrame(self.association_rules)
        df['antecedent'] = df['antecedent'].apply(lambda x: ', '.join(x))
        df['consequent'] = df['consequent'].apply(lambda x: ', '.join(x))
        return df

    def print_summary(self):
        print("APRIORI ANALYSIS SUMMARY")
        if self.transactions:
            print(f"\n📦 TRANSACTIONS:")
            print(f"\tTotal: {len(self.transactions)}")
            print(f"\tAvg items: {sum(len(t) for t in self.transactions) / len(self.transactions):.2f}")

        if self.frequent_item_sets:
            print(f"\n🔍 FREQUENT ITEM SETS:")
            total = sum(len(item_sets) for item_sets in self.frequent_item_sets.values())
            print(f"\tTotal: {total}")
            for k, item_sets in sorted(self.frequent_item_sets.items()):
                print(f"\t{k}-item_sets: {len(item_sets)}")

        if self.association_rules:
            print(f"\n📏ASSOCIATION RULES:")
            print(f"\tTotal: {len(self.association_rules)}")

            confidences = [r['confidence'] for r in self.association_rules]
            lifts = [r['lift'] for r in self.association_rules]

            print(f"\tAvg confidence: {sum(confidences) / len(confidences):.3f}")
            print(f"\tAvg lift: {sum(lifts) / len(lifts):.3f}")
            print(f"\tMax lift: {max(lifts):.3f}")

            print(f"\n🏆 TOP 3 RULES (by lift):")
            for i, rule in enumerate(self.association_rules[:3], 1):
                ant = ', '.join(rule['antecedent'][:2])
                cons = ', '.join(rule['consequent'][:1])
                print(f"\t{i}. {ant} → {cons}")
                print(f"\t\tConfidence: {rule['confidence']:.1%}, Lift: {rule['lift']:.2f}")
                print(f"\t\tConfidence: {rule['confidence']:.1%}, Lift: {rule['lift']:.2f}")