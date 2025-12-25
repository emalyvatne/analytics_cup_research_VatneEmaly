import pandas as pd
import numpy as np


def compute_peak_intensities_from_tracking(
    tracking_df: pd.DataFrame,
    windows_seconds = (60, 120, 180, 240, 300),
    hsr: float = 5.28,   # HSR threshold (m/s) for RLFC but can be adjusted
    spr: float = 6.39,   # Sprint threshold (m/s) for RLFC but can be adjusted
    fps: float = 10.0    # frames per second in SkillCorner tracking
) -> pd.DataFrame:
    """
    okay so this lovely function computes peak running intensities from SkillCorner tracking data

    the parameters/inputs are:
    tracking_df : a pandas df that must contain columns the columns 
        ['match_id', 'player_id', 'team_name', 'timestamp', 'x', 'y']
    windows_seconds : list of integers that represent the window lengths in SECONDS over which peak m/min will be computed
    hsr, spr : floats that represent the speed thresholds in m/s to classify distance bands

    then the function returns:
    a single dataframe that has:
        one row per match_id-player_id-team_name with:
        - total / HSR / sprint distances
        - peak m/min for each window
        - For each window length W: Peak m/min Ws_FrameStart, Peak m/min Ws_TimeStart
          giving the frame and timestamp at the *start* of the peak window
    """

    df = tracking_df.copy()

    # ----- first make sure the timestamp column is datetime and sort -----
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values(["match_id", "player_id", "period", "frame"])

    results = []

    # group by match, player, and team
    for (match_id, player_id, team_name), g in df.groupby(
        ["match_id", "player_id", "team_name"]
    ):
        g = g.copy().sort_values(["period", "frame"])

        # create time step from frame and fps (per period)
        g["frame_diff"] = g.groupby("period")["frame"].diff().fillna(1)
        g["dt"] = g["frame_diff"] / fps  # seconds

        # calculate frame-to-frame displacement (per period) 
        g["dx"] = g.groupby("period")["x"].diff().fillna(0.0)
        g["dy"] = g.groupby("period")["y"].diff().fillna(0.0)
        g["step_distance"] = np.sqrt(g["dx"] ** 2 + g["dy"] ** 2)

        # calculate instantaneous speed & m/min 
        g["Velocity"] = g["step_distance"] / g["dt"]  # m/s

        # filter out clearly impossible speeds (e.g., tracking glitches)
        g.loc[g["Velocity"] > 20.0, "Velocity"] = np.nan
        g.loc[g["Velocity"] < 0, "Velocity"] = np.nan

        g["m_per_min"] = g["Velocity"] * 60.0  # m/min

        # apply distance bands (treat NaN velocity as 0 for bands) 
        vel = g["Velocity"].fillna(0.0)
        g["Total_Distance_m"] = g["step_distance"]
        g["High_Speed_Distance_m"] = np.where(vel > hsr, g["step_distance"], 0.0)
        g["Sprint_Distance_m"] = np.where(vel > spr, g["step_distance"], 0.0)

        # calculate peaks over time windows 
        peak_metrics = {}
        for w_sec in windows_seconds:
            window_size = int(round(w_sec * fps))  # samples in that many seconds
            if window_size < 1 or len(g) == 0:
                continue

            col_name = f"Peak m/min {w_sec}s"

            # calculate rolling mean of m_per_min across the series
            rolling_mean = g["m_per_min"].fillna(0.0).rolling(
                window=window_size,
                min_periods=1
            ).mean()

            # identify the peak magnitude
            peak_value = float(rolling_mean.max(skipna=True))
            peak_metrics[col_name] = peak_value

            # really important for identifying why: retain the index (label) of the max rolling mean
            peak_idx_label = rolling_mean.idxmax()
            
            # convert that to positional index
            peak_pos = g.index.get_loc(peak_idx_label)
            # start position of that window (right-aligned rolling window)
            start_pos = max(0, peak_pos - window_size + 1)

            # record frame + timestamp of the *start* of that peak window
            start_frame = int(g.iloc[start_pos]["frame"])
            start_time = g.iloc[start_pos]["timestamp"]

            peak_metrics[f"{col_name}_FrameStart"] = start_frame
            peak_metrics[f"{col_name}_TimeStart"] = start_time

        # aggregate the distances over the whole series 
        summary = {
            "match_id": match_id,
            "player_id": player_id,
            "team_name": team_name,
            "Total Distance (m)": float(g["Total_Distance_m"].sum(skipna=True)),
            "High Speed Running Distance (m)": float(g["High_Speed_Distance_m"].sum(skipna=True)),
            "Sprint Distance (m)": float(g["Sprint_Distance_m"].sum(skipna=True)),
        }
        summary.update(peak_metrics)
        results.append(summary)

    peak_intensity = pd.DataFrame(results) if results else pd.DataFrame()
    return peak_intensity

import pandas as pd
import numpy as np

def merge_wcs_peaks_with_events(
    peak_intensity: pd.DataFrame,
    event_df: pd.DataFrame,
    window_seconds: int,
    player_col: str = "player_id",
    tolerance_frames: int | None = None,
    return_summary: bool = False,
) -> pd.DataFrame | tuple[pd.DataFrame, pd.DataFrame]:
    """
    Take the per-player peak intensity rows from `peak_intensity` and merge them
    with the closest event for that same player in `event_df` for a given
    WCS window (e.g., 60s).

    Parameters
    ----------
    peak_intensity : DataFrame
        DataFrame with peak intensities from compute_peak_intensities_from_tracking.
    event_df : DataFrame
        SkillCorner dynamic events DataFrame.
    window_seconds : int
        WCS window length in seconds (e.g., 60, 120, 180, ...).
    player_col : str, default 'player_id'
        Column in event_df that identifies the player to match on.
    tolerance_frames : int or None, default None
        If set, events farther than this many frames from the WCS
        start frame will be discarded (event fields set to NaN).
    return_summary : bool, default False
        If True, also returns a by-team event summary table.

    Returns
    -------
    merged_WCS_events : DataFrame
        One row per WCS peak (for the chosen window), with the closest
        event for that player/match attached.

    If return_summary=True:
        (merged_WCS_events, event_summary)
        where `event_summary` is a tidy table of event types/sub-types
        that precede WCS demands, summarized by team.
    """

    # ----- 1. Build peak columns dynamically -----
    peak_col = f"Peak m/min {window_seconds}s"
    frame_col = f"{peak_col}_FrameStart"
    time_col = f"{peak_col}_TimeStart"

    required_peak_cols = [
        "match_id",
        "player_id",
        "team_name",
        peak_col,
        frame_col,
        time_col,
    ]
    missing_peak = [c for c in required_peak_cols if c not in peak_intensity.columns]
    if missing_peak:
        raise KeyError(
            f"Missing columns in peak_intensity for window {window_seconds}s: {missing_peak}"
        )

    peak_df = (
        peak_intensity[required_peak_cols]
        .rename(
            columns={
                frame_col: "frame_peak_start",
                time_col: "time_peak_start",
            }
        )
        .copy()
    )

    # drop any rows without a valid frame
    peak_df = peak_df.dropna(subset=["frame_peak_start"]).copy()

    # enforce the int column types for the merge
    peak_df["match_id"] = peak_df["match_id"].astype(int)
    peak_df["player_id"] = peak_df["player_id"].astype(int)
    peak_df["frame_peak_start"] = peak_df["frame_peak_start"].astype(int)

    # ----- 2. Prepare events df -----
    events_for_merge = event_df.copy()

    if player_col not in events_for_merge.columns:
        raise KeyError(f"'player_col'='{player_col}' not found in event_df columns.")

    required_event_cols = ["match_id", player_col, "frame_start"]
    missing_event = [c for c in required_event_cols if c not in events_for_merge.columns]
    if missing_event:
        raise KeyError(f"Missing columns in event_df: {missing_event}")

    # keep only players that appear in the peak_df and clean key names
    events_for_merge = events_for_merge[
        events_for_merge[player_col].isin(peak_df["player_id"].unique())
    ].copy()
    events_for_merge = events_for_merge.rename(columns={player_col: "player_id"})

    # enforce column types for merge keys
    events_for_merge["match_id"] = events_for_merge["match_id"].astype(int)
    events_for_merge["player_id"] = events_for_merge["player_id"].astype(int)
    events_for_merge["frame_start"] = events_for_merge["frame_start"].astype(int)

    # ----- 3. Manually match each peak to the nearest event for that player -----
    merged_rows = []

    for _, peak in peak_df.iterrows():
        mid = peak["match_id"]
        pid = peak["player_id"]
        f_peak = peak["frame_peak_start"]

        events_sub = events_for_merge[
            (events_for_merge["match_id"] == mid)
            & (events_for_merge["player_id"] == pid)
        ]

        if events_sub.empty:
            row = peak.to_dict()
            row["frame_start"] = np.nan
            row["event_id"] = np.nan
            row["event_type"] = np.nan
            row["event_subtype"] = np.nan
            row["time_start"] = np.nan
            row["time_end"] = np.nan
            merged_rows.append(row)
            continue

        # identify nearest event in frame space
        diffs = (events_sub["frame_start"] - f_peak).abs()
        idx_closest = diffs.idxmin()
        min_diff = diffs.loc[idx_closest]

        # apply tolerance if specified
        if (tolerance_frames is not None) and (min_diff > tolerance_frames):
            row = peak.to_dict()
            row["frame_start"] = np.nan
            row["event_id"] = np.nan
            row["event_type"] = np.nan
            row["event_subtype"] = np.nan
            row["time_start"] = np.nan
            row["time_end"] = np.nan
            merged_rows.append(row)
            continue

        event_row = events_sub.loc[idx_closest]

        # combine the peak intensity and event
        row = peak.to_dict()
        for col in events_sub.columns:
            if col in row:  # don't overwrite match_id/player_id
                continue
            row[col] = event_row[col]

        merged_rows.append(row)

    merged_WCS_events = pd.DataFrame(merged_rows)

    # -------------------------------------------------
    # 4. Optional: build by-team event summary
    # -------------------------------------------------
    if not return_summary:
        return merged_WCS_events

    # If team_name isn't present, we can't summarize by team
    if "team_name" not in merged_WCS_events.columns:
        return merged_WCS_events, pd.DataFrame()

    # ----- Create a clean summary by team -----
    cols_keep = [
        "team_id",
        "team_name",
        peak_col,       # window-specific peak column (not used in summary yet, but kept)
        "event_type",
        "event_subtype",
    ]
    cols_keep = [c for c in cols_keep if c in merged_WCS_events.columns]

    events_for_summary = merged_WCS_events[cols_keep].copy()

    # drop rows without a matched event_type
    events_for_summary = events_for_summary.dropna(subset=["event_type"]).copy()

    # fill in missing subtypes
    events_for_summary["event_subtype"] = (
        events_for_summary["event_subtype"].fillna("No Sub-Type")
    )

    # summary by event type with percentages
    event_type_summary = (
        events_for_summary
        .groupby(["team_name", "event_type"])
        .size()
        .reset_index(name="EventType_Count")
    )

    event_type_summary["% of Events that Precede WCS"] = (
        event_type_summary["EventType_Count"]
        / event_type_summary.groupby("team_name")["EventType_Count"].transform("sum")
        * 100
    ).round(2)

    # summary by event sub-type
    event_subtype_summary = (
        events_for_summary
        .groupby(["team_name", "event_type", "event_subtype"])
        .size()
        .reset_index(name="Subtype_Count")
    )

    # merge subtype summary back with type-level counts/percentages
    event_summary = pd.merge(
        event_subtype_summary,
        event_type_summary,
        on=["team_name", "event_type"],
        how="left",
    )

    # ----- clean up for presentation -----
    event_summary = (
        event_summary.rename(
            columns={
                "team_name": "Team",
                "event_type": "Event Type",
                "event_subtype": "Event Sub-Type",
            }
        )
        .sort_values(["Team", "EventType_Count", "Subtype_Count"],
                     ascending=[True, False, False])
        .reset_index(drop=True)
    )

    # set column order (only keep those that exist)
    desired_cols = [
        "Team",
        "Event Type",
        "EventType_Count",
        "% of Events that Precede WCS",
        "Event Sub-Type",
        "Subtype_Count",
    ]
    existing_cols = [c for c in desired_cols if c in event_summary.columns]
    event_summary = event_summary[existing_cols]

    return merged_WCS_events, event_summary


def summarize_team_wcs(peak_intensity: pd.DataFrame) -> pd.DataFrame:
    """
    Summarize WCS peak running intensities by team across all available
    Peak m/min windows in `peak_intensity`.

    Returns a table with one row per team and one column per
    Peak m/min window containing "mean (min – max)".
    """
    peak_cols = [
        c for c in peak_intensity.columns
        if c.startswith("Peak m/min ") and c.endswith("s")
    ]

    summary_list = []

    # group by team_name
    for team, df_team in peak_intensity.groupby("team_name"):
        row = {"Team": team}

        for col in peak_cols:
            values = df_team[col].dropna()
            if len(values) > 0:
                mean_val = values.mean()
                min_val = values.min()
                max_val = values.max()
                row[col] = f"{mean_val:.1f} ({min_val:.1f} – {max_val:.1f})"
            else:
                row[col] = "N/A"

        summary_list.append(row)

    summary_df = pd.DataFrame(summary_list)
    return summary_df.sort_values("Team").reset_index(drop=True)
