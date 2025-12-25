from pathlib import Path
import pandas as pd
import numpy as np
import requests


class SkillCorner:
    def load(self, match_id: int):
        # ----- setup directory/check that it exists -----
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)

        # ----- metadata -----
        meta_url = (
            f"https://raw.githubusercontent.com/SkillCorner/opendata/master/"
            f"data/matches/{match_id}/{match_id}_match.json"
        )
        meta_file = data_dir / f"{match_id}_meta.json"

        if not meta_file.exists():
            response = requests.get(meta_url)
            response.raise_for_status()
            meta_file.write_text(response.text, encoding="utf-8")

        metadata_json = pd.read_json(meta_file, lines=True)

        home_team = metadata_json["home_team"][0]
        away_team = metadata_json["away_team"][0]
        match_date = metadata_json["date_time"][0].date()

        metadata_df = pd.DataFrame(
            [
                {
                    "match_id": match_id,
                    "match_date": match_date,
                    "home_team": home_team["name"],
                    "away_team": away_team["name"],
                    "home_team_jersey_color": metadata_json["home_team_kit"][0][
                        "jersey_color"
                    ],
                    "home_team_number_color": metadata_json["home_team_kit"][0][
                        "number_color"
                    ],
                    "away_team_jersey_color": metadata_json["away_team_kit"][0][
                        "jersey_color"
                    ],
                    "away_team_number_color": metadata_json["away_team_kit"][0][
                        "number_color"
                    ],
                }
            ]
        )

        # Map player_id to team_name (only for the players who actually played)
        players_meta = metadata_json["players"][0]
        player2team = {
            p["id"]: home_team["name"]
            if p["team_id"] == home_team["id"]
            else away_team["name"]
            for p in players_meta
            if p["start_time"] is not None
        }

        # ----- tracking data -----
        tracking_url = (
            f"https://media.githubusercontent.com/media/SkillCorner/opendata/master/"
            f"data/matches/{match_id}/{match_id}_tracking_extrapolated.jsonl"
        )
        tracking_file = data_dir / f"{match_id}_tracking.jsonl"

        if not tracking_file.exists():
            response = requests.get(tracking_url)
            response.raise_for_status()
            tracking_file.write_text(response.text, encoding="utf-8")

        tracking_json = pd.read_json(tracking_file, lines=True)

        home_side_map = {"left_to_right": 1, "right_to_left": -1}
        tracking_records = []

        for _, row in tracking_json.iterrows():
            possession_group = row["possession"]["group"]
            if possession_group not in ["home team", "away team"]:
                continue

            period = int(row["period"])
            home_team_side = home_side_map.get(
                metadata_json["home_team_side"][0][period - 1], 1
            )
            away_team_side = -home_team_side

            for p in row["player_data"]:
                pid = p["player_id"]
                if pid not in player2team:  # skip players who didn't actually play
                    continue

                team_name = player2team[pid]
                side = home_team_side if team_name == home_team["name"] else away_team_side

                possession_label = (
                    "In"
                    if (possession_group == "home team") == (team_name == home_team["name"])
                    else "Out"
                )

                tracking_records.append(
                    {
                        "match_id": match_id,
                        "period": period,
                        "frame": row["frame"],
                        "timestamp": row["timestamp"],
                        "player_id": pid,
                        "team_name": team_name,
                        "possession": possession_label,
                        "x": p["x"] * side,
                        "y": p["y"] * side,
                    }
                )

        tracking_df = pd.DataFrame(tracking_records)

        # ----- add phases of play to the tracking data df -----
        phases_url = (
            f"https://raw.githubusercontent.com/SkillCorner/opendata/master/"
            f"data/matches/{match_id}/{match_id}_phases_of_play.csv"
        )
        phases_file = data_dir / f"{match_id}_phases_of_play.csv"

        if not phases_file.exists():
            response = requests.get(phases_url)
            response.raise_for_status()
            phases_file.write_text(response.text, encoding="utf-8")

        phases_df = pd.read_csv(phases_file)

        # assign phase by frame and possession
        intervals = pd.IntervalIndex.from_arrays(
            phases_df["frame_start"], phases_df["frame_end"], closed="left"
        )
        phase_idx = intervals.get_indexer(tracking_df["frame"])

        tracking_df["phase"] = np.nan
        valid = phase_idx != -1

        tracking_df.loc[valid, "phase"] = np.where(
            tracking_df.loc[valid, "possession"] == "In",
            phases_df.iloc[phase_idx[valid]]["team_in_possession_phase_type"].values,
            phases_df.iloc[phase_idx[valid]][
                "team_out_of_possession_phase_type"
            ].values,
        )

        # ----- event data -----
        event_url = (
            f"https://raw.githubusercontent.com/SkillCorner/opendata/master/"
            f"data/matches/{match_id}/{match_id}_dynamic_events.csv"
        )
        event_file = data_dir / f"{match_id}_dynamic_events.csv"

        if not event_file.exists():
            response = requests.get(event_url)
            response.raise_for_status()
            event_file.write_text(response.text, encoding="utf-8")

        event_df = pd.read_csv(event_file)
        event_df["match_id"] = match_id

        print(f"{home_team['name']} vs {away_team['name']} on {match_date} parsed...")

        return metadata_df, tracking_df, event_df

import os
import matplotlib.pyplot as plt
from pandas.plotting import table as pd_table

def save_table_as_image(df, filename="table.png", folder="figs", dpi=300):
    # ensure figs directory exists
    os.makedirs(folder, exist_ok=True)

    # create figure with appropriate size based on df shape
    fig, ax = plt.subplots(figsize=(max(8, df.shape[1] * 2.2),
                                    max(4, df.shape[0] * 0.4)))
    
    ax.axis("off")  # hide axes

    # render the table
    tbl = pd_table(ax, df, loc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)

    # save figure
    output_path = os.path.join(folder, filename)
    plt.savefig(output_path, dpi=dpi, bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)

    print(f"Saved table image to: {output_path}")
