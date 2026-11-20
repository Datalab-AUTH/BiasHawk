import pandas as pd
from core.analysis.associations import associations
from core.analysis.thresholds import (
    DISPARATE_IMPACT_MAX,
    DISPARATE_IMPACT_MIN,
    STATISTICAL_PARITY_MAX,
    impact_ok,
    parity_ok,
)
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.preprocessing import LabelEncoder
from itertools import combinations
from pandas.api.types import CategoricalDtype, is_numeric_dtype
import numpy as np  # Added for isnan checks and other numeric ops
import json  # MODIFICATION: Added for JSON export


# A sensitive feature is compared by grouping the rows on its distinct values,
# so a continuous column such as an amount produces roughly one group per row.
# Nothing can be measured inside a group of one: the old behaviour was to emit
# a line of "insufficient data" per value, hundreds of them, and no comparison.
# Such a feature is left out of the group comparisons instead, with a warning.
MAX_GROUP_VALUES = 50
MIN_ROWS_PER_GROUP = 10


def create_warning(test_name, feature, description, severity, data):
    """
    Creates a structured warning object with severity.
    """
    return {
        "test_name": test_name,
        "feature": feature,
        "description": description,
        "severity": severity,
        "data": data
    }


class BiasFairness:
    """Class to perform bias and fairness tests on a dataset."""

    def __init__(self, df, sensitive_features, favorable_outcome, label):
        """
        Initialize BiasFairness.
        Args:
            df (pd.DataFrame): Input dataset.
            sensitive_features (list): List of sensitive attribute column names.
            favorable_outcome (any): Value in the label column considered favorable.
            label (str): Target variable column name.
        """
        self.df = df.copy()  # Work on a copy
        self.sensitive_features = sensitive_features
        self.label = label
        self.favorable_outcome = favorable_outcome

        self.warnings = []
        self.analysis_results = {}  # Centralized storage for analysis results

        # Validate inputs
        if not isinstance(self.df, pd.DataFrame):
            raise ValueError("df must be a pandas DataFrame.")
        if not isinstance(self.sensitive_features, list) or not all(
                isinstance(sf, str) for sf in self.sensitive_features):
            raise ValueError("sensitive_features must be a list of strings.")
        if self.label not in self.df.columns:
            raise ValueError(f"Label column '{self.label}' not found in DataFrame.")
        for sf in self.sensitive_features:
            if sf not in self.df.columns:
                raise ValueError(f"Sensitive feature '{sf}' not found in DataFrame.")

        # Which of them can actually be grouped on, and what the others are.
        self.grouping_features = []
        self.ungroupable_features = {}
        for sf in self.sensitive_features:
            distinct = int(self.df[sf].nunique(dropna=True))
            per_group = (len(self.df) / distinct) if distinct else 0.0
            if distinct > MAX_GROUP_VALUES or per_group < MIN_ROWS_PER_GROUP:
                self.ungroupable_features[sf] = {
                    "distinct_values": distinct,
                    "rows_per_group": round(per_group, 2),
                    "total_rows": int(len(self.df)),
                }
            else:
                self.grouping_features.append(sf)

    def add_warning(self, test_name, feature, description, severity, data):
        warning = create_warning(test_name, feature, description, severity, data)
        self.warnings.append(warning)

    def _warn_ungroupable(self):
        """Say once, per feature, why it is not in the group comparisons."""
        for feature, info in self.ungroupable_features.items():
            self.add_warning(
                "Ungroupable Sensitive Feature",
                feature,
                f"'{feature}' has {info['distinct_values']} distinct values across "
                f"{info['total_rows']} rows, about {info['rows_per_group']} rows per group. "
                f"Groups that small carry no comparable metrics, so this feature is left out "
                f"of the representation, fairness and performance comparisons. It is still "
                f"checked as a proxy and for predictability. Band it into ranges to compare it.",
                "medium",
                info,
            )

    def _generate_combinations(self, min_size=2, max_size=None):
        # Only features that can be grouped on: an intersection with a column
        # of a thousand values is thinner still than the column alone.
        if not self.grouping_features: return []
        if max_size is None: max_size = len(self.grouping_features)
        max_size = min(max_size, len(self.grouping_features))
        min_size = min(min_size, len(self.grouping_features), max_size)
        if min_size < 1: min_size = 1

        all_combinations_tuples = []
        for i in range(min_size, max_size + 1):
            if i > len(self.grouping_features): break
            all_combinations_tuples.extend(combinations(self.grouping_features, i))
        return [list(c) for c in all_combinations_tuples]

    def proxy_identification(self, threshold=0.7):
        df_for_proxy = self.df.copy()

        nominal_columns = []
        for col in df_for_proxy.columns:
            if not is_numeric_dtype(df_for_proxy[col]):
                nominal_columns.append(col)
                df_for_proxy[col] = df_for_proxy[col].astype(str)

        nominal_columns = sorted(list(set(nominal_columns)))
        nominal_columns = [col for col in nominal_columns if col in df_for_proxy.columns]

        try:
            # Removed 'comment=None' argument
            assoc_results = associations(df_for_proxy,
                                         nominal_columns=nominal_columns,
                                         plot=False,
                                         nan_strategy='drop_samples',
                                         compute_only=True,
                                         mark_columns=False)

            if 'corr' not in assoc_results or assoc_results['corr'] is None:
                raise ValueError("associations() did not return a valid 'corr' matrix.")
            assoc_matrix = assoc_results['corr']

        except Exception as e:
            self.add_warning("Proxy Identification", "General", f"Could not compute associations: {e}", "low",
                             {"error_details": str(e)})
            self.analysis_results['proxy_identification'] = {'params': {'threshold': threshold}, 'results': {},
                                                             'error': str(e)}
            return {}

        results_dict = {}
        for feature in self.sensitive_features:
            if feature not in assoc_matrix.columns:
                self.add_warning("Proxy Identification", feature,
                                 f"Sensitive feature '{feature}' not found in associations matrix. Skipping.", "low",
                                 {})
                continue

            correlations_series = assoc_matrix[feature]
            non_sensitive_cols = [col for col in df_for_proxy.columns if col not in self.sensitive_features]
            potential_proxies = correlations_series.loc[correlations_series.index.isin(non_sensitive_cols)].abs()

            # MODIFICATION: Store all correlation values, not just those above the threshold.
            results_dict[feature] = potential_proxies.to_dict()

            # The warning logic remains the same, only flagging high correlations.
            filtered = potential_proxies[potential_proxies > threshold]
            if not filtered.empty:
                self.add_warning("Proxy Identification", feature,
                                 f"High correlation with non-sensitive features exceeds threshold ({threshold}).",
                                 "medium", filtered.to_dict())

        self.analysis_results['proxy_identification'] = {'params': {'threshold': threshold}, 'results': results_dict}
        return results_dict

    def sensitive_predictability(self, threshold=0.5):
        results_dict = {}
        encoded_df = self.df.copy()

        encoders = {}
        for col in encoded_df.columns:
            if not is_numeric_dtype(encoded_df[col]):
                le = LabelEncoder()
                encoded_df[col] = le.fit_transform(encoded_df[col].astype(str))
                encoders[col] = le

        for feature in self.sensitive_features:
            if feature not in encoded_df.columns:
                self.add_warning("Sensitive Predictability", feature, f"Feature '{feature}' not found. Skipping.",
                                 "low", {})
                continue

            y = encoded_df[feature]

            features_to_drop_for_X = [feature]
            features_to_drop_for_X.extend([sf for sf in self.sensitive_features if sf != feature])
            if self.label and self.label not in features_to_drop_for_X:
                features_to_drop_for_X.append(self.label)

            X = encoded_df.drop(columns=list(set(features_to_drop_for_X)), errors='ignore')

            if X.empty:
                self.add_warning("Sensitive Predictability", feature, f"No features left to predict '{feature}'.",
                                 "low", {})
                results_dict[feature] = "Error: No features for X"
                continue
            if y.nunique() < 2:
                self.add_warning("Sensitive Predictability", feature,
                                 f"Not enough unique values to predict for '{feature}'.", "low", {})
                results_dict[feature] = "Error: y has < 2 unique values"
                continue

            try:
                stratify_y = y if y.nunique() >= 2 and all(y.value_counts() >= 2) else None
                X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42,
                                                                    stratify=stratify_y)

                if X_train.empty or X_test.empty:
                    self.add_warning("Sensitive Predictability", feature, f"Train or test set empty for '{feature}'.",
                                     "low", {})
                    results_dict[feature] = "Error: Empty train/test split"
                    continue
                model = RandomForestClassifier(random_state=42)
                model.fit(X_train, y_train)
                accuracy = round(accuracy_score(y_test, model.predict(X_test)), 2)
                results_dict[feature] = accuracy
                if accuracy > threshold:
                    self.add_warning("Sensitive Predictability", feature,
                                     f"Highly predictable (accuracy={accuracy:.2f}, threshold={threshold}).",
                                     "high", {"accuracy": accuracy})
            except Exception as e:
                self.add_warning("Sensitive Predictability", feature, f"Error predicting '{feature}': {e}", "low",
                                 {"error": str(e)})
                results_dict[feature] = f"Error: {str(e)}"

        self.analysis_results['sensitive_predictability'] = {'params': {'threshold': threshold},
                                                             'results': results_dict}
        return results_dict

    def _perform_discrimination_analysis(self, group_by_features, disparity_threshold, is_intersectional=False):
        if not self.label:
            raise ValueError("Target label must be provided.")

        results_container = {}
        encoded_df_model = self.df.copy()

        encoders = {}
        for col in encoded_df_model.columns:
            if not is_numeric_dtype(encoded_df_model[col]):
                le = LabelEncoder()
                encoded_df_model[col] = le.fit_transform(encoded_df_model[col].astype(str))
                encoders[col] = le

        if not pd.api.types.is_numeric_dtype(encoded_df_model[self.label]):
            if self.label not in encoders:
                le_label = LabelEncoder()
                encoded_df_model[self.label] = le_label.fit_transform(encoded_df_model[self.label].astype(str))
                encoders[self.label] = le_label

        group_name_prefix = "_&_".join(group_by_features) if is_intersectional else group_by_features[0]

        interaction_col_name = None
        if is_intersectional:
            if not group_by_features or not all(feat in self.df.columns for feat in group_by_features):
                self.add_warning(f"{'Intersectional ' if is_intersectional else ''}Performance Discrimination",
                                 group_name_prefix, f"One or more features in {group_by_features} not found.", "low",
                                 {})
                return {"error": "Invalid group_by_features"}

            interaction_col_name = "__temp_interaction_group__"
            encoded_df_model[interaction_col_name] = self.df[group_by_features].apply(
                lambda row: '_&_'.join(row.astype(str)), axis=1)
            unique_groups_iter = encoded_df_model[interaction_col_name].unique()
            loop_feature_for_masking = interaction_col_name
        else:
            feature = group_by_features[0]
            if feature not in self.df.columns:
                self.add_warning("Performance Discrimination", feature, f"Feature '{feature}' not found.", "low", {})
                return {"error": f"Feature '{feature}' not found"}
            unique_groups_iter = self.df[feature].unique()
            loop_feature_for_masking = feature

        group_performances = {}
        for group_value_iter in unique_groups_iter:
            if is_intersectional:
                subset_mask = (encoded_df_model[loop_feature_for_masking] == group_value_iter)
                group_value_display_name = group_value_iter
            else:
                subset_mask = (self.df[loop_feature_for_masking] == group_value_iter)
                group_value_display_name = str(group_value_iter)

            subset_for_model = encoded_df_model[subset_mask]

            if subset_for_model.empty or subset_for_model[self.label].nunique() < 2 or len(subset_for_model) < 10:
                group_performances[group_value_display_name] = None
                continue

            cols_to_drop_X = self.sensitive_features + [self.label]
            if is_intersectional and interaction_col_name:
                cols_to_drop_X.append(interaction_col_name)

            X = subset_for_model.drop(columns=list(set(cols_to_drop_X)), errors='ignore')
            y = subset_for_model[self.label]

            if X.empty:
                group_performances[group_value_display_name] = None
                continue

            try:
                can_stratify = y.nunique() >= 2 and all(y.value_counts() >= (2 if len(y) * 0.3 >= 2 else 1))

                X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42,
                                                                    stratify=y if can_stratify else None)

                if X_train.empty or X_test.empty or y_train.nunique() < 1 or (y_test.nunique() < 1 and len(y_test) > 0):
                    group_performances[group_value_display_name] = None
                    continue

                if len(y_test) == 0:
                    group_performances[group_value_display_name] = 0.0
                    continue

                model = RandomForestClassifier(random_state=42)
                model.fit(X_train, y_train)
                y_pred = model.predict(X_test)
                f1 = round(f1_score(y_test, y_pred, average='weighted', zero_division=0), 2)
                group_performances[group_value_display_name] = f1
            except ValueError as e:
                group_performances[group_value_display_name] = None
                self.add_warning(f"{'Intersectional ' if is_intersectional else ''}Performance Discrimination",
                                 group_name_prefix,
                                 f"Error training model for subgroup '{group_value_display_name}': {e}", "low",
                                 {"subgroup": group_value_display_name, "error": str(e)})

        results_container[group_name_prefix] = group_performances

        valid_scores = [s for s in group_performances.values() if
                        s is not None and not (isinstance(s, float) and np.isnan(s))]
        if len(valid_scores) > 1:
            max_score, min_score = max(valid_scores), min(valid_scores)
            disparity = round(max_score - min_score, 2)
            if disparity > disparity_threshold:
                self.add_warning(f"{'Intersectional ' if is_intersectional else ''}Performance Discrimination",
                                 group_name_prefix,
                                 f"Performance disparity ({disparity:.2f}) exceeds threshold ({disparity_threshold}).",
                                 "high",
                                 {"disparity": disparity, "max_score": max_score, "min_score": min_score,
                                  "scores": group_performances})

        if is_intersectional and interaction_col_name and interaction_col_name in encoded_df_model.columns:
            del encoded_df_model[interaction_col_name]

        return results_container

    def performance_discrimination(self, disparity_threshold=0.2):
        all_feature_results = {}
        for feature in self.grouping_features:
            result = self._perform_discrimination_analysis(group_by_features=[feature],
                                                           disparity_threshold=disparity_threshold,
                                                           is_intersectional=False)
            all_feature_results.update(result)
        self.analysis_results['performance_discrimination'] = {'params': {'disparity_threshold': disparity_threshold},
                                                               'results': all_feature_results}
        return all_feature_results

    def intersectional_performance_discrimination(self, disparity_threshold=0.2, combination_level=2):
        if len(self.grouping_features) < combination_level or combination_level < 2:
            msg = f"Skipping: Not enough sensitive features ({len(self.grouping_features)}) for combination_level={combination_level}."
            self.add_warning("Intersectional Performance Discrimination", f"Level {combination_level}", msg, "low", {})
            self.analysis_results['intersectional_performance_discrimination'] = {
                'params': {'disparity_threshold': disparity_threshold, 'combination_level': combination_level},
                'results': {}, 'skipped_reason': msg}
            return {}

        feature_combinations = self._generate_combinations(min_size=combination_level, max_size=combination_level)
        all_combo_results = {}
        for combo in feature_combinations:
            result = self._perform_discrimination_analysis(group_by_features=combo,
                                                           disparity_threshold=disparity_threshold,
                                                           is_intersectional=True)
            all_combo_results.update(result)

        self.analysis_results['intersectional_performance_discrimination'] = {
            'params': {'disparity_threshold': disparity_threshold, 'combination_level': combination_level},
            'results': all_combo_results
        }
        return all_combo_results

    def _perform_representativity_analysis(self, group_by_features, min_pct, is_intersectional=False):
        results_container = {}
        group_name_prefix = "_&_".join(group_by_features) if is_intersectional else group_by_features[0]

        try:
            if is_intersectional:
                if not group_by_features or not all(feat in self.df.columns for feat in group_by_features):
                    self.add_warning(f"{'Intersectional ' if is_intersectional else ''}Sensitive Representativity",
                                     group_name_prefix, f"One or more features in {group_by_features} not found.",
                                     "low", {})
                    return {"error": "Invalid group_by_features"}
                group_counts_abs = self.df.groupby(group_by_features, observed=True).size()
            else:
                feature = group_by_features[0]
                if feature not in self.df.columns:
                    self.add_warning("Sensitive Representativity", feature, f"Feature '{feature}' not found.", "low",
                                     {})
                    return {"error": f"Feature '{feature}' not found"}
                group_counts_abs = self.df[feature].value_counts()

            if group_counts_abs.empty:
                results_container[group_name_prefix] = {}
                return results_container

            group_counts_pct = group_counts_abs / len(self.df)

            # MODIFICATION: Store representation for ALL groups, not just underrepresented ones.
            all_groups_representation = {}
            for group_val, pct in group_counts_pct.items():
                group_val_str = "_&_".join(map(str, group_val)) if isinstance(group_val, tuple) else str(group_val)
                actual_count = group_counts_abs.loc[group_val]
                all_groups_representation[group_val_str] = {"percentage": round(pct, 4), "count": int(actual_count)}
                
                # Still add warnings for underrepresented groups
                if pct < min_pct:
                    self.add_warning(f"{'Intersectional ' if is_intersectional else ''}Sensitive Representativity",
                                     group_name_prefix,
                                     f"Group '{group_val_str}' is underrepresented ({pct:.2%}, count: {actual_count}).",
                                     "medium",
                                     {"group": group_val_str, "percentage": round(pct, 4), "count": int(actual_count)})

            results_container[group_name_prefix] = all_groups_representation
        except Exception as e:
            self.add_warning(f"{'Intersectional ' if is_intersectional else ''}Sensitive Representativity",
                             group_name_prefix, f"Error calculating representativity: {str(e)}", "low",
                             {"error": str(e)})
            results_container[group_name_prefix] = {"error": str(e)}
        return results_container

    def sensitive_representativity(self, min_pct=0.01):
        all_feature_results = {}
        for feature in self.grouping_features:
            result = self._perform_representativity_analysis(group_by_features=[feature],
                                                             min_pct=min_pct,
                                                             is_intersectional=False)
            all_feature_results.update(result)
        self.analysis_results['sensitive_representativity'] = {'params': {'min_pct': min_pct},
                                                               'results': all_feature_results}
        return all_feature_results

    def intersectional_sensitive_representativity(self, min_pct=0.01, combination_level=2):
        if len(self.grouping_features) < combination_level or combination_level < 2:
            msg = f"Skipping: Not enough sensitive features ({len(self.grouping_features)}) for combination_level={combination_level}."
            self.add_warning("Intersectional Sensitive Representativity", f"Level {combination_level}", msg, "low", {})
            self.analysis_results['intersectional_sensitive_representativity'] = {
                'params': {'min_pct': min_pct, 'combination_level': combination_level}, 'results': {},
                'skipped_reason': msg}
            return {}

        feature_combinations = self._generate_combinations(min_size=combination_level, max_size=combination_level)
        all_combo_results = {}
        for combo in feature_combinations:
            result = self._perform_representativity_analysis(group_by_features=combo,
                                                             min_pct=min_pct,
                                                             is_intersectional=True)
            all_combo_results.update(result)

        self.analysis_results['intersectional_sensitive_representativity'] = {
            'params': {'min_pct': min_pct, 'combination_level': combination_level},
            'results': all_combo_results
        }
        return all_combo_results

    def _perform_fairness_metrics_analysis(self, group_by_features, parity_threshold, impact_threshold, prob_threshold,
                                           is_intersectional=False, impact_upper_threshold=DISPARATE_IMPACT_MAX):
        if not self.label: raise ValueError("Target label must be provided.")
        results_container = {}
        group_name_prefix = "_&_".join(group_by_features) if is_intersectional else group_by_features[0]

        try:
            if is_intersectional:
                if not group_by_features or not all(feat in self.df.columns for feat in group_by_features):
                    self.add_warning(f"{'Intersectional ' if is_intersectional else ''}Fairness Metrics",
                                     group_name_prefix, f"One or more features in {group_by_features} not found.",
                                     "low", {})
                    return {group_name_prefix: {"error": "Invalid group_by_features"}}
                group_val_counts = self.df.groupby(group_by_features, observed=True)[self.label].value_counts(
                    normalize=True)
            else:
                feature = group_by_features[0]
                if feature not in self.df.columns:
                    self.add_warning("Fairness Metrics", feature, f"Feature '{feature}' not found.", "low", {})
                    return {feature: {"error": f"Feature '{feature}' not found"}}
                group_val_counts = self.df.groupby(feature, observed=True)[self.label].value_counts(normalize=True)

            if group_val_counts.empty:
                results_container[group_name_prefix] = {"error": "No data after grouping."}
                return results_container

            favorable_probs_unstacked = group_val_counts.unstack(fill_value=0)

            if self.favorable_outcome not in favorable_probs_unstacked.columns:
                self.add_warning(f"{'Intersectional ' if is_intersectional else ''}Fairness Metrics", group_name_prefix,
                                 f"Favorable outcome '{self.favorable_outcome}' not found in target variable '{self.label}' for any group. All favorable probabilities are 0.",
                                 "medium", {})
                favorable_probs = pd.Series(0.0, index=favorable_probs_unstacked.index)
            else:
                favorable_probs = favorable_probs_unstacked[self.favorable_outcome]

            if favorable_probs.empty:
                results_container[group_name_prefix] = {"error": "Favorable probabilities series is empty."}
                return results_container

            min_prob, max_prob = favorable_probs.min(), favorable_probs.max()
            stat_parity = round(max_prob - min_prob, 2)

            if max_prob == 0:
                disp_impact = 1.0
            elif min_prob == 0:
                disp_impact = 0.0
            else:
                disp_impact = round(min_prob / max_prob, 2)

            metrics = {
                "Statistical Parity": stat_parity,
                "Disparate Impact Ratio": disp_impact,
                "Favorable Probabilities": {("_&_".join(map(str, k)) if isinstance(k, tuple) else str(k)): round(v, 2)
                                            for k, v in favorable_probs.to_dict().items()}
            }
            results_container[group_name_prefix] = metrics

            # SP <= parity_threshold is acceptable; above it is a problem.
            if not parity_ok(stat_parity, parity_threshold):
                self.add_warning(f"{'Intersectional ' if is_intersectional else ''}Fairness Metrics", group_name_prefix,
                                 f"Statistical Parity ({stat_parity:.2f}) exceeds threshold ({parity_threshold}).",
                                 "medium",
                                 {"Statistical Parity": stat_parity, "threshold": parity_threshold})
            # DI is acceptable inside [impact_threshold, impact_upper_threshold].
            if not impact_ok(disp_impact, impact_threshold, impact_upper_threshold):
                self.add_warning(f"{'Intersectional ' if is_intersectional else ''}Fairness Metrics", group_name_prefix,
                                 f"Disparate Impact Ratio ({disp_impact:.2f}) is outside the acceptable range "
                                 f"({impact_threshold} to {impact_upper_threshold}).",
                                 "high",
                                 {"Disparate Impact Ratio": disp_impact, "threshold": impact_threshold,
                                  "upper_threshold": impact_upper_threshold})
            # Compared on the same rounded value as Statistical Parity, so the two
            # checks cannot disagree at the boundary (a 0.104 gap is SP 0.10: fine).
            if stat_parity > prob_threshold:
                self.add_warning(f"{'Intersectional ' if is_intersectional else ''}Fairness Metrics", group_name_prefix,
                                 f"Favorable Probabilities difference ({stat_parity:.2f}) exceeds threshold ({prob_threshold}).",
                                 "medium",
                                 {"prob_difference": stat_parity, "threshold": prob_threshold,
                                  "probabilities": metrics["Favorable Probabilities"]})
        except Exception as e:
            self.add_warning(f"{'Intersectional ' if is_intersectional else ''}Fairness Metrics", group_name_prefix,
                             f"Error calculating metrics: {str(e)}", "low", {"error": str(e)})
            results_container[group_name_prefix] = {"error": str(e)}
        return results_container

    def fairness_metrics(self, parity_threshold=STATISTICAL_PARITY_MAX, impact_threshold=DISPARATE_IMPACT_MIN,
                         prob_threshold=STATISTICAL_PARITY_MAX, impact_upper_threshold=DISPARATE_IMPACT_MAX):
        all_feature_results = {}
        for feature in self.grouping_features:
            result = self._perform_fairness_metrics_analysis(group_by_features=[feature],
                                                             parity_threshold=parity_threshold,
                                                             impact_threshold=impact_threshold,
                                                             prob_threshold=prob_threshold,
                                                             is_intersectional=False,
                                                             impact_upper_threshold=impact_upper_threshold)
            all_feature_results.update(result)
        self.analysis_results['fairness_metrics'] = {
            'params': {'parity_threshold': parity_threshold, 'impact_threshold': impact_threshold,
                       'impact_upper_threshold': impact_upper_threshold,
                       'prob_threshold': prob_threshold}, 'results': all_feature_results}
        return all_feature_results

    def intersectional_fairness_metrics(self, parity_threshold=STATISTICAL_PARITY_MAX,
                                        impact_threshold=DISPARATE_IMPACT_MIN,
                                        prob_threshold=STATISTICAL_PARITY_MAX, combination_level=2,
                                        impact_upper_threshold=DISPARATE_IMPACT_MAX):
        if len(self.grouping_features) < combination_level or combination_level < 2:
            msg = f"Skipping: Not enough sensitive features ({len(self.grouping_features)}) for combination_level={combination_level}."
            self.add_warning("Intersectional Fairness Metrics", f"Level {combination_level}", msg, "low", {})
            self.analysis_results['intersectional_fairness_metrics'] = {
                'params': {'parity_threshold': parity_threshold, 'impact_threshold': impact_threshold,
                           'impact_upper_threshold': impact_upper_threshold,
                           'prob_threshold': prob_threshold, 'combination_level': combination_level}, 'results': {},
                'skipped_reason': msg}
            return {}

        feature_combinations = self._generate_combinations(min_size=combination_level, max_size=combination_level)
        all_combo_results = {}
        for combo in feature_combinations:
            result = self._perform_fairness_metrics_analysis(group_by_features=combo,
                                                             parity_threshold=parity_threshold,
                                                             impact_threshold=impact_threshold,
                                                             prob_threshold=prob_threshold,
                                                             is_intersectional=True,
                                                             impact_upper_threshold=impact_upper_threshold)
            all_combo_results.update(result)

        self.analysis_results['intersectional_fairness_metrics'] = {
            'params': {'parity_threshold': parity_threshold, 'impact_threshold': impact_threshold,
                       'impact_upper_threshold': impact_upper_threshold,
                       'prob_threshold': prob_threshold, 'combination_level': combination_level},
            'results': all_combo_results
        }
        return all_combo_results

    def run_all_analyses(self,
                         proxy_threshold=0.7,
                         predictability_threshold=0.5,
                         perf_discr_threshold=0.2,
                         repr_min_pct=0.01,
                         fm_parity_threshold=STATISTICAL_PARITY_MAX, fm_impact_threshold=DISPARATE_IMPACT_MIN,
                         fm_prob_threshold=STATISTICAL_PARITY_MAX, fm_impact_upper_threshold=DISPARATE_IMPACT_MAX,
                         # Intersectional params (can be same or different)
                         int_perf_discr_threshold=0.2,
                         int_repr_min_pct=0.01,
                         int_fm_parity_threshold=STATISTICAL_PARITY_MAX, int_fm_impact_threshold=DISPARATE_IMPACT_MIN,
                         int_fm_prob_threshold=STATISTICAL_PARITY_MAX,
                         int_fm_impact_upper_threshold=DISPARATE_IMPACT_MAX,
                         combination_level=2):
        """Runs all analyses with specified parameters and stores results."""
        self.warnings = []
        self.analysis_results = {}
        self._warn_ungroupable()

        print("Running Proxy Identification...")
        self.proxy_identification(threshold=proxy_threshold)
        print("Running Sensitive Feature Predictability...")
        self.sensitive_predictability(threshold=predictability_threshold)
        print("Running Performance Discrimination (Single Feature)...")
        self.performance_discrimination(disparity_threshold=perf_discr_threshold)
        print("Running Sensitive Feature Representativity...")
        self.sensitive_representativity(min_pct=repr_min_pct)
        print("Running Fairness Metrics (Single Feature)...")
        self.fairness_metrics(parity_threshold=fm_parity_threshold,
                              impact_threshold=fm_impact_threshold,
                              prob_threshold=fm_prob_threshold,
                              impact_upper_threshold=fm_impact_upper_threshold)

        if len(self.grouping_features) >= combination_level and combination_level >= 2:
            print(f"Running Intersectional Analyses (Level {combination_level})...")
            self.intersectional_performance_discrimination(disparity_threshold=int_perf_discr_threshold,
                                                           combination_level=combination_level)
            self.intersectional_sensitive_representativity(min_pct=int_repr_min_pct,
                                                           combination_level=combination_level)
            self.intersectional_fairness_metrics(parity_threshold=int_fm_parity_threshold,
                                                 impact_threshold=int_fm_impact_threshold,
                                                 prob_threshold=int_fm_prob_threshold,
                                                 combination_level=combination_level,
                                                 impact_upper_threshold=int_fm_impact_upper_threshold)
        else:
            msg = f"Skipping intersectional analyses: not enough sensitive features ({len(self.grouping_features)}) for combination_level={combination_level} or combination_level < 2."
            print(msg)
            placeholder_params_int = {'combination_level': combination_level}
            self.analysis_results['intersectional_performance_discrimination'] = {
                'params': {**placeholder_params_int, 'disparity_threshold': int_perf_discr_threshold}, 'results': {},
                'skipped_reason': msg}
            self.analysis_results['intersectional_sensitive_representativity'] = {
                'params': {**placeholder_params_int, 'min_pct': int_repr_min_pct}, 'results': {}, 'skipped_reason': msg}
            self.analysis_results['intersectional_fairness_metrics'] = {
                'params': {**placeholder_params_int, 'parity_threshold': int_fm_parity_threshold,
                           'impact_threshold': int_fm_impact_threshold,
                           'impact_upper_threshold': int_fm_impact_upper_threshold,
                           'prob_threshold': int_fm_prob_threshold},
                'results': {}, 'skipped_reason': msg}

        print(f"\nAll analyses run. {len(self.warnings)} warnings collected. Results stored in self.analysis_results.")
        return self.analysis_results

    def get_all_warnings(self):
        return self.warnings

    def generate_summary(self):
        """Generates a string summary of the analysis results."""
        if not self.analysis_results:
            return "No analysis results found. Please run analyses first (e.g., using `run_all_analyses()`)."

        summary_lines = ["Bias and Fairness Analysis Summary:", "---"]

        analysis_order = [
            "proxy_identification", "sensitive_predictability",
            "performance_discrimination", "sensitive_representativity", "fairness_metrics",
            "intersectional_performance_discrimination", "intersectional_sensitive_representativity",
            "intersectional_fairness_metrics"
        ]
        for analysis_name in analysis_order:
            if analysis_name not in self.analysis_results: continue

            data = self.analysis_results[analysis_name]
            params_str = ", ".join([f"{k}={v}" for k, v in data.get('params', {}).items()])
            summary_lines.append(
                f"\n* {analysis_name.replace('_', ' ').title()} (Params: {params_str if params_str else 'Defaults'})")
            if data.get('skipped_reason'):
                summary_lines.append(f"  - Skipped: {data['skipped_reason']}")
            elif data.get('error'):
                summary_lines.append(f"  - Error: {data['error']}")
            elif not data.get('results'):
                summary_lines.append("  - No specific findings or all values within thresholds.")
            else:
                results_preview = data['results']
                if isinstance(results_preview, dict) and results_preview:
                    preview_keys = list(results_preview.keys())
                    summary_lines.append(
                        f"  - Findings for features/groups: {', '.join(preview_keys[:3])}{'...' if len(preview_keys) > 3 else ''}")
                elif results_preview:
                    summary_lines.append(f"  - Results: {str(results_preview)[:100]}...")

        summary_lines.append(f"\n---\nTotal Warnings Generated: {len(self.warnings)}")
        return "\n".join(summary_lines)

    def generate_metrics_report_markdown(self):
        """Generates a detailed Markdown report of all analysis metrics."""
        markdown = "# Bias and Fairness Metrics Report\n\n"
        if not self.analysis_results:
            markdown += "No analysis results found. Please run analyses first (e.g., using `run_all_analyses()`).\n"
            return markdown

        if self.ungroupable_features:
            markdown += "## Features Excluded From Group Comparisons\n"
            for feature, info in self.ungroupable_features.items():
                markdown += (
                    f"- `{feature}`: {info['distinct_values']} distinct values across "
                    f"{info['total_rows']} rows, about {info['rows_per_group']} rows per group. "
                    "Too few rows per group to compare, so it is not broken down below. "
                    "Band it into ranges to measure it; it is still checked as a proxy and "
                    "for predictability." + "\n"
                )
            markdown += "\n"

        analysis_order = [
            "proxy_identification", "sensitive_predictability",
            "performance_discrimination", "sensitive_representativity", "fairness_metrics",
            "intersectional_performance_discrimination", "intersectional_sensitive_representativity",
            "intersectional_fairness_metrics"
        ]

        for analysis_key in analysis_order:
            if analysis_key not in self.analysis_results: continue

            data = self.analysis_results[analysis_key]
            title = analysis_key.replace("_", " ").title()
            markdown += f"## {title}\n"

            params_info = ", ".join([f"`{k}`=`{v}`" for k, v in data.get('params', {}).items()])
            markdown += f"_Parameters used: {params_info}_\n\n" if params_info else "\n"

            if data.get('skipped_reason'):
                markdown += f"_{data['skipped_reason']}_\n\n"
                continue
            if data.get('error') and not data.get('results'):
                markdown += f"_Error during analysis: {data['error']}_\n\n"
                continue

            results_content = data.get('results', {})
            if not results_content and not data.get('error'):
                markdown += "_No specific findings or all values within thresholds/parameters._\n\n"
                continue
            if data.get('error') and results_content:
                markdown += f"_Note: There might have been errors for specific items (see below or warnings report). General error for analysis: {data['error']}_\n\n"

            for feature_or_group_name, metrics_or_values in results_content.items():
                markdown += f"### Feature/Group: `{feature_or_group_name}`\n"

                if isinstance(metrics_or_values, str) and "Error:" in metrics_or_values:
                    markdown += f"- {metrics_or_values}\n"
                    continue
                if isinstance(metrics_or_values, dict) and "error" in metrics_or_values:
                    markdown += f"- Error: `{metrics_or_values['error']}`\n"
                    continue

                if analysis_key == "proxy_identification":
                    if isinstance(metrics_or_values, dict):
                        markdown += "  - Potential Proxy Features (Correlation > Threshold):\n"
                        for proxy_feat, corr_val in metrics_or_values.items():
                            markdown += f"    - `{proxy_feat}`: Correlation `{corr_val:.2f}`\n"
                elif analysis_key == "sensitive_predictability":
                    markdown += f"  - Predictability Score (Accuracy): `{metrics_or_values}`\n"
                elif "fairness_metrics" in analysis_key:
                    if isinstance(metrics_or_values, dict):
                        markdown += f"  - Statistical Parity: `{metrics_or_values.get('Statistical Parity', 'N/A')}`\n"
                        markdown += f"  - Disparate Impact Ratio: `{metrics_or_values.get('Disparate Impact Ratio', 'N/A')}`\n"
                        markdown += "  - Favorable Probabilities:\n"
                        for subgroup, prob in metrics_or_values.get("Favorable Probabilities", {}).items():
                            markdown += f"    - `{subgroup}`: `{prob}`\n"
                elif "representativity" in analysis_key:
                    if isinstance(metrics_or_values, dict) and metrics_or_values:
                        markdown += "  - Underrepresented Groups/Values (Percentage < Min Pct & Count):\n"
                        for grp_str, rep_data in metrics_or_values.items():
                            markdown += f"    - Group `{grp_str}`: Percentage `{rep_data['percentage']:.2%}`, Count `{rep_data['count']}`\n"
                    elif not metrics_or_values:
                        markdown += "  - All subgroups are adequately represented for this feature/group.\n"
                elif "performance_discrimination" in analysis_key:
                    if isinstance(metrics_or_values, dict):
                        markdown += "  - Subgroup F1-Scores:\n"
                        valid_scores = []
                        for subgroup, score in metrics_or_values.items():
                            score_display = f"`{score}`" if score is not None else "`N/A (e.g., insufficient data)`"
                            markdown += f"    - `{subgroup}`: {score_display}\n"
                            if score is not None and not (isinstance(score, float) and np.isnan(score)):
                                valid_scores.append(score)
                        if len(valid_scores) > 1:
                            disparity = round(max(valid_scores) - min(valid_scores), 2)
                            markdown += f"  - *Performance Disparity (Max - Min F1)*: `{disparity:.2f}`\n"
                        elif valid_scores:
                            markdown += f"  - *Only one valid subgroup score available for disparity calculation.*\n"
                        else:
                            markdown += "  - *No valid scores to calculate disparity for this feature/group.*\n"
                else:
                    markdown += f"  - Data: `{str(metrics_or_values)}`\n"
            markdown += "\n"
        return markdown

    def generate_warnings_report_markdown(self):
        """Generates a Markdown report of all collected warnings."""
        markdown = "# Bias and Fairness Warnings Report\n\n"
        if not self.warnings:
            markdown += "No warnings generated.\n"
            return markdown

        markdown += f"Total warnings: {len(self.warnings)}\n\n---\n"
        for idx, warning in enumerate(self.warnings):
            markdown += f"\n## Warning {idx + 1}: {warning['test_name']}\n"
            markdown += f"- **Concerned Feature/Group**: `{warning['feature']}`\n"
            markdown += f"- **Severity**: `{warning['severity']}`\n"
            markdown += f"- **Description**: {warning['description']}\n"
            if warning['data']:
                markdown += "- **Details**:\n"
                for key, value in warning['data'].items():
                    if isinstance(value, dict):
                        md_val = "\n" + "\n".join([f"    - `{dk}`: `{dv}`" for dk, dv in value.items()])
                        markdown += f"  - `{key}`: {md_val}\n"
                    elif isinstance(value, list):
                        md_val = ", ".join([f"`{item}`" for item in value])
                        markdown += f"  - `{key}`: [{md_val}]\n"
                    else:
                        markdown += f"  - `{key}`: `{value}`\n"
            markdown += "\n---\n"
        return markdown


