# app.py
# Dash dashboard for NHANES (DEMO_L + BMX_L) similar to your screenshot layout

import pandas as pd
import numpy as np

from dash import Dash, html, dcc, Input, Output
import plotly.express as px

# -----------------------------
# 1) LOAD + PREP NHANES DATA
# -----------------------------
# ✅ Update these paths to YOUR laptop paths
BMX_PATH  = r"C:\Users\User\Desktop\Alatoo university CS\Term1 2025-2026\Data visualisation\NHANES\BMX_L.xpt"
DEMO_PATH = r"C:\Users\User\Desktop\Alatoo university CS\Term1 2025-2026\Data visualisation\NHANES\DEMO_L.xpt"

demo = pd.read_sas(DEMO_PATH, format="xport")
bmx  = pd.read_sas(BMX_PATH,  format="xport")

df = pd.merge(demo, bmx, on="SEQN", how="inner")

# Keep only what we need
df = df[[
    "SEQN",
    "RIDAGEYR",   # age
    "RIAGENDR",   # sex
    "RIDRETH3",   # ethnicity
    "INDFMPIR",   # PIR (SES)
    "BMXBMI",     # BMI
    "BMXWT",      # weight
    "BMXHT"       # height
]].copy()

# Rename for simplicity
df.rename(columns={
    "RIDAGEYR": "age",
    "RIAGENDR": "sex_code",
    "RIDRETH3": "race_eth",
    "INDFMPIR": "pir",
    "BMXBMI": "bmi",
    "BMXWT": "weight_kg",
    "BMXHT": "height_cm"
}, inplace=True)

df["sex"] = df["sex_code"].map({1: "Male", 2: "Female"})
df = df.dropna(subset=["age", "sex", "bmi"]).copy()

# Optional: make PIR groups (quartiles) for filtering/plots
df_ses = df.dropna(subset=["pir"]).copy()
if len(df_ses) > 0:
    df_ses["pir_group"] = pd.qcut(
        df_ses["pir"],
        q=4,
        labels=["Lowest SES", "Lower-middle SES", "Upper-middle SES", "Highest SES"]
    )

# Age groups for heatmap
bins = [0, 18, 30, 45, 60, 75, 120]
labels = ["0–17", "18–29", "30–44", "45–59", "60–74", "75+"]
df["age_group"] = pd.cut(df["age"], bins=bins, labels=labels, right=False)

# Obesity flag
df["obese"] = (df["bmi"] >= 30).astype(int)

# -----------------------------
# 2) DASH APP LAYOUT
# -----------------------------
app = Dash(__name__)
app.title = "NHANES BMI Dashboard"

sex_options = [{"label": "All", "value": "All"}] + [{"label": s, "value": s} for s in sorted(df["sex"].dropna().unique())]

min_age = int(np.nanmin(df["age"]))
max_age = int(np.nanmax(df["age"]))

pir_group_options = [{"label": "All", "value": "All"}]
if "pir_group" in df_ses.columns:
    pir_group_options += [{"label": g, "value": g} for g in df_ses["pir_group"].dropna().astype(str).unique()]

app.layout = html.Div(
    style={"fontFamily": "Arial", "margin": "18px"},
    children=[
        html.H2("NHANES 2021–2023: Demographic & Anthropometric Dashboard", style={"textAlign": "center"}),

        # Controls row
        html.Div(
            style={"display": "flex", "gap": "18px", "alignItems": "center", "justifyContent": "center", "flexWrap": "wrap"},
            children=[
                html.Div([
                    html.Label("Sex"),
                    dcc.Dropdown(id="sex_dd", options=sex_options, value="All", clearable=False, style={"width": "220px"})
                ]),
                html.Div([
                    html.Label("Age range"),
                    dcc.RangeSlider(
                        id="age_slider",
                        min=min_age, max=max_age,
                        value=[max(min_age, 18), min(max_age, 80)],
                        step=1,
                        marks={min_age: str(min_age), 18: "18", 30: "30", 45: "45", 60: "60", 75: "75", max_age: str(max_age)}
                    )
                ], style={"width": "520px", "maxWidth": "90vw"}),
                html.Div([
                    html.Label("PIR group (SES)"),
                    dcc.Dropdown(id="pir_dd", options=pir_group_options, value="All", clearable=False, style={"width": "260px"})
                ]),
            ]
        ),

        html.Hr(),

        # Top row: two donut/pie-like charts (similar layout to your screenshot)
        html.Div(
            style={"display": "flex", "gap": "18px", "justifyContent": "center", "flexWrap": "wrap"},
            children=[
                html.Div([dcc.Graph(id="fig_obesity_share")], style={"flex": "1", "minWidth": "420px"}),
                html.Div([dcc.Graph(id="fig_sex_share")], style={"flex": "1", "minWidth": "420px"}),
            ]
        ),

        # Middle row: bar chart
        html.Div(
            style={"display": "flex", "justifyContent": "center"},
            children=[html.Div([dcc.Graph(id="fig_bmi_by_age_sex")], style={"width": "100%", "maxWidth": "1100px"})]
        ),

        # Bottom row: heatmap + scatter
        html.Div(
            style={"display": "flex", "gap": "18px", "justifyContent": "center", "flexWrap": "wrap"},
            children=[
                html.Div([dcc.Graph(id="fig_obesity_heatmap")], style={"flex": "1", "minWidth": "520px"}),
                html.Div([dcc.Graph(id="fig_age_bmi_scatter")], style={"flex": "1", "minWidth": "520px"}),
            ]
        ),

        html.Div(
            style={"textAlign": "center", "fontSize": "12px", "opacity": 0.8, "marginTop": "10px"},
            children="Controls filter all plots simultaneously (Sex, Age range, and PIR quartile group when available)."
        )
    ]
)

