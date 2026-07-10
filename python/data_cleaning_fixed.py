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

REFERENCE_DIR = BASE_DIR / "data" / "reference"
CODE_DESCRIPTION_URLS = {
    "subway": "https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/996cfe8d-fb35-40ce-b569-698d51fc683b/resource/b2d8f5e0-0997-46b5-8abd-caa685a0290b/download/code-descriptions.csv",
    "bus": "https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/e271cdae-8788-4980-96ce-6a5c95bc6618/resource/874ae66c-9f6f-443f-91e0-1d37d416e0d8/download/code-descriptions.csv",
    "streetcar": "https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/b68cb71b-44a7-4394-97e2-5d2f41462a5d/resource/06d13be4-a8b7-4365-ac68-2169de8e0630/download/code-descriptions.csv",
}


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


def fix_mojibake(value):
    """
    Some TTC code description files contain mojibake such as 'â'.
    This converts it back to readable punctuation when possible.
    """
    if pd.isna(value):
        return value

    value = str(value).strip()

    try:
        if "â" in value or "Ã" in value:
            return value.encode("latin1").decode("utf-8")
    except Exception:
        pass

    return value


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


def load_code_descriptions():
    """
    Load official TTC delay code descriptions.

    This creates three useful fields later:
    - incident_description: official readable description
    - incident_category: broad analysis category
    - incident_mapping_status: whether the code was matched cleanly
    """
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)

    lookup_frames = []

    for mode, url in CODE_DESCRIPTION_URLS.items():
        local_file = REFERENCE_DIR / f"{mode}_code_descriptions.csv"

        if local_file.exists():
            code_df = pd.read_csv(local_file)
        else:
            code_df = pd.read_csv(url)
            code_df.to_csv(local_file, index=False)

        code_df.columns = [clean_column_name(col) for col in code_df.columns]
        code_df = code_df.rename(
            columns={
                "code": "incident_code",
                "description": "incident_description",
            }
        )

        code_df["mode_source"] = mode
        code_df["incident_code"] = (
            code_df["incident_code"]
            .astype(str)
            .str.strip()
            .str.upper()
        )
        code_df["incident_description"] = code_df["incident_description"].apply(fix_mojibake)

        lookup_frames.append(
            code_df[["mode_source", "incident_code", "incident_description"]]
            .dropna(subset=["incident_code"])
            .drop_duplicates()
        )

    lookup_df = pd.concat(lookup_frames, ignore_index=True)
    lookup_df.to_csv(REFERENCE_DIR / "incident_code_lookup.csv", index=False)

    return lookup_df


def standardize_columns(df, mode):
    """
    Standardize subway, bus, and streetcar delay files into one common structure.
    """

    df = df.copy()
    df.columns = [clean_column_name(col) for col in df.columns]

    # Different TTC files may use slightly different column names.
    # Important: raw "Incident" is a description, not a broad incident type.
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
        "incident": "incident_description_raw",
        "description": "incident_description_raw",
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
        "incident_description_raw",
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


