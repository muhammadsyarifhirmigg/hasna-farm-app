import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
from datetime import date, datetime
import time
import io
import hashlib
import logging
from fpdf import FPDF
from streamlit_option_menu import option_menu
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field, validator, ValidationError
import base64

st.set_page_config(
    page_title="Hasna Farm ERP",
    page_icon="🐓",
    layout="wide",
    initial_sidebar_state="collapsed"
)

def get_img_as_base64(file):
    try:
        with open(file, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except:
        return ""

def inject_login_css():
    img = get_img_as_base64("background.jpg")
    if img:
        bg_url = f"data:image/jpeg;base64,{img}"
    else:
        bg_url = "https://images.unsplash.com/photo-1500595046743-cd271d694d30?q=80"

    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
        html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; color: #1f2937; }}
        .stApp {{
            background-image: url("{bg_url}");
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            background-attachment: fixed;
        }}
        .stApp::before {{
            content: ""; position: absolute; top: 0; left: 0; width: 100%; height: 100%;
            background-color: rgba(0, 0, 0, 0.2); z-index: -1;
        }}
        header[data-testid="stHeader"] {{ display: none; }}
        .block-container {{ padding-top: 4rem !important; max-width: 1000px; }}
        .brand-box {{
            background-color: rgba(255, 255, 255, 0.85);
            backdrop-filter: blur(10px);
            padding: 40px; border-radius: 24px; text-align: center;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
            border: 1px solid rgba(255, 255, 255, 0.18);
            display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%;
        }}
        .brand-logo-img {{ width: 150px; display: block; margin-bottom: 15px; }}
        .brand-subtitle {{ color: #3B2417; font-size: 1.4rem; font-weight: 800; margin: 0; }}
        .brand-desc {{ color: #3B2417; font-size: 1rem; margin-top: 10px; font-weight: 500; }}
        div[data-testid="stForm"] {{
            background-color: #ffffff; border: none; border-radius: 24px;
            padding: 40px; box-shadow: 0 15px 35px rgba(0, 0, 0, 0.2);
        }}
        input {{ border-radius: 8px !important; padding: 14px 16px !important; border: 1px solid #ddd !important; }}
        button[kind="primary"] {{
            background-color: #768209; color: white; border-radius: 8px; border: none; font-weight: 700;
            font-size: 18px; width: 100%; padding: 12px; margin-top: 10px;
        }}
        button[kind="primary"]:hover {{ background-color: #5a6307; }}
        </style>
    """, unsafe_allow_html=True)

def inject_main_css():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
        html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: #1f2937; }
        .stApp {
            background-image: none !important;
            background-color: #f7f3e8; 
        }
        .stApp::before { display: none; }
        header[data-testid="stHeader"] { display: none; }
        .block-container { padding-top: 2rem !important; max-width: 1200px; }
        div[data-testid="stForm"], div.sap-container {
            background-color: #ffffff; 
            border: 1px solid #e5e7eb; 
            border-radius: 12px;
            padding: 24px; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.05); 
            margin-bottom: 20px;
        }
        .streamlit-expanderHeader {
            background-color: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
        }
        .streamlit-expanderContent {
            background-color: #ffffff;
            border-bottom-left-radius: 8px;
            border-bottom-right-radius: 8px;
            border: 1px solid #e5e7eb;
            border-top: none;
            padding: 20px;
        }
        div[data-testid="stMetric"] {
            background-color: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 12px; padding: 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            border-top: 4px solid #768209;
        }
        button[kind="primary"] {
            background-color: #768209; color: white; border: none; border-radius: 8px; font-weight: 600;
        }
        input:focus, select:focus {
            border-color: #768209 !important;
            box-shadow: 0 0 0 1px #768209 !important;
        }
        </style>
    """, unsafe_allow_html=True)

logging.basicConfig(filename='system.log', level=logging.INFO, format='%(asctime)s %(message)s')

def log_activity(u, a, d): 
    logging.info(f"{u}|{a}|{d}")

def make_hash(pw): 
    return hashlib.sha256(str.encode(pw)).hexdigest()

class JurnalSchema(BaseModel):
    tanggal: date
    deskripsi: str = Field(..., min_length=3)
    akun_debit: str
    akun_kredit: str
    nominal: float = Field(..., gt=0)
    created_by: str
    
    @validator('akun_kredit')
    def cek_beda(cls, v, values):
        if 'akun_debit' in values and v == values['akun_debit']: 
            raise ValueError("Akun Debit dan Kredit tidak boleh sama!")
        return v

class DatabaseManager:
    def __init__(self, db_name): 
        self.db_name = db_name
    
    def _conn(self):
        c = sqlite3.connect(self.db_name)
        c.row_factory = sqlite3.Row
        return c

    def get_inventory_card_df(self, kode_barang):
        STD_COSTS = {"TELUR": 333, "PUPUK": 15000, "PKN-MERAH": 360000, "PKN-BIRU": 435000, "VIT-OBAT": 125000}
        logs = self.get_df("SELECT * FROM stock_log WHERE kode_barang=? ORDER BY tanggal ASC, id ASC", (kode_barang,))
        std_price = STD_COSTS.get(kode_barang, 0)
        data = []
        running_qty = 0
        
        saldo_awal_log = logs[(logs['keterangan'].str.contains('Saldo Awal', case=False, na=False)) & (logs['jenis_gerak'] == 'IN')]
        
        def fmt(v): return f"{v:,.0f}" if v > 0 else ""
        def fmt_rp(v): return f"Rp{v:,.0f}" if v > 0 else ""

        if not saldo_awal_log.empty:
            sa = saldo_awal_log.iloc[0]
            running_qty = sa['jumlah']
            data.append(["", "Saldo Awal", "", "", "", "", "", "", fmt(running_qty), fmt_rp(std_price), fmt_rp(running_qty*std_price)])
            logs = logs.drop(saldo_awal_log.index)

        for _, row in logs.iterrows():
            qty = row['jumlah']
            gerak = row['jenis_gerak']
            p = row['harga_satuan'] if row['harga_satuan'] > 0 else std_price
            
            in_q = qty if gerak=='IN' else 0
            out_q = qty if gerak=='OUT' else 0
            
            if gerak=='IN':
                running_qty += qty
            else:
                running_qty -= qty
            
            data.append([
                row['tanggal'], row['keterangan'],
                fmt(in_q), fmt_rp(p) if in_q else "", fmt_rp(in_q*p),
                fmt(out_q), fmt_rp(p) if out_q else "", fmt_rp(out_q*p),
                fmt(running_qty), fmt_rp(p), fmt_rp(running_qty*p)
            ])

        cols = pd.MultiIndex.from_tuples([
            ("Detail","Date"),("Detail","Desc"),
            ("IN","Qty"),("IN","Price"),("IN","Total"),
            ("OUT","Qty"),("OUT","Price"),("OUT","Total"),
            ("Balance","Qty"),("Balance","Price"),("Balance","Total")
        ])
        return pd.DataFrame(data, columns=cols)

    def init_db(self):
        with self._conn() as c:
            c.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS akun (id INTEGER PRIMARY KEY AUTOINCREMENT, kode_akun TEXT UNIQUE, nama_akun TEXT UNIQUE, tipe_akun TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS jurnal (id INTEGER PRIMARY KEY, tanggal TEXT, deskripsi TEXT, akun_debit TEXT, akun_kredit TEXT, nominal REAL, created_at TIMESTAMP, created_by TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS inventory (id INTEGER PRIMARY KEY, kode_barang TEXT UNIQUE, nama_barang TEXT, kategori TEXT, satuan TEXT, stok_saat_ini REAL, min_stok REAL)")
            c.execute("CREATE TABLE IF NOT EXISTS stock_log (id INTEGER PRIMARY KEY, tanggal TEXT, kode_barang TEXT, jenis_gerak TEXT, jumlah REAL, harga_satuan REAL DEFAULT 0, keterangan TEXT, user TEXT)")

            if not c.execute("SELECT * FROM users").fetchone():
                c.execute("INSERT INTO users VALUES (?,?,?)", ('admin', make_hash('admin123'), 'Manager'))
                c.execute("INSERT INTO users VALUES (?,?,?)", ('kasir', make_hash('staff123'), 'Staff'))
            
            if not c.execute("SELECT * FROM akun").fetchone():
                real_accounts = [
                    ("1-11", "Kas", "Aset"), ("1-12", "Bank Mandiri", "Aset"), ("1-13", "Piutang Dagang", "Aset"),
                    ("1-14", "Persediaan Telur Puyuh", "Aset"), ("1-15", "Persediaan Kotoran (Pupuk)", "Aset"),
                    ("1-16", "Persediaan Pakan Ternak", "Aset"), ("1-17", "Persediaan Obat & Vitamin", "Aset"),
                    ("1-21", "Bangunan Kandang", "Aset"), ("1-22", "Akumulasi Penyusutan Kandang", "Aset"),
                    ("1-23", "Kendaraan", "Aset"), ("1-24", "Akumulasi Penyusutan Kendaraan", "Aset"),
                    ("2-11", "Hutang Usaha", "Kewajiban"), ("3-11", "Modal Pemilik", "Modal"), ("3-12", "Prive", "Modal"),
                    ("4-11", "Penjualan Telur Puyuh", "Pendapatan"), ("4-12", "Penjualan Kotoran (Pupuk)", "Pendapatan"),
                    ("4-13", "Return Penjualan", "Pendapatan"),
                    ("5-11", "HPP Telur Puyuh", "Beban"), ("5-12", "HPP Kotoran (Pupuk)", "Beban"),
                    ("5-13", "Beban Pakan", "Beban"), ("5-14", "Beban Obat & Vitamin", "Beban"),
                    ("6-11", "Beban Transportasi", "Beban"), ("6-12", "Beban Listrik, Air, dan Telepon", "Beban"),
                    ("6-13", "Beban Penyusutan Kandang", "Beban"), ("6-14", "Beban Penyusutan Kendaraan", "Beban")
                ]
                c.executemany("INSERT INTO akun (kode_akun, nama_akun, tipe_akun) VALUES (?,?,?)", real_accounts)
            
            if not c.execute("SELECT * FROM inventory").fetchone():
                real_inv = [
                    ("PKN-MERAH", "Pakan Kukila Merah", "Pakan", "Sak", 10, 5),
                    ("PKN-BIRU", "Pakan Kukila Biru", "Pakan", "Sak", 10, 5),
                    ("TELUR", "Telur Puyuh", "Produk", "Dus", 100, 10),
                    ("PUPUK", "Pupuk Organik (Kotoran)", "Produk", "Sak", 50, 5),
                    ("VIT-OBAT", "Vitamin & Obat", "Obat", "Paket", 10, 2)
                ]
                c.executemany("INSERT INTO inventory (kode_barang, nama_barang, kategori, satuan, stok_saat_ini, min_stok) VALUES (?,?,?,?,?,?)", real_inv)

            if not c.execute("SELECT * FROM jurnal").fetchone():
                sa_date = "2025-10-01"
                saldo_awal = [
                    ("Kas", "Modal Pemilik", 20000000), ("Piutang Dagang", "Modal Pemilik", 1000000),
                    ("Persediaan Telur Puyuh", "Modal Pemilik", 6250000), ("Persediaan Kotoran (Pupuk)", "Modal Pemilik", 150000),
                    ("Persediaan Pakan Ternak", "Modal Pemilik", 2500000), ("Persediaan Obat & Vitamin", "Modal Pemilik", 300000),
                    ("Bangunan Kandang", "Modal Pemilik", 30000000), ("Kendaraan", "Modal Pemilik", 140000000),
                    ("Modal Pemilik", "Akumulasi Penyusutan Kandang", 3000000), ("Modal Pemilik", "Akumulasi Penyusutan Kendaraan", 14000000)
                ]
                for d, k, n in saldo_awal:
                    c.execute("INSERT INTO jurnal (tanggal, deskripsi, akun_debit, akun_kredit, nominal, created_by) VALUES (?,?,?,?,?,?)", (sa_date, "Saldo Awal Neraca", d, k, n, "system"))

                trx_list = [
                    ("2025-10-01", "Tambahan Modal Pemilik", "Kas", "Modal Pemilik", 5000000),
                    ("2025-10-02", "Beli Pakan Kukila", "Persediaan Pakan Ternak", "Kas", 2460000),
                    ("2025-10-05", "Jual Telur (3 Dus)", "Kas", "Penjualan Telur Puyuh", 750000),
                    ("2025-10-05", "HPP Jual Telur", "HPP Telur Puyuh", "Persediaan Telur Puyuh", 300000),
                    ("2025-10-05", "Beli Vitamin", "Persediaan Obat & Vitamin", "Kas", 250000),
                    ("2025-10-06", "Jual Telur (Kredit)", "Piutang Dagang", "Penjualan Telur Puyuh", 500000),
                    ("2025-10-06", "HPP Jual Telur", "HPP Telur Puyuh", "Persediaan Telur Puyuh", 200000),
                    ("2025-10-08", "Jual Pupuk", "Kas", "Penjualan Kotoran (Pupuk)", 15000),
                    ("2025-10-08", "HPP Pupuk", "HPP Kotoran (Pupuk)", "Persediaan Kotoran (Pupuk)", 6000),
                    ("2025-10-08", "Jual Telur (1 Dus)", "Kas", "Penjualan Telur Puyuh", 250000),
                    ("2025-10-08", "HPP Jual Telur", "HPP Telur Puyuh", "Persediaan Telur Puyuh", 100000),
                    ("2025-10-10", "Beli Bensin", "Beban Transportasi", "Kas", 100000),
                    ("2025-10-11", "Jual Telur (4 Dus)", "Kas", "Penjualan Telur Puyuh", 1000000),
                    ("2025-10-11", "HPP Jual Telur", "HPP Telur Puyuh", "Persediaan Telur Puyuh", 400000),
                    ("2025-10-12", "Jual Pupuk (2 Sak)", "Kas", "Penjualan Kotoran (Pupuk)", 30000),
                    ("2025-10-12", "HPP Pupuk", "HPP Kotoran (Pupuk)", "Persediaan Kotoran (Pupuk)", 12000),
                    ("2025-10-14", "Jual Telur (4 Dus)", "Kas", "Penjualan Telur Puyuh", 1000000),
                    ("2025-10-14", "HPP Jual Telur", "HPP Telur Puyuh", "Persediaan Telur Puyuh", 400000),
                    ("2025-10-15", "Jual Pupuk", "Kas", "Penjualan Kotoran (Pupuk)", 30000),
                    ("2025-10-15", "HPP Pupuk", "HPP Kotoran (Pupuk)", "Persediaan Kotoran (Pupuk)", 12000),
                    ("2025-10-19", "Jual Telur (3 Dus)", "Kas", "Penjualan Telur Puyuh", 750000),
                    ("2025-10-19", "HPP Jual Telur", "HPP Telur Puyuh", "Persediaan Telur Puyuh", 300000),
                    ("2025-10-20", "Jual Telur (2 Dus)", "Kas", "Penjualan Telur Puyuh", 500000),
                    ("2025-10-20", "HPP Jual Telur", "HPP Telur Puyuh", "Persediaan Telur Puyuh", 200000),
                    ("2025-10-21", "Retur Penjualan", "Return Penjualan", "Kas", 300000),
                    ("2025-10-21", "Retur Stok", "Persediaan Telur Puyuh", "HPP Telur Puyuh", 120000),
                    ("2025-10-22", "Jual Telur (2 Dus)", "Kas", "Penjualan Telur Puyuh", 500000),
                    ("2025-10-22", "Jual Pupuk (3 Sak)", "Kas", "Penjualan Kotoran (Pupuk)", 45000),
                    ("2025-10-22", "HPP Jual Telur", "HPP Telur Puyuh", "Persediaan Telur Puyuh", 200000),
                    ("2025-10-22", "HPP Pupuk", "HPP Kotoran (Pupuk)", "Persediaan Kotoran (Pupuk)", 18000),
                    ("2025-10-25", "Prive Pemilik", "Prive", "Kas", 4000000),
                    ("2025-10-26", "Pelunasan Piutang", "Kas", "Piutang Dagang", 500000),
                    ("2025-10-27", "Beli Pakan", "Persediaan Pakan Ternak", "Kas", 360000),
                    ("2025-10-28", "Jual Telur", "Kas", "Penjualan Telur Puyuh", 500000),
                    ("2025-10-28", "HPP Jual Telur", "HPP Telur Puyuh", "Persediaan Telur Puyuh", 200000),
                    ("2025-10-30", "Bayar Listrik", "Beban Listrik, Air, dan Telepon", "Kas", 300000),
                    ("2025-10-31", "Penyusutan Kandang Okt", "Beban Penyusutan Kandang", "Akumulasi Penyusutan Kandang", 450000),
                    ("2025-10-31", "Penyusutan Kendaraan Okt", "Beban Penyusutan Kendaraan", "Akumulasi Penyusutan Kendaraan", 1239583),
                    ("2025-10-31", "Pemakaian Pakan (Costing)", "Beban Pakan", "Persediaan Pakan Ternak", 732000),
                    ("2025-10-31", "Pemakaian Obat & Vitamin", "Beban Obat & Vitamin", "Persediaan Obat & Vitamin", 1414583),
                ]
                for tgl, desc, d, k, n in trx_list:
                    c.execute("INSERT INTO jurnal (tanggal, deskripsi, akun_debit, akun_kredit, nominal, created_by) VALUES (?,?,?,?,?,?)", (tgl, desc, d, k, n, "system"))
            c.commit()

    def run_query(self, q, p=()):
        q = q.replace('%s', '?')
        try:
            with self._conn() as c:
                c.execute(q, p)
                c.commit()
            return True
        except Exception as e:
            st.error(f"DB Error: {e}")
            return False
    
    def get_df(self, q, p=()):
        q = q.replace('%s', '?')
        try:
            with self._conn() as c:
                return pd.read_sql_query(q, c, params=p)
        except:
            return pd.DataFrame()
    
    def get_one(self, q, p=()):
        q = q.replace('%s', '?')
        with self._conn() as c:
            return c.execute(q, p).fetchone()
    
    def get_acc_by_type(self, types):
        ph = ','.join(['?']*len(types))
        df = self.get_df(f"SELECT nama_akun FROM akun WHERE tipe_akun IN ({ph})", tuple(types))
        return df['nama_akun'].tolist() if not df.empty else []
    
    def get_all_acc(self):
        df = self.get_df("SELECT nama_akun FROM akun ORDER BY kode_akun")
        return df['nama_akun'].tolist() if not df.empty else []

db = DatabaseManager("hasna_real_data.db")
db.init_db()

def generate_pdf(id_trx, tgl, desc, nominal, debit, kredit):
    class PDF(FPDF):
        def header(self):
            try:
                self.image('logo.png', 10, 8, 25)
            except:
                pass
            self.set_font('Arial', 'B', 14)
            self.cell(0, 10, 'HASNA FARM ENTERPRISE', 0, 1, 'C')
            self.ln(10)
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, f"Receipt #{id_trx}", 0, 1, "C")
    pdf.ln(5)
    pdf.cell(0, 10, f"Date: {tgl} | Amount: Rp {nominal:,.0f}", 0, 1)
    pdf.cell(0, 10, f"Desc: {desc}", 0, 1)
    pdf.cell(0, 10, f"Dr: {debit} | Cr: {kredit}", 0, 1)
    return pdf.output(dest="S").encode("latin-1")

def generate_smart_insights(df):
    insights = []
    if df.empty:
        return ["⚠️ Belum ada cukup data."]
    try:
        kas_m = df[df['akun_debit']=='Kas']['nominal'].sum()
        kas_k = df[df['akun_kredit']=='Kas']['nominal'].sum()
        saldo = kas_m - kas_k
        if saldo < 1000000:
            insights.append("⚠️ **Peringatan Kas:** Saldo menipis (< 1 Jt).")
        elif saldo > 50000000:
            insights.append("✅ **Likuiditas Tinggi:** Kas berlebih (> 50 Jt).")
    except:
        pass
    
    bbn = db.get_acc_by_type(['Beban'])
    df_b = df[df['akun_debit'].isin(bbn)]
    if not df_b.empty:
        top = df_b.groupby('akun_debit')['nominal'].sum().sort_values(ascending=False).head(1)
        insights.append(f"ℹ️ **Top Pengeluaran:** {top.index[0]} (Rp {top.values[0]:,.0f}).")
    return insights

def generate_sankey(df):
    if df.empty:
        return None
    pdp = db.get_acc_by_type(['Pendapatan'])
    bbn = db.get_acc_by_type(['Beban'])
    
    df_in = df[df['akun_kredit'].isin(pdp)].groupby('akun_kredit')['nominal'].sum().reset_index()
    df_in.columns = ['S','V']
    df_in['T'] = 'Kas Utama'
    
    df_out = df[df['akun_debit'].isin(bbn)].groupby('akun_debit')['nominal'].sum().reset_index()
    df_out.columns = ['T','V']
    df_out['S'] = 'Kas Utama'
    
    links = pd.concat([df_in, df_out], ignore_index=True)
    if links.empty:
        return None
    
    nodes = list(pd.concat([links['S'], links['T']]).unique())
    node_map = {n: i for i, n in enumerate(nodes)}
    
    fig = go.Figure(data=[go.Sankey(node=dict(pad=15, thickness=20, line=dict(color="black", width=0.5), label=nodes, color="blue"), 
                                    link=dict(source=links['S'].map(node_map), target=links['T'].map(node_map), value=links['V'], color='rgba(118, 130, 9, 0.2)'))])
    fig.update_layout(title_text="Flow of Funds", font_size=10, height=300, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    return fig

def login_required(func):
    def wrapper(*args, **kwargs):
        if not st.session_state.get('logged_in'):
            st.stop()
        return func(*args, **kwargs)
    return wrapper

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = ""
if 'role' not in st.session_state:
    st.session_state['role'] = ""

@login_required
def page_dashboard():
    st.title("Dashboard Overview")
    df = db.get_df("SELECT * FROM jurnal ORDER BY tanggal ASC")
    if not df.empty:
        df['tanggal_dt'] = pd.to_datetime(df['tanggal'])
    
    st.subheader("🤖 AI Business Insights")
    with st.expander("Lihat Analisis Bisnis", expanded=True):
        saran_list = generate_smart_insights(df)
        for saran in saran_list:
            st.markdown(saran)
    st.markdown("<br>", unsafe_allow_html=True)

    pdp = db.get_acc_by_type(['Pendapatan'])
    bbn = db.get_acc_by_type(['Beban'])
    rev=0
    exp=0
    laba=0
    kas=0
    
    if not df.empty:
        rev = df[df['akun_kredit'].isin(pdp)]['nominal'].sum()
        exp = df[df['akun_debit'].isin(bbn)]['nominal'].sum()
        laba = rev - exp
        kas = df[df['akun_debit'] == 'Kas']['nominal'].sum() - df[df['akun_kredit'] == 'Kas']['nominal'].sum()
    
    low_stock = len(db.get_df("SELECT * FROM inventory WHERE stok_saat_ini <= min_stok"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Revenue", f"Rp {rev/1000000:.1f} M")
    c2.metric("Total Expense", f"Rp {exp/1000000:.1f} M")
    c3.metric("Net Profit", f"Rp {laba/1000000:.1f} M")
    c4.metric("Stock Alert", f"{low_stock} Items", delta="Warning" if low_stock>0 else "OK", delta_color="inverse")

    st.markdown("<br>", unsafe_allow_html=True)
    c_title, c_filter = st.columns([3, 1])
    with c_title:
        st.subheader("📊 Analisis Grafik")
    with c_filter:
        time_mode = st.selectbox("Periode:", ["Harian", "Bulanan", "Tahunan"], label_visibility="collapsed")
    
    if not df.empty:
        if time_mode == "Bulanan":
            df['periode'] = df['tanggal_dt'].dt.strftime('%Y-%m')
        elif time_mode == "Tahunan":
            df['periode'] = df['tanggal_dt'].dt.strftime('%Y')
        else:
            df['periode'] = df['tanggal']

    c_l, c_r = st.columns([2, 1])
    with c_l:
        st.caption(f"Arus Kas ({time_mode})")
        if not df.empty:
            df_inc = df[df['akun_kredit'].isin(pdp)].groupby('periode')['nominal'].sum().reset_index()
            df_inc['Type'] = 'Pemasukan'
            df_out = df[df['akun_debit'].isin(bbn)].groupby('periode')['nominal'].sum().reset_index()
            df_out['Type'] = 'Pengeluaran'
            df_cf = pd.concat([df_inc, df_out])
            fig = px.bar(df_cf, x='periode', y='nominal', color='Type', barmode='group', color_discrete_map={'Pemasukan': '#768209', 'Pengeluaran': '#d32f2f'})
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(t=0, b=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No Data")

    with c_r:
        st.caption(f"Tren Profit ({time_mode})")
        if not df.empty:
            df_pv = df_cf.pivot_table(index='periode', columns='Type', values='nominal', aggfunc='sum').fillna(0)
            if 'Pemasukan' not in df_pv:
                df_pv['Pemasukan']=0
            if 'Pengeluaran' not in df_pv:
                df_pv['Pengeluaran']=0
            df_pv['Profit'] = df_pv['Pemasukan'] - df_pv['Pengeluaran']
            fig_l = px.line(df_pv.reset_index(), x='periode', y='Profit', markers=True, color_discrete_sequence=['#3B2417'])
            fig_l.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(t=0, b=0))
            st.plotly_chart(fig_l, use_container_width=True)
        else:
            st.info("No Data")

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("🍕 Komposisi Pengeluaran")
    if not df.empty:
        df_b = df[df['akun_debit'].isin(bbn)]
        if not df_b.empty:
            fig_p = px.pie(df_b.groupby('akun_debit')['nominal'].sum().reset_index(), values='nominal', names='akun_debit', hole=0.5, color_discrete_sequence=['#768209', '#8E9926', '#A7B042', '#3B2417', '#5A3A29'])
            fig_p.update_layout(height=400, margin=dict(t=20, b=20), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_p, use_container_width=True)
        else:
            st.info("Belum ada pengeluaran.")
    else:
        st.info("Belum ada data.")

@login_required
def page_inventory():
    st.title("📦 Inventory Management")
    items_df = db.get_df("SELECT kode_barang, nama_barang, stok_saat_ini, min_stok, satuan FROM inventory ORDER BY nama_barang")
    tab_titles = ["📝 Input & Master"] + ([f"📦 {row['nama_barang']}" for _, row in items_df.iterrows()] if not items_df.empty else [])
    tabs = st.tabs(tab_titles)
    
    with tabs[0]:
        c_a, c_b = st.columns([1,1])
        
        with c_a:
            st.subheader("🆕 Register New Item")
            with st.form("new_itm"):
                kd = st.text_input("Kode Barang (e.g. PKN-01)")
                nm = st.text_input("Nama Barang")
                c1, c2 = st.columns(2)
                cat = c1.selectbox("Kategori", ["Pakan","Obat","Produk","Lainnya"])
                sat = c2.text_input("Satuan", "Pcs")
                min_s = st.number_input("Min. Stok Alert", 10)
                if st.form_submit_button("Simpan", type="primary"):
                    if db.run_query("INSERT INTO inventory (kode_barang, nama_barang, kategori, satuan, min_stok) VALUES (?,?,?,?,?)", (kd, nm, cat, sat, min_s)):
                        st.success("Item Created!")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("Kode sudah ada!")
        
        with c_b:
            st.subheader("📝 Stock Transaction")
            with st.form("stock_entry"):
                c1, c2 = st.columns(2)
                tgl = c1.date_input("Tanggal", date.today())
                item_opts = [f"{r['kode_barang']} | {r['nama_barang']} (Sisa: {r['stok_saat_ini']})" for _, r in items_df.iterrows()]
                sel_item = c2.selectbox("Pilih Barang", item_opts)
                c3, c4, c5 = st.columns(3)
                act = c3.radio("Aksi", ["IN", "OUT"])
                qty = c4.number_input("Qty", min_value=0.1)
                prc = c5.number_input("Harga @", min_value=0.0, step=1000.0)
                note = st.text_input("Ket")
                st.markdown("---")
                auto_jurnal = st.checkbox("Auto Jurnal?", value=True)
                aset = db.get_acc_by_type(['Aset'])
                beban = db.get_acc_by_type(['Beban'])
                if auto_jurnal:
                    j1, j2 = st.columns(2)
                    if act=="IN":
                        jd=j1.selectbox("Db (Aset)", aset)
                        jk=j2.selectbox("Cr (Kas)", aset)
                    else:
                        jd=j1.selectbox("Db (Beban/HPP)", beban)
                        jk=j2.selectbox("Cr (Persediaan)", aset)
                if st.form_submit_button("Simpan Transaksi", type="primary"):
                    if not item_opts:
                        st.error("Barang Kosong")
                        st.stop()
                    code = sel_item.split(" | ")[0]
                    curr = db.get_one("SELECT stok_saat_ini FROM inventory WHERE kode_barang=?", (code,))[0]
                    if act=="OUT" and curr<qty:
                        st.error("Stok Kurang")
                    else:
                        op = "+" if act=="IN" else "-"
                        db.run_query(f"UPDATE inventory SET stok_saat_ini=stok_saat_ini{op}? WHERE kode_barang=?", (qty,code))
                        db.run_query("INSERT INTO stock_log (tanggal, kode_barang, jenis_gerak, jumlah, harga_satuan, keterangan, user) VALUES (?,?,?,?,?,?,?)", (tgl,code,act,qty,prc,note,st.session_state['username']))
                        if auto_jurnal and prc>0:
                            db.run_query("INSERT INTO jurnal (tanggal, deskripsi, akun_debit, akun_kredit, nominal, created_by) VALUES (?,?,?,?,?,?)", (tgl, f"STOK {code}: {note}", jd, jk, qty*prc, "SYS"))
                        st.success("Saved!")
                        time.sleep(0.5)
                        st.rerun()
            
            logs_df = db.get_df("SELECT * FROM stock_log ORDER BY id DESC LIMIT 20")
            if not logs_df.empty:
                with st.expander("🔧 Hapus Riwayat Stok"):
                    l_opt = logs_df.apply(lambda x: f"ID:{x['id']} | {x['kode_barang']} {x['jenis_gerak']} {x['jumlah']}", axis=1)
                    s_log = st.selectbox("Pilih Log:", l_opt)
                    if st.button("🗑️ Hapus & Reverse Stok", type="primary"):
                        lid = int(s_log.split(" |")[0].replace("ID:", ""))
                        ld = db.get_one("SELECT * FROM stock_log WHERE id=?", (lid,))
                        rev_op = "-" if ld['jenis_gerak']=="IN" else "+"
                        db.run_query(f"UPDATE inventory SET stok_saat_ini=stok_saat_ini{rev_op}? WHERE kode_barang=?", (ld['jumlah'], ld['kode_barang']))
                        db.run_query("DELETE FROM stock_log WHERE id=?", (lid,))
                        st.success("Reversed!")
                        time.sleep(0.5)
                        st.rerun()

    for i, (_, row) in enumerate(items_df.iterrows()):
        with tabs[i+1]:
            st.markdown(f"### {row['nama_barang']}")
            st.caption(f"Min: {row['min_stok']}")
            df_c = db.get_inventory_card_df(row['kode_barang'])
            if not df_c.empty: 
                st.dataframe(df_c.style.set_properties(**{'text-align': 'right'}, subset=df_c.columns[2:]).set_table_styles([{'selector': 'th', 'props': [('text-align', 'center'), ('background-color', '#f0f2f6')]}]), use_container_width=True, height=500)
            else:
                st.info("No Tx")

@login_required
def page_jurnal():
    st.title("Journal Entries")
    curr_user = st.session_state['username']
    kas = db.get_acc_by_type(['Aset'])
    pdp = db.get_acc_by_type(['Pendapatan'])
    bbn = db.get_acc_by_type(['Beban'])
    all_acc = db.get_all_acc()
    t1, t2, t3 = st.tabs(["🛒 Jual", "🛍️ Beli", "⚙️ Umum"])
    
    def post_trx(tgl, desc, d, c, qty, price, manual_total, tipe):
        if qty > 0 and price > 0:
            final_nominal = qty * price
            full_desc = f"{desc} ({qty} x {price:,.0f})"
        else:
            final_nominal = manual_total
            full_desc = desc
        try:
            dat = JurnalSchema(tanggal=tgl, deskripsi=full_desc, akun_debit=d, akun_kredit=c, nominal=final_nominal, created_by=curr_user)
            if db.run_query("INSERT INTO jurnal (tanggal, deskripsi, akun_debit, akun_kredit, nominal, created_by) VALUES (?,?,?,?,?,?)", (dat.tanggal, dat.deskripsi, dat.akun_debit, dat.akun_kredit, dat.nominal, dat.created_by)):
                log_activity(curr_user, "POST", f"{tipe}-{full_desc}")
                st.success(f"✅ Berhasil! Total: Rp {final_nominal:,.0f}")
                time.sleep(0.5)
                st.rerun()
        except ValidationError as e:
            st.error(e.errors()[0]['msg'])
            
    with t1:
        st.info("💡 Tips: Isi 'Qty' dan 'Harga' untuk hitung otomatis. Atau isi 'Total Manual' saja.")
        with st.form("in"):
            c1, c2 = st.columns(2)
            t = c1.date_input("Tgl", date.today())
            d = c2.text_input("Ket")
            c3, c4 = st.columns(2)
            dk = c3.selectbox("Db", kas)
            ck = c4.selectbox("Cr", pdp)
            st.markdown("---")
            k1, k2, k3 = st.columns([1,1,2])
            q = k1.number_input("Q", 0.0)
            p = k2.number_input("P", 0.0)
            m = k3.number_input("Total Manual", 0.0)
            if st.form_submit_button("Post", type="primary"):
                post_trx(t, d, dk, ck, q, p, m, "IN")
    with t2:
        st.info("💡 Tips: Isi 'Qty' dan 'Harga' untuk hitung otomatis.")
        with st.form("out"):
            c1, c2 = st.columns(2)
            t = c1.date_input("Tgl", key="o1")
            d = c2.text_input("Ket", key="o2")
            c3, c4 = st.columns(2)
            dk = c3.selectbox("Db", bbn+kas)
            ck = c4.selectbox("Cr", kas, key="o3")
            st.markdown("---")
            k1, k2, k3 = st.columns([1,1,2])
            q = k1.number_input("Q", 0.0, key="oq")
            p = k2.number_input("P", 0.0, key="op")
            m = k3.number_input("Total Manual", 0.0, key="om")
            if st.form_submit_button("Post", type="primary"):
                post_trx(t, d, dk, ck, q, p, m, "OUT")
    with t3:
        with st.form("gen"):
            c1, c2 = st.columns(2)
            t = c1.date_input("Tgl", key="g1")
            d = c2.text_input("Ref", key="g2")
            c3, c4 = st.columns(2)
            dk = c3.selectbox("Db", all_acc, key="g3")
            ck = c4.selectbox("Cr", all_acc, index=1, key="g4")
            st.markdown("---")
            k1, k2, k3 = st.columns([1, 1, 2])
            q = k1.number_input("Q", 0.0, key="gq")
            p = k2.number_input("P", 0.0, key="gp")
            m = k3.number_input("Total Manual", 0.0, key="gm")
            if st.form_submit_button("Post", type="primary"):
                post_trx(t, d, dk, ck, q, p, m, "GEN")
    st.markdown("---")
    
    col_header, col_filter = st.columns([2, 1])
    with col_header:
        st.subheader("📋 Buku Jurnal Umum")
    with col_filter:
        f_mode = st.selectbox("Filter Kategori:", ["Semua", "🛒 Penjualan", "🛍️ Pembelian", "⚙️ Umum"])
        
    df = db.get_df("SELECT * FROM jurnal ORDER BY id DESC")
    if not df.empty:
        if f_mode == "🛒 Penjualan":
            df = df[df['deskripsi'].str.contains("PENJUALAN", case=False) | df['akun_kredit'].isin(pdp)]
        elif f_mode == "🛍️ Pembelian":
            df = df[df['deskripsi'].str.contains("PEMBELIAN", case=False) | df['akun_debit'].isin(bbn)]
        elif f_mode == "⚙️ Umum":
            df = df[~df['deskripsi'].str.contains("PENJUALAN|PEMBELIAN", case=False)]
        if not df.empty:
            view=[]
            for _,r in df.iterrows():
                view.append({"Tanggal":r['tanggal'],"Keterangan":r['akun_debit'],"Ref":"Db","Debit":r['nominal'],"Kredit":0,"Detail":r['deskripsi']})
                view.append({"Tanggal":"","Keterangan":f"      {r['akun_kredit']}","Ref":"Cr","Debit":0,"Kredit":r['nominal'],"Detail":""})
            df_view = pd.DataFrame(view)
            st.dataframe(df_view, column_config={"Tanggal": st.column_config.TextColumn("Tanggal", width="small"), "Keterangan": st.column_config.TextColumn("Nama Akun", width="large"), "Ref": st.column_config.TextColumn("Ref", width="small"), "Debit": st.column_config.NumberColumn("Debit", format="Rp %.0f"), "Kredit": st.column_config.NumberColumn("Kredit", format="Rp %.0f"), "Detail": st.column_config.TextColumn("Keterangan Transaksi", width="medium")}, use_container_width=True, hide_index=True, height=500)
            st.markdown("---")
            c1, c2 = st.columns([1,1])
            with c1:
                b=io.BytesIO()
                with pd.ExcelWriter(b, engine='xlsxwriter') as w: df.to_excel(w, index=False)
                st.download_button("📥 Excel", b, "Data.xlsx")
            with c2:
                with st.expander("🔧 Hapus/Cetak"):
                    sel = st.selectbox("Pilih", df.apply(lambda x: f"{x['id']} | {x['deskripsi']} | {x['nominal']:,.0f}", axis=1))
                    if sel:
                        sid = int(sel.split(" |")[0])
                        cx, cy = st.columns(2)
                        with cx: 
                            t = df[df['id']==sid].iloc[0]
                            st.download_button("🖨️ PDF", generate_pdf(sid, t['tanggal'], t['deskripsi'], t['nominal'], t['akun_debit'], t['akun_kredit']), "Doc.pdf")
                        with cy:
                            if st.button("🗑️ Hapus", type="primary"):
                                db.run_query("DELETE FROM jurnal WHERE id=?", (sid,))
                                st.success("Dihapus")
                                st.rerun()
        else:
            st.info("Kosong")
    else:
        st.info("Belum ada data")

@login_required
def page_buku_besar():
    st.title("General Ledger")
    acc_name = st.selectbox("Pilih Akun:", db.get_all_acc())
    acc_info = db.get_df("SELECT kode_akun, tipe_akun FROM akun WHERE nama_akun=?", (acc_name,)).iloc[0]
    is_db = True if acc_info['tipe_akun'] in ['Aset','Beban'] else False
    st.caption(f"Kode: {acc_info['kode_akun']} | Normal: {'Debit' if is_db else 'Kredit'}")

    df = db.get_df("SELECT * FROM jurnal WHERE akun_debit=? OR akun_kredit=? ORDER BY tanggal ASC, id ASC", (acc_name, acc_name))
    if not df.empty:
        data = []
        run_bal = 0
        for _, r in df.iterrows():
            d = r['nominal'] if r['akun_debit']==acc_name else 0
            c = r['nominal'] if r['akun_kredit']==acc_name else 0
            if is_db:
                run_bal += (d - c)
            else:
                run_bal += (c - d)
            bd = run_bal if (is_db and run_bal>=0) or (not is_db and run_bal<0) else 0
            bc = run_bal if (not is_db and run_bal>=0) or (is_db and run_bal<0) else 0
            data.append([pd.to_datetime(r['tanggal']).strftime("%m"), pd.to_datetime(r['tanggal']).strftime("%d"), r['deskripsi'], f"Rp{d:,.0f}" if d else "", f"Rp{c:,.0f}" if c else "", f"Rp{bd:,.0f}" if bd else "", f"Rp{bc:,.0f}" if bc else ""])
        
        cols = pd.MultiIndex.from_tuples([("Tgl","Bln"),("Tgl","Hari"),("Ket",""),("Mutasi","Debit"),("Mutasi","Kredit"),("Saldo","Debit"),("Saldo","Kredit")])
        st.markdown("<style>th{text-align:center;background:#FFC107 !important;color:black !important;border:1px solid #ddd !important} td{border:1px solid #ddd !important}</style>", unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(data, columns=cols), use_container_width=True, height=500)
    else:
        st.info("No data")

@login_required
def page_laporan():
    st.title("Reports")
    t_ns, t_lr, t_pos = st.tabs(["⚖️ Neraca Saldo", "📉 Laba Rugi (Detail)", "🏛️ Neraca"])
    df = db.get_df("SELECT * FROM jurnal")
    if df.empty:
        st.info("No Data")
        return

    with t_ns:
        st.markdown('<h4 style="text-align:center">NERACA SALDO</h4><hr>', unsafe_allow_html=True)
        accs = db.get_df("SELECT kode_akun, nama_akun, tipe_akun FROM akun ORDER BY kode_akun")
        data=[]
        td=0
        tk=0
        for _,r in accs.iterrows():
            d = df[df['akun_debit']==r['nama_akun']]['nominal'].sum()
            k = df[df['akun_kredit']==r['nama_akun']]['nominal'].sum()
            if r['tipe_akun'] in ["Aset","Beban"] and "Akumulasi" not in r['nama_akun']:
                bal=d-k
                sd=bal if bal>0 else 0
                sk=abs(bal) if bal<0 else 0
            else:
                bal=k-d
                sd=0
                sk=bal
            if sd!=0 or sk!=0:
                data.append([r['kode_akun'], r['nama_akun'], sd, sk])
                td+=sd
                tk+=sk
        data.append(["", "TOTAL", td, tk])
        df_ns = pd.DataFrame(data, columns=["Kode", "Akun", "Debit", "Kredit"])
        st.dataframe(df_ns.style.format({"Debit":"Rp {:,.0f}", "Kredit":"Rp {:,.0f}"}).apply(lambda x: ['font-weight:bold; background:#ffdcb2' if x.name==len(df_ns)-1 else '' for _ in x], axis=1), use_container_width=True, hide_index=True)

    with t_lr:
        st.markdown('<h4 style="text-align:center">LAPORAN LABA RUGI</h4>', unsafe_allow_html=True)
        def show_detail_section(label, filter_col, acc_list):
            subset = df[df[filter_col].isin(acc_list)]
            total = subset['nominal'].sum()
            st.markdown(f"**{label}**")
            st.write(f"Total: **Rp {total:,.0f}**")
            with st.expander(f"👁️ Lihat Rincian {label}"):
                if not subset.empty:
                    st.dataframe(subset[['tanggal', 'deskripsi', 'nominal']].sort_values('tanggal'), use_container_width=True, hide_index=True)
                else:
                    st.caption("- Kosong -")
            return total
        st.write("##### I. PENDAPATAN")
        pdp = db.get_acc_by_type(['Pendapatan'])
        retur = [x for x in pdp if "Return" in x]
        sales = [x for x in pdp if "Return" not in x]
        tot_s = show_detail_section("Penjualan Kotor", "akun_kredit", sales)
        st.write("") 
        tot_r = show_detail_section("Retur Penjualan", "akun_debit", retur)
        net_s = tot_s - tot_r
        st.info(f"💰 **Pendapatan Bersih: Rp {net_s:,.0f}**")
        st.markdown("---")
        st.write("##### II. BEBAN OPERASIONAL")
        bbn = db.get_acc_by_type(['Beban'])
        pokok = [b for b in bbn if any(x in b for x in ['HPP','Pakan','Obat','Ternak'])]
        umum = [b for b in bbn if b not in pokok]
        tot_p = show_detail_section("A. Beban Pokok Produksi", "akun_debit", pokok)
        st.write("")
        tot_u = show_detail_section("B. Beban Umum & Administrasi", "akun_debit", umum)
        laba = net_s - (tot_p + tot_u)
        st.divider()
        st.markdown(f"<h3 style='text-align:right; color:{'green' if laba>=0 else 'red'}'>LABA BERSIH: Rp {laba:,.0f}</h3>", unsafe_allow_html=True)

    with t_pos:
        st.markdown('<h4 style="text-align:center">POSISI KEUANGAN</h4>', unsafe_allow_html=True)
        ast = db.get_acc_by_type(['Aset'])
        liab = db.get_acc_by_type(['Kewajiban'])
        mod = db.get_acc_by_type(['Modal'])
        def get_bal(ac, is_ast):
            res=[]
            tot=0
            for a in ac:
                d=df[df['akun_debit']==a]['nominal'].sum()
                k=df[df['akun_kredit']==a]['nominal'].sum()
                if "Akumulasi" in a:
                    val=k-d
                    tot-=val
                    txt=f"({val:,.0f})"
                elif is_ast:
                    val=d-k
                    tot+=val
                    txt=f"{val:,.0f}"
                else:
                    val=k-d
                    tot+=val
                    txt=f"{val:,.0f}"
                if val!=0:
                    res.append([a, txt])
            return res, tot
        da, ta = get_bal(ast, True)
        dl, tl = get_bal(liab, False)
        dm, tm = get_bal(mod, False)
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("ASET")
            st.table(pd.DataFrame(da, columns=["Akun","Nilai"]))
            st.info(f"TOTAL ASET: Rp {ta:,.0f}")
        with c2:
            st.subheader("PASIVA")
            st.write("Kewajiban")
            st.table(pd.DataFrame(dl, columns=["Akun","Nilai"]))
            st.write("Ekuitas")
            dfm = pd.DataFrame(dm, columns=["Akun","Nilai"])
            dfm.loc[len(dfm)]=["Laba Berjalan", f"{laba:,.0f}"]
            st.table(dfm)
            st.success(f"TOTAL PASIVA: Rp {tl+tm+laba:,.0f}")

@login_required
def page_master():
    st.title("Master Data")
    t1, t2 = st.tabs(["Accounts", "Logs"])
    with t1:
        with st.form("add_acc"):
            kd = st.text_input("Code (e.g. 1-11)")
            nm = st.text_input("Name")
            tp = st.selectbox("Type", ["Aset","Kewajiban","Modal","Pendapatan","Beban"])
            if st.form_submit_button("Save", type="primary"): 
                db.run_query("INSERT INTO akun (kode_akun, nama_akun, tipe_akun) VALUES (?,?,?)", (kd,nm,tp))
                st.rerun()
        st.dataframe(db.get_df("SELECT * FROM akun ORDER BY kode_akun"), use_container_width=True)
    with t2:
        try:
            with open("system.log", "r") as f:
                st.text(f.read())
        except:
            st.info("No logs")
    st.markdown("---")
    with st.expander("🔥 Factory Reset (Danger Zone)"):
        st.warning("Ini akan menghapus SEMUA transaksi jurnal dan stok!")
        if st.button("RESET SEMUA DATA", type="primary"):
            db.run_query("DELETE FROM jurnal")
            db.run_query("DELETE FROM stock_log")
            db.run_query("UPDATE inventory SET stok_saat_ini = 0")
            st.success("Sistem Bersih!")
            time.sleep(1)
            st.rerun()

def login_page():
    inject_login_css()
    col_left, col_right = st.columns([1.3, 1], gap="large")
    with col_left:
        logo_html = ""
        try:
            img_b64 = get_img_as_base64("logo.png")
            logo_html = f'<img src="data:image/png;base64,{img_b64}" class="brand-logo-img">'
        except:
            logo_html = "<h2>Hasna Farm</h2>"
        st.markdown(f"""<div class="brand-box">{logo_html}<p class="brand-subtitle">Hasna Farm Enterprise</p><p class="brand-desc">Sistem Informasi Akuntansi &<br>Manajemen Peternakan Modern</p></div>""", unsafe_allow_html=True)
    with col_right:
        with st.form("login_form"):
            st.markdown("<h3 style='text-align:center; color:#333; margin:0 0 20px 0;'>Login</h3>", unsafe_allow_html=True)
            u = st.text_input("Username", placeholder="Masukkan username")
            p = st.text_input("Password", type="password", placeholder="Masukkan password")
            st.markdown("<br>", unsafe_allow_html=True)
            if st.form_submit_button("MASUK"):
                user = db.get_one("SELECT * FROM users WHERE username=? AND password=?", (u, make_hash(p)))
                if user:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = user['username']
                    st.session_state['role'] = user['role']
                    st.rerun()
                else:
                    st.error("Username atau Password Salah")
        st.markdown("<p style='text-align:center; font-size:12px; color:#fff; margin-top:20px; text-shadow: 0 1px 2px rgba(0,0,0,0.8);'>© 2025 Hasna Farm Enterprise</p>", unsafe_allow_html=True)

def main_app():
    inject_main_css()
    role = st.session_state['role']
    if role == "Manager":
        opts = ["Launchpad", "Inventory", "Journal", "General Ledger", "Reports", "Master Data", "Logout"]
        icns = ["grid-fill", "box-seam-fill", "receipt", "book-half", "file-earmark-bar-graph", "database-fill-gear", "power"]
    else:
        opts = ["Inventory", "Journal", "General Ledger", "Logout"] 
        icns = ["box-seam-fill", "receipt", "book-half", "power"]
    c_logo_kiri, c_menu, c_logo_kanan = st.columns([1, 10, 1])
    with c_logo_kiri:
        try:
            st.write("")
            st.image("logo.png", width=80)
        except:
            st.empty()
    with c_menu:
        selected = option_menu(menu_title=None, options=opts, icons=icns, default_index=0, orientation="horizontal",
            styles={"container": {"padding": "5px!important", "background-color": "#768209", "border-radius": "10px", "box-shadow": "0 4px 6px rgba(0,0,0,0.1)"},
                    "icon": {"color": "white", "font-size": "16px"}, "nav-link": {"font-size": "14px", "text-align": "center", "margin": "0px 5px", "color": "white", "font-weight": "500"},
                    "nav-link-hover": {"background-color": "#5a6307"}, "nav-link-selected": {"background-color": "#3B2417", "font-weight": "700", "border-radius": "8px"}})
    with c_logo_kanan:
        try:
            st.write("")
            st.image("logo_kanan.png", width=80)
        except:
            st.empty()
    if selected != "Logout":
        st.markdown(f"""<div style='text-align: right; padding: 10px 0; font-size: 0.9rem; color: #666;'>Login sebagai: <b>{st.session_state['username']}</b> <span style='background:#e5e7eb; padding:2px 8px; border-radius:10px; font-size:0.8rem;'>{role}</span></div>""", unsafe_allow_html=True)
    if selected == "Launchpad": page_dashboard()
    elif selected == "Inventory": page_inventory()
    elif selected == "Journal": page_jurnal()
    elif selected == "General Ledger": page_buku_besar()
    elif selected == "Reports": page_laporan()
    elif selected == "Master Data": page_master()
    elif selected == "Logout":
        log_activity(st.session_state['username'], "LOGOUT", "User logged out")
        st.session_state['logged_in'] = False
        st.rerun()

if __name__ == "__main__":
    if st.session_state['logged_in']: main_app()
    else: login_page()