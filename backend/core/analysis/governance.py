# --- START OF FILE Data_Describer.py ---

import pandas as pd
import numpy as np  # Import numpy for datetime dtype checking

class DataDescriber:
    """
    Class to generate a detailed Markdown summary report for a dataset.
    """

    def __init__(self, df):
        """
        Initialize DataDescriber with a dataset.
        Args:
            df (pd.DataFrame): The dataset to describe.
        """
        if not isinstance(df, pd.DataFrame):
            raise ValueError("Input must be a pandas DataFrame.")
        # Work on a copy to avoid modifying the original DataFrame
        self.df = df.copy()

    def _format_memory(self, byte_size):
        """Helper to format memory size."""
        if byte_size < 1024:
            return f"{byte_size} Bytes"
        elif byte_size < 1024**2:
            return f"{byte_size/1024:.2f} KB"
        elif byte_size < 1024**3:
            return f"{byte_size/1024**2:.2f} MB"
        else:
            return f"{byte_size/1024**3:.2f} GB"

    def generate_summary_markdown(self):
        """
        Generate a Markdown summary report for the dataset with improved formatting
        and additional details.
        Returns:
            str: The summary report in Markdown format.
        """
        if self.df.empty:
            return "## Dataset Description\n\n- The provided DataFrame is empty."

        report = []

        # --- General Information ---
        report.append("## 1. General Dataset Information")
        report.append(f"- **Number of Rows:** {self.df.shape[0]}")
        report.append(f"- **Number of Columns:** {self.df.shape[1]}")
        # Calculate memory usage
        try:
            mem_usage = self.df.memory_usage(deep=True).sum()
            report.append(f"- **Total Memory Usage:** {self._format_memory(mem_usage)}")
        except Exception:
            report.append("- **Total Memory Usage:** Could not be calculated.")
        # Duplicate rows
        duplicate_count = self.df.duplicated().sum()
        report.append(f"- **Duplicate Rows:** {duplicate_count} ({duplicate_count / self.df.shape[0]:.2%} of total)")
        report.append("---")

        # --- Data Types Summary ---
        report.append("\n## 2. Data Types Overview")
        dtype_counts = self.df.dtypes.value_counts()
        numeric_types = self.df.select_dtypes(include=np.number).shape[1]
        datetime_types = self.df.select_dtypes(include=np.datetime64).shape[1]
        # Count object and category separately for more clarity if needed
        object_types = self.df.select_dtypes(include=['object', 'string']).shape[1]
        category_types = self.df.select_dtypes(include=['category']).shape[1]
        bool_types = self.df.select_dtypes(include=['bool']).shape[1]
        other_types = self.df.shape[1] - (numeric_types + datetime_types + object_types + category_types + bool_types)

        report.append("- **Column Type Counts:**")
        if numeric_types > 0: report.append(f"  - **Numeric:** {numeric_types}")
        if object_types > 0: report.append(f"  - **Object (Text/Mixed):** {object_types}")
        if category_types > 0: report.append(f"  - **Category:** {category_types}")
        if datetime_types > 0: report.append(f"  - **Datetime:** {datetime_types}")
        if bool_types > 0: report.append(f"  - **Boolean:** {bool_types}")
        if other_types > 0: report.append(f"  - **Other Specific Types:** {other_types}") # e.g., timedelta

        report.append("\n- **Specific Data Types per Column:**")
        for column, dtype in self.df.dtypes.items():
            report.append(f"  - **{column}:** `{dtype}`")
        report.append("---")


        # --- Missing Data ---
        report.append("\n## 3. Missing Data")
        missing_data = self.df.isnull().sum()
        missing_cols = missing_data[missing_data > 0]
        if missing_cols.empty:
            report.append("- **No missing data found.**")
        else:
            report.append("- **Columns with missing data:**")
            # Sort by percentage missing, descending
            missing_cols_pct = (missing_cols / self.df.shape[0]) * 100
            for column, count in missing_cols.sort_values(ascending=False).items():
                report.append(f"  - **{column}:** {count} missing values ({missing_cols_pct[column]:.2f}%)")
        report.append("---")

        # --- Unique Values ---
        report.append("\n## 4. Unique Values Per Column")
        unique_counts = self.df.nunique()
        report.append("- **Unique value counts:**")
        # Sort by number of unique values, ascending (useful for finding constants/low cardinality)
        for column, count in unique_counts.sort_values(ascending=True).items():
            variability_ratio = count / self.df.shape[0] if self.df.shape[0] > 0 else 0
            report.append(f"  - **{column}:** {count} unique values (Variability ratio: {variability_ratio:.2%})")
        report.append("---")

        # --- Statistical Summary (Numeric Columns) ---
        report.append("\n## 5. Statistical Summary (Numeric Columns)")
        numeric_df = self.df.select_dtypes(include=np.number)
        if numeric_df.empty:
             report.append("- **No numeric columns found.**")
        else:
            try:
                numeric_summary = numeric_df.describe().round(2) # Round for cleaner output
                report.append("- **Summary statistics:**")
                for column in numeric_summary.columns:
                    stats = numeric_summary[column]
                    report.append(f"  - **`{column}`:**")
                    report.append(f"    - Count: {stats.get('count', 'N/A')}")
                    report.append(f"    - Mean: {stats.get('mean', 'N/A')}")
                    report.append(f"    - Std Dev: {stats.get('std', 'N/A')}")
                    report.append(f"    - Min: {stats.get('min', 'N/A')}")
                    report.append(f"    - 25%: {stats.get('25%', 'N/A')}")
                    report.append(f"    - Median (50%): {stats.get('50%', 'N/A')}")
                    report.append(f"    - 75%: {stats.get('75%', 'N/A')}")
                    report.append(f"    - Max: {stats.get('max', 'N/A')}")
            except Exception as e:
                report.append(f"- **Error generating numeric summary:** {e}")
        report.append("---")

        # --- Value Distribution (Categorical/Object Columns) ---
        report.append("\n## 6. Value Distribution (Categorical & Object Columns)")
        # Select both 'object' and 'category' types
        categorical_columns = self.df.select_dtypes(include=['object', 'string', 'category'])
        if categorical_columns.empty:
            report.append("- **No categorical or object columns found.**")
        else:
            report.append("- **Top value counts (showing up to top 10):**")
            for col in categorical_columns.columns:
                report.append(f"  - **`{col}`** (Unique: {self.df[col].nunique()}):")
                value_counts = categorical_columns[col].value_counts()
                # Show top N values + potentially an 'Other' count
                top_n = 10
                for i, (value, count) in enumerate(value_counts.head(top_n).items()):
                    # Handle potential long string values by truncating
                    display_value = str(value)
                    if len(display_value) > 50: display_value = display_value[:47] + "..."
                    report.append(f"    - '{display_value}': {count} ({count / self.df.shape[0]:.2%})")
                if len(value_counts) > top_n:
                    other_count = value_counts.iloc[top_n:].sum()
                    report.append(f"    - (Other values): {other_count} ({other_count / self.df.shape[0]:.2%})")
        report.append("---")

        # --- Timestamp Columns Summary ---
        report.append("\n## 7. Timestamp Columns Summary")
        # Use np.datetime64 to catch various datetime types including timezone-aware
        timestamp_columns = self.df.select_dtypes(include=np.datetime64)
        if timestamp_columns.empty:
            report.append("- **No timestamp columns found.**")
        else:
            for col in timestamp_columns.columns:
                report.append(f"\n### Summary for `{col}`:")
                if self.df[col].isnull().all():
                     report.append("- Column contains only null values.")
                     continue # Skip stats for all-null column

                try:
                    min_ts = self.df[col].min()
                    max_ts = self.df[col].max()
                    report.append(f"- **Earliest Timestamp:** {min_ts}")
                    report.append(f"- **Latest Timestamp:** {max_ts}")
                    if pd.api.types.is_datetime64_any_dtype(self.df[col].dtype) and min_ts is not pd.NaT and max_ts is not pd.NaT:
                         try:
                              duration = max_ts - min_ts
                              report.append(f"- **Duration (Range):** {duration}")
                         except TypeError:
                              report.append("- **Duration (Range):** Could not calculate (potentially mixed timezones or types).") # Handle potential issues
                    report.append(f"- **Unique Timestamps:** {self.df[col].nunique()}")
                    # Value counts often less useful for timestamps unless they are discrete dates/times
                    # report.append("```")
                    # report.append(self.df[col].value_counts().head(10).to_string())
                    # report.append("```")
                except Exception as e:
                    report.append(f"- **Error analyzing timestamp column:** {e}")
        report.append("---") # End marker for the section

        return "\n".join(report)

    def print_summary(self):
        """
        Print the summary report to the console.
        """
        print(self.generate_summary_markdown())

def generate_data_description(df):
    """
    Convenience function to generate a data description report from a DataFrame.
    
    Args:
        df (pd.DataFrame): The dataset to describe.
    
    Returns:
        str: The summary report in Markdown format.
    """
    try:
        describer = DataDescriber(df)
        return describer.generate_summary_markdown()
    except Exception as e:
        return f"## Error\n\nFailed to generate data description: {str(e)}"