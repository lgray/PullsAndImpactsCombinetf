import uproot
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import pandas as pd
import argparse
import dash
import dash_core_components as dcc
import dash_daq as daq
import dash_html_components as html
from dash.dependencies import Input, Output

def plotImpacts(df, title, pulls=False, pullrange=[-5,5]):
    
    fig = make_subplots(rows=1,cols=2 if pulls else 1,
            horizontal_spacing=0.1, shared_yaxes=True)
    
    ndisplay = len(df)
    fig.add_trace(
        go.Scatter(
            x=np.zeros(ndisplay),
            y=df['modlabel'],
            mode="markers",
            marker=dict(color='black', size=8,),
            error_x=dict(
                array=df['impact'],
                color="black",
                thickness=1.5,
                width=5,
            ),
            name="impacts",
        ),
        row=1,col=1,
    )
    if pulls:
        fig.add_trace(
            go.Scatter(
                x=df['pull'],
                y=df['modlabel'],
                mode="markers",
                marker=dict(color='black', size=8,),
                error_x=dict(
                    array=df['constraint'],
                    color="black",
                    thickness=1.5,
                    width=5,
                ),
                name="impacts",
            ),
            row=1,col=2,
    )
    fig.update_layout(paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis_title="Impact on mass (GeV)",
        title={
            'text': title,
            'y':.999 if ndisplay > 100 else 0.98,
            'x': 0.5,
            'xanchor': 'center',
            'yanchor': 'top'},
        margin=dict(l=20,r=20,t=50,b=20),
        xaxis=dict(range=[-25, 25],
                showgrid=True, gridwidth=2,gridcolor='LightPink',
                zeroline=True, zerolinewidth=4, zerolinecolor='Gray',
                tickmode='linear',
                tick0=0.,
                dtick=5
            ),
        yaxis=dict(range=[-1, ndisplay]),
        showlegend=False,
        height=100+ndisplay*21.5,width=800,
    )
    if pulls:
        fig.update_layout(
            xaxis2=dict(range=pullrange,
                    showgrid=True, gridwidth=2,gridcolor='LightBlue',
                    zeroline=True, zerolinewidth=4, zerolinecolor='Gray',
                    tickmode='linear',
                    tick0=0.,
                    dtick=1 if pullrange[1]-pullrange[0] > 2.5 else 0.5,
                ),
            xaxis2_title="pull+constraint",
            yaxis2=dict(range=[-1, ndisplay]),
            yaxis2_visible=False,
        )
    return fig

def readFitInfoFromFile(filename, group=False, sort=None, ascending=True):
    rf = uproot.open(filename)
    name = "nuisance_group_impact_nois" if group else "nuisance_impact_nois"
    
    tree = rf["fitresults"]
    impactHist= rf[name]
    impactVal = impactHist.to_numpy()[0][0,:]
    tot = tree[impactHist.axis(0).labels()[0]+"_err"].array(library="np")
    ylabels = np.array(impactHist.axis(1).labels())
    
    pulls = np.zeros(len(impactVal))
    constraints = np.zeros(len(impactVal))
    if not group:
        pulls = np.array([tree[k].array()[0] for k in ylabels])
        constraints = np.array([tree[k+"_err"].array()[0] for k in ylabels])
    
    idx = np.argsort(np.abs(impactVal))
    impacts = np.append(impactVal[idx]*100, tot*100)
    labels = np.append(ylabels[idx], "Total")
    modlabel = labels
    pulls = np.append(pulls[idx], 0)
    constraints = np.append(constraints[idx], 0)
    neg = ["-"+x for x in modlabel[impacts<0]]
    modlabel[impacts<0] = neg
    df = pd.DataFrame(np.array((pulls, np.abs(impacts), constraints), dtype=np.float64).T, columns=["pull", "impact", "constraint"])
    df.insert(0, "label", labels)
    df.insert(0, "modlabel", modlabel)
    if sort:
        df = df.sort_values(by=sort, ascending=ascending)
    return df