# -----------------------------
# 3) CALLBACKS
# -----------------------------
@app.callback(
    Output("fig_obesity_share", "figure"),
    Output("fig_sex_share", "figure"),
    Output("fig_bmi_by_age_sex", "figure"),
    Output("fig_obesity_heatmap", "figure"),
    Output("fig_age_bmi_scatter", "figure"),
    Input("sex_dd", "value"),
    Input("age_slider", "value"),
    Input("pir_dd", "value"),
)
def update_all(sex_value, age_range, pir_group_value):
    lo, hi = age_range

    # Base filtered df (no PIR filter yet)
    d = df[(df["age"] >= lo) & (df["age"] <= hi)].copy()
    if sex_value != "All":
        d = d[d["sex"] == sex_value].copy()

    # PIR filtering requires df_ses (since df may have missing PIR)
    d_ses = df_ses[(df_ses["age"] >= lo) & (df_ses["age"] <= hi)].copy()
    if sex_value != "All":
        d_ses = d_ses[d_ses["sex"] == sex_value].copy()
    if pir_group_value != "All" and "pir_group" in d_ses.columns:
        d_ses = d_ses[d_ses["pir_group"].astype(str) == str(pir_group_value)].copy()

    # --- Chart 1: Obesity share (donut) ---
    # Use d (BMI always present)
    obese_counts = d["obese"].value_counts(dropna=False).reindex([1, 0], fill_value=0)
    pie1_df = pd.DataFrame({
        "Status": ["Obese (BMI ≥ 30)", "Not obese (BMI < 30)"],
        "Count": [int(obese_counts.loc[1]), int(obese_counts.loc[0])]
    })
    fig_obesity_share = px.pie(
        pie1_df, names="Status", values="Count", hole=0.55,
        title="Obesity Share (Filtered Sample)"
    )
    fig_obesity_share.update_traces(textinfo="percent+label")

    # --- Chart 2: Sex share (donut) ---
    sex_counts = d["sex"].value_counts().reset_index()
    sex_counts.columns = ["Sex", "Count"]
    fig_sex_share = px.pie(
        sex_counts, names="Sex", values="Count", hole=0.55,
        title="Sex Composition (Filtered Sample)"
    )
    fig_sex_share.update_traces(textinfo="percent+label")

    # --- Chart 3: BMI by age group and sex (grouped bar of mean BMI) ---
    # Use d
    bar_df = (d.dropna(subset=["age_group", "sex", "bmi"])
              .groupby(["age_group", "sex"])["bmi"]
              .mean()
              .reset_index())
    fig_bmi_by_age_sex = px.bar(
        bar_df, x="age_group", y="bmi", color="sex", barmode="group",
        title="Mean BMI by Age Group and Sex",
        labels={"age_group": "Age group", "bmi": "Mean BMI (kg/m²)"}
    )

    # --- Chart 4: Obesity prevalence heatmap (age_group × sex) ---
    # Use d
    pivot = (d.dropna(subset=["age_group", "sex"])
             .groupby(["sex", "age_group"])["obese"]
             .mean()
             .unstack())
    # Ensure consistent columns order
    pivot = pivot.reindex(columns=labels)
    heat_vals = (pivot * 100).round(1)

    fig_obesity_heatmap = px.imshow(
        heat_vals,
        text_auto=True,
        aspect="auto",
        title="Obesity Prevalence (%) by Age Group and Sex",
        labels={"x": "Age group", "y": "Sex", "color": "Prevalence (%)"}
    )

    # --- Chart 5: Age vs BMI scatter (use SES-filtered if PIR selected) ---
    # If user picked a PIR group, show d_ses scatter; else show d
    d_scatter = d_ses if (pir_group_value != "All" and len(d_ses) > 0) else d
    fig_age_bmi_scatter = px.scatter(
        d_scatter,
        x="age", y="bmi", color="sex",
        opacity=0.45,
        title="Age vs BMI (Interactive)",
        labels={"age": "Age (years)", "bmi": "BMI (kg/m²)"}
    )

    # Minor layout polish
    for f in [fig_obesity_share, fig_sex_share, fig_bmi_by_age_sex, fig_obesity_heatmap, fig_age_bmi_scatter]:
        f.update_layout(margin=dict(l=30, r=30, t=60, b=30))

    return fig_obesity_share, fig_sex_share, fig_bmi_by_age_sex, fig_obesity_heatmap, fig_age_bmi_scatter


# -----------------------------
# 4) RUN
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True, port=8050)
