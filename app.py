
import streamlit as st
import requests
import time
import asyncio
import aiohttp
import pandas as pd
from datetime import datetime
import json
import base64

# Page config
st.set_page_config(
    page_title="NVIDIA NIM Model Dashboard",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for clean, professional, mobile-responsive design
st.markdown("""
<style>
    /* Font and base styles */
    .stApp {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        background-color: #ffffff;
        color: #333333;
    }
    
    /* Header */
    .dashboard-header {
        font-size: 28px;
        font-weight: 700;
        color: #1a1a1a;
        margin-bottom: 20px;
        text-align: center;
    }
    
    /* Card styles */
    .metric-card {
        background: #f8f9fa;
        border-radius: 8px;
        padding: 15px;
        margin: 5px 0;
        border: 1px solid #e9ecef;
    }
    
    /* Button styles */
    .stButton > button {
        background-color: #0066cc;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 10px 20px;
        font-weight: 600;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        background-color: #0052a3;
        transform: translateY(-1px);
    }
    .stButton > button:active {
        transform: translateY(0);
    }
    
    /* Input styles */
    .stTextInput > div > div > input {
        border-radius: 6px;
        border: 1px solid #ddd;
        padding: 10px;
    }
    
    /* Table styles */
    .dataframe {
        font-size: 14px;
        border-radius: 8px;
        overflow: hidden;
    }
    .dataframe th {
        background-color: #f8f9fa;
        font-weight: 600;
        color: #495057;
        padding: 12px;
        border-bottom: 2px solid #dee2e6;
    }
    .dataframe td {
        padding: 10px 12px;
        border-bottom: 1px solid #e9ecef;
    }
    
    /* Status badges */
    .status-success {
        color: #28a745;
        font-weight: 600;
    }
    .status-error {
        color: #dc3545;
        font-weight: 600;
    }
    .status-checking {
        color: #ffc107;
        font-weight: 600;
    }
    
    /* Mobile responsive */
    @media (max-width: 768px) {
        .dashboard-header {
            font-size: 22px;
        }
        .stButton > button {
            width: 100%;
            padding: 12px;
        }
        .dataframe {
            font-size: 12px;
        }
        .dataframe th, .dataframe td {
            padding: 8px;
        }
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "api_key" not in st.session_state:
    st.session_state.api_key = ""
if "models_data" not in st.session_state:
    st.session_state.models_data = None
if "last_check" not in st.session_state:
    st.session_state.last_check = None
if "is_checking" not in st.session_state:
    st.session_state.is_checking = False

# Load API key from localStorage (via JavaScript injection)
st.markdown("""
<script>
    // Load API key from localStorage on page load
    const savedKey = localStorage.getItem('nvidia_nim_api_key');
    if (savedKey && window.location.pathname.includes('nim-model-dashboard')) {
        window.parent.postMessage({type: 'api_key', value: savedKey}, '*');
    }
    
    // Listen for API key updates
    window.addEventListener('message', function(event) {
        if (event.data.type === 'api_key_update') {
            localStorage.setItem('nvidia_nim_api_key', event.data.value);
        }
    });
</script>
""", unsafe_allow_html=True)

# Handle API key from parent (Streamlit hack)
def handle_api_key():
    if "api_key_from_js" in st.session_state:
        st.session_state.api_key = st.session_state.api_key_from_js
        st.session_state.pop("api_key_from_js")

# API Key Management Section
st.markdown('<div class="dashboard-header">🚀 NVIDIA NIM Model Dashboard</div>', unsafe_allow_html=True)

with st.expander("⚙️ API Key Settings", expanded=False):
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        api_key_input = st.text_input(
            "NVIDIA NIM API Key",
            value=st.session_state.api_key,
            type="password",
            label_visibility="collapsed",
            placeholder="Enter your NVIDIA NIM API Key"
        )
    with col2:
        if st.button("💾 Save", use_container_width=True):
            st.session_state.api_key = api_key_input
            # Save to localStorage via JavaScript
            st.markdown(f"""
            <script>
                localStorage.setItem('nvidia_nim_api_key', '{api_key_input}');
            </script>
            """, unsafe_allow_html=True)
            st.success("API Key saved!")
    with col3:
        if st.button("🗑️ Clear", use_container_width=True):
            st.session_state.api_key = ""
            st.markdown("""
            <script>
                localStorage.removeItem('nvidia_nim_api_key');
            </script>
            """, unsafe_allow_html=True)
            st.success("API Key cleared!")

# Check if API key is provided
if not st.session_state.api_key:
    st.warning("⚠️ Please enter your NVIDIA NIM API Key to start checking models.")
    st.stop()

# Headers
st.markdown("---")

# Check Button
col1, col2 = st.columns([3, 1])
with col1:
    check_button = st.button("🔍 Check All Models", use_container_width=True, disabled=st.session_state.is_checking)
with col2:
    if st.session_state.models_data is not None:
        st.metric("Last Check", st.session_state.last_check.strftime("%H:%M") if st.session_state.last_check else "Never")

if check_button:
    st.session_state.is_checking = True
    st.session_state.models_data = None
    
    # Progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Headers for API
    headers = {
        "Authorization": f"Bearer {st.session_state.api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        # Step 1: Get model list
        status_text.text("📡 Fetching model list from NVIDIA NIM...")
        models_response = requests.get("https://api.nvcf.nvidia.com/v2/nvcf/functions", headers=headers, timeout=30)
        
        if models_response.status_code != 200:
            st.error(f"❌ Failed to fetch model list: {models_response.status_code} - {models_response.text}")
            st.session_state.is_checking = False
            st.stop()
        
        models_list = models_response.json().get("functions", [])
        # Filter for NIM models (usually have specific naming pattern)
        nim_models = [m for m in models_list if "nvcf" in m.get("id", "").lower() or "nim" in m.get("name", "").lower()]
        
        # If no specific NIM models found, use all functions
        if not nim_models:
            nim_models = models_list
        
        total_models = len(nim_models)
        status_text.text(f"🔎 Found {total_models} models. Starting health checks...")
        
        # Step 2: Health check each model
        results = []
        
        async def check_model(session, model, idx, total):
            model_id = model.get("id", "unknown")
            model_name = model.get("name", model_id)
            
            try:
                start_time = time.time()
                # Send a minimal request
                payload = {
                    "model": model_id,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": 1
                }
                
                async with session.post(
                    "https://api.nvcf.nvidia.com/v2/nvcf/pexec/functions/" + model_id,
                    headers=headers,
                    json=payload,
                    timeout=30
                ) as response:
                    end_time = time.time()
                    duration_ms = (end_time - start_time) * 1000
                    
                    if response.status == 200:
                        resp_data = await response.json()
                        tokens = len(resp_data.get("choices", [{}])[0].get("message", {}).get("content", ""))
                        tokens_sec = tokens / (duration_ms / 1000) if duration_ms > 0 else 0
                        return {
                            "model": model_name,
                            "status": "✅",
                            "response_time": round(duration_ms, 2),
                            "tokens_per_sec": round(tokens_sec, 2),
                            "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "error": ""
                        }
                    else:
                        return {
                            "model": model_name,
                            "status": "❌",
                            "response_time": "-",
                            "tokens_per_sec": "-",
                            "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "error": f"HTTP {response.status}"
                        }
            except Exception as e:
                return {
                    "model": model_name,
                    "status": "❌",
                    "response_time": "-",
                    "tokens_per_sec": "-",
                    "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "error": str(e)
                }
        
        # Run async checks with limited concurrency
        async def main():
            async with aiohttp.ClientSession() as session:
                tasks = []
                for i, model in enumerate(nim_models):
                    tasks.append(check_model(session, model, i, total_models))
                    # Update progress
                    progress = int((i + 1) / total_models * 100)
                    progress_bar.progress(progress)
                    status_text.text(f"🔍 Checking model {i+1}/{total_models}...")
                    await asyncio.sleep(0.1)  # Small delay to avoid rate limit
                
                results = await asyncio.gather(*tasks)
        
        asyncio.run(main())
        
        # Store results
        st.session_state.models_data = results
        st.session_state.last_check = datetime.now()
        st.session_state.is_checking = False
        progress_bar.empty()
        status_text.empty()
        st.success(f"✅ Completed checking {len(results)} models!")
        
    except Exception as e:
        st.error(f"❌ An error occurred: {str(e)}")
        st.session_state.is_checking = False

# Display results if available
if st.session_state.models_data:
    st.markdown("---")
    
    # Convert to DataFrame
    df = pd.DataFrame(st.session_state.models_data)
    
    # Filter controls
    col1, col2 = st.columns(2)
    with col1:
        filter_status = st.selectbox(
            "Filter by Status",
            ["All", "Success (✅)", "Failed (❌)"],
            key="filter_status"
        )
    with col2:
        sort_by = st.selectbox(
            "Sort by",
            ["Response Time (Fastest)", "Tokens/sec (Fastest)", "Model Name (A-Z)", "Status"],
            key="sort_by"
        )
    
    # Apply filter
    if filter_status == "Success (✅)":
        df = df[df["status"] == "✅"]
    elif filter_status == "Failed (❌)":
        df = df[df["status"] == "❌"]
    
    # Apply sort
    if sort_by == "Response Time (Fastest)":
        df = df.sort_values("response_time", key=lambda x: pd.to_numeric(x, errors="coerce"))
    elif sort_by == "Tokens/sec (Fastest)":
        df = df.sort_values("tokens_per_sec", key=lambda x: pd.to_numeric(x, errors="coerce"), ascending=False)
    elif sort_by == "Model Name (A-Z)":
        df = df.sort_values("model")
    elif sort_by == "Status":
        df = df.sort_values("status", ascending=False)
    
    # Summary metrics
    total = len(df)
    success = len(df[df["status"] == "✅"])
    failed = len(df[df["status"] == "❌"])
    avg_time = df[df["status"] == "✅"]["response_time"].mean() if success > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Models", total)
    col2.metric("Success", success, delta=f"{success/total*100:.1f}%")
    col3.metric("Failed", failed, delta=f"{failed/total*100:.1f}%", delta_color="inverse")
    col4.metric("Avg Response Time", f"{avg_time:.0f} ms" if avg_time else "N/A")
    
    # Display table
    st.markdown("### 📊 Model Status Details")
    
    # Custom styling for the dataframe
    def style_status(val):
        if val == "✅":
            return "color: #28a745; font-weight: bold;"
        elif val == "❌":
            return "color: #dc3545; font-weight: bold;"
        return ""
    
    styled_df = df.style.applymap(style_status, subset=["status"])
    
    # Make it responsive
    st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "model": st.column_config.TextColumn("Model Name", width="medium"),
            "status": st.column_config.TextColumn("Status", width="small"),
            "response_time": st.column_config.NumberColumn("Response Time (ms)", format="%.2f"),
            "tokens_per_sec": st.column_config.NumberColumn("Tokens/sec", format="%.2f"),
            "last_check": st.column_config.TextColumn("Last Check", width="small"),
            "error": st.column_config.TextColumn("Error", width="large")
        }
    )
    
    # Mobile view: Show as cards if screen is small
    st.markdown("""
    <script>
        // Simple mobile card view toggle (optional enhancement)
        function toggleCardView() {
            const isMobile = window.innerWidth <= 768;
            // This could be enhanced to show cards on mobile
        }
        window.addEventListener('resize', toggleCardView);
    </script>
    """, unsafe_allow_html=True)

else:
    st.info("👆 Click 'Check All Models' to start checking NVIDIA NIM models.")

# Footer
st.markdown("---")
st.markdown(
    '<div style="text-align: center; color: #6c757d; font-size: 12px;">'
    'NVIDIA NIM Model Dashboard | Built with Streamlit | Data refreshed on check'
    '</div>',
    unsafe_allow_html=True
)