def add_incident_descriptions(df, lookup_df):
    """
    Map each incident_code to an official TTC incident description.

    Priority:
    1. Match by mode + code.
    2. If the same code appears in another TTC mode's lookup table, use that as fallback.
    3. If raw data has an incident description, use it.
    4. Otherwise mark as Unknown.
    """
    df = df.copy()

    df["incident_code"] = (
        df["incident_code"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    lookup_df = lookup_df.copy()
    lookup_df["incident_code"] = (
        lookup_df["incident_code"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    by_mode = {
        mode: dict(zip(group["incident_code"], group["incident_description"]))
        for mode, group in lookup_df.groupby("mode_source")
    }

    global_lookup = {}
    for _, row in lookup_df.iterrows():
        global_lookup.setdefault(row["incident_code"], row["incident_description"])

    def get_description(row):
        code = row["incident_code"]
        mode = row["mode"]
        raw_description = row.get("incident_description_raw", None)

        if code in by_mode.get(mode, {}):
            return by_mode[mode][code], "Official mode-code match"

        if code in global_lookup:
            return global_lookup[code], "Official cross-mode code match"

        if pd.notna(raw_description) and str(raw_description).strip() not in ["", "nan", "None", "Unknown"]:
            return fix_mojibake(raw_description), "Raw incident text fallback"

        return "Unknown", "Unmapped code"

    mapped_values = df.apply(get_description, axis=1, result_type="expand")
    df["incident_description"] = mapped_values[0]
    df["incident_mapping_status"] = mapped_values[1]

    return df


def categorize_incident(code, description):
    """
    Convert detailed TTC descriptions into broad business-friendly categories.
    These are used for cleaner dashboard visuals.
    """
    code = str(code or "").strip().upper()
    text = str(description or "").upper()

    if text in ["", "UNKNOWN", "NAN", "NONE"]:
        return "Unknown"

    security_keywords = [
        "ASSAULT", "DISORDERLY", "BOMB", "POLICE", "ROBBERY",
        "SUSPICIOUS", "SECURITY", "GRAFFITI", "SCRATCHITI",
    ]
    passenger_keywords = [
        "ILL CUSTOMER", "INJURED", "MEDICAL", "PASSENGER",
        "PATRON", "CUSTOMER", "ON BOARD INJURY", "PASSENGER ALARM",
    ]
    vehicle_keywords = [
        "DOOR", "BRAKE", "PROPULSION", "BODY", "HVAC",
        "AIR CONDITIONING", "VOLTAGE", "COMPRESSED AIR", "ENGINE",
        "COUPLER", "CHOPPER", "CAR", "TRAIN", "VEHICLE",
        "EQUIPMENT", "TRUCKS", "RAMP",
    ]
    infrastructure_keywords = [
        "SIGNAL", "TRACK", "SWITCH", "POWER", "ELECTRICAL",
        "OVERHEAD", "PLANT", "ESCALATOR", "ELEVATOR", "ATC",
        "RC&S", "COMMUNICATION",
    ]
    operations_keywords = [
        "NO OPERATOR", "OPERATOR", "CREW", "SUPERVISORY",
        "CONTROLLER", "LATE", "TRANSPORTATION", "MAINLINE",
        "SERVICE", "LABOUR", "CLERK", "COLLECTOR",
    ]
    external_keywords = [
        "DIVERSION", "PARADE", "WEATHER", "FORCE MAJEURE",
        "CONSTRUCTION", "FIRE", "SMOKE", "DEBRIS", "CLEANING",
        "UNSANITARY", "FARE", "AUTO FOUL", "COLLISION",
    ]

    if any(keyword in text for keyword in security_keywords):
        return "Security / Safety"
    if any(keyword in text for keyword in passenger_keywords):
        return "Passenger / Medical"
    if any(keyword in text for keyword in vehicle_keywords):
        return "Vehicle / Equipment"
    if any(keyword in text for keyword in infrastructure_keywords):
        return "Infrastructure / Signals"
    if any(keyword in text for keyword in operations_keywords):
        return "Operations / Staffing"
    if any(keyword in text for keyword in external_keywords):
        return "External / Other"

    # Fallback based on TTC delay code family.
    if code.startswith("S"):
        return "Security / Safety"
    if code.startswith("E"):
        return "Vehicle / Equipment"
    if code.startswith("P"):
        return "Infrastructure / Signals"
    if code.startswith("T"):
        return "Operations / Staffing"
    if code.startswith("M"):
        return "External / Other"

    return "Other"


def clean_delay_data(df, lookup_df):
    """
    Clean dates, times, numeric columns, and create useful analysis fields.
    """

    df = df.copy()

    # Date
    # Date
    # Bus date format can look like "2025-01-01T00:00:00".
    # Extract the YYYY-MM-DD part first to avoid parsing failures.
    df["date_raw"] = df["date"].astype(str).str.strip()

    df["date"] = df["date_raw"].str.extract(r"(\d{4}-\d{2}-\d{2})", expand=False)
    df["date"] = df["date"].fillna(df["date_raw"])
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    print("\nInvalid date counts by mode BEFORE dropping bad dates:")
    print(df.assign(date_missing=df["date"].isna()).groupby("mode")["date_missing"].sum())

    # Time
    df["time"] = df["time"].astype(str).str.strip()
    df["time"] = pd.to_datetime(df["time"], errors="coerce", format="mixed").dt.time

    # Numeric fields
    df["min_delay"] = pd.to_numeric(df["min_delay"], errors="coerce").fillna(0)
    df["min_gap"] = pd.to_numeric(df["min_gap"], errors="coerce").fillna(0)

    # Text fields
    text_cols = [
        "day_name",
        "route_line",
        "location",
        "incident_code",
        "incident_description_raw",
        "direction",
        "vehicle",
        "mode",
    ]

    for col in text_cols:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace(["nan", "None", ""], "Unknown")

    # Add official incident descriptions and categories
    df = add_incident_descriptions(df, lookup_df)
    df["incident_category"] = [
        categorize_incident(code, desc)
        for code, desc in zip(df["incident_code"], df["incident_description"])
    ]

    # Backward-compatible name for Power BI visuals.
    # Use incident_description for detailed cause charts; use incident_category for broad cause charts.
    df["incident_type"] = df["incident_category"]

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
    print("\nMode counts AFTER dropping bad dates:")
    print(df["mode"].value_counts(dropna=False))

    
    # Sort
    df = df.sort_values(["date", "hour", "mode"]).reset_index(drop=True)

    # Add ID
    df.insert(0, "incident_id", range(1, len(df) + 1))

    final_columns = [
        "incident_id",
        "date",
        "time",
        "day_name",
        "route_line",
        "location",
        "incident_code",
        "incident_description",
        "incident_category",
        "incident_type",
        "incident_mapping_status",
        "min_delay",
        "min_gap",
        "direction",
        "vehicle",
        "mode",
        "year",
        "month",
        "month_name",
        "hour",
        "time_period",
        "delay_severity",
    ]

    return df[final_columns]


def main():
    all_data = []
    lookup_df = load_code_descriptions()

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
    cleaned_df = clean_delay_data(combined_df, lookup_df)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cleaned_df.to_csv(
    OUTPUT_FILE,
    index=False,
    encoding="utf-8-sig",
    errors="replace"
)


    print("Cleaning complete.")
    print(f"Rows cleaned: {len(cleaned_df)}")
    print(f"Output saved to: {OUTPUT_FILE}")
    print()
    print("Incident mapping quality check:")
    print(cleaned_df["incident_mapping_status"].value_counts(dropna=False))
    print()
    print("Incident category check:")
    print(cleaned_df["incident_category"].value_counts(dropna=False))


if __name__ == "__main__":
    main()
