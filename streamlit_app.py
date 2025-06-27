import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import altair as alt
import matplotlib.pyplot as plt

st.set_page_config(page_title="DCF Valuation", layout="centered")

st.title("📈 Discounted Cash Flow (DCF) Valuation App")

@st.cache_data

def get_data(ticker):
    company = yf.Ticker(ticker)
    return company.financials.T, company.balance_sheet.T, company.cashflow.T, company.info

# Input Ticker
ticker = st.text_input("Enter Stock Ticker (e.g., AAPL, TSLA, MSFT)", value="AAPL").upper()

if ticker:
    try:
        with st.spinner("Fetching financials and calculating..."):
            income, balance, cashflow, info = get_data(ticker)

            # Company Info
            st.sidebar.markdown(f"**{info.get('longName', 'N/A')}**")
            st.sidebar.markdown(f"Sector: {info.get('sector', 'N/A')}")
            st.sidebar.markdown(f"Market Cap: ${info.get('marketCap', 0)/1e9:.2f}B")

            # Extract Revenue
            revenue_series = income['Total Revenue'].dropna()
            last_revenue = revenue_series.iloc[-1] / 1e6  # in millions

            st.success(f"Latest Revenue for {ticker}: ${last_revenue:,.2f}M")

            # Sidebar Assumptions
            st.sidebar.header("Assumptions")
            scenario = st.sidebar.selectbox("Select Scenario", ["Base", "Bull", "Bear"])

            # Default values
            growth_rate = 0.05
            ebit_margin = 0.25
            if scenario == "Bull":
                growth_rate, ebit_margin = 0.10, 0.30
            elif scenario == "Bear":
                growth_rate, ebit_margin = 0.03, 0.15

            growth_rate = st.sidebar.slider("Revenue Growth Rate", 0.01, 0.20, growth_rate, 0.01)
            ebit_margin = st.sidebar.slider("EBIT Margin", 0.05, 0.40, ebit_margin, 0.01)
            tax_rate = st.sidebar.slider("Tax Rate", 0.00, 0.50, 0.21, 0.01)
            capex_pct = st.sidebar.slider("CapEx (% of Revenue)", 0.01, 0.20, 0.06, 0.01)
            dep_pct = st.sidebar.slider("Depreciation (% of Revenue)", 0.01, 0.20, 0.05, 0.01)
            nwc_pct = st.sidebar.slider("Change in NWC (% of Revenue)", 0.00, 0.10, 0.02, 0.005)
            discount_rate = st.sidebar.slider("Discount Rate", 0.05, 0.15, 0.08, 0.005)
            terminal_growth = st.sidebar.slider("Terminal Growth Rate", 0.00, 0.05, 0.025, 0.005)

            # Forecast years
            years = list(range(2024, 2029))
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

            tv = projections['FCF (M)'].iloc[-1] * (1 + terminal_growth) / (discount_rate - terminal_growth)
            tv_disc = tv / ((1 + discount_rate) ** len(years))

            enterprise_value = projections['Discounted FCF (M)'].sum() + tv_disc

            # Charts and Tables
            st.subheader("💰 Projected Free Cash Flows")
            with st.expander("📊 See Calculation Breakdown"):
                st.dataframe(projections.style.format("{:,.2f}"))

            st.altair_chart(
                alt.Chart(projections).transform_fold(
                    ['Revenue (M)', 'FCF (M)']
                ).mark_line().encode(
                    x='Year:O',
                    y='value:Q',
                    color='key:N'
                ), use_container_width=True
            )

            st.metric(label="📌 Estimated Enterprise Value", value=f"${enterprise_value:,.2f}M")

            # Equity Value
            shares = info.get('sharesOutstanding', 0)
            cash = balance['Cash'].iloc[0] if 'Cash' in balance.columns else 0
            debt = balance['Long Term Debt'].iloc[0] if 'Long Term Debt' in balance.columns else 0
            equity_value = enterprise_value * 1e6 - debt + cash
            price_target = equity_value / shares if shares else 0

            st.metric("Estimated Equity Value", f"${equity_value / 1e9:.2f}B")
            st.metric("Estimated Price per Share", f"${price_target:.2f}")

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
                    sensitivity.loc[f"{d:.3f}", f"{g:.3f}"] = round(total_val / 1000, 2)

            st.dataframe(sensitivity)

            # Monte Carlo Simulation
            st.subheader("🎲 Monte Carlo Simulation: Enterprise Value")
            num_simulations = 1000
            np.random.seed(42)

            growth_samples = np.random.normal(growth_rate, 0.02, num_simulations)
            margin_samples = np.random.normal(ebit_margin, 0.03, num_simulations)
            ev_results = []

            for g, m in zip(growth_samples, margin_samples):
                temp_fcf = [
                    (last_revenue * ((1 + g) ** (i + 1))) * m * (1 - tax_rate) +
                    (last_revenue * ((1 + g) ** (i + 1))) * dep_pct -
                    (last_revenue * ((1 + g) ** (i + 1))) * capex_pct -
                    (last_revenue * ((1 + g) ** (i + 1))) * nwc_pct
                    for i in range(5)
                ]
                disc_fcf = sum([cf / (1 + discount_rate) ** (i + 1) for i, cf in enumerate(temp_fcf)])
                tv_sim = temp_fcf[-1] * (1 + terminal_growth) / (discount_rate - terminal_growth)
                tv_disc_sim = tv_sim / ((1 + discount_rate) ** 5)
                ev_results.append(disc_fcf + tv_disc_sim)

            fig, ax = plt.subplots()
            ax.hist(np.array(ev_results) / 1e3, bins=50, color='skyblue', edgecolor='black')
            ax.set_title('Monte Carlo Simulation of Enterprise Value')
            ax.set_xlabel('Enterprise Value ($B)')
            ax.set_ylabel('Frequency')
            st.pyplot(fig)

            st.metric("Mean EV from Simulation ($B)", f"{np.mean(ev_results)/1e3:.2f}")

            # Download Excel
            st.subheader("📥 Download Valuation as Excel")
            with pd.ExcelWriter("Valuation_Output.xlsx", engine="openpyxl") as writer:
                projections.to_excel(writer, sheet_name="Projections", index=False)
                sensitivity.to_excel(writer, sheet_name="Sensitivity Table")
            with open("Valuation_Output.xlsx", "rb") as f:
                st.download_button("Download Excel File", f, file_name="Valuation_Output.xlsx")

            # Historical FCF Chart
            st.subheader("📉 Historical Free Cash Flow")
            try:
                actual_fcf = (cashflow['Total Cash From Operating Activities'] - cashflow['Capital Expenditures']) / 1e6
                st.line_chart(actual_fcf.tail(5))
            except:
                st.info("Historical FCF data not available.")

    except KeyError as ke:
        st.error(f"Missing data field: {ke}")
    except Exception as e:
        st.error(f"Something went wrong: {e}")
