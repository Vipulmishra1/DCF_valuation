

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="DCF Valuation", layout="centered")

st.title("📈 Discounted Cash Flow (DCF) Valuation App")

# Input Ticker
ticker = st.text_input("Enter Stock Ticker (e.g., AAPL, TSLA, MSFT)", value="AAPL").upper()

if ticker:
    try:
        company = yf.Ticker(ticker)
        income = company.financials.T
        balance = company.balance_sheet.T
        cashflow = company.cashflow.T

        # Extract revenue
        revenue_series = income['Total Revenue'].dropna()
        last_revenue = revenue_series.iloc[-1] / 1e6  # Convert to millions

        st.success(f"Latest Revenue for {ticker}: ${last_revenue:,.2f}M")

        # Sidebar assumptions
        st.sidebar.header("Assumptions")
        growth_rate = st.sidebar.slider("Revenue Growth Rate", 0.01, 0.20, 0.05, 0.01)
        ebit_margin = st.sidebar.slider("EBIT Margin", 0.05, 0.40, 0.25, 0.01)
        tax_rate = st.sidebar.slider("Tax Rate", 0.00, 0.50, 0.21, 0.01)
        capex_pct = st.sidebar.slider("CapEx (% of Revenue)", 0.01, 0.20, 0.06, 0.01)
        dep_pct = st.sidebar.slider("Depreciation (% of Revenue)", 0.01, 0.20, 0.05, 0.01)
        nwc_pct = st.sidebar.slider("Change in NWC (% of Revenue)", 0.00, 0.10, 0.02, 0.005)
        discount_rate = st.sidebar.slider("Discount Rate", 0.05, 0.15, 0.08, 0.005)
        terminal_growth = st.sidebar.slider("Terminal Growth Rate", 0.00, 0.05, 0.025, 0.005)

        # Forecast years
        years = [2024, 2025, 2026, 2027, 2028]

        # Build projections
        fcf_data = []
        for i, year in enumerate(years):
            revenue = last_revenue * ((1 + growth_rate) ** (i + 1))
            ebit = revenue * ebit_margin
            tax = ebit * tax_rate
            nopat = ebit - tax
            depreciation = revenue * dep_pct
            capex = revenue * capex_pct
            nwc_change = revenue * nwc_pct
            fcf = nopat + depreciation - capex - nwc_change
            fcf_data.append({
                'Year': year,
                'Revenue (M)': revenue,
                'EBIT (M)': ebit,
                'NOPAT (M)': nopat,
                'Depreciation (M)': depreciation,
                'CapEx (M)': capex,
                '∆NWC (M)': nwc_change,
                'FCF (M)': fcf
            })

        projections = pd.DataFrame(fcf_data)
        projections['Discount Factor'] = [(1 / (1 + discount_rate) ** (i + 1)) for i in range(len(years))]
        projections['Discounted FCF (M)'] = projections['FCF (M)'] * projections['Discount Factor']

        # Terminal value
        tv = projections['FCF (M)'].iloc[-1] * (1 + terminal_growth) / (discount_rate - terminal_growth)
        tv_disc = tv / ((1 + discount_rate) ** len(years))

        # EV
        enterprise_value = projections['Discounted FCF (M)'].sum() + tv_disc

        st.subheader("💰 Projected Free Cash Flows")
        st.dataframe(projections.style.format("{:,.2f}"))

        st.metric(label="📌 Estimated Enterprise Value", value=f"${enterprise_value:,.2f}M")

        # Sensitivity Table
        st.subheader("📊 Sensitivity Analysis (EV in $B)")

        discounts = np.arange(0.07, 0.105, 0.005)
        growths = np.arange(0.01, 0.045, 0.005)
        sensitivity = pd.DataFrame(index=[f"{d:.3f}" for d in discounts],
                                   columns=[f"{g:.3f}" for g in growths])

        for d in discounts:
            for g in growths:
                tv = projections['FCF (M)'].iloc[-1] * (1 + g) / (d - g)
                tv_disc = tv / ((1 + d) ** len(years))
                fcf_disc = sum(projections['FCF (M)'] * [(1 / (1 + d) ** (i + 1)) for i in range(len(years))])
                total_val = fcf_disc + tv_disc
                sensitivity.loc[f"{d:.3f}", f"{g:.3f}"] = round(total_val / 1000, 2)  # in Billions

        st.dataframe(sensitivity)

        # Excel Download
        st.subheader("📥 Download Valuation as Excel")
        with pd.ExcelWriter("Valuation_Output.xlsx", engine="openpyxl") as writer:
            projections.to_excel(writer, sheet_name="Projections", index=False)
            sensitivity.to_excel(writer, sheet_name="Sensitivity Table")
        with open("Valuation_Output.xlsx", "rb") as f:
            st.download_button("Download Excel File", f, file_name="Valuation_Output.xlsx")

    except Exception as e:
        st.warning(f"⚠️ Could not fetch data for {ticker}. Check ticker or financials availability.")
        st.stop()
