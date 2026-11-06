"""
AI Natural Language Test Automation — Streamlit Interactive Web Application.

Run with:
    streamlit run app/web_ui.py
"""
import json
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from config.settings import AppConfig, get_config
from app.runner import run_test


st.set_page_config(
    page_title="AI Natural Language Test Automation",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🤖 AI Natural Language Test Automation")
st.caption("Convert plain-English browser test cases into structured Playwright automation with verifiable PASS/FAIL evidence.")

# Sidebar Settings
with st.sidebar:
    st.header("⚙️ Execution Settings")
    llm_provider = st.selectbox(
        "LLM Provider",
        options=["mock", "gemini", "openai"],
        index=0,
        help="Use 'mock' for offline deterministic testing without API keys, or 'gemini' / 'openai' with keys configured.",
    )

    if llm_provider == "gemini":
        gemini_key = st.text_input(
            "Gemini API Key",
            type="password",
            value=os.environ.get("GEMINI_API_KEY", ""),
        )
        gemini_model = st.text_input("Gemini Model", value="gemini-2.5-flash")
    elif llm_provider == "openai":
        openai_key = st.text_input(
            "OpenAI API Key",
            type="password",
            value=os.environ.get("OPENAI_API_KEY", ""),
        )
        openai_model = st.text_input("OpenAI Model", value="gpt-4o-mini")

    st.subheader("Browser Options")
    headless = st.checkbox("Headless Browser", value=False, help="Uncheck to watch the browser actions live.")
    slow_mo = st.slider("Action Delay (ms)", min_value=0, max_value=1000, value=300, step=50, help="Slow down actions for visual inspection.")
    timeout_sec = st.number_input("Step Timeout (sec)", min_value=1, max_value=60, value=15, step=1)

    st.divider()
    st.markdown("**Safe Automation Bounds:**")
    st.markdown("- Zero `eval()` / `exec()`")
    st.markdown("- Protocol allowlist (`http`/`https` only)")
    st.markdown("- Automatic credential masking")

# Main Interface Tabs
tab_run, tab_reports, tab_architecture = st.tabs(["🚀 Run Test", "📊 Reports & Evidence", "🏗️ Architecture"])

with tab_run:
    col_url, col_preset = st.columns([3, 1])
    with col_preset:
        preset = st.selectbox(
            "Example Presets",
            options=[
                "Custom",
                "PHPTravels Demo (Public Flow)",
                "Books to Scrape (E-Commerce)",
                "Example Domain (Simple Smoke)",
                "Local Integration Test (Sample Page)",
            ],
            index=0,
        )

    preset_urls = {
        "PHPTravels Demo (Public Flow)": "https://phptravels.com/demo",
        "Books to Scrape (E-Commerce)": "https://books.toscrape.com",
        "Example Domain (Simple Smoke)": "https://example.com",
        "Local Integration Test (Sample Page)": "http://127.0.0.1:8000/sample_page.html",
    }
    preset_instructions = {
        "PHPTravels Demo (Public Flow)": "Open the PHPTravels demo page and verify the title contains 'PHPTRAVELS' and the demo access section is visible",
        "Books to Scrape (E-Commerce)": "Open the bookstore catalogue and verify the page title contains 'All products' and books are visible",
        "Example Domain (Simple Smoke)": "Open the website and verify its title contains 'Example Domain' and header is visible",
        "Local Integration Test (Sample Page)": "Open the sample page, log in with username 'admin' and password 'admin123', and verify the success message appears",
    }

    default_url = preset_urls.get(preset, "https://example.com")
    default_instruction = preset_instructions.get(preset, "Open the website and verify its title is visible")

    with col_url:
        base_url = st.text_input("Target Base URL", value=default_url, placeholder="https://example.com")

    instruction = st.text_area(
        "Plain-English Test Instruction",
        value=default_instruction,
        placeholder="e.g. Open the website, log in as customer, and verify the dashboard is shown.",
        rows=3,
    )

    with st.expander("🔒 Optional Credentials & Authentication", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            username = st.text_input("Username / Email", placeholder="demo_user@example.com")
        with c2:
            password = st.text_input("Password", type="password", placeholder="••••••••")

    credentials = {}
    if username.strip():
        credentials["username"] = username.strip()
    if password.strip():
        credentials["password"] = password.strip()

    run_btn = st.button("▶️ Execute Natural Language Test", type="primary", use_container_width=True)

    if run_btn:
        if not base_url.strip():
            st.error("Please enter a valid base URL.")
        elif not instruction.strip():
            st.error("Please provide natural language test instructions.")
        else:
            with st.spinner("🤖 Planning with LLM and executing Playwright browser actions..."):
                cfg = get_config(reload=True)
                cfg.llm_provider = llm_provider
                cfg.headless = headless
                cfg.slow_mo_ms = slow_mo
                cfg.default_timeout_ms = int(timeout_sec * 1000)

                if llm_provider == "gemini" and "gemini_key" in locals() and gemini_key:
                    cfg.gemini_api_key = gemini_key
                    cfg.gemini_model = gemini_model
                elif llm_provider == "openai" and "openai_key" in locals() and openai_key:
                    cfg.openai_api_key = openai_key
                    cfg.openai_model = openai_model

                try:
                    result = run_test(
                        instruction=instruction.strip(),
                        base_url=base_url.strip(),
                        credentials=credentials,
                        headless=headless,
                        slow_mo=slow_mo,
                        config=cfg,
                    )

                    # Display Status Metric Cards
                    st.divider()
                    m1, m2, m3, m4, m5 = st.columns(5)
                    status_colors = {
                        "PASS": "🟢 PASS",
                        "FAIL": "🔴 FAIL",
                        "ERROR": "🟠 ERROR",
                        "NEEDS_CLARIFICATION": "🔵 CLARIFICATION",
                    }
                    m1.metric("Status", status_colors.get(result.status, result.status))
                    m2.metric("Duration", f"{result.duration_sec:.2f}s")
                    m3.metric("Total Steps", result.total_steps)
                    m4.metric("Passed", result.passed_steps)
                    m5.metric("Failed", result.failed_steps)

                    if result.clarification_prompt:
                        st.info(f"ℹ️ **Clarification Required:** {result.clarification_prompt}")

                    if result.error_message and result.status in ("FAIL", "ERROR"):
                        st.error(f"⚠️ **Failure Diagnostic:** {result.error_message}")

                    # Step Details
                    if result.steps:
                        st.subheader("Step-by-Step Execution")
                        step_data = []
                        for s in result.steps:
                            step_data.append({
                                "#": s.step_number,
                                "Status": s.status,
                                "Action": s.action,
                                "Description": s.description,
                                "Target": s.target_info or "-",
                                "Value": s.input_value or "-",
                                "Duration (ms)": f"{s.duration_ms:.1f}",
                            })
                        st.dataframe(step_data, use_container_width=True)

                    # Evidence Screenshots
                    if result.screenshots:
                        st.subheader("📸 Captured Evidence Screenshots")
                        for sc in result.screenshots:
                            if Path(sc).exists():
                                st.image(sc, caption=Path(sc).name, use_column_width=True)

                    st.success(f"Report saved: reports/report_{result.run_id}.html")

                except Exception as e:
                    st.exception(e)

with tab_reports:
    st.header("Saved Test Run Reports")
    reports_dir = Path("reports")
    if reports_dir.exists():
        html_reports = sorted(reports_dir.glob("report_*.html"), key=os.path.getmtime, reverse=True)
        if html_reports:
            st.write(f"Found **{len(html_reports)}** test execution reports:")
            for r in html_reports:
                col_name, col_view = st.columns([4, 1])
                with col_name:
                    st.markdown(f"📄 **`{r.name}`**")
                with col_view:
                    with open(r, "r", encoding="utf-8") as f:
                        st.download_button("Download HTML", f.read(), file_name=r.name, mime="text/html", key=r.name)
        else:
            st.info("No reports generated yet. Execute a test in the 'Run Test' tab.")
    else:
        st.info("Reports directory does not exist yet.")

with tab_architecture:
    st.header("System Architecture")
    st.markdown("""
    The **AI Natural Language Test Automation** platform is built on 9 decoupled, verifiable architectural components:

    ```mermaid
    flowchart TD
        User["User Natural Language Instruction"] --> TestCaseInput["1. TestCaseInput"]
        TestCaseInput --> LLMPlanner["2. LLMPlanner (Gemini / OpenAI / Mock)"]
        LLMPlanner --> TestPlan["Structured JSON TestPlan"]
        TestPlan --> PlanValidator["3. PlanValidator (Allowlist, Schema, Bounds)"]
        PlanValidator --> BrowserExecutor["4. BrowserExecutor (Playwright Engine)"]
        BrowserExecutor --> SmartLocator["5. SmartLocator (Role, Text, Test-ID, Auto-fallback)"]
        BrowserExecutor --> AssertionEngine["6. AssertionEngine (Visible, Text, Title, URL)"]
        AssertionEngine --> ResultReporter["7. ResultReporter (JSON, Standalone HTML, Console)"]
        ConfigManager["8. ConfigManager (.env / Settings)"] -.-> BrowserExecutor
        SecurityManager["9. SecurityManager (Protocols, Masking, No-eval)"] -.-> PlanValidator
    ```
    """)

