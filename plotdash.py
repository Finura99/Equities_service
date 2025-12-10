from dash import Dash, html, dcc, Input, Output
import plotly.express as px
import pandas as pd

TRADES_DF = pd.read_csv("trades.csv")  # grabs mock data

app = Dash(__name__) 

app.layout = html.Div(
    style={
        "backgroundColor": "#0f172a",
        "color": "#f1f5f9",
        "minHeight": "100vh",
        "padding": "20px",
        "fontFamily": "system-ui",
    },
    children=[
        html.H1("My first Dash"),
        html.H2("Learning how equities work – this is cool"),
        html.H3("Preview of mock trades"),

        # Table preview (first 5 rows)
        html.Table(
            [
                html.Tr(
                    [
                        html.Th(
                            col,
                            style={"backgroundColor": "#1e293b", "padding": "8px"},
                        )
                        for col in TRADES_DF.columns
                    ]
                )
            ]
            + [
                html.Tr(
                    [
                        html.Td(
                            TRADES_DF.iloc[i][col],
                            style={"backgroundColor": "#0f172a", "padding": "6px"},
                        )
                        for col in TRADES_DF.columns
                    ]
                )
                for i in range(min(5, len(TRADES_DF)))
            ]
        ),

        html.H3("Filter trades by minimum quantity"),

        dcc.Slider(
            id="min-qty",
            min=int(TRADES_DF["qty"].min()),
            max=int(TRADES_DF["qty"].max()),
            step=50,
            value=100,
            tooltip={"placement": "bottom", "always_visible": True},
        ),

        html.Div(id="slider-value", style={"marginTop": "10px"}),

        dcc.Graph(id="notional-chart"),
    ],
)


@app.callback(
    Output("notional-chart", "figure"),
    Output("slider-value", "children"),
    Input("min-qty", "value"),
)
def update_chart(min_qty):
    filtered = TRADES_DF[TRADES_DF["qty"] >= min_qty].copy()
    filtered["notional"] = filtered["qty"] * filtered["price"]

    if filtered.empty:
        fig = px.bar(title="No trades match that filter yet")
    else:
        fig = px.bar(
            filtered,
            x="symbol",
            y="notional",
            title=f"Notional by Symbol (qty ≥ {min_qty})",
        )

    # apply dark theme to the chart
    fig.update_layout(
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0f172a",
        font_color="#f1f5f9",
    )

    label = f"Showing trades where qty ≥ {min_qty}"
    return fig, label


if __name__ == "__main__":
    app.run(debug=True)
