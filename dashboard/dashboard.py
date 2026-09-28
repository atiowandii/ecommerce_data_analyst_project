import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import streamlit as st
from babel.numbers import format_currency

sns.set_theme(style='white')
BAR_PALETTE = 'Blues_r'
PIE_PALETTE = 'pastel'
ACCENT_PALETTE = ['#4C72B0', '#DD8452']

# 1. FUNGSI PEMROSESAN DATA

DATE_COLUMNS = [
    'order_purchase_timestamp', 'order_approved_at',
    'order_delivered_carrier_date', 'order_delivered_customer_date',
    'order_estimated_delivery_date', 'review_creation_date',
    'review_answer_timestamp', 'shipping_limit_date',
]


def load_data(path):
    df = pd.read_csv(path)
    for col in DATE_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    return df


def get_order_level_df(df):
    """Satu baris per order_id (dedup), lengkap dengan revenue & status telat."""
    order_df = df.drop_duplicates(subset='order_id')[[
        'order_id', 'customer_id', 'customer_unique_id', 'customer_city',
        'customer_state', 'order_status', 'order_purchase_timestamp',
        'order_delivered_customer_date', 'order_estimated_delivery_date',
        'review_score',
    ]].copy()

    payment_df = df[['order_id', 'payment_sequential', 'payment_value']].drop_duplicates()
    revenue_per_order = (
        payment_df.groupby('order_id')['payment_value']
        .sum()
        .reset_index()
        .rename(columns={'payment_value': 'order_revenue'})
    )
    order_df = order_df.merge(revenue_per_order, on='order_id', how='left')

    order_df['is_late'] = (
        order_df['order_delivered_customer_date'] > order_df['order_estimated_delivery_date']
    )
    order_df['delivery_status'] = order_df['is_late'].map(
        {True: 'Terlambat', False: 'Tepat Waktu'}
    )
    order_df['delivery_days'] = (
        order_df['order_delivered_customer_date'] - order_df['order_purchase_timestamp']
    ).dt.days

    return order_df


def get_item_level_df(df):
    """Satu baris per order_item (dedup), untuk analisis kategori/seller/revenue produk."""
    item_cols = [
        'order_id', 'order_item_id', 'product_id',
        'product_category_name_english', 'seller_id', 'seller_city',
        'seller_state', 'price', 'freight_value',
    ]
    item_df = df[item_cols].drop_duplicates()
    item_df['item_revenue'] = item_df['price'] + item_df['freight_value']
    return item_df


def create_daily_orders_df(order_df):
    daily = order_df.resample(rule='D', on='order_purchase_timestamp').agg(
        order_count=('order_id', 'nunique'),
        revenue=('order_revenue', 'sum'),
    ).reset_index()
    return daily


def create_bystate_df(order_df, top_n=10):
    bystate = (
        order_df.groupby('customer_state')['order_id']
        .nunique()
        .sort_values(ascending=False)
        .head(top_n)
        .reset_index()
    )
    bystate.columns = ['customer_state', 'order_count']
    return bystate


def create_bycategory_df(item_df, top_n=10):
    bycat = (
        item_df.groupby('product_category_name_english')['order_id']
        .nunique()
        .sort_values(ascending=False)
        .head(top_n)
        .reset_index()
    )
    bycat.columns = ['product_category_name_english', 'order_count']
    return bycat


def create_payment_type_df(df):
    payment_df = df[['order_id', 'payment_sequential', 'payment_type']].drop_duplicates()
    pay_counts = payment_df['payment_type'].value_counts().reset_index()
    pay_counts.columns = ['payment_type', 'count']
    return pay_counts


def create_order_status_df(order_df):
    status_counts = order_df['order_status'].value_counts().reset_index()
    status_counts.columns = ['order_status', 'count']
    return status_counts


def create_late_status_df(order_df):
    delivered = order_df.dropna(subset=['order_delivered_customer_date'])
    late_counts = delivered['delivery_status'].value_counts().reset_index()
    late_counts.columns = ['delivery_status', 'count']
    return late_counts


def create_rating_by_category_df(order_df, item_df, top_n=10):
    order_category = item_df[['order_id', 'product_category_name_english']].drop_duplicates()
    merged = order_category.merge(
        order_df[['order_id', 'review_score']], on='order_id', how='left'
    )
    rating_cat = (
        merged.groupby('product_category_name_english')['review_score']
        .mean()
        .round(2)
        .sort_values(ascending=False)
        .head(top_n)
        .reset_index()
    )
    return rating_cat


def create_rating_by_late_df(order_df):
    delivered = order_df.dropna(subset=['order_delivered_customer_date', 'review_score'])
    rating_late = (
        delivered.groupby('delivery_status')['review_score']
        .mean()
        .round(2)
        .reset_index()
    )
    return rating_late


def create_revenue_by_category_df(item_df, top_n=10):
    rev_cat = (
        item_df.groupby('product_category_name_english')['item_revenue']
        .sum()
        .sort_values(ascending=False)
        .head(top_n)
        .reset_index()
    )
    return rev_cat


