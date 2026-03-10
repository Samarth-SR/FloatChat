import streamlit as st
import requests
import plotly.graph_objects as go
from streamlit_folium import st_folium
import folium
import time
from typing import List, Dict, Any

# Configuration
BACKEND_BASE = "http://localhost:8000"
TIMEOUT = 6

# Helpers to call backend
def call_backend_query(query: str) -> Dict[str, Any]:
    url = f"{BACKEND_BASE}/query"
    try:
        r = requests.post(url, json={"query": query}, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e), "mock": mock_query_response(query)}


def get_profiles_nearby(lat: float, lon: float, radius_km: float=100) -> List[Dict[str, Any]]:
    url = f"{BACKEND_BASE}/profiles/nearby"
    params = {"lat": lat, "lon": lon, "radius_km": radius_km}
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return mock_profiles_nearby(lat, lon, radius_km)


def get_profile(profile_id: str) -> Dict[str, Any]:
    url = f"{BACKEND_BASE}/profile/{profile_id}"
    try:
        r = requests.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return mock_profile(profile_id)


def compare_profiles(ids: List[str], params: List[str]) -> Dict[str, Any]:
    url = f"{BACKEND_BASE}/profiles/compare"
    try:
        r = requests.post(url, json={"ids": ids, "params": params}, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e), "mock": {"ids": ids, "params": params}}


# --- Mock data (fallback demo) ---

def mock_query_response(query: str):
    return {
        "answer": f"(mock) I understood: '{query}'. I found 3 matching profiles near equator.",
        "results": [
            {"id": "P1", "lat": 0.5, "lon": 45.0, "date": "2023-03-05"},
            {"id": "P2", "lat": -0.2, "lon": 42.0, "date": "2023-03-18"},
        ]
    }


def mock_profiles_nearby(lat, lon, rad):
    return [
        {"id": "P1", "lat": lat + 0.5, "lon": lon + 1.0, "date": "2023-03-05"},
        {"id": "P2", "lat": lat - 0.4, "lon": lon - 0.8, "date": "2023-03-18"},
    ]


def mock_profile(profile_id):
    depths = list(range(0, 1001, 10))
    temp = [20 - 0.01*d for d in depths]
    sal = [35 + 0.005*d for d in depths]
    return {"id": profile_id, "depth": depths, "temperature": temp, "salinity": sal, "lat": 0.1, "lon": 45.1, "date": "2023-03-05"}


# --- Plotting helpers ---

def plot_profile(profile: Dict[str, Any], params: List[str]=["temperature", "salinity"]):
    fig = go.Figure()
    depth = profile.get("depth")
    if not depth:
        st.warning("No depth data available for this profile")
        return None
    for p in params:
        if p in profile:
            fig.add_trace(go.Scatter(x=profile[p], y=depth, mode='lines+markers', name=p))
    fig.update_yaxes(autorange='reversed', title_text='Depth (m)')
    fig.update_xaxes(title_text='Value')
    fig.update_layout(height=500, margin=dict(l=40, r=20, t=30, b=40))
    return fig


def show_map(profiles: List[Dict[str, Any]]):
    if not profiles:
        st.info("No float locations to show")
        return
    # center map at mean coords
    mean_lat = sum([p['lat'] for p in profiles]) / len(profiles)
    mean_lon = sum([p['lon'] for p in profiles]) / len(profiles)
    m = folium.Map(location=[mean_lat, mean_lon], zoom_start=4)
    for p in profiles:
        folium.Marker([p['lat'], p['lon']], popup=f"ID: {p['id']}<br/>{p.get('date','')}").add_to(m)
    st_folium(m, width=700, height=400)


# --- Streamlit UI ---

st.set_page_config(page_title="Float Chat PoC - ARGO Data", layout="wide")
st.title("Float Chat PoC - ARGO Data")

if 'messages' not in st.session_state:
    st.session_state.messages = []

col1, col2 = st.columns([2, 1])

with col1:
    st.header("Chat")
    query = st.text_area("Ask about ARGO data (natural language)", height=100, key='query_input')
    if st.button("Send"):
        if query.strip():
            st.session_state.messages.append({"role": "user", "text": query})
            with st.spinner("Contacting backend..."):
                resp = call_backend_query(query)
                time.sleep(0.2)
            if resp.get('error'):
                st.session_state.messages.append({"role": "assistant", "text": f"Error connecting to backend: {resp['error']} (showing mock)."})
                # include mock answer if present
                if resp.get('mock'):
                    st.session_state.messages.append({"role": "assistant", "text": resp['mock']['answer']})
            else:
                # Prefer structured answer if available
                answer = resp.get('answer') or resp.get('answer_text') or str(resp)
                st.session_state.messages.append({"role": "assistant", "text": answer})
                # store results in session for quick plotting
                st.session_state._last_results = resp.get('results', [])

    # show chat history
    for msg in st.session_state.messages[::-1]:
        if msg['role'] == 'assistant':
            st.markdown(f"**Assistant:** {msg['text']}")
        else:
            st.markdown(f"**You:** {msg['text']}")

    st.markdown("---")
    st.subheader("Quick actions")
    lat = st.number_input("Lat", value=0.0, format="%.4f")
    lon = st.number_input("Lon", value=45.0, format="%.4f")
    radius = st.slider("Radius (km)", 10, 2000, 200)
    if st.button("Find nearby floats"):
        profiles = get_profiles_nearby(lat, lon, radius)
        st.session_state._last_results = profiles
        st.success(f"Found {len(profiles)} profiles")

    st.markdown("Tip: try queries like 'Show me salinity profiles near the equator in March 2023'")

with col2:
    st.header("Map")
    profiles = st.session_state.get('_last_results', [])
    show_map(profiles)

    st.markdown("---")
    st.header("Profile Viewer")
    sel_id = st.selectbox("Select profile ID", options=[p['id'] for p in profiles] if profiles else [])
    if sel_id:
        profile = get_profile(sel_id)
        fig = plot_profile(profile)
        if fig:
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.header("Compare Profiles")
    ids_text = st.text_input("Profile IDs (comma-separated)")
    params_text = st.text_input("Parameters to compare (comma-separated, e.g. salinity,temperature)")
    if st.button("Compare"):
        ids = [s.strip() for s in ids_text.split(",") if s.strip()]
        params = [s.strip() for s in params_text.split(",") if s.strip()]
        if ids and params:
            cmp = compare_profiles(ids, params)
            st.write(cmp)
        else:
            st.warning("Provide at least one profile ID and one parameter")


# Footer
st.markdown("---")
st.caption("This is a PoC frontend that expects a backend LLM/RAG service running on localhost. The code falls back to mock data if backend calls fail.")


if __name__ == '__main__':
    pass
