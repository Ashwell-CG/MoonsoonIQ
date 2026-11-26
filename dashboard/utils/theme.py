"""Shared visual theme for the MonsoonIQ Streamlit dashboard.

Inspired by modern, airy meteorological intelligence interfaces (Geoaether reference).
Features a clean light aesthetic: soft-tinted sky/slate backdrop, pure white cards
with soft shadows, refined typography, and high-contrast accents.
"""

from __future__ import annotations

import streamlit as st


def apply_theme() -> None:
    """Apply the dashboard-wide visual system."""
    st.markdown(
        """
        <style>
        :root {
            --miq-bg: #F8FAFC;
            --miq-canvas: #F1F5F9;
            --miq-panel: #FFFFFF;
            --miq-panel-raised: #FFFFFF;
            --miq-panel-hover: #F8FAFC;
            --miq-line: #E2E8F0;
            --miq-line-subtle: #EDF2F7;
            --miq-text: #0F172A;
            --miq-text-muted: #475569;
            --miq-muted: #64748B;
            --miq-subtle: #94A3B8;
            --miq-cyan: #0284C7;
            --miq-cyan-light: #E0F2FE;
            --miq-blue: #0369A1;
            --miq-green: #10B981;
            --miq-amber: #F59E0B;
            --miq-red: #EF4444;
            --miq-radius: 16px;
            --miq-radius-sm: 10px;
            --miq-shadow-sm: 0 1px 3px rgba(15, 23, 42, 0.04), 0 1px 2px rgba(15, 23, 42, 0.02);
            --miq-shadow: 0 4px 14px -2px rgba(15, 23, 42, 0.05), 0 2px 6px -1px rgba(15, 23, 42, 0.02);
            --miq-shadow-md: 0 10px 25px -4px rgba(15, 23, 42, 0.08), 0 4px 8px -2px rgba(15, 23, 42, 0.03);
        }

        /* ---------------- Global App Backdrop ---------------- */
        html, body, [class*="stApp"] {
            background-color: var(--miq-bg);
            color: var(--miq-text);
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
                         "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            -webkit-font-smoothing: antialiased;
        }

        .stApp {
            background:
                radial-gradient(ellipse at 88% -15%, rgba(2, 132, 199, 0.09) 0%, transparent 48%),
                radial-gradient(ellipse at 12% 105%, rgba(56, 189, 248, 0.07) 0%, transparent 42%),
                #F8FAFC;
        }

        [data-testid="stHeader"] {
            background: rgba(248, 250, 252, 0.85);
            backdrop-filter: blur(8px);
            border-bottom: 1px solid rgba(226, 232, 240, 0.7);
        }

        [data-testid="stToolbar"] { right: 1.25rem; }

        .main .block-container {
            max-width: 1640px;
            padding: 1.75rem clamp(1.2rem, 3.2vw, 3.2rem) 3.5rem;
        }

        /* Typography */
        h1, h2, h3, h4, h5, h6 {
            color: var(--miq-text);
            letter-spacing: -0.025em;
            font-weight: 700;
        }
        h1 { font-size: 2rem; font-weight: 750; }
        h2 { font-size: 1.45rem; font-weight: 700; }
        h3 { font-size: 1.15rem; font-weight: 650; }
        p, li { color: var(--miq-text-muted); line-height: 1.55; }
        [data-testid="stCaptionContainer"] { color: var(--miq-muted); font-size: 0.8rem; }
        hr { border-color: var(--miq-line); margin: 1.25rem 0; }

        /* ---------------- Sidebar Styling ---------------- */
        section[data-testid="stSidebar"] {
            background: #FFFFFF !important;
            border-right: 1px solid var(--miq-line) !important;
            box-shadow: 2px 0 12px rgba(15, 23, 42, 0.02) !important;
        }
        section[data-testid="stSidebar"][data-collapsed="false"] {
            min-width: min(21rem, 86vw) !important;
            max-width: min(21rem, 86vw) !important;
        }

        section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
            padding: 1.35rem 1.15rem 2rem;
            background: #FFFFFF !important;
        }

        @media screen {
            section[data-testid="stSidebar"],
            section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
                max-height: 100vh;
                max-height: 100dvh;
            }
            section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
                box-sizing: border-box;
                overflow-y: auto;
                overscroll-behavior-y: contain;
                scrollbar-color: #718995 #f1f5f9;
            }
        }

        section[data-testid="stSidebar"] hr {
            border-color: var(--miq-line) !important;
            margin: 0.9rem 0 !important;
        }

        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {
            margin: 1.1rem 0 0.45rem;
            color: var(--miq-muted);
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.09em;
            text-transform: uppercase;
        }

        /* Sidebar Brand */
        .miq-brand {
            padding: 0.2rem 0.15rem 1.15rem;
            border-bottom: 1px solid var(--miq-line);
            margin-bottom: 0.4rem;
        }
        .miq-brand-mark {
            color: var(--miq-text);
            font-size: 1.25rem;
            font-weight: 800;
            letter-spacing: -0.035em;
        }
        .miq-brand-subtitle {
            margin-top: 0.25rem;
            color: var(--miq-text-muted);
            font-size: 0.8125rem;
            line-height: 1.45;
        }

        /* Sidebar Navigation Radio Buttons (Pill Nav) */
        section[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] {
            gap: 0.25rem;
        }

        section[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label {
            min-height: 2.35rem;
            padding: 0.5rem 0.85rem !important;
            border-radius: var(--miq-radius-sm);
            color: var(--miq-text-muted) !important;
            background: transparent !important;
            transition: all 0.15s ease-in-out !important;
            cursor: pointer !important;
            border: 1px solid transparent !important;
            display: flex !important;
            align-items: center !important;
            width: 100% !important;
            margin-bottom: 2px !important;
        }

        section[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label p,
        section[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label span,
        section[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label div {
            font-size: 0.84rem;
            font-weight: 550;
            color: var(--miq-text-muted);
            line-height: 1.3;
        }

        section[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:hover {
            background: #F1F5F9 !important;
        }
        section[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:hover p,
        section[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:hover span {
            color: var(--miq-text) !important;
        }

        /* Active radio pill */
        section[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) {
            background: #E0F2FE !important;
            border-color: #BAE6FD !important;
        }
        section[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) p,
        section[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) span {
            color: #0284C7 !important;
            font-weight: 700 !important;
        }

        /* Selectboxes & Dropdowns */
        section[data-testid="stSidebar"] [data-testid="stSelectbox"] label,
        section[data-testid="stSidebar"] [data-testid="stSlider"] label {
            color: var(--miq-muted) !important;
            font-size: 0.74rem !important;
            font-weight: 650 !important;
            margin-bottom: 0.2rem;
        }

        section[data-testid="stSidebar"] [data-testid="stSelectbox"] div[data-baseweb="select"],
        section[data-testid="stSidebar"] [data-testid="stSelectbox"] div[data-baseweb="select"] > div {
            background-color: #FFFFFF !important;
            border: 1px solid #CBD5E1 !important;
            border-radius: var(--miq-radius-sm) !important;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03) !important;
            transition: border-color 0.15s ease, box-shadow 0.15s ease;
        }

        section[data-testid="stSidebar"] [data-testid="stSelectbox"] div[data-baseweb="select"]:hover,
        section[data-testid="stSidebar"] [data-testid="stSelectbox"] div[data-baseweb="select"] > div:hover {
            border-color: #94A3B8 !important;
        }

        section[data-testid="stSidebar"] [data-testid="stSelectbox"] div[data-baseweb="select"]:focus-within,
        section[data-testid="stSidebar"] [data-testid="stSelectbox"] div[data-baseweb="select"] > div:focus-within {
            border-color: #0284C7 !important;
            box-shadow: 0 0 0 2px rgba(2, 132, 199, 0.18) !important;
        }

        section[data-testid="stSidebar"] [data-testid="stSelectbox"] div[data-baseweb="select"] * {
            color: #0F172A !important;
            font-weight: 550 !important;
            font-size: 0.76rem !important;
        }

        section[data-testid="stSidebar"] [data-testid="stSelectbox"] svg {
            color: var(--miq-muted);
        }

        .miq-sidebar-footnote {
            padding-top: 0.85rem;
            border-top: 1px solid var(--miq-line);
            color: var(--miq-subtle);
            font-size: 0.68rem;
            line-height: 1.55;
        }
        .miq-sidebar-footnote strong {
            color: var(--miq-muted);
            font-weight: 600;
        }

        /* ---------------- Header Component ---------------- */
        .miq-header {
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            gap: 1.5rem;
            padding: 0.2rem 0 1.25rem;
            border-bottom: 1px solid var(--miq-line);
            margin-bottom: 1.25rem;
        }
        .miq-eyebrow {
            color: var(--miq-cyan);
            font-size: 0.7rem;
            font-weight: 750;
            letter-spacing: 0.14em;
            text-transform: uppercase;
        }
        .miq-title {
            margin: 0.25rem 0 0.15rem;
            color: var(--miq-text);
            font-size: clamp(1.8rem, 3.2vw, 2.35rem);
            font-weight: 800;
            letter-spacing: -0.04em;
            line-height: 1.1;
        }
        .miq-subtitle {
            margin: 0;
            color: var(--miq-muted);
            font-size: 0.92rem;
            font-weight: 450;
        }
        .miq-context {
            display: flex;
            flex-wrap: wrap;
            justify-content: flex-end;
            gap: 0.45rem;
            max-width: 460px;
        }
        .miq-context-item {
            padding: 0.38rem 0.75rem;
            border: 1px solid var(--miq-line);
            border-radius: 9999px;
            background: #FFFFFF;
            color: var(--miq-text-muted);
            font-size: 0.72rem;
            font-weight: 500;
            white-space: nowrap;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
        }
        .miq-context-item strong {
            color: var(--miq-text);
            font-weight: 650;
        }

        /* ---------------- Provenance / Alert Banner ---------------- */
        .miq-provenance {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            padding: 0.85rem 1.15rem;
            margin: 0.3rem 0 1.2rem;
            border: 1px solid #BAE6FD;
            border-left: 4px solid var(--miq-cyan);
            border-radius: 14px;
            background: linear-gradient(135deg, #F0F9FF 0%, #E0F2FE 100%);
            box-shadow: 0 2px 6px rgba(2, 132, 199, 0.04);
        }
        .miq-provenance-title {
            color: #0369A1;
            font-size: 0.82rem;
            font-weight: 700;
        }
        .miq-provenance-note {
            margin-top: 0.2rem;
            color: #334155;
            font-size: 0.73rem;
            line-height: 1.45;
        }
        .miq-status {
            flex: none;
            padding: 0.28rem 0.65rem;
            border: 1px solid rgba(2, 132, 199, 0.3);
            border-radius: 9999px;
            background: #0284C7;
            color: #FFFFFF;
            font-size: 0.64rem;
            font-weight: 750;
            letter-spacing: 0.08em;
            box-shadow: 0 1px 3px rgba(2, 132, 199, 0.25);
        }

        /* ---------------- Metric Cards ---------------- */
        .miq-metrics {
            display: grid;
            grid-template-columns: repeat(6, minmax(0, 1fr));
            gap: 0.85rem;
            margin-bottom: 1.45rem;
        }
        .miq-metric {
            min-width: 0;
            padding: 1rem 1.15rem 0.95rem;
            border: 1px solid var(--miq-line);
            border-radius: var(--miq-radius);
            background: var(--miq-panel);
            box-shadow: var(--miq-shadow);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .miq-metric:hover {
            transform: translateY(-2px);
            box-shadow: var(--miq-shadow-md);
        }
        .miq-metric-label {
            min-height: 1.6rem;
            color: var(--miq-muted);
            font-size: 0.68rem;
            font-weight: 700;
            letter-spacing: 0.06em;
            line-height: 1.3;
            text-transform: uppercase;
        }
        .miq-metric-value {
            margin-top: 0.4rem;
            color: var(--miq-text);
            font-size: clamp(1.4rem, 1.85vw, 1.85rem);
            font-variant-numeric: tabular-nums;
            font-weight: 800;
            letter-spacing: -0.035em;
            line-height: 1.05;
            white-space: nowrap;
        }
        .miq-metric-detail {
            margin-top: 0.35rem;
            color: var(--miq-subtle);
            font-size: 0.72rem;
            line-height: 1.35;
            font-weight: 500;
        }

        /* ---------------- Selected Cell Card ---------------- */
        .miq-selected-cell {
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 0.45rem 1.15rem;
            padding: 0.9rem 1.25rem;
            margin: 0.9rem 0 1.2rem;
            border: 1px solid var(--miq-line);
            border-left: 4px solid var(--miq-cyan);
            border-radius: 14px;
            background: #FFFFFF;
            box-shadow: var(--miq-shadow);
        }
        .miq-selected-title {
            color: var(--miq-cyan);
            font-size: 0.86rem;
            font-weight: 750;
        }
        .miq-selected-detail {
            color: var(--miq-text-muted);
            font-size: 0.8rem;
        }
        .miq-selected-detail strong {
            color: var(--miq-text);
            font-weight: 650;
        }

        /* ---------------- Native Streamlit Components ---------------- */
        /* Tabs */
        [data-testid="stTabs"] [role="tablist"] {
            gap: 0.5rem;
            border-bottom: 1px solid var(--miq-line);
            padding-bottom: 0.2rem;
        }
        [data-testid="stTabs"] button[role="tab"] {
            color: var(--miq-muted);
            font-weight: 550;
            font-size: 0.86rem;
            border-radius: 8px 8px 0 0;
            padding: 0.6rem 1.1rem;
            border: none;
            background: transparent;
            transition: all 0.15s ease;
        }
        [data-testid="stTabs"] button[role="tab"]:hover {
            color: var(--miq-text);
            background: #F1F5F9;
        }
        [data-testid="stTabs"] button[aria-selected="true"] {
            color: var(--miq-cyan) !important;
            font-weight: 700 !important;
            border-bottom: 2.5px solid var(--miq-cyan) !important;
            background: transparent !important;
        }

        /* Expanders */
        [data-testid="stExpander"] {
            border: 1px solid var(--miq-line);
            border-radius: 14px;
            background: #FFFFFF;
            box-shadow: var(--miq-shadow-sm);
            margin-bottom: 0.75rem;
            overflow: hidden;
        }
        [data-testid="stExpander"] details summary {
            padding: 0.75rem 1rem;
            font-weight: 650;
            color: var(--miq-text);
        }
        [data-testid="stExpander"] details summary:hover {
            color: var(--miq-cyan);
        }

        /* Streamlit Metrics */
        [data-testid="stMetric"] {
            padding: 0.9rem 1.1rem;
            border: 1px solid var(--miq-line);
            border-radius: 14px;
            background: var(--miq-panel);
            box-shadow: var(--miq-shadow-sm);
        }
        [data-testid="stMetricLabel"] {
            color: var(--miq-muted) !important;
            font-size: 0.72rem !important;
            font-weight: 700 !important;
            letter-spacing: 0.04em !important;
            text-transform: uppercase !important;
        }
        [data-testid="stMetricValue"] {
            color: var(--miq-text) !important;
            font-weight: 800 !important;
            font-size: 1.55rem !important;
            letter-spacing: -0.03em !important;
        }

        /* Plotly Charts & DataFrames Containers */
        [data-testid="stPlotlyChart"] {
            overflow: hidden;
            border: 1px solid var(--miq-line);
            border-radius: var(--miq-radius);
            background: #FFFFFF;
            box-shadow: var(--miq-shadow);
            padding: 0.65rem 0.65rem 0.25rem;
            margin-bottom: 1rem;
        }

        [data-testid="stDataFrame"] {
            overflow: hidden;
            border: 1px solid var(--miq-line);
            border-radius: 14px;
            box-shadow: var(--miq-shadow-sm);
            background: #FFFFFF;
        }

        /* Advisory State Card */
        .miq-advisory-status {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            padding: 1.1rem 1.35rem;
            margin: 0.8rem 0 1.2rem;
            border: 1px solid color-mix(in srgb, var(--miq-state) 30%, #E2E8F0);
            border-left: 4px solid var(--miq-state);
            border-radius: 14px;
            background: color-mix(in srgb, var(--miq-state) 7%, #FFFFFF);
            box-shadow: var(--miq-shadow-sm);
        }
        .miq-advisory-state {
            color: var(--miq-state);
            font-size: 1.15rem;
            font-weight: 800;
            letter-spacing: 0.03em;
        }
        .miq-advisory-context {
            color: var(--miq-text-muted);
            font-size: 0.83rem;
            font-weight: 550;
            text-align: right;
        }

        .miq-analysis-note {
            padding: 0.85rem 1.1rem;
            margin: 0.5rem 0 1.1rem;
            border: 1px solid #BAE6FD;
            border-radius: 12px;
            background: #F0F9FF;
            color: #0369A1;
            font-size: 0.8rem;
            line-height: 1.5;
            font-weight: 450;
        }

        /* Regime Summary Cards */
        .miq-regime-summary {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.75rem;
            margin-bottom: 0.85rem;
        }
        .miq-regime-card {
            padding: 0.9rem 1.05rem;
            border: 1px solid var(--miq-line);
            border-left: 3.5px solid var(--miq-regime);
            border-radius: 12px;
            background: #FFFFFF;
            box-shadow: var(--miq-shadow-sm);
        }
        .miq-regime-name {
            color: var(--miq-text);
            font-size: 0.82rem;
            font-weight: 700;
        }
        .miq-regime-meta {
            margin-top: 0.35rem;
            color: var(--miq-muted);
            font-size: 0.72rem;
            line-height: 1.4;
        }

        /* Section headings & sub-headings */
        .miq-section-heading {
            margin: 1.1rem 0 0.2rem;
            color: var(--miq-text);
            font-size: 1.15rem;
            font-weight: 700;
            letter-spacing: -0.02em;
        }
        .miq-subhead {
            margin: 1.1rem 0 0.45rem;
            color: var(--miq-muted);
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.09em;
            text-transform: uppercase;
        }
        .miq-reasoning {
            padding: 0.7rem 1.1rem 0.7rem 1.1rem;
            border: 1px solid var(--miq-line);
            border-left: 3.5px solid var(--miq-state, var(--miq-cyan));
            border-radius: 12px;
            background: #FFFFFF;
            box-shadow: var(--miq-shadow-sm);
        }
        .miq-reasoning ul { margin: 0; padding-left: 1.1rem; }
        .miq-reasoning li { margin: 0.3rem 0; font-size: 0.86rem; color: var(--miq-text-muted); }

        /* Map frame */
        iframe[title="streamlit_folium.st_folium"] {
            border: 1px solid var(--miq-line);
            border-radius: var(--miq-radius);
            box-shadow: var(--miq-shadow);
        }

        /* Native metrics: tabular figures, tighter label */
        [data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; }
        [data-testid="stAlert"] { border-radius: 12px; }

        /* ================= Atmosphere, depth & motion ================= */
        /* Drifting cloud layer behind the app (decorative, no pointer events). */
        .stApp::before {
            content: "";
            position: fixed;
            inset: 0;
            z-index: 0;
            pointer-events: none;
            background:
                radial-gradient(ellipse 380px 120px at 12% 18%, rgba(255,255,255,0.95), transparent 70%),
                radial-gradient(ellipse 520px 150px at 78% 10%, rgba(255,255,255,0.9), transparent 70%),
                radial-gradient(ellipse 440px 130px at 55% 62%, rgba(224,242,254,0.7), transparent 70%);
            background-repeat: no-repeat;
            animation: miq-drift 90s ease-in-out infinite alternate;
        }
        @keyframes miq-drift {
            from { transform: translate3d(-2%, 0, 0); }
            to   { transform: translate3d(3%, 1.5%, 0); }
        }
        [data-testid="stAppViewContainer"] { position: relative; z-index: 1; }

        /* Page transition */
        .main .block-container { animation: miq-rise 0.55s cubic-bezier(.2,.7,.2,1) both; }
        @keyframes miq-rise {
            from { opacity: 0; transform: translateY(10px); }
            to   { opacity: 1; transform: none; }
        }

        /* Hero header with sky depth + light rain streaks */
        .miq-header {
            position: relative;
            overflow: hidden;
            isolation: isolate;
            padding: 1.5rem 1.75rem;
            border: 1px solid #BAE6FD;
            border-radius: 20px;
            background: linear-gradient(160deg, #FFFFFF 0%, #F0F9FF 55%, #E0F2FE 100%);
            box-shadow: var(--miq-shadow), inset 0 1px 0 #FFFFFF;
        }
        .miq-header > * { position: relative; z-index: 2; }
        .miq-sky { position: absolute; inset: 0; z-index: 0; pointer-events: none; }
        .miq-cloud {
            position: absolute;
            border-radius: 9999px;
            background: rgba(255,255,255,0.85);
            filter: blur(14px);
            box-shadow: 40px 12px 0 -6px rgba(255,255,255,0.85), -36px 10px 0 -8px rgba(255,255,255,0.8);
            animation: miq-float 26s ease-in-out infinite alternate;
        }
        .miq-cloud.c1 { width: 150px; height: 46px; right: 8%; top: -10px; }
        .miq-cloud.c2 { width: 110px; height: 34px; right: 34%; bottom: -8px; animation-duration: 34s; opacity: .8; }
        @keyframes miq-float { to { transform: translateX(-34px); } }
        .miq-rain {
            position: absolute; inset: 0; opacity: 0.5;
            background-image: repeating-linear-gradient(105deg, transparent 0 14px, rgba(2,132,199,0.16) 14px 15px);
            background-size: 120px 120px;
            -webkit-mask-image: linear-gradient(90deg, transparent 35%, #000 100%);
                    mask-image: linear-gradient(90deg, transparent 35%, #000 100%);
            animation: miq-rain 2.4s linear infinite;
        }
        @keyframes miq-rain { to { background-position: -30px 120px; } }

        /* 3D depth on KPI cards (staggered entry + tilt on hover) */
        .miq-metrics { perspective: 900px; }
        .miq-metric {
            position: relative;
            overflow: hidden;
            animation: miq-rise 0.6s cubic-bezier(.2,.7,.2,1) both;
            transform-style: preserve-3d;
            transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
        }
        .miq-metric::before {
            content: ""; position: absolute; left: 0; top: 0; right: 0; height: 3px;
            background: linear-gradient(90deg, #0284C7, #0EA5E9);
            opacity: 0.85;
        }
        .miq-metric:nth-child(2) { animation-delay: .05s; } .miq-metric:nth-child(3) { animation-delay: .1s; }
        .miq-metric:nth-child(4) { animation-delay: .15s; } .miq-metric:nth-child(5) { animation-delay: .2s; }
        .miq-metric:nth-child(6) { animation-delay: .25s; }
        .miq-metric:hover {
            transform: translateY(-4px) rotateX(3deg) rotateY(-2deg);
            border-color: #BAE6FD;
            box-shadow: 0 18px 30px -12px rgba(2,132,199,0.22), 0 4px 8px -2px rgba(15,23,42,0.05);
        }

        /* Charts, native metrics and map fade up; charts lift gently on hover */
        [data-testid="stPlotlyChart"], [data-testid="stMetric"], iframe[title="streamlit_folium.st_folium"] {
            animation: miq-rise 0.6s cubic-bezier(.2,.7,.2,1) both;
        }
        [data-testid="stPlotlyChart"] { transition: box-shadow .25s ease, transform .25s ease; }
        [data-testid="stPlotlyChart"]:hover, [data-testid="stMetric"]:hover {
            box-shadow: var(--miq-shadow-md);
            transform: translateY(-2px);
        }
        [data-testid="stMetric"] { transition: box-shadow .25s ease, transform .25s ease; }

        /* Data-mode variants for provenance banner */
        .miq-provenance[data-status="EXPERIMENTAL"] { border-color:#FDE68A; border-left-color:#D97706; background:linear-gradient(135deg,#FFFBEB,#FEF3C7); }
        .miq-provenance[data-status="EXPERIMENTAL"] .miq-provenance-title { color:#B45309; }
        .miq-provenance[data-status="EXPERIMENTAL"] .miq-status { background:#D97706; border-color:#D97706; }
        .miq-provenance[data-status="NOT CONNECTED"] { border-color:#CBD5E1; border-left-color:#64748B; background:linear-gradient(135deg,#F8FAFC,#F1F5F9); }
        .miq-provenance[data-status="NOT CONNECTED"] .miq-provenance-title { color:#475569; }
        .miq-provenance[data-status="NOT CONNECTED"] .miq-status { background:#64748B; border-color:#64748B; }

        /* Data modes list (sidebar) */
        .miq-modes { list-style: none; margin: 0.4rem 0 0; padding: 0; }
        .miq-modes li { display:flex; align-items:center; gap:.5rem; padding:.28rem 0; font-size:.74rem; color: var(--miq-muted); }
        .miq-modes .dot { width:8px; height:8px; border-radius:50%; background:#CBD5E1; flex:none; }
        .miq-modes li.on { color: var(--miq-text); font-weight:650; }
        .miq-modes li.on .dot { background:#16A34A; box-shadow:0 0 0 3px rgba(22,163,74,.18); }
        .miq-modes small { margin-left:auto; font-size:.62rem; letter-spacing:.06em; color:var(--miq-subtle); }

        /* Sidebar select values: sized so 'District · cell_XXX · lat, lon' fits */
        section[data-testid="stSidebar"] [data-testid="stSelectbox"] input { font-size: 0.78rem !important; }

        /* Smooth dropdown/popover entry */
        [data-baseweb="popover"] { animation: miq-rise 0.18s ease-out both; }
        [data-testid="stSidebar"] [data-testid="stSelectbox"] div[data-baseweb="select"] > div { min-height: 2.5rem; }

        /* Tabs: scroll instead of wrapping on narrow screens */
        [data-testid="stTabs"] [role="tablist"] { overflow-x: auto; scrollbar-width: none; flex-wrap: nowrap; }
        [data-testid="stTabs"] [role="tablist"]::-webkit-scrollbar { display: none; }
        [data-testid="stTabs"] button[role="tab"] { white-space: nowrap; }

        /* Respect reduced motion: no ambient or entrance animation */
        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after {
                animation: none !important;
                transition: none !important;
            }
        }
        /* Mobile: drop ambient layers, keep it light */
        @media (max-width: 768px) {
            .stApp::before, .miq-rain, .miq-cloud.c2 { display: none; }
            .modebar-container { display: none !important; }
            .main h3 { font-size: 1.15rem !important; line-height: 1.25; }
            .miq-header { padding: 1.1rem 1.1rem; border-radius: 16px; }
            .miq-metric:hover { transform: none; }
        }

        /* ---------------- Responsive Rules ---------------- */
        @media (max-width: 1200px) {
            .miq-metrics { grid-template-columns: repeat(3, minmax(0, 1fr)); }
            .miq-header { align-items: flex-start; flex-direction: column; gap: 0.9rem; }
            .miq-context { justify-content: flex-start; }
        }

        @media (max-width: 680px) {
            .main .block-container { padding: 1.25rem 0.9rem 2.25rem; }
            .miq-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.55rem; }
            .miq-metric { padding: 0.8rem 0.85rem; }
            .miq-metric-value { font-size: 1.35rem; }
            .miq-provenance { align-items: flex-start; flex-direction: column; gap: 0.5rem; }
            .miq-regime-summary { grid-template-columns: 1fr; }
            .miq-advisory-status { align-items: flex-start; flex-direction: column; gap: 0.4rem; }
            .miq-advisory-context { text-align: left; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
