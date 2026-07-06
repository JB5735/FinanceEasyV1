import streamlit as st
import pandas as pd
from datetime import date

st.set_page_config(page_title="FinanceEasy", page_icon="💰", layout="wide")

# ---------- Session State ----------
if "transactions" not in st.session_state:
    st.session_state.transactions = []

# ---------- Title + Layout ----------
st.title("💰 FinanceEasy")
st.write("A simple personal finance tracker for college budgeting.")

st.divider()

# ---------- Expense Input Form ----------
st.header("Add a Transaction")

with st.form("transaction_form", clear_on_submit=True):
    col1, col2 = st.columns(2)

    with col1:
        transaction_date = st.date_input("Date", value=date.today())
        description = st.text_input("Description / Merchant")

    with col2:
        category = st.selectbox(
            "Category",
            [
                "Food",
                "Transport",
                "Entertainment",
                "Shopping",
                "School",
                "Subscriptions",
                "Income",
                "Other",
            ],
        )
        amount = st.number_input("Amount", min_value=0.0, step=0.01)

    transaction_type = st.selectbox("Type", ["Expense", "Income"])

    submitted = st.form_submit_button("Add Transaction")

    if submitted:
        if description.strip() == "":
            st.error("Please enter a description.")
        elif amount <= 0:
            st.error("Amount must be greater than 0.")
        else:
            new_transaction = {
                "date": transaction_date,
                "description": description.strip(),
                "category": category,
                "amount": amount,
                "type": transaction_type,
            }

            st.session_state.transactions.append(new_transaction)
            st.success("Transaction added!")

# ---------- Create DataFrame From Entries ----------
df = pd.DataFrame(st.session_state.transactions)

st.divider()

# ---------- Display Transactions ----------
st.header("Transactions")

if df.empty:
    st.info("No transactions yet. Add one above to get started.")
else:
    df["date"] = pd.to_datetime(df["date"])

    st.subheader("All Transactions")
    st.dataframe(df, use_container_width=True)

    # ---------- Filtering Rows ----------
    st.subheader("Filter Transactions")

    filter_col1, filter_col2 = st.columns(2)

    with filter_col1:
        selected_category = st.selectbox(
            "Filter by Category",
            ["All"] + sorted(df["category"].unique().tolist()),
        )

    with filter_col2:
        selected_type = st.selectbox(
            "Filter by Type",
            ["All", "Expense", "Income"],
        )

    filtered_df = df.copy()

    if selected_category != "All":
        filtered_df = filtered_df[filtered_df["category"] == selected_category]

    if selected_type != "All":
        filtered_df = filtered_df[filtered_df["type"] == selected_type]

    st.dataframe(filtered_df, use_container_width=True)

    # ---------- Calculate Totals ----------
    expenses_df = df[df["type"] == "Expense"]
    income_df = df[df["type"] == "Income"]

    total_spent = expenses_df["amount"].sum()
    total_income = income_df["amount"].sum()
    current_balance = total_income - total_spent
    transaction_count = len(df)

    st.subheader("Summary")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Income", f"${total_income:,.2f}")
    col2.metric("Total Spent", f"${total_spent:,.2f}")
    col3.metric("Current Balance", f"${current_balance:,.2f}")
    col4.metric("Transactions", transaction_count)

    # ---------- Category Totals ----------
    st.subheader("Spending by Category")

    if not expenses_df.empty:
        category_totals = (
            expenses_df.groupby("category")["amount"]
            .sum()
            .reset_index()
            .sort_values("amount", ascending=False)
        )

        st.dataframe(category_totals, use_container_width=True)
    else:
        st.info("No expenses yet, so category totals are not available.")