import pandas as pd
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]

RAW_DIRS = {
    "subway": BASE_DIR / "data" / "raw" / "subway",
    "bus": BASE_DIR / "data" / "raw" / "bus",
    "streetcar": BASE_DIR / "data" / "raw" / "streetcar",
}

OUTPUT_DIR = BASE_DIR / "data" / "cleaned"
OUTPUT_FILE = OUTPUT_DIR / "ttc_delay_cleaned.csv"


def clean_column_name(col):
    """
    Convert raw column names into simpler snake_case format.
    Example: 'Min Delay' -> 'min_delay'
    """
    return (
        str(col)
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("/", "_")
        .replace("(", "")
        .replace(")", "")
    )


def read_raw_file(file_path):
    """
    Read either CSV or Excel file.
    """
    suffix = file_path.suffix.lower()

    if suffix == ".csv":
        return pd.read_csv(file_path)
    elif suffix in [".xlsx", ".xls"]:
        return pd.read_excel(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_path}")


def standardize_columns(df, mode):
    """
    Standardize subway, bus, and streetcar delay files into one common structure.
    """

    df = df.copy()
    df.columns = [clean_column_name(col) for col in df.columns]

    # Different TTC files may use slightly different column names.
    rename_map = {
        "report_date": "date",
        "date": "date",
        "time": "time",
        "day": "day_name",
        "station": "location",
        "location": "location",
        "route": "route_line",
        "line": "route_line",
        "bound": "direction",
        "direction": "direction",
        "code": "incident_code",
        "incident": "incident_type",
        "min_delay": "min_delay",
        "min_gap": "min_gap",
        "vehicle": "vehicle",
    }

    df = df.rename(columns={col: rename_map[col] for col in df.columns if col in rename_map})

    required_columns = [
        "date",
        "time",
        "day_name",
        "route_line",
        "location",
        "incident_code",
        "incident_type",
        "min_delay",
        "min_gap",
        "direction",
        "vehicle",
    ]

    for col in required_columns:
        if col not in df.columns:
            df[col] = None

    df = df[required_columns]
    df["mode"] = mode

    return df


def clean_delay_data(df):
    """
    Clean dates, times, numeric columns, and create useful analysis fields.
    """

    df = df.copy()

    # Date
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # Time
    df["time"] = df["time"].astype(str).str.strip()
    df["time"] = pd.to_datetime(df["time"], errors="coerce").dt.time

    # Numeric fields
    df["min_delay"] = pd.to_numeric(df["min_delay"], errors="coerce").fillna(0)
    df["min_gap"] = pd.to_numeric(df["min_gap"], errors="coerce").fillna(0)

    # Text fields
    text_cols = [
        "day_name",
        "route_line",
        "location",
        "incident_code",
        "incident_type",
        "direction",
        "vehicle",
        "mode",
    ]

    for col in text_cols:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace(["nan", "None", ""], "Unknown")

    # Feature engineering
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["month_name"] = df["date"].dt.month_name()
    df["hour"] = pd.to_datetime(df["time"].astype(str), errors="coerce").dt.hour

    def time_period(hour):
        if pd.isna(hour):
            return "Unknown"
        elif 6 <= hour < 10:
            return "Morning Rush"
        elif 10 <= hour < 15:
            return "Midday"
        elif 15 <= hour < 19:
            return "Evening Rush"
        elif 19 <= hour < 24:
            return "Night"
        else:
            return "Late Night"

    df["time_period"] = df["hour"].apply(time_period)

    def delay_severity(minutes):
        if minutes == 0:
            return "No Delay"
        elif minutes < 5:
            return "Minor"
        elif minutes < 15:
            return "Moderate"
        elif minutes < 30:
            return "Major"
        else:
            return "Severe"

    df["delay_severity"] = df["min_delay"].apply(delay_severity)

    # Remove rows without valid date
    df = df.dropna(subset=["date"])

    # Sort
    df = df.sort_values(["date", "hour", "mode"]).reset_index(drop=True)

    # Add ID
    df.insert(0, "incident_id", range(1, len(df) + 1))

    return df


def main():
    all_data = []

    for mode, folder in RAW_DIRS.items():
        files = list(folder.glob("*.csv")) + list(folder.glob("*.xlsx")) + list(folder.glob("*.xls"))

        if not files:
            print(f"No files found for {mode}: {folder}")
            continue

        for file_path in files:
            print(f"Reading {mode} file: {file_path.name}")
            raw_df = read_raw_file(file_path)
            standardized_df = standardize_columns(raw_df, mode)
            all_data.append(standardized_df)

    if not all_data:
        print("No raw files found. Please add TTC delay files into data/raw folders.")
        return

    combined_df = pd.concat(all_data, ignore_index=True)
    cleaned_df = clean_delay_data(combined_df)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cleaned_df.to_csv(OUTPUT_FILE, index=False)

    print("Cleaning complete.")
    print(f"Rows cleaned: {len(cleaned_df)}")
    print(f"Output saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()