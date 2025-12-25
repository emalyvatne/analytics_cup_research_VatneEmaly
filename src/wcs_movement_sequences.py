import plotly.graph_objects as go
import numpy as np
import pandas as pd

def create_wcs_movement_animation(
    tracking_df: pd.DataFrame,
    peak_intensity: pd.DataFrame,
    match_id: int,
    player_id: int,
    window_seconds: int = 60,
    fps: float = 10.0,
):
    """
    Create an animated movement sequence for a selected player during their
    worst-case scenario (WCS) window, with the movement trail color-coded
    by instantaneous speed, overlaid on a football pitch.
    """

    # ----- 1. Get this player's WCS window for the chosen duration -----
    peak_col = f"Peak m/min {window_seconds}s"
    frame_col = f"{peak_col}_FrameStart"

    player_peaks = peak_intensity[
        (peak_intensity["match_id"] == match_id) &
        (peak_intensity["player_id"] == player_id)
    ]

    if player_peaks.empty:
        raise ValueError(
            f"No peak intensity row found for match_id={match_id}, player_id={player_id}"
        )

    # If there are multiple, take the one with the highest peak value
    peak_row = player_peaks.loc[player_peaks[peak_col].idxmax()]

    start_frame = int(peak_row[frame_col])
    end_frame = start_frame + int(window_seconds * fps)

    # ----- 2. Slice tracking data for this player & window -----
    traj = tracking_df[
        (tracking_df["match_id"] == match_id) &
        (tracking_df["player_id"] == player_id) &
        (tracking_df["frame"].between(start_frame, end_frame))
    ].copy()

    if traj.empty:
        raise ValueError("No tracking data in the selected WCS window for this player.")

    traj = traj.sort_values(["period", "frame"])

    # ----- 2a. Compute instantaneous speed (m/s) -----
    traj["frame_diff"] = traj.groupby("period")["frame"].diff().fillna(1)
    traj["dt"] = traj["frame_diff"] / fps

    traj["dx"] = traj.groupby("period")["x"].diff().fillna(0.0)
    traj["dy"] = traj.groupby("period")["y"].diff().fillna(0.0)
    traj["step_distance"] = np.sqrt(traj["dx"] ** 2 + traj["dy"] ** 2)

    traj["Velocity"] = traj["step_distance"] / traj["dt"]
    traj.loc[traj["Velocity"] > 20.0, "Velocity"] = np.nan
    traj.loc[traj["Velocity"] < 0, "Velocity"] = np.nan
    traj["Velocity"] = traj["Velocity"].fillna(0.0)

    vmin = float(traj["Velocity"].min())
    vmax = float(traj["Velocity"].max())

    # ----- 3. Fixed pitch bounds (SkillCorner-style, 105 x 68 m) -----
    # Center at (0,0): x in [-52.5, 52.5]; y in [-34, 34]
    pitch_xmin, pitch_xmax = -60, 60
    pitch_ymin, pitch_ymax = -34, 34

    # ----- 4. Build animation frames -----
    frames = []
    frames_unique = traj["frame"].unique()

    for f in frames_unique:
        trail = traj[traj["frame"] <= f]
        current = traj[traj["frame"] == f].iloc[-1]

        frames.append(
            go.Frame(
                data=[
                    # grey path line
                    go.Scatter(
                        x=trail["x"],
                        y=trail["y"],
                        mode="lines",
                        line=dict(width=2, color="lightgray"),
                        showlegend=False,
                        name="Path",
                    ),
                    # markers coloured by instantaneous speed
                    go.Scatter(
                        x=trail["x"],
                        y=trail["y"],
                        mode="markers",
                        marker=dict(
                            size=6,
                            color=trail["Velocity"],
                            colorscale="Viridis",
                            cmin=vmin,
                            cmax=vmax,
                            colorbar=dict(title="Speed (m/s)"),
                        ),
                        hovertemplate=(
                            "x: %{x:.1f}<br>"
                            "y: %{y:.1f}<br>"
                            "speed: %{marker.color:.2f} m/s<extra></extra>"
                        ),
                        showlegend=False,
                        name="Speed trail",
                    ),
                    # current position (bigger marker)
                    go.Scatter(
                        x=[current["x"]],
                        y=[current["y"]],
                        mode="markers",
                        marker=dict(
                            size=12,
                            color="black",
                            line=dict(width=1, color="white"),
                        ),
                        hovertemplate=(
                            "x: %{x:.1f}<br>y: %{y:.1f}<extra>Current position</extra>"
                        ),
                        name="Player",
                    ),
                ],
                name=str(f),
            )
        )

    # ----- 5. Base figure (first frame) -----
    first_trail = traj[traj["frame"] <= frames_unique[0]]
    first_pos = traj[traj["frame"] == frames_unique[0]].iloc[-1]

    fig = go.Figure(
        data=[
            go.Scatter(
                x=first_trail["x"],
                y=first_trail["y"],
                mode="lines",
                line=dict(width=2, color="lightgray"),
                showlegend=False,
                name="Path",
            ),
            go.Scatter(
                x=first_trail["x"],
                y=first_trail["y"],
                mode="markers",
                marker=dict(
                    size=6,
                    color=first_trail["Velocity"],
                    colorscale="Viridis",
                    cmin=vmin,
                    cmax=vmax,
                    colorbar=dict(title="Speed (m/s)"),
                ),
                hovertemplate=(
                    "x: %{x:.1f}<br>"
                    "y: %{y:.1f}<br>"
                    "speed: %{marker.color:.2f} m/s<extra></extra>"
                ),
                showlegend=False,
                name="Speed trail",
            ),
            go.Scatter(
                x=[first_pos["x"]],
                y=[first_pos["y"]],
                mode="markers",
                marker=dict(
                    size=12,
                    color="black",
                    line=dict(width=1, color="white"),
                ),
                hovertemplate=(
                    "x: %{x:.1f}<br>y: %{y:.1f}<extra>Current position</extra>"
                ),
                name="Player",
            ),
        ],
        frames=frames,
    )

    # ----- 6. Add pitch drawing as shapes -----
    # Dimensions (all approx, in meters, centered at 0,0):
    # - Full pitch: 105 x 68 -> x: [-52.5, 52.5], y: [-34, 34]
    # - Penalty box depth: 16.5; width: 40.3
    # - 6-yard box depth: 5.5; width: 18.32
    # - Centre circle radius: 9.15
    penalty_depth = 16.5
    penalty_width = 40.3 / 2
    goal_depth = 5.5
    goal_width = 18.32 / 2
    center_circle_r = 9.15

    shapes = [
        # Outer pitch
        dict(
            type="rect",
            x0=pitch_xmin,
            x1=pitch_xmax,
            y0=pitch_ymin,
            y1=pitch_ymax,
            line=dict(color="black", width=2),
            fillcolor="rgba(255,255,255,0)",
        ),
        # Halfway line
        dict(
            type="line",
            x0=0,
            x1=0,
            y0=pitch_ymin,
            y1=pitch_ymax,
            line=dict(color="black", width=1),
        ),
        # Left penalty box
        dict(
            type="rect",
            x0=pitch_xmin,
            x1=pitch_xmin + penalty_depth,
            y0=-penalty_width,
            y1=penalty_width,
            line=dict(color="black", width=1),
        ),
        # Right penalty box
        dict(
            type="rect",
            x0=pitch_xmax - penalty_depth,
            x1=pitch_xmax,
            y0=-penalty_width,
            y1=penalty_width,
            line=dict(color="black", width=1),
        ),
        # Left 6-yard box
        dict(
            type="rect",
            x0=pitch_xmin,
            x1=pitch_xmin + goal_depth,
            y0=-goal_width,
            y1=goal_width,
            line=dict(color="black", width=1),
        ),
        # Right 6-yard box
        dict(
            type="rect",
            x0=pitch_xmax - goal_depth,
            x1=pitch_xmax,
            y0=-goal_width,
            y1=goal_width,
            line=dict(color="black", width=1),
        ),
        # Centre circle
        dict(
            type="circle",
            x0=-center_circle_r,
            x1=center_circle_r,
            y0=-center_circle_r,
            y1=center_circle_r,
            line=dict(color="black", width=1),
        ),
    ]

    fig.update_layout(
        title=f"{window_seconds}-second WCS Demands Movement Sequence for Player {player_id}",
        xaxis=dict(
            range=[pitch_xmin, pitch_xmax],
            zeroline=False,
            showgrid=False,
            showticklabels=False,  
            title="Pitch X (m)",
            ticks='', 
            scaleanchor="y",
            scaleratio=1
            ),
        yaxis=dict(
            range=[pitch_ymin, pitch_ymax],
            zeroline=False,
            showgrid=False,
            showticklabels=False, 
            title="Pitch Y (m)",
            ticks=''     
        ),
        width=900,
        height=550,
        showlegend=False,
        plot_bgcolor="white",
        paper_bgcolor="white",
        shapes=shapes,
        updatemenus=[
            dict(
                type="buttons",
                showactive=False,
                y=1.08,
                x=1.0,
                xanchor="right",
                yanchor="bottom",
                buttons=[
                    dict(
                        label="Play",
                        method="animate",
                        args=[
                            None,
                            {
                                "frame": {"duration": 80, "redraw": True},
                                "fromcurrent": True,
                                "transition": {"duration": 0},
                            },
                        ],
                    ),
                    dict(
                        label="Pause",
                        method="animate",
                        args=[
                            [None],
                            {
                                "frame": {"duration": 0, "redraw": False},
                                "mode": "immediate",
                                "transition": {"duration": 0},
                            },
                        ],
                    ),
                ],
            )
        ],
        sliders=[
            {
                "active": 0,
                "y": -0.05,
                "x": 0.1,
                "len": 0.8,
                "steps": [
                    {
                        "label": str(f),
                        "method": "animate",
                        "args": [
                            [str(f)],
                            {
                                "frame": {"duration": 0, "redraw": True},
                                "mode": "immediate",
                            },
                        ],
                    }
                    for f in frames_unique
                ],
            }
        ],
    )

    return fig

from IPython.display import display, clear_output
import ipywidgets as widgets

def build_wcs_widget(tracking_df, peak_intensity, match_id, fps=10.0):
    # unique player_ids for this match
    player_options = sorted(
        peak_intensity.loc[peak_intensity["match_id"] == match_id, "player_id"].unique()
    )

    # get the available window durations based on columns in peak_intensity
    window_options = sorted(
        int(c.replace("Peak m/min ", "").replace("s", ""))
        for c in peak_intensity.columns
        if c.startswith("Peak m/min ") and c.endswith("s")
    )

    # widgets
    player_dropdown = widgets.Dropdown(
        options=player_options,
        value=player_options[0],
        description="Player ID:",
    )

    window_dropdown = widgets.Dropdown(
        options=window_options,
        value=60 if 60 in window_options else window_options[0],
        description="Window (s):",
    )

    output = widgets.Output()

    def update_plot(*args):
        with output:
            output.clear_output(wait=True)
            fig = create_wcs_movement_animation(
                tracking_df=tracking_df,
                peak_intensity=peak_intensity,
                match_id=match_id,
                player_id=player_dropdown.value,
                window_seconds=window_dropdown.value,
                fps=fps,
            )
            # IMPORTANT: only show here
            fig.show()

    # hook callbacks (only once, inside this function)
    player_dropdown.observe(update_plot, names="value")
    window_dropdown.observe(update_plot, names="value")

    # initial draw
    update_plot()

    ui = widgets.VBox([player_dropdown, window_dropdown, output])
    display(ui)
