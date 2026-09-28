# E-Commerce Data Analysis Dashboard 

## Deskripsi Proyek
Proyek ini menganalisis dataset publik dari platform e-commerce Brasil untuk menjawab dua pertanyaan bisnis utama:

1. **Pengaruh keterlambatan pengiriman terhadap review score:** Mengukur seberapa besar dampak keterlambatan pengiriman terhadap kepuasan pelanggan (review_score) pada pesanan berstatus "delivered" selama periode 2017–2018.
2. **Kategori produk dengan revenue tinggi namun review score rendah:** Mengidentifikasi kategori produk yang berkontribusi besar terhadap pendapatan tetapi memiliki proporsi ulasan buruk (skor ≤2) yang tinggi.

## Teknik Analisis yang Digunakan
- **Data Wrangling**: Penanganan missing value, konversi tipe data datetime, dan validasi data duplikat/invalid.
- **Exploratory Data Analysis (EDA)**: Analisis korelasi antara keterlambatan pengiriman dan review score, serta agregasi revenue dan review per kategori produk.
- **Visualization**: Bar chart perbandingan review score (tepat waktu vs terlambat), scatter plot revenue vs proporsi review rendah, dan heatmap korelasi.
- **Analisis Lanjutan**: Korelasi multivariabel antara delay_time, price, freight_value, dan review_score menggunakan heatmap.

## Struktur Proyek
```
├── dashboard/
│   ├── dashboard.py        # Streamlit dashboard
│   └── main_data.csv       # Data hasil olahan untuk dashboard
├── data/                   # Dataset mentah (CSV)
├── notebook.ipynb          # Notebook analisis data
├── requirements.txt        # Daftar library
├── README.md
└── url.txt
```

## Setup Environment - Anaconda
```
conda create --name main-ds python=3.9
conda activate main-ds
pip install -r requirements.txt
```

## Setup Environment - Shell/Terminal
```
mkdir proyek_analisis_data
cd proyek_analisis_data
pipenv install
pipenv shell
pip install -r requirements.txt
```

## Run Streamlit App
```
cd dashboard
streamlit run dashboard.py
```