def parseArgs():
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--inputFile", 
        default="/Users/kenneth/cernbox/CombineStudies/WGen/etal_ptl_smear_unrolled_scetlib/fitresults_123456789.root", 
        help="fitresults output ROOT file from combinetf")
    parser.add_argument("-s", "--sort", default="impact", type=str, choices=["label", "pull", "constraint", "impact"], help="Sort mode for nuisances")
    parser.add_argument("-d", "--sortDescending", dest='ascending', action='store_false', help="Sort mode for nuisances")
    parser.add_argument("-g", "--group", action='store_true', help="Show impacts of groups")
    parsers = parser.add_subparsers(dest='mode')
    interactive = parsers.add_parser("interactive", help="Launch and interactive dash session")
    interactive.add_argument("-i", "--interface", default="localhost", help="The network interface to bind to.")
    output = parsers.add_parser("output", help="Produce plots as output (not interactive)")
    output.add_argument("-o", "--outputFile", default="test.html", type=str, help="Output file (extension specifies if html or pdf/png)")
    output.add_argument("-n", "--num", default=20, type=str, help="Number of nuisances to plot")
    output.add_argument("--noPulls", action='store_true', help="Don't show pulls (not defined for groups)")
    output.add_argument("-t", "--title", type=str, default="Mass impact", help="Title of output plot")
    
    return parser.parse_args()

app = dash.Dash(__name__)

@app.callback(
    Output("scatter-plot", "figure"), 
    [Input("maxShow", "value")],
    [Input("sortBy", "value")],
    [Input("sortDescending", "on")],
    [Input("filterLabels", "value")],
    [Input("groups", "on")],
)
def draw_figure(maxShow, sortBy, sortDescending, filterLabels, groups):
    df = groupsdataframe if groups else dataframe
    df = df[0 if not maxShow else -1*maxShow:].copy()
    df = df.sort_values(by=sortBy, ascending=sortDescending)
    if filterLabels:
        filt = np.full(len(df["label"]), False)
        for label in filterLabels.split(","):
            filt = filt | (df["label"].str.find(label.strip()) >= 0)
        df = df[filt]
    return plotImpacts(df, title="Contribution to uncertainty in mW", pulls=not groups, pullrange=[-5,5])

dataframe = pd.DataFrame()
groupsdataframe = pd.DataFrame()

if __name__ == '__main__':
    args = parseArgs()
    dataframe = readFitInfoFromFile(args.inputFile, False, sort=args.sort, ascending=args.ascending)
    groupsdataframe = readFitInfoFromFile(args.inputFile, True, sort=args.sort, ascending=args.ascending)
    if args.mode == "interactive":
        app.layout = html.Div([
                dcc.Input(
                    id="maxShow", type="number", placeholder="maxShow",
                    min=0, max=10000, step=1,
                ),
                dcc.Input(
                    id="filterLabels", type="text", placeholder="filter labels (comma-separated list)",
					style={
						'width': '25%'
					},
                ),
                html.Br(),
                html.Label('Sort by'),
                dcc.Dropdown(
                    id='sortBy',
                    options=[{'label' : v, "value" : v.lower()} for v in ["Impact", "Pull", "Constraint", "Label"]
                    ],
                    placeholder='select sort criteria...',
					style={
						'width': '25%'
					},
                    value=args.sort
                ),
                daq.BooleanSwitch('sortDescending', label="Decreasing order", labelPosition="top", on=True),
                daq.BooleanSwitch('groups', label="Show nuisance groups", labelPosition="top", on=False),
                dcc.Graph(id="scatter-plot", style={'width': '100%', 'height': '100%'}),
            ],
            style={
                "width": "100%",
                "height": "100%",
                "display": "inline-block",
                "padding-top": "10px",
                "padding-left": "1px",
                "overflow": "hidden"
            },
        )

        app.run_server(debug=True, port=3389, host=args.interface)
    elif args.mode == 'output':
        df = dataframe if not args.group else groupsdataframe
        fig = plotImpacts(df[:-1], title=args.title, pulls=not args.noPulls and not args.group, pullrange=[-5,5])
        if ".html" in args.outputFile[-5:]:
            fig.write_html(args.outputFile)
        else:
            fig.write_image(args.outputFile)
    else:
        raise ValueError("Must select mode 'interactive' or 'output'")
