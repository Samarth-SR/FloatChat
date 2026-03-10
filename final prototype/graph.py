import matplotlib.pyplot as plt
import streamlit as st
import pandas as pd

def render_graph(graph_data):
    x = graph_data.get("x", [])
    title = graph_data.get("title", "")
    graph_type = graph_data.get("graph_type", "line")
    
    if x:
        x = pd.to_datetime(x)
    else:
        x = []

    fig, ax = plt.subplots()
    # plot both y1 and y2 on the same axis
    if "y1" in graph_data and "y2" in graph_data:
        y1 = graph_data.get("y1", [])
        y2 = graph_data.get("y2", [])

        ax.plot(x, y1, marker="o", label=graph_data.get("region1", "Y1"), color="tab:blue")
        ax.plot(x, y2, marker="s", linestyle="--", label=graph_data.get("region2", "Y2"), color="tab:orange")

        ax.set_xlabel(graph_data.get("xlabel", "X-axis"))
        ax.set_ylabel(f'{graph_data.get("ylabel1", "Y1")} and {graph_data.get("ylabel2", "Y2")}')
        ax.set_title(title)
        ax.legend()
    # plot single y
    else:
        y = graph_data.get("y", [])
        if graph_type == "bar":
            ax.bar(x, y)
        elif graph_type == "line":
            ax.plot(x, y)
        elif graph_type == "pie":
            fig, ax = plt.subplots()
            ax.pie(y, labels=x, autopct='%1.1f%%')
            ax.set_title(title)
        elif graph_type == "scatter":
            ax.scatter(x, y)
        elif graph_type == "hist":
            ax.hist(y, bins=10)   
        else:
            ax.plot(x, y, marker="o")
        ax.set_xlabel(graph_data.get("xlabel"))
        ax.set_ylabel(graph_data.get("ylabel"))
        ax.set_title(title)

        if graph_type not in ["pie", "hist"]: # These chart types don't have a time-based x-axis
            fig.autofmt_xdate() 

    st.pyplot(fig)