def perform_bias_assessment(df, sensitive_features, favorable_outcome=None, label=None, **kwargs):
    """
    Perform bias assessment on a CSV file from URL.
    
    Args:
        df (pd.DataFrame): The dataset
        sensitive_features (list): List of sensitive feature column names
        favorable_outcome (any, optional): Value in the label column considered favorable
        label (str, optional): Target variable column name
        **kwargs: Additional parameters for analysis methods
        
    Returns:
        dict: Analysis results containing bias assessment data
    """
    try:
        
        if label is None:
            raise ValueError("No target label column found. Please specify the 'label' parameter.")
        
        if favorable_outcome is None :
            raise ValueError("No favorable outcome specified. Please provide the 'favorable_outcome' parameter.")
        
        bf_analyzer = BiasFairness(
            df=df,
            sensitive_features=sensitive_features,
            favorable_outcome=favorable_outcome,
            label=label
        )
        
        analysis_results = bf_analyzer.run_all_analyses()
        
        summary_text = bf_analyzer.generate_summary()
        metrics_report = bf_analyzer.generate_metrics_report_markdown()
        warnings_report = bf_analyzer.generate_warnings_report_markdown()
        warnings_list = bf_analyzer.get_all_warnings()
        
            
        return {
            'success': True,
            'analysis_results': analysis_results,
            'summary': summary_text,
            'metrics_report': metrics_report,
            'warnings_report': warnings_report,
            'warnings': warnings_list,
            'metadata': {
                'dataset_shape': df.shape,
                'sensitive_features': sensitive_features,
                'label': label,
                'favorable_outcome': favorable_outcome,
            }
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__
        }
