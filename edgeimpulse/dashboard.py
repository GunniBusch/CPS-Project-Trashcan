import os
import time
import requests
import streamlit as st
import matplotlib.pyplot as plt

API_HOST = os.environ.get('DASH_HOST', '127.0.0.1')
API_PORT = int(os.environ.get('DASH_PORT', '8008'))
BASE_URL = f"http://{API_HOST}:{API_PORT}"

st.set_page_config(page_title='Trashcan Dashboard', layout='wide')
st.title('Trashcan Dashboard')

# Sidebar: refresh + API base
st.sidebar.header('Refresh')
st.sidebar.button('Refresh now')

st.sidebar.header('API')
api_url = st.sidebar.text_input('Base URL', value=BASE_URL)

# Helper calls

def get_json(path: str, default=None):
    try:
        r = requests.get(api_url + path, timeout=2.0)
        if r.ok:
            return r.json()
    except Exception:
        return default
    return default

def get_bytes(path: str):
    try:
        r = requests.get(api_url + path, timeout=2.0)
        if r.ok:
            return r.content
    except Exception:
        return None
    return None

def post_json(path: str, payload: dict):
    try:
        r = requests.post(api_url + path, json=payload, timeout=3.0)
        if r.ok:
            return r.json()
        return {'ok': False, 'status': r.status_code, 'detail': r.text}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

# Status section
st.header('Status')
state_obj = get_json('/api/state', default={}) or {}
col1, col2, col3 = st.columns(3)
with col1:
    st.metric('State', state_obj.get('state', 'UNKNOWN'))
with col2:
    ts = state_obj.get('ts')
    ts_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts)) if ts else '-'
    st.metric('Timestamp', ts_str)
with col3:
    st.metric('Last error', state_obj.get('error', '-'))

# Control section
st.header('Controls')
cc1, cc2, cc3, cc4, cc5 = st.columns(5)
with cc1:
    start_type = st.selectbox('Start type', options=[('PLASTIC',0), ('GLAS',1), ('CAN',2)], format_func=lambda x: x[0])
    if st.button('Start cycle'):
        res = post_json('/api/control/start', {'type': start_type[1]})
        st.write(res)
with cc2:
    mtray_type = st.selectbox('mTray type', options=[('PLASTIC',0), ('GLAS',1), ('CAN',2)], key='mtray', format_func=lambda x: x[0])
    if st.button('mTray'):
        res = post_json('/api/control/mtray', {'type': mtray_type[1]})
        st.write(res)
with cc3:
    if st.button('Bottle drop (1)'):
        res = post_json('/api/control/mbottle', {'mode': 1})
        st.write(res)
with cc4:
    if st.button('Bottle init (2)'):
        res = post_json('/api/control/mbottle', {'mode': 2})
        st.write(res)
with cc5:
    if st.button('ESTOP'):
        res = post_json('/api/control/estop', {})
        st.error(res)
    if st.button('Recover'):
        res = post_json('/api/control/recover', {})
        st.write(res)

# Classification section
st.header('Last classification')
res = get_json('/api/result', default={}) or {}
left, right = st.columns([1,1])
with left:
    st.write({
        'top_label': res.get('top_label'),
        'top_score': round(res.get('top_score', 0.0), 3) if res.get('top_score') is not None else None,
        'mapped_type_id': res.get('type_id'),
        'mapped_type_name': res.get('type_name'),
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(res.get('ts', 0))) if res.get('ts') else '-'
    })
with right:
    scores = res.get('scores') or {}
    if scores:
        labels = list(scores.keys())
        values = [scores[k] for k in labels]
        fig, ax = plt.subplots(figsize=(6,3))
        ax.bar(labels, values)
        ax.set_ylim(0, 1)
        ax.set_ylabel('Score')
        ax.set_title('Class scores')
        for i, v in enumerate(values):
            ax.text(i, min(0.98, v + 0.02), f'{v:.2f}', ha='center', fontsize=8)
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)
    else:
        st.info('No scores available')

# Visualizations
st.header('Last audio segment')
cols = st.columns([1,1])
with cols[0]:
    png = get_bytes('/api/segment/wave')
    if png:
        st.image(png, caption='Waveform (daemon)')
    else:
        st.info('Waveform not available')
    wav = get_bytes('/api/segment/audio')
    if wav:
        st.audio(wav, format='audio/wav')
    else:
        st.info('Audio not available')
with cols[1]:
    spec = get_bytes('/api/segment/spec')
    if spec:
        st.image(spec, caption='Spectrogram (daemon)')
    else:
        st.info('Spectrogram not available')

st.caption('This UI drives the daemon via HTTP and visualizes its latest state and results.')
