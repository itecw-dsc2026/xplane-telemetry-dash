import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import csv
import io

# --- Page Configuration ---
st.set_page_config(page_title="Flight Telemetry Dashboard", layout="wide", initial_sidebar_state="collapsed")

# --- Custom X-Plane Parser ---
@st.cache_data
def parse_xplane_csv(file_bytes, filename):
    lines = file_bytes.decode('utf-8').splitlines()
    header_line = lines[2].strip()
    reader = csv.reader(io.StringIO(header_line))
    header_row = next(reader)
    
    col_indices = [i for i, h in enumerate(header_row) if i > 0 and h != '|' and h != '']
    raw_columns = [header_row[i].strip('"') for i in col_indices]
    
    seen = {}
    columns = []
    for c in raw_columns:
        if c in seen:
            seen[c] += 1
            columns.append(f"{c}_{seen[c]}")
        else:
            seen[c] = 0
            columns.append(c)
            
    data_rows = []
    for l in lines[3:]:
        if not l.strip(): continue
        r_reader = csv.reader(io.StringIO(l.strip()))
        row_vals = list(next(r_reader))
        if len(row_vals) > max(col_indices):
            vals = [row_vals[i].strip('"') for i in col_indices]
            data_rows.append(vals)
            
    df = pd.DataFrame(data_rows, columns=columns)
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        
    df['Time_mins'] = (df['_real,_time'] - df['_real,_time'].min()) / 60.0
    df['Total_FF'] = df['FF__1,_lb/h'] + df['FF__2,_lb/h']
    df['Flight_Name'] = filename
    return df

# --- UI Header ---
st.title("✈️ WSSS (Singapore Changi International Airport) to WMKK (Kuala Lumpur International Airport): Telemetry & Eco-Optimization Dashboard")
st.markdown("Upload data comma separated value files from X Plane Flight Simulator to instantly generate comparative analytics and flight deck evaluations.")

# --- File Uploader ---
uploaded_files = st.file_uploader("Drop X-Plane 12 CSV files here", accept_multiple_files=True, type=['csv'])

if uploaded_files:
    dataframes = []
    for f in uploaded_files:
        df = parse_xplane_csv(f.getvalue(), f.name)
        dataframes.append(df)
        
    master_df = pd.concat(dataframes, ignore_index=True)
    flight_names = sorted(master_df['Flight_Name'].unique())

    # --- 1. Interactive Multi-Flight Graphics (Plotly) ---
    st.subheader("📊 Dynamic Flight Profiles")
    
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        subplot_titles=("Altitude (ft MSL)", "Speed (Mach)", "Total Fuel Flow (lbs/hr)"),
                        vertical_spacing=0.08)

    for flight in flight_names:
        f_df = master_df[master_df['Flight_Name'] == flight]
        
        # Altitude
        fig.add_trace(go.Scatter(x=f_df['Time_mins'], y=f_df['___CG,ftMSL'], mode='lines', name=f"{flight} Alt"), row=1, col=1)
        # Mach
        fig.add_trace(go.Scatter(x=f_df['Time_mins'], y=f_df['_Mach,ratio'], mode='lines', name=f"{flight} Mach"), row=2, col=1)
        # Fuel Flow
        fig.add_trace(go.Scatter(x=f_df['Time_mins'], y=f_df['Total_FF'], mode='lines', name=f"{flight} FF"), row=3, col=1)

    # Add Target Lines
    fig.add_hline(y=30000, line_dash="dash", line_color="green", annotation_text="Target FL300", row=1, col=1)
    fig.add_hline(y=0.68, line_dash="dash", line_color="green", annotation_text="Eco Mach 0.68", row=2, col=1)

    fig.update_layout(height=800, hovermode="x unified", template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

    # --- 2. Flight Evaluation Engine ---
    st.subheader("⚖️ Performance Evaluation (Good vs. Bad)")
    
    eval_cols = st.columns(len(flight_names))
    for idx, flight in enumerate(flight_names):
        f_df = master_df[master_df['Flight_Name'] == flight]
        max_alt = f_df['___CG,ftMSL'].max()
        max_mach = f_df['_Mach,ratio'].max()
        fuel_burn = (f_df['Total_FF'] * f_df['_real,_time'].diff().fillna(0) / 3600.0).sum()
        landing_g = f_df[(f_df['_gear,ftagl'] < 10) & (f_df['___CG,ftMSL'] < 500)]['Gload,norml'].max()
        if pd.isna(landing_g): landing_g = f_df['Gload,norml'].max()

        with eval_cols[idx]:
            st.markdown(f"### {flight}")
            
            # Good Portions
            st.success("**The Good:**")
            if max_alt >= 29000: st.write("✅ Reached optimal thin-air cruise altitude (FL300).")
            if max_mach <= 0.69: st.write("✅ Maintained highly economical cruise speeds.")
            if landing_g < 2.0: st.write("✅ Executed a survivable, structurally sound landing.")
            if max_alt < 29000 and max_mach > 0.69 and landing_g >= 2.0: st.write("No major optimal parameters met on this run.")

            # Bad Portions
            st.error("**The Bad:**")
            if max_alt < 29000: st.write("❌ Cruised too low, suffering massive parasite drag.")
            if max_mach > 0.69: st.write("❌ Excessive speed pushed engines out of eco-band.")
            if landing_g >= 2.0: st.write(f"❌ Catastrophic/Hard landing ({landing_g:.2f} G).")
            if fuel_burn > 4800: st.write(f"❌ High carbon footprint ({fuel_burn:.0f} lbs burned).")

    # --- 3. Optimal Flight Settings ---
    st.markdown("---")
    st.subheader("🎯 Master Targets for future flights")
    st.markdown("Program your FMC and autopilot with these exact parameters to hit the **4,557 lbs** fuel-burn target.")
    
    optimal_data = {
        "Phase": ["Climb", "Cruise", "Top of Descent (T/D)", "Final Approach", "Flare / Touchdown"],
        "Altitude": ["Surface to FL300", "FL300 (30,000 ft)", "Start descent ~100nm out", "Intercept at ~3,000 ft", "30 - 50 ft AGL"],
        "Airspeed": ["250 KIAS below 10,000 ft", "Mach 0.65 - 0.68", "Mach 0.68 transitioning to KIAS", "140 - 160 KIAS (VREF)", "VREF - 5 knots"],
        "Vertical Speed (VVI)": ["+1,500 to +2,000 fpm", "0 fpm (Level Flight)", "Continuous -1,500 fpm glide", "-700 fpm on Glideslope", "-100 to -200 fpm"],
        "Engine RPM (N1 % / FF)": ["Climb Thrust (CLB) ~85% N1", "Auto-throttle Eco-Band", "Flight Idle (~20% N1)", "Spool up slightly to maintain VREF", "Cut to Idle upon flare"]
    }
    st.table(pd.DataFrame(optimal_data))
else:
    st.info("Awaiting telemetry data. Please upload your CSV files above to initialize the vibe.")