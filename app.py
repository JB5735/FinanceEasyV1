import os
from datetime import date

import pandas as pd
import streamlit as st

# ---------- App Config ----------
st.set_page_config(page_title="FinanceEasy", page_icon="💰", layout="wide")

DATA_FILE = "data/expenses.csv"
COLUMNS = ["date", "description", "category", "amount", "type"]


# ---------- Helper Functions ----------
def ensure_data_file_exists():
    os.makedirs("data", exist_ok=True)

    if not os.path.exists(DATA_FILE):
        empty_df = pd.DataFrame(columns=COLUMNS)
        empty_df.to_csv(DATA_FILE, index=False)


def load_transactions():
    ensure_data_file_exists()

    try:
        df = pd.read_csv(DATA_FILE)

        for column in COLUMNS:
            if column not in df.columns:
                df[column] = ""

        df = df[COLUMNS]
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)

        return df

    except Exception:
        return pd.DataFrame(columns=COLUMNS)


def save_transactions(df):
    df.to_csv(DATA_FILE, index=False)


def add_transaction(df, transaction):
    new_row = pd.DataFrame([transaction])
    updated_df = pd.concat([df, new_row], ignore_index=True)
    save_transactions(updated_df)
    return updated_df


def delete_transaction(df, index_to_delete):
    updated_df = df.drop(index=index_to_delete).reset_index(drop=True)
    save_transactions(updated_df)
    return updated_df


# ---------- Load CSV on Startup ----------
if "transactions_df" not in st.session_state:
    st.session_state.transactions_df = load_transactions()


# ---------- Title + Layout ----------
st.title("💰 FinanceEasy")
st.write("A simple personal finance tracker for college budgeting.")

st.divider()


# ---------- Transaction Form ----------
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
                "date": transaction_date.isoformat(),
                "description": description.strip(),
                "category": category,
                "amount": float(amount),
                "type": transaction_type,
            }

            st.session_state.transactions_df = add_transaction(
                st.session_state.transactions_df,
                new_transaction,
            )

            st.success("Transaction added and saved!")


# ---------- Current Data ----------
df = st.session_state.transactions_df.copy()

st.divider()


# ---------- Display Transactions ----------
st.header("Transactions")

if df.empty:
    st.info("No transactions yet. Add one above to get started.")
else:
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    st.subheader("Saved Transactions")

    display_df = df.copy()
    display_df["date"] = display_df["date"].dt.strftime("%Y-%m-%d")

    st.dataframe(display_df, use_container_width=True)

    # ---------- Delete Transaction ----------
    st.subheader("Delete a Transaction")

    delete_options = [
        f"{index}: {row['date']} | {row['description']} | {row['category']} | ${row['amount']:,.2f}"
        for index, row in display_df.iterrows()
    ]

    selected_transaction = st.selectbox(
        "Choose a transaction to delete",
        delete_options,
    )

    if st.button("Delete Selected Transaction"):
        index_to_delete = int(selected_transaction.split(":")[0])

        st.session_state.transactions_df = delete_transaction(
            st.session_state.transactions_df,
            index_to_delete,
        )

        st.success("Transaction deleted and CSV updated!")
        st.rerun()

    st.divider()

    # ---------- Filtering ----------
    st.subheader("Filter Transactions")

    filter_col1, filter_col2 = st.columns(2)

    with filter_col1:
        selected_category = st.selectbox(
            "Filter by Category",
            ["All"] + sorted(df["category"].dropna().unique().tolist()),
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

    filtered_display_df = filtered_df.copy()
    filtered_display_df["date"] = filtered_display_df["date"].dt.strftime("%Y-%m-%d")

    st.dataframe(filtered_display_df, use_container_width=True)

    # ---------- Summary ----------
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

    # ---------- Spending by Category ----------
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