def create_revenue_by_state_df(order_df, item_df, top_n=10):
    order_state = order_df[['order_id', 'customer_state']]
    merged = item_df.merge(order_state, on='order_id', how='left')
    rev_state = (
        merged.groupby('customer_state')['item_revenue']
        .sum()
        .sort_values(ascending=False)
        .head(top_n)
        .reset_index()
    )
    return rev_state


def create_revenue_by_seller_df(item_df, top_n=10):
    rev_seller = (
        item_df.groupby('seller_id')['item_revenue']
        .sum()
        .sort_values(ascending=False)
        .head(top_n)
        .reset_index()
    )
    return rev_seller



# 2. LOAD DATA

all_df = load_data(os.path.join(os.path.dirname(os.path.abspath(__file__)), "main_data.csv"))

min_date = all_df['order_purchase_timestamp'].min()
max_date = all_df['order_purchase_timestamp'].max()

# 3. SIDEBAR: FILTER GLOBAL

def reset_filters():
    """Kembalikan semua filter ke kondisi awal (data keseluruhan)."""
    st.session_state['start_date_value'] = min_date.date()
    st.session_state['end_date_value'] = max_date.date()
    st.session_state['selected_states'] = []
    st.session_state['selected_categories'] = []


with st.sidebar:
    st.title('E-Commerce Dashboard')

    prev_start = st.session_state.get('start_date_value', min_date.date())
    prev_end = st.session_state.get('end_date_value', max_date.date())

    start_date = st.date_input(
        label='Tanggal Awal',
        value=prev_start,
        min_value=min_date.date(),
        max_value=prev_end,
    )

    end_date = st.date_input(
        label='Tanggal Akhir',
        value=prev_end,
        min_value=start_date,
        max_value=max_date.date(),
    )

    st.session_state['start_date_value'] = start_date
    st.session_state['end_date_value'] = end_date

    state_options = sorted(all_df['customer_state'].dropna().unique())
    selected_states = st.multiselect(
        label='Customer State',
        options=state_options,
        default=[],
        key='selected_states',
        help='Kosongkan untuk menampilkan semua state',
    )

    category_options = sorted(all_df['product_category_name_english'].dropna().unique())
    selected_categories = st.multiselect(
        label='Product Category',
        options=category_options,
        default=[],
        key='selected_categories',
        help='Kosongkan untuk menampilkan semua kategori',
    )

    st.button(
        'Reset Filter',
        on_click=reset_filters,
        use_container_width=True,
    )

filtered_df = all_df[
    (all_df['order_purchase_timestamp'] >= pd.to_datetime(start_date))
    & (all_df['order_purchase_timestamp'] < pd.to_datetime(end_date) + pd.Timedelta(days=1))
]
if selected_states:
    filtered_df = filtered_df[filtered_df['customer_state'].isin(selected_states)]
if selected_categories:
    filtered_df = filtered_df[
        filtered_df['product_category_name_english'].isin(selected_categories)
    ]

order_df = get_order_level_df(filtered_df)
item_df = get_item_level_df(filtered_df)


# 4. HEADER & SCORECARD UTAMA + LINE CHART

st.header('E-Commerce Dashboard')

st.subheader('Ringkasan Pesanan')

total_orders = order_df['order_id'].nunique()
total_revenue = order_df['order_revenue'].sum()
avg_rating = order_df['review_score'].mean()

col1, col2 = st.columns(2)

with col1:
    st.metric('Total Pesanan', value=f'{total_orders:,}')

with col2:
    st.metric('Rata-rata Rating', value=f'{avg_rating:.2f}' if pd.notna(avg_rating) else '-')

revenue_display = format_currency(total_revenue, 'BRL', locale='pt_BR')
st.metric('Total Revenue', value=revenue_display)


daily_orders_df = create_daily_orders_df(order_df)

fig, ax = plt.subplots(figsize=(16, 6))
ax.plot(
    daily_orders_df['order_purchase_timestamp'],
    daily_orders_df['order_count'],
    linewidth=1,
    color='#4C72B0',
)
ax.fill_between(
    daily_orders_df['order_purchase_timestamp'],
    daily_orders_df['order_count'],
    color='#4C72B0',
    alpha=0.15,
)
ax.set_title('Tren Total Pesanan Harian')
sns.despine(ax=ax)
st.pyplot(fig)


# 5. DISTRIBUSI PESANAN (bar chart)

st.subheader('Distribusi Pesanan')

col1, col2 = st.columns(2)

with col1:
    bystate_df = create_bystate_df(order_df)
    fig, ax = plt.subplots(figsize=(10, 8))
    sns.barplot(x='order_count', y='customer_state', data=bystate_df, palette=BAR_PALETTE, ax=ax)
    ax.set_title('Top 10 Customer State by Total Pesanan')
    ax.set_xlabel('Total Pesanan')
    ax.set_ylabel(None)
    sns.despine(ax=ax)
    st.pyplot(fig)

with col2:
    bycategory_df = create_bycategory_df(item_df)
    fig, ax = plt.subplots(figsize=(10, 8))
    sns.barplot(
        x='order_count', y='product_category_name_english',
        data=bycategory_df, palette=BAR_PALETTE, ax=ax,
    )
    ax.set_title('Top 10 Product Category by Total Pesanan')
    ax.set_xlabel('Total Pesanan')
    ax.set_ylabel(None)
    sns.despine(ax=ax)
    st.pyplot(fig)


# 6. KOMPOSISI (pie chart)

st.subheader('Komposisi Pembayaran & Status Pesanan')

col1, col2 = st.columns(2)

with col1:
    payment_df = create_payment_type_df(filtered_df)
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.pie(
        payment_df['count'], labels=payment_df['payment_type'], autopct='%1.1f%%',
        colors=sns.color_palette(PIE_PALETTE, len(payment_df)),
    )
    ax.set_title('Metode Pembayaran')
    st.pyplot(fig)

with col2:
    status_df = create_order_status_df(order_df)
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.pie(
        status_df['count'], labels=status_df['order_status'], autopct='%1.1f%%',
        colors=sns.color_palette(PIE_PALETTE, len(status_df)),
    )
    ax.set_title('Order Status')
    st.pyplot(fig)


# 7. PERFORMA PENGIRIMAN

st.subheader('Performa Pengiriman')

col1, col2 = st.columns(2)

with col1:
    late_df = create_late_status_df(order_df)
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.barplot(x='delivery_status', y='count', data=late_df, palette=ACCENT_PALETTE, ax=ax)
    ax.set_title('Tepat Waktu vs Terlambat')
    ax.set_xlabel(None)
    ax.set_ylabel('Total Pesanan')
    sns.despine(ax=ax)
    st.pyplot(fig)

with col2:
    delivery_days = order_df['delivery_days'].dropna()
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.histplot(delivery_days, bins=30, color='#4C72B0', ax=ax)
    ax.set_title('Distribusi Lama Pengiriman (hari)')
    ax.set_xlabel('Hari')
    sns.despine(ax=ax)
    st.pyplot(fig)


# 8. RATING

st.subheader('Rating Pesanan')

col1, col2 = st.columns(2)

with col1:
    rating_cat_df = create_rating_by_category_df(order_df, item_df)
    fig, ax = plt.subplots(figsize=(10, 8))
    sns.barplot(
        x='review_score', y='product_category_name_english',
        data=rating_cat_df, palette=BAR_PALETTE, ax=ax,
    )
    ax.set_title('Rata-rata Rating per Kategori (Top 10)')
    ax.set_xlabel('Rata-rata Rating')
    ax.set_ylabel(None)
    ax.set_xlim(0, 5)
    sns.despine(ax=ax)
    st.pyplot(fig)

with col2:
    rating_late_df = create_rating_by_late_df(order_df)
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.barplot(x='delivery_status', y='review_score', data=rating_late_df, palette=ACCENT_PALETTE, ax=ax)
    ax.set_title('Rata-rata Rating: Tepat Waktu vs Terlambat')
    ax.set_xlabel(None)
    ax.set_ylabel('Rata-rata Rating')
    ax.set_ylim(0, 5)
    sns.despine(ax=ax)
    st.pyplot(fig)


# 9. REVENUE

st.subheader('Revenue')

col1, col2, col3 = st.columns(3)

with col1:
    rev_cat_df = create_revenue_by_category_df(item_df)
    fig, ax = plt.subplots(figsize=(8, 10))
    sns.barplot(
        x='item_revenue', y='product_category_name_english',
        data=rev_cat_df, palette=BAR_PALETTE, ax=ax,
    )
    ax.set_title('Top 10 Revenue by Category')
    ax.set_xlabel('Revenue')
    ax.set_ylabel(None)
    sns.despine(ax=ax)
    st.pyplot(fig)

with col2:
    rev_state_df = create_revenue_by_state_df(order_df, item_df)
    fig, ax = plt.subplots(figsize=(8, 10))
    sns.barplot(
        x='item_revenue', y='customer_state',
        data=rev_state_df, palette=BAR_PALETTE, ax=ax,
    )
    ax.set_title('Top 10 Revenue by Customer State')
    ax.set_xlabel('Revenue')
    ax.set_ylabel(None)
    sns.despine(ax=ax)
    st.pyplot(fig)

with col3:
    rev_seller_df = create_revenue_by_seller_df(item_df)
    fig, ax = plt.subplots(figsize=(8, 10))
    sns.barplot(
        x='item_revenue', y='seller_id',
        data=rev_seller_df, palette=BAR_PALETTE, ax=ax,
    )
    ax.set_title('Top 10 Revenue by Seller')
    ax.set_xlabel('Revenue')
    ax.set_ylabel(None)
    ax.tick_params(axis='y', labelsize=8)
    sns.despine(ax=ax)
    st.pyplot(fig)

st.caption('E-Commerce Dashboard - dibuat dengan Streamlit')
