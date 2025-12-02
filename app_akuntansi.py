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
            c.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    id INTEGER PRIMARY KEY, 
                    kode_barang TEXT UNIQUE, 
                    nama_barang TEXT, 
                    kategori TEXT, 
                    satuan TEXT, 
                    stok_saat_ini REAL, 
                    min_stok REAL
                )
            """)

            
            cursor = c.execute("PRAGMA table_info(inventory)")
            
            existing_cols = [row['name'] for row in cursor.fetchall()]

            
            if 'akun_aset' not in existing_cols:
                c.execute("ALTER TABLE inventory ADD COLUMN akun_aset TEXT")
            
            if 'akun_hpp' not in existing_cols:
                c.execute("ALTER TABLE inventory ADD COLUMN akun_hpp TEXT")
            
            if 'std_cost' not in existing_cols:
                c.execute("ALTER TABLE inventory ADD COLUMN std_cost REAL DEFAULT 0")

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
                    ("PKN-MERAH", "Pakan Kukila Merah", "Pakan", "Sak", 0, 5, "Persediaan Pakan Ternak", "Beban Pakan", 360000),
                    ("PKN-BIRU", "Pakan Kukila Biru", "Pakan", "Sak", 0, 5, "Persediaan Pakan Ternak", "Beban Pakan", 435000),
                    ("TELUR", "Telur Puyuh", "Produk", "Dus", 0, 10, "Persediaan Telur Puyuh", "HPP Telur Puyuh", 285000),
                    ("PUPUK", "Pupuk Organik (Kotoran)", "Produk", "Sak", 0, 5, "Persediaan Kotoran (Pupuk)", "HPP Kotoran (Pupuk)", 5000),
                    ("VIT-OBAT", "Vitamin & Obat", "Obat", "Paket", 0, 2, "Persediaan Obat & Vitamin", "Beban Obat & Vitamin", 100000)
                ]
                
                c.executemany("INSERT INTO inventory (kode_barang, nama_barang, kategori, satuan, stok_saat_ini, min_stok, akun_aset, akun_hpp, std_cost) VALUES (?,?,?,?,?,?,?,?,?)", real_inv)
            
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
    
   
    st.markdown("""
    <style>
        .info-box {
            background-color: #f4f6e6;      /* Warna Latar: Krem Kehijauan (sesuai tema) */
            border-left: 6px solid #768209; /* Garis Kiri: Hijau Tua (Logo) */
            padding: 20px;
            border-radius: 10px;
            color: #2c3e50;
            margin-bottom: 25px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .info-box ul {
            margin-bottom: 0;
            padding-left: 20px;
        }
        .info-box li {
            margin-bottom: 5px;
        }
    </style>
    
    <div class="info-box">
        <strong>Halaman ini berfungsi sebagai pusat kendali utama untuk memantau performa bisnis Hasna Farm secara Real-Time.</strong>
        <br><br>
        <strong>Di sini Anda dapat melihat:</strong>
        <ul>
            <li>🤖 <b>AI Insights:</b> Analisis cerdas otomatis mengenai kondisi likuiditas kas dan pos pengeluaran terbesar.</li>
            <li>📊 <b>Key Metrics:</b> Ringkasan cepat Total Pendapatan, Pengeluaran, Net Profit, dan Peringatan Stok Menipis.</li>
            <li>📈 <b>Grafik Tren:</b> Visualisasi pergerakan Arus Kas (Pemasukan vs Pengeluaran) dan Tren Profitabilitas antar periode.</li>
            <li>🍕 <b>Komposisi Beban:</b> Persentase alokasi biaya operasional untuk membantu efisiensi anggaran.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    # -------------------------------------------------------------

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
    val_rev = f"Rp {rev/1000000:.1f} Jt".replace('.', ',')
    val_exp = f"Rp {exp/1000000:.1f} Jt".replace('.', ',')
    val_laba = f"Rp {laba/1000000:.1f} Jt".replace('.', ',')
    
    c1.metric("Total Pendapatan", val_rev)
    c2.metric("Total Pengeluaran", val_exp)
    c3.metric("Laba Bersih", val_laba)
    c4.metric("Peringatan Stok", f"{low_stock} Barang", delta="Perhatian" if low_stock>0 else "Aman", delta_color="inverse")

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
    st.title("📦 Inventory Monitoring")
    
    
    st.markdown("""
    <style>
        .stock-card {
            background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px;
            padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.02);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .stock-card:hover {
            transform: translateY(-5px); box-shadow: 0 10px 15px rgba(118, 130, 9, 0.15); border-color: #768209;
        }
        .card-title { font-size: 16px; font-weight: 700; color: #1f2937; margin-bottom: 5px; }
        .card-category { font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; }
        .stock-val { font-size: 24px; font-weight: 800; color: #768209; }
        .stock-unit { font-size: 14px; color: #6b7280; font-weight: 500; }
        .progress-bg { background-color: #f3f4f6; height: 8px; border-radius: 4px; overflow: hidden; margin-top: 10px; }
        .progress-fill { height: 100%; border-radius: 4px; transition: width 0.5s ease-in-out; }
        .badge { padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; float: right; }
        .badge-safe { background-color: #dcfce7; color: #166534; }
        .badge-low { background-color: #fee2e2; color: #991b1b; }
        
        /* Tabel Transparan */
        .custom-table { width: 100%; border-collapse: collapse; margin-top: 15px; color: #374151; background-color: transparent !important; }
        .custom-table thead tr:first-child th { background-color: #768209; color: white; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; padding: 8px; border-radius: 6px 6px 0 0; }
        .custom-table thead tr:last-child th { border-bottom: 2px solid #768209; font-size: 12px; color: #768209; font-weight: 700; padding: 10px 8px; text-align: right; }
        .custom-table thead tr:last-child th:nth-child(1), .custom-table thead tr:last-child th:nth-child(2) { text-align: left; }
        .custom-table tbody tr { background-color: transparent !important; border-bottom: 1px solid rgba(0,0,0,0.05); }
        .custom-table tbody tr:hover { background-color: rgba(118, 130, 9, 0.05) !important; }
        .custom-table td { padding: 12px 8px; font-size: 13.5px; text-align: right; }
        .custom-table td:nth-child(1) { text-align: left; white-space: nowrap; font-weight: 600; color: #555; }
        .custom-table td:nth-child(2) { text-align: left; color: #1f2937; }
        .val-in { color: #15803d; font-weight: 700; background-color: rgba(22, 163, 74, 0.05); border-radius: 4px; padding: 2px 6px; }
        .val-out { color: #b91c1c; font-weight: 700; background-color: rgba(220, 38, 38, 0.05); border-radius: 4px; padding: 2px 6px; }
        .val-bal { font-weight: 800; color: #374151; }
        
        .info-box { background-color: #f4f6e6; border-left: 6px solid #768209; padding: 20px; border-radius: 10px; color: #2c3e50; margin-bottom: 25px; }
        .info-box ul { margin-bottom: 0; padding-left: 20px; }
    </style>
    """, unsafe_allow_html=True)

    
    st.markdown("""
    <div class="info-box">
        <strong>Monitoring Stok Gudang Real-Time</strong>
        <ul>
            <li>📦 <b>Visualisasi Kartu:</b> Melihat ketersediaan barang dengan tampilan visual.</li>
            <li>⚠️ <b>Indikator Warna:</b> Batang stok merah jika menipis.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    
    df_inv = db.get_df("SELECT kode_barang, nama_barang, kategori, satuan, stok_saat_ini, min_stok FROM inventory ORDER BY nama_barang ASC")
    if df_inv.empty:
        st.info("Belum ada data barang."); return

   
    c_filter, c_metric = st.columns([1, 2])
    with c_filter:
        pilih_kat = st.selectbox("📂 Filter Kategori:", ["Semua"] + df_inv['kategori'].unique().tolist())
    with c_metric:
        low_stock = len(df_inv[df_inv['stok_saat_ini'] <= df_inv['min_stok']])
        st.markdown(f"""<div style="padding-top:15px;"><b>Total SKU:</b> {len(df_inv)} | <span style="color:{'#d32f2f' if low_stock > 0 else '#768209'}"><b>Perlu Restock:</b> {low_stock}</span></div>""", unsafe_allow_html=True)
    st.markdown("---")

    
    view_df = df_inv.copy()
    if pilih_kat != "Semua": view_df = view_df[view_df['kategori'] == pilih_kat]

    def get_icon(kat):
        if "Pakan" in kat: return "🐔"
        if "Obat" in kat: return "💊"
        if "Telur" in kat or "Produk" in kat: return "🥚"
        return "📦"

    cols = st.columns(3)
    for i, row in view_df.reset_index().iterrows():
        is_low = row['stok_saat_ini'] <= row['min_stok']
        color = "#ef4444" if is_low else "#768209"
        bg_badge = "badge-low" if is_low else "badge-safe"
        txt_badge = "PERLU RESTOCK" if is_low else "AMAN"
        max_visual = row['min_stok'] * 4 if row['min_stok'] > 0 else 100
        pct = min((row['stok_saat_ini'] / max_visual) * 100, 100)
        
        with cols[i % 3]:
            st.markdown(f"""
            <div class="stock-card">
                <div style="display:flex; justify-content:space-between; align-items:start;">
                    <div class="card-category">{get_icon(row['kategori'])} {row['kategori']}</div>
                    <span class="badge {bg_badge}">{txt_badge}</span>
                </div>
                <div class="card-title">{row['nama_barang']}</div>
                <div style="margin-top:10px;"><span class="stock-val">{row['stok_saat_ini']:,.0f}</span> <span class="stock-unit">{row['satuan']}</span></div>
                <div class="progress-bg"><div class="progress-fill" style="width: {pct}%; background-color: {color};"></div></div>
                <div style="font-size:11px; color:#9ca3af; margin-top:5px;">Min. Alert: {row['min_stok']} {row['satuan']}</div>
            </div>""", unsafe_allow_html=True)
            if st.button("📜 Riwayat", key=f"btn_{row['kode_barang']}", use_container_width=True):
                st.session_state['active_item'] = row['kode_barang']
                st.session_state['active_name'] = row['nama_barang']

    
    if 'active_item' in st.session_state:
        st.markdown("---"); st.subheader(f"🔍 Riwayat: {st.session_state['active_name']}")
        df_kartu = db.get_inventory_card_df(st.session_state['active_item'])
        
        if not df_kartu.empty:
            table_html = """
            <table class="custom-table">
                <thead>
                    <tr><th colspan="2" style="text-align:center">Info Transaksi</th><th colspan="3" style="text-align:center">🟢 Masuk (IN)</th><th colspan="3" style="text-align:center">🔴 Keluar (OUT)</th><th colspan="3" style="text-align:center">📦 Saldo Akhir</th></tr>
                    <tr><th width="10%">Tanggal</th><th width="25%">Keterangan</th><th width="5%">Qty</th><th>Harga</th><th>Total</th><th width="5%">Qty</th><th>Harga</th><th>Total</th><th width="5%">Qty</th><th>Harga</th><th>Total</th></tr>
                </thead><tbody>"""
            
            for _, row in df_kartu.iterrows():
                desc = row.get(('Detail', 'Desc'), '')
                if desc.strip() in ["Buy:", ""]: desc = '<span style="color:#9ca3af; font-style:italic;">(Pembelian Stok)</span>'
                elif desc.strip() in ["Sold:", "Sell:"]: desc = '<span style="color:#9ca3af; font-style:italic;">(Penjualan Produk)</span>'
                
                table_html += f"""<tr>
                    <td>{row.get(('Detail', 'Date'), '')}</td><td>{desc}</td>
                    <td><span class="{'val-in' if row.get(('IN', 'Qty')) else ''}">{row.get(('IN', 'Qty'), '')}</span></td><td style="color:#666">{row.get(('IN', 'Price'), '')}</td><td style="color:#666">{row.get(('IN', 'Total'), '')}</td>
                    <td><span class="{'val-out' if row.get(('OUT', 'Qty')) else ''}">{row.get(('OUT', 'Qty'), '')}</span></td><td style="color:#666">{row.get(('OUT', 'Price'), '')}</td><td style="color:#666">{row.get(('OUT', 'Total'), '')}</td>
                    <td class="val-bal">{row.get(('Balance', 'Qty'), '')}</td><td>{row.get(('Balance', 'Price'), '')}</td><td>{row.get(('Balance', 'Total'), '')}</td>
                </tr>"""
            table_html += "</tbody></table>"
            st.markdown(table_html, unsafe_allow_html=True)
        else: st.info("Belum ada riwayat transaksi.")
        
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Tutup Detail"): del st.session_state['active_item']; st.rerun()

@login_required
def page_jurnal():
    st.title("💸 Financial Journal")
    
    
    st.markdown("""
    <style>
        .stTabs [data-baseweb="tab-list"] { justify-content: center; width: 100%; }
        .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: transparent; border-radius: 4px 4px 0px 0px; gap: 1px; padding-top: 10px; padding-bottom: 10px; flex: 1; }
        div[data-baseweb="tab-highlight"] { background-color: #768209 !important; }
        div[data-baseweb="tab-list"] button[aria-selected="true"] p { color: #768209 !important; font-weight: bold; }
        button[kind="primary"] { background-color: #768209 !important; border-color: #768209 !important; color: white !important; transition: background-color 0.3s ease; }
        button[kind="primary"]:hover { background-color: #5a6307 !important; border-color: #5a6307 !important; }
        
        .info-box { background-color: #f4f6e6; border-left: 6px solid #768209; padding: 20px; border-radius: 10px; color: #2c3e50; margin-bottom: 25px; }
        .journal-table { width: 100%; border-collapse: collapse; font-family: 'Inter', sans-serif; margin-top: 15px; color: #374151; }
        .journal-table thead th { background-color: #768209; color: white; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; padding: 10px; text-align: left; }
        .journal-table tbody tr { border-bottom: 1px solid rgba(0,0,0,0.05); transition: background-color 0.1s; }
        .journal-table tbody tr:hover { background-color: rgba(118, 130, 9, 0.05); }
        .journal-table td { padding: 10px; font-size: 14px; vertical-align: top; }
        .acc-cr { padding-left: 30px !important; color: #4b5563; font-style: italic; }
        .tag-db { background-color: #dcfce7; color: #166534; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight:bold; }
        .tag-cr { background-color: #fee2e2; color: #991b1b; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight:bold; }
        .money { font-family: 'Courier New', monospace; font-weight: 600; text-align: right; }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("""<div class="info-box"><strong>Pencatatan Transaksi Terintegrasi</strong><br>Sistem ini otomatis menghubungkan arus uang dengan stok fisik.<ul><li>💰 <b>Penjualan:</b> Stok berkurang otomatis, Pendapatan bertambah.</li><li>🛒 <b>Pembelian:</b> Stok bertambah otomatis, Kas berkurang.</li></ul></div>""", unsafe_allow_html=True)

    
    akun_kas = db.get_acc_by_type(['Aset'])
    akun_pdp = db.get_acc_by_type(['Pendapatan'])
    akun_bbn = db.get_acc_by_type(['Beban'])
    all_acc = db.get_all_acc()
    inv_df = db.get_df("SELECT kode_barang, nama_barang, stok_saat_ini FROM inventory")
    inv_opts = {f"{r['nama_barang']} (Sisa: {r['stok_saat_ini']})": r['kode_barang'] for _, r in inv_df.iterrows()} if not inv_df.empty else {}
    user_now = st.session_state['username']

    
    t1, t2, t3, t4 = st.tabs(["💰 Penjualan", "🛒 Pembelian", "⚙️ Biaya Umum", "📂 Saldo Awal"])
    
    with t1:
        with st.form("jual"):
            c1, c2 = st.columns(2)
            tgl = c1.date_input("Tgl", date.today(), key="j_tgl")
            brg = c2.selectbox("Produk", list(inv_opts.keys())) if inv_opts else None
            c3, c4, c5 = st.columns(3)
            qty = c3.number_input("Qty", 1.0, step=1.0, key="j_qty")
            prc = c4.number_input("Harga", step=500.0, key="j_prc")
            tot = qty * prc
            c5.metric("Total", f"Rp {tot:,.0f}")
            ket = st.text_input("Ket", placeholder="Pembeli...")
            ca, cb = st.columns(2)
            adb = ca.selectbox("Masuk Ke", akun_kas, key="j_db")
            acr = cb.selectbox("Sumber", akun_pdp, key="j_cr")
        
            if st.form_submit_button("Simpan Penjualan", type="primary"):
                if brg:
                    kd = inv_opts[brg]
                
                
                    cur_data = db.get_one("SELECT stok_saat_ini, akun_aset, akun_hpp, std_cost FROM inventory WHERE kode_barang=?", (kd,))
                    stok_db, acc_aset, acc_hpp, std_cost = cur_data
                
                    if qty > stok_db: st.error("Stok Kurang!"); st.stop()
                
                    nilai_hpp_total = qty * (std_cost if std_cost else 0)
                
               
                    db.run_query("UPDATE inventory SET stok_saat_ini=stok_saat_ini-? WHERE kode_barang=?", (qty, kd))
                    db.run_query("INSERT INTO stock_log (tanggal, kode_barang, jenis_gerak, jumlah, harga_satuan, keterangan, user) VALUES (?,?,?,?,?,?,?)", (tgl, kd, "OUT", qty, prc, f"Sold: {ket}", user_now))
                
               
                    db.run_query("INSERT INTO jurnal (tanggal, deskripsi, akun_debit, akun_kredit, nominal, created_by) VALUES (?,?,?,?,?,?)", (tgl, f"JUAL {brg.split(' (')[0]}: {ket}", adb, acr, tot, user_now))
                
                
                if nilai_hpp_total > 0 and acc_aset and acc_hpp:
                    desc_hpp = f"Cost of Goods Sold (Ref: {brg.split(' (')[0]})"
                    db.run_query("INSERT INTO jurnal (tanggal, deskripsi, akun_debit, akun_kredit, nominal, created_by) VALUES (?,?,?,?,?,?)", 
                                (tgl, desc_hpp, acc_hpp, acc_aset, nilai_hpp_total, user_now))
                
                st.success("OK - Pendapatan & HPP Tercatat"); time.sleep(1); st.rerun()

    with t2:
        with st.form("beli"): 
            st.caption("Pembelian (Otomatis Masuk Persediaan)")
            
            c1, c2 = st.columns(2)
            tgl = c1.date_input("Tgl", date.today(), key="b_tgl")
            brg_key = c2.selectbox("Barang", list(inv_opts.keys())) if inv_opts else None
            
            c3, c4, c5 = st.columns(3)
            qty = c3.number_input("Qty", 1.0, step=1.0, key="b_qty")
            tot = c4.number_input("Total Bayar", step=1000.0, key="b_tot")
            c5.metric("Harga/Unit", f"Rp {tot/qty:,.0f}" if qty>0 else 0)
            
            ket = st.text_input("Ket", placeholder="Toko...")
            
            
            ca, cb = st.columns(2)
            target_aset = ""
            target_kode = ""
            
            if brg_key:
                target_kode = inv_opts[brg_key]
            
                try:
                    data_brg = db.get_one("SELECT akun_aset FROM inventory WHERE kode_barang=?", (target_kode,))
                    if data_brg and data_brg[0]:
                        target_aset = data_brg[0]
                    else:
                        target_aset = "Persediaan (Umum)"
                except:
                     target_aset = "Persediaan (Umum)"

            
            adb = ca.text_input("Masuk Ke (Debit)", value=target_aset, disabled=True) 
            acr = cb.selectbox("Bayar Pakai (Kredit)", akun_kas, key="b_cr")
            
            
            if st.form_submit_button("Simpan Pembelian", type="primary"):
                if brg_key and target_aset:
                   
                    db.run_query("UPDATE inventory SET stok_saat_ini=stok_saat_ini+? WHERE kode_barang=?", (qty, target_kode))
                    
                    
                    harga_satuan = tot/qty if qty > 0 else 0
                    db.run_query("INSERT INTO stock_log (tanggal, kode_barang, jenis_gerak, jumlah, harga_satuan, keterangan, user) VALUES (?,?,?,?,?,?,?)", 
                                (tgl, target_kode, "IN", qty, harga_satuan, f"Buy: {ket}", user_now))
                    
                    
                    db.run_query("INSERT INTO jurnal (tanggal, deskripsi, akun_debit, akun_kredit, nominal, created_by) VALUES (?,?,?,?,?,?)", 
                                (tgl, f"BELI {brg_key.split(' (')[0]}: {ket}", target_aset, acr, tot, user_now))
                    
                    st.success("OK - Persediaan Bertambah")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Data Barang/Akun tidak valid.")

    with t3:
        with st.form("umum"):
            c1, c2 = st.columns(2)
            tgl = c1.date_input("Tgl", date.today(), key="u_tgl")
            desc = c2.text_input("Ket", placeholder="Biaya...")
            c3, c4, c5 = st.columns([1,1,1])
            adb = c3.selectbox("Debit", all_acc, key="u_db")
            acr = c4.selectbox("Kredit", all_acc, index=1, key="u_cr")
            nom = c5.number_input("Rp", step=1000.0, key="u_nom")
            if st.form_submit_button("Simpan", type="primary"):
                db.run_query("INSERT INTO jurnal (tanggal, deskripsi, akun_debit, akun_kredit, nominal, created_by) VALUES (?,?,?,?,?,?)", (tgl, desc, adb, acr, nom, user_now))
                st.success("OK"); time.sleep(1); st.rerun()

    with t4:
        st.info("ℹ️ Input Saldo Awal untuk migrasi data. Pilih 'Jenis Saldo' sesuai kebutuhan.")
    
        inv_data = db.get_df("SELECT kode_barang, nama_barang, satuan FROM inventory")
        inv_dict = {f"{r['nama_barang']} ({r['satuan']})": r['kode_barang'] for _, r in inv_data.iterrows()} if not inv_data.empty else {}

        with st.form("saldo_awal_v2"):
           
            jenis_sa = st.radio("Jenis Saldo Awal:", ["💰 Akun Keuangan (Kas/Bank/Modal/dll)", "📦 Stok Barang (Inventory)"], horizontal=True)
            st.markdown("---")

            c1, c2 = st.columns(2)
            tgl = c1.date_input("Tanggal Saldo", date(date.today().year, 1, 1), key="sa_tgl_v2")
            
            
            if "Stok Barang" in jenis_sa:
                
                if not inv_dict:
                    st.error("Data Barang Master masih kosong!")
                    st.stop()
                
                sel_brg_label = c2.selectbox("Pilih Barang Fisik", list(inv_dict.keys()))
                sel_brg_kode = inv_dict[sel_brg_label]
                
                c3, c4, c5 = st.columns(3)
                qty_fisik = c3.number_input("Jumlah Fisik (Qty)", min_value=0.1, step=1.0)
                hpp_satuan = c4.number_input("HPP / Harga Modal per Unit", min_value=0.0, step=100.0)
                
                nom_total = qty_fisik * hpp_satuan
                c5.metric("Total Nilai (Rp)", f"{nom_total:,.0f}")
                
                
                aset_only = db.get_acc_by_type(['Aset'])
                target_acc = st.selectbox("Link ke Akun Aset Persediaan:", aset_only, help="Pilih akun Aset yang menampung nilai barang ini")
                
                posisi = "Debit" 
                ket_default = f"Saldo Awal Stok: {sel_brg_label}"
            
            else:
                
                target_acc = c2.selectbox("Pilih Akun", all_acc, key="sa_acc_v2")
                c3, c4 = st.columns(2)
                posisi_raw = c3.radio("Posisi Saldo", ["Debit (Aset/Beban)", "Kredit (Kewajiban/Modal/Pendapatan)"], horizontal=True, key="sa_pos_v2")
                posisi = "Debit" if "Debit" in posisi_raw else "Kredit"
                nom_total = c4.number_input("Nominal (Rp)", min_value=0.0, step=1000.0, key="sa_nom_v2")
                ket_default = f"Saldo Awal Akun: {target_acc}"

            ket_input = st.text_input("Keterangan", value=ket_default)

            if st.form_submit_button("💾 Simpan Saldo Awal", type="primary"):
                if nom_total > 0:
                    
                    contra_acc = "Historical Balancing"
                    
                    if posisi == "Debit":
                        adb, acr = target_acc, contra_acc
                    else:
                        adb, acr = contra_acc, target_acc
                    
                    db.run_query("INSERT INTO jurnal (tanggal, deskripsi, akun_debit, akun_kredit, nominal, created_by) VALUES (?,?,?,?,?,?)", 
                                (tgl, ket_input, adb, acr, nom_total, user_now))
                    
                    
                    if "Stok Barang" in jenis_sa:
                       
                        db.run_query("UPDATE inventory SET stok_saat_ini = stok_saat_ini + ? WHERE kode_barang = ?", (qty_fisik, sel_brg_kode))
                        
                        
                        
                        desc_log = "Saldo Awal (Opname)"
                        db.run_query("INSERT INTO stock_log (tanggal, kode_barang, jenis_gerak, jumlah, harga_satuan, keterangan, user) VALUES (?,?,?,?,?,?,?)", 
                                    (tgl, sel_brg_kode, "IN", qty_fisik, hpp_satuan, desc_log, user_now))
                        
                        st.toast(f"Stok {sel_brg_label} bertambah {qty_fisik}!", icon="📦")

                    st.success("Data berhasil disimpan & terintegrasi!")
                    time.sleep(1.5)
                    st.rerun()
                else:
                    st.error("Nominal/Jumlah tidak boleh 0")

   
    st.markdown("---")
    
    
    c_title, c_filt, c_down = st.columns([2, 1.5, 1])
    with c_title:
        st.subheader("📜 Riwayat Jurnal")
    with c_filt:
        f_mode = st.selectbox("Filter Kategori:", ["Semua", "💰 Penjualan", "🛒 Pembelian", "⚙️ Umum", "📂 Saldo Awal"], label_visibility="collapsed")
    
    
    query = "SELECT * FROM jurnal"
    if f_mode == "💰 Penjualan":
        query += " WHERE deskripsi LIKE 'JUAL%' OR akun_kredit LIKE '%Pendapatan%'"
    elif f_mode == "🛒 Pembelian":
        query += " WHERE deskripsi LIKE 'BELI%' OR akun_debit LIKE '%Beban%'"
    elif f_mode == "⚙️ Umum":
        query += " WHERE deskripsi NOT LIKE 'JUAL%' AND deskripsi NOT LIKE 'BELI%' AND deskripsi NOT LIKE 'Saldo Awal%'"
    elif f_mode == "📂 Saldo Awal":
        query += " WHERE deskripsi LIKE 'Saldo Awal%'"
    
    query += " ORDER BY tanggal DESC, id DESC LIMIT 50" 
    
    df_j = db.get_df(query)

    with c_down:
        
        if not df_j.empty:
            b = io.BytesIO()
            with pd.ExcelWriter(b, engine='xlsxwriter') as w: 
                df_j.to_excel(w, index=False)
            st.download_button("📥 Excel", b, "jurnal.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key='btn_xls')

    if not df_j.empty:
        
        html = """<table class="journal-table"><thead><tr><th width="15%">Tanggal</th><th width="45%">Akun & Keterangan</th><th width="10%">Ref</th><th width="15%" style="text-align:right">Debit</th><th width="15%" style="text-align:right">Kredit</th></tr></thead><tbody>"""
        for _, r in df_j.iterrows():
            nom = f"Rp {r['nominal']:,.0f}"
            html += f"""<tr><td style="border:none; font-weight:bold;">{r['tanggal']}</td><td style="border:none;" class="acc-db">{r['akun_debit']}</td><td style="border:none;"><span class="tag-db">Debit</span></td><td style="border:none;" class="money">{nom}</td><td style="border:none;"></td></tr>
                        <tr><td style="font-size:11px; color:#999;">ID: {r['id']}</td><td class="acc-cr">↳ {r['akun_kredit']} <br><span style="font-size:12px; color:#888;">Note: {r['deskripsi']}</span></td><td><span class="tag-cr">Kredit</span></td><td></td><td class="money">{nom}</td></tr>"""
        st.markdown(html+"</tbody></table>", unsafe_allow_html=True)
        
        
        with st.expander("🛠️ Tools: Hapus / Cetak Bukti PDF"):
            col_act1, col_act2 = st.columns(2)
            with col_act1:
                st.caption("Cetak Kwitansi per Transaksi")
                
                id_opts = df_j['id'].tolist()
                sel_id = st.selectbox("Pilih ID Transaksi:", id_opts)
                if st.button("🖨️ Download PDF", type="secondary"):
                   
                    trx = df_j[df_j['id'] == sel_id].iloc[0]
                    pdf_data = generate_pdf(trx['id'], trx['tanggal'], trx['deskripsi'], trx['nominal'], trx['akun_debit'], trx['akun_kredit'])
                    
                    st.download_button("Klik untuk Unduh PDF", pdf_data, file_name=f"Bukti_{sel_id}.pdf", mime="application/pdf")
            
            with col_act2:
                st.caption("🗑️ Hapus Transaksi & Koreksi Stok")
                st.info("Gunakan ini jika terjadi kesalahan input.")
                
               
                del_id = st.number_input("Masukkan ID Jurnal:", min_value=0, step=1, help="Lihat kolom ID di tabel sebelah kiri")
                
                
                st.write("---")
                is_stok_trx = st.checkbox("Kembalikan Stok Fisik juga?", help="Centang jika yang dihapus adalah transaksi Jual/Beli Barang")
                
                kode_brg_restore = None
                qty_restore = 0.0
                jenis_koreksi = "IN" 
                
                if is_stok_trx:
                   
                    inv_for_del = db.get_df("SELECT kode_barang, nama_barang FROM inventory")
                    inv_del_map = {f"{r['nama_barang']}": r['kode_barang'] for _, r in inv_for_del.iterrows()}
                    
                    pilih_brg = st.selectbox("Pilih Barang:", list(inv_del_map.keys()), key="del_brg_sel")
                    kode_brg_restore = inv_del_map[pilih_brg]
                    
                    qty_restore = st.number_input("Jumlah (Qty) yang dikembalikan:", min_value=0.1, step=1.0, key="del_qty")
                    
                    tipe_trx = st.radio("Jenis Transaksi yg Dihapus:", ["Penjualan (Barang Kembali ke Gudang)", "Pembelian (Barang Keluar dari Gudang)"])
                    if "Pembelian" in tipe_trx:
                        jenis_koreksi = "OUT"
                    else:
                        jenis_koreksi = "IN"

                if st.button("🚀 Eksekusi Hapus & Koreksi", type="primary"):
                    
                    cek = db.get_one("SELECT * FROM jurnal WHERE id=?", (del_id,))
                    if not cek:
                        st.error("ID Transaksi tidak ditemukan!")
                    else:
                        
                        db.run_query("DELETE FROM jurnal WHERE id=?", (del_id,))
                        msg = f"Jurnal ID {del_id} berhasil dihapus."
                        
                        
                        if is_stok_trx and kode_brg_restore and qty_restore > 0:
                            if jenis_koreksi == "IN":
                                db.run_query("UPDATE inventory SET stok_saat_ini=stok_saat_ini+? WHERE kode_barang=?", (qty_restore, kode_brg_restore))
                                msg += f" Dan Stok {pilih_brg} dikembalikan (+{qty_restore})."
                            else:
                                db.run_query("UPDATE inventory SET stok_saat_ini=stok_saat_ini-? WHERE kode_barang=?", (qty_restore, kode_brg_restore))
                                msg += f" Dan Stok {pilih_brg} dibatalkan (-{qty_restore})."
                            
                           
                            db.run_query("INSERT INTO stock_log (tanggal, kode_barang, jenis_gerak, jumlah, harga_satuan, keterangan, user) VALUES (?,?,?,?,?,?,?)", 
                                        (date.today(), kode_brg_restore, jenis_koreksi, qty_restore, 0, f"Koreksi Hapus ID {del_id}", st.session_state['username']))

                        st.success(msg)
                        time.sleep(2)
                        st.rerun()
    else:
        st.info("Data tidak ditemukan untuk kategori ini.")


def generate_gl_rows(df, acc_name, is_normal_debit):
    rows_html = ""
    running_balance = 0
    total_debit = 0
    total_kredit = 0

    for _, r in df.iterrows():
        if r['akun_debit'] == acc_name:
            mut_debit = r['nominal']
            mut_kredit = 0
            ref = "DB"
        else:
            mut_debit = 0
            mut_kredit = r['nominal']
            ref = "CR"
        
        if is_normal_debit:
            running_balance += (mut_debit - mut_kredit)
        else:
            running_balance += (mut_kredit - mut_debit)
        
        total_debit += mut_debit
        total_kredit += mut_kredit

        str_d = f"{mut_debit:,.0f}" if mut_debit > 0 else "-"
        str_c = f"{mut_kredit:,.0f}" if mut_kredit > 0 else "-"
        str_b = f"{running_balance:,.0f}"
        
        
        rows_html += f"""
        <tr>
            <td style="white-space:nowrap;">{r['tanggal']}</td>
            <td>
                <span style="font-weight:600; color:#374151;">{r['deskripsi']}</span><br>
                <span class="ref-badge">Ref: {ref}-{r['id']}</span>
            </td>
            <td class="val-db">{str_d}</td>
            <td class="val-cr">{str_c}</td>
            <td class="val-bal">Rp {str_b}</td>
        </tr>
        """
    
    return rows_html, total_debit, total_kredit, running_balance


@login_required
def page_buku_besar():
    st.title("📖 General Ledger")
    
   
    st.markdown("""
    <style>
        .gl-table { width: 100%; border-collapse: collapse; font-family: 'Inter', sans-serif; margin-top: 15px; color: #374151; }
        .gl-table thead th { 
            background-color: #768209; color: white; font-size: 12px; 
            text-transform: uppercase; letter-spacing: 1px; padding: 12px 8px; 
            text-align: right; 
        }
        .gl-table thead th:first-child, .gl-table thead th:nth-child(2) { text-align: left; }
        .gl-table tbody tr { border-bottom: 1px solid rgba(0,0,0,0.05); transition: background-color 0.1s; }
        .gl-table tbody tr:hover { background-color: rgba(118, 130, 9, 0.05); }
        .gl-table td { padding: 10px 8px; font-size: 13.5px; vertical-align: middle; text-align: right; }
        .gl-table td:first-child, .gl-table td:nth-child(2) { text-align: left; }
        .val-db { color: #166534; } 
        .val-cr { color: #991b1b; } 
        .val-bal { font-weight: 800; color: #1f2937; } 
        .ref-badge { background-color: #e5e7eb; color: #374151; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 600; }
        .info-box { background-color: #f4f6e6; border-left: 6px solid #768209; padding: 20px; border-radius: 10px; margin-bottom: 25px; }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("""<div class="info-box"><strong>Buku Besar</strong><br>Detail mutasi dan saldo per akun.</div>""", unsafe_allow_html=True)

    
    all_acc = db.get_all_acc()
    if not all_acc: st.warning("Data Akun Kosong"); return
    
    c1, c2 = st.columns([2,1])
    with c1: acc_name = st.selectbox("Pilih Akun:", all_acc)
    
    
    acc_data = db.get_df("SELECT * FROM akun WHERE nama_akun=?", (acc_name,)).iloc[0]
    is_debit = acc_data['tipe_akun'] in ['Aset', 'Beban']
    
    with c2: 
        st.markdown(f"<div style='margin-top:30px; text-align:center; font-weight:bold; color:#768209'>Saldo Normal: {'DEBIT' if is_debit else 'KREDIT'}</div>", unsafe_allow_html=True)

    
    df = db.get_df("SELECT * FROM jurnal WHERE akun_debit=? OR akun_kredit=? ORDER BY tanggal ASC, id ASC", (acc_name, acc_name))

    if not df.empty:
        
        rows_html = ""
        run_bal = 0
        sum_d = 0
        sum_k = 0
        
        for _, r in df.iterrows():
            if r['akun_debit'] == acc_name:
                d, k = r['nominal'], 0
                ref = "DB"
            else:
                d, k = 0, r['nominal']
                ref = "CR"
            
            if is_debit: run_bal += (d - k)
            else: run_bal += (k - d)
            
            sum_d += d; sum_k += k
            
            rows_html += f"""
            <tr>
                <td style="white-space:nowrap;">{r['tanggal']}</td>
                <td><span style="font-weight:600; color:#374151;">{r['deskripsi']}</span><br><span class="ref-badge">Ref: {ref}-{r['id']}</span></td>
                <td class="val-db">{f"{d:,.0f}" if d else "-"}</td>
                <td class="val-cr">{f"{k:,.0f}" if k else "-"}</td>
                <td class="val-bal">Rp {run_bal:,.0f}</td>
            </tr>"""

        
        full_html = f"""
        <table class="gl-table">
            <thead>
                <tr>
                    <th width="12%">Tanggal</th><th width="40%">Keterangan</th>
                    <th width="15%">Debit</th><th width="15%">Kredit</th><th width="18%">Saldo</th>
                </tr>
            </thead>
            <tbody>{rows_html}</tbody>
            <tfoot>
                <tr style="background-color:#f4f6e6; font-weight:bold; border-top:2px solid #768209;">
                    <td colspan="2" style="text-align:right;">TOTAL:</td>
                    <td class="val-db">{sum_d:,.0f}</td>
                    <td class="val-cr">{sum_k:,.0f}</td>
                    <td class="val-bal">Rp {run_bal:,.0f}</td>
                </tr>
            </tfoot>
        </table>
        """
        
        st.markdown(full_html, unsafe_allow_html=True)
        
       
        st.markdown("<br>", unsafe_allow_html=True)
        b = io.BytesIO()
        with pd.ExcelWriter(b, engine='xlsxwriter') as w: df.to_excel(w, index=False)
        st.download_button("📥 Download Excel", b, "gl.xlsx")
        
    else:
        st.info("Belum ada transaksi.")

@login_required
def page_laporan():
    st.title("📑 Financial Reports")

    
    st.markdown("""
    <style>
        /* Container untuk mencegah overflow */
        .block-container {
            max-width: 100%;
            padding-left: 1rem;
            padding-right: 1rem;
        }
        
        /* Tabel Teks Sederhana Transparan */
        .text-table { 
            width: 100%; 
            border-collapse: collapse; 
            font-family: 'Inter', sans-serif; 
            color: #333;
            table-layout: fixed; /* Penting untuk mencegah overflow */
        }
        .text-table th { 
            text-align: left; 
            border-bottom: 2px solid #768209; 
            padding: 10px 5px;
            color: #768209;
            font-size: 14px;
            text-transform: uppercase;
            word-wrap: break-word;
        }
        .text-table td { 
            padding: 8px 5px; 
            border-bottom: 1px solid #eee;
            font-size: 14px;
            vertical-align: top;
            word-wrap: break-word;
            overflow-wrap: break-word;
        }
        .text-table tr:last-child td { border-bottom: none; }
        
        /* Helper Alignment */
        .money { text-align: right; font-family: 'Courier New', monospace; font-weight: 600; }
        .indent { padding-left: 30px !important; color: #555; }
        .bold { font-weight: bold; color: #000; }
        .total-row td { 
            border-top: 2px solid #768209 !important; 
            background-color: rgba(118, 130, 9, 0.1); 
            font-weight: bold; 
            padding: 12px 5px;
        }
        
        .info-box { 
            background-color: #f4f6e6; 
            border-left: 6px solid #768209; 
            padding: 15px; 
            border-radius: 5px; 
            margin-bottom: 20px; 
        }
        
        /* Fix untuk scroll horizontal */
        .stTabs [data-baseweb="tab-panel"] {
            overflow-x: hidden;
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""<div class="info-box">Laporan ini digenerate otomatis dari jurnal transaksi.</div>""", unsafe_allow_html=True)

    
    df = db.get_df("SELECT * FROM jurnal")
    if df.empty:
        st.warning("Belum ada data.")
        return

    
    df['nominal'] = pd.to_numeric(df['nominal'], errors='coerce').fillna(0)

    
    def get_total_html(tipe_list, normal_kredit=True):
        acc_list = db.get_acc_by_type(tipe_list)
        html_rows = ""
        total_val = 0.0
        
        for ac in acc_list:
            d = df[df['akun_debit'] == ac]['nominal'].sum()
            k = df[df['akun_kredit'] == ac]['nominal'].sum()
            
            val = (k - d) if normal_kredit else (d - k)
            
            if val != 0:
                total_val += val
                txt_val = f"({abs(val):,.0f})" if val < 0 else f"{val:,.0f}"
                html_rows += f"<tr><td class='indent'>{ac}</td><td class='money'>{txt_val}</td></tr>"
        
        return html_rows, total_val

    
    t1, t2, t3 = st.tabs(["⚖️ Neraca Saldo", "📉 Laba Rugi", "🏛️ Neraca"])

   
    with t1:
        accs = db.get_df("SELECT kode_akun, nama_akun, tipe_akun FROM akun ORDER BY kode_akun")
        rows = ""
        tot_d = 0.0
        tot_k = 0.0
        
        for _, r in accs.iterrows():
            d_sum = df[df['akun_debit'] == r['nama_akun']]['nominal'].sum()
            k_sum = df[df['akun_kredit'] == r['nama_akun']]['nominal'].sum()
            
            is_debit = r['tipe_akun'] in ["Aset", "Beban"] and "Akumulasi" not in r['nama_akun']
            bal = d_sum - k_sum if is_debit else k_sum - d_sum
            
            vd = bal if is_debit and bal > 0 else 0
            vk = bal if not is_debit and bal > 0 else 0
            
            if is_debit and bal < 0: vk = abs(bal); vd = 0
            if not is_debit and bal < 0: vd = abs(bal); vk = 0
            
            tot_d += vd
            tot_k += vk
            
            if bal != 0 or True:
                rows += f"""<tr>
                    <td style="width:15%">{r['kode_akun']}</td>
                    <td style="width:45%">{r['nama_akun']}</td>
                    <td class='money' style="width:20%">{f"{vd:,.0f}" if vd else "-"}</td>
                    <td class='money' style="width:20%">{f"{vk:,.0f}" if vk else "-"}</td>
                </tr>"""
        
        st.markdown(f"""
        <div style="overflow-x: auto;">
        <table class="text-table">
            <thead><tr>
                <th style="width:15%">Kode</th>
                <th style="width:45%">Nama Akun</th>
                <th style="text-align:right; width:20%">Debit</th>
                <th style="text-align:right; width:20%">Kredit</th>
            </tr></thead>
            <tbody>{rows}</tbody>
            <tfoot><tr class="total-row">
                <td colspan="2">TOTAL</td>
                <td class="money">{tot_d:,.0f}</td>
                <td class="money">{tot_k:,.0f}</td>
            </tr></tfoot>
        </table>
        </div>
        """, unsafe_allow_html=True)

    
    with t2:
        rows_pdp, tot_pdp = get_total_html(['Pendapatan'], True)
        rows_bbn, tot_bbn = get_total_html(['Beban'], False)
        laba = tot_pdp - tot_bbn
        color = "#166534" if laba >= 0 else "#991b1b"

        st.markdown(f"""
        <div style="overflow-x: auto;">
        <table class="text-table">
            <thead><tr>
                <th style="width:70%">Keterangan</th>
                <th style="text-align:right; width:30%">Nominal (Rp)</th>
            </tr></thead>
            <tbody>
                <tr><td class="bold" style="padding-top:15px;">PENDAPATAN</td><td></td></tr>
                {rows_pdp if rows_pdp else "<tr><td class='indent'>-</td><td class='money'>-</td></tr>"}
                <tr style="background:#fafafa;"><td class="bold indent">Total Pendapatan</td><td class="money bold">{tot_pdp:,.0f}</td></tr>
                
                <tr><td class="bold" style="padding-top:15px;">BEBAN OPERASIONAL</td><td></td></tr>
                {rows_bbn if rows_bbn else "<tr><td class='indent'>-</td><td class='money'>-</td></tr>"}
                <tr style="background:#fafafa;"><td class="bold indent">Total Beban</td><td class="money bold">({tot_bbn:,.0f})</td></tr>
            </tbody>
            <tfoot>
                <tr class="total-row">
                    <td>LABA BERSIH</td>
                    <td class="money" style="color:{color};">{laba:,.0f}</td>
                </tr>
            </tfoot>
        </table>
        </div>
        """, unsafe_allow_html=True)

   
    with t3:
        _, t_p = get_total_html(['Pendapatan'], True)
        _, t_b = get_total_html(['Beban'], False)
        profit_now = t_p - t_b
        
        def get_bal_html(tipe, is_asset):
            acc_list = db.get_acc_by_type([tipe])
            rows = ""
            tot = 0.0
            for ac in acc_list:
                d = df[df['akun_debit'] == ac]['nominal'].sum()
                k = df[df['akun_kredit'] == ac]['nominal'].sum()
                
                val = 0.0
                if "Akumulasi" in ac and is_asset: 
                    val = (k - d) 
                    tot -= val
                    display = f"({val:,.0f})"
                else:
                    val = (d - k) if is_asset else (k - d)
                    tot += val
                    display = f"{val:,.0f}"
                
                if val != 0:
                    rows += f"<tr><td class='indent'>{ac}</td><td class='money'>{display}</td></tr>"
            return rows, tot

        r_ast, t_ast = get_bal_html('Aset', True)
        r_liab, t_liab = get_bal_html('Kewajiban', False)
        r_mod, t_mod = get_bal_html('Modal', False)
        
        final_equity = t_mod + profit_now

        c_left, c_right = st.columns(2)
        
        with c_left:
            st.markdown(f"""
            <div style="overflow-x: auto;">
            <table class="text-table">
                <thead><tr><th colspan="2">ASET (AKTIVA)</th></tr></thead>
                <tbody>
                    {r_ast if r_ast else "<tr><td class='indent'>-</td><td class='money'>-</td></tr>"}
                </tbody>
                <tfoot><tr class="total-row"><td style="width:60%">TOTAL ASET</td><td class="money" style="width:40%">{t_ast:,.0f}</td></tr></tfoot>
            </table>
            </div>
            """, unsafe_allow_html=True)
            
        with c_right:
            st.markdown(f"""
            <div style="overflow-x: auto;">
            <table class="text-table">
                <thead><tr><th colspan="2">KEWAJIBAN & EKUITAS</th></tr></thead>
                <tbody>
                    <tr><td class="bold" style="font-size:12px;">KEWAJIBAN</td><td></td></tr>
                    {r_liab if r_liab else "<tr><td class='indent'>-</td><td class='money'>-</td></tr>"}
                    
                    <tr><td class="bold" style="font-size:12px; padding-top:10px;">EKUITAS</td><td></td></tr>
                    {r_mod}
                    <tr><td class='indent bold' style="color:#166534;">Laba Tahun Berjalan</td><td class='money bold' style="color:#166534;">{profit_now:,.0f}</td></tr>
                </tbody>
                <tfoot><tr class="total-row"><td style="width:60%">TOTAL PASIVA</td><td class="money" style="width:40%">{t_liab + final_equity:,.0f}</td></tr></tfoot>
            </table>
            </div>
            """, unsafe_allow_html=True)
            

@login_required
def page_master():
    st.title("🗂️ Master Data")
    

    st.markdown("""
    <style>
        .info-box { 
            background-color: #f4f6e6; 
            border-left: 6px solid #768209; 
            padding: 15px; 
            border-radius: 8px; 
            margin-bottom: 20px; 
            color: #2c3e50; 
        }
    </style>
    <div class="info-box">
        <strong>Pengaturan Data Induk</strong><br>
        Kelola daftar Akun (Chart of Accounts) dan sistem di sini.
    </div>
    """, unsafe_allow_html=True)

    
    t_acc, t_log, t_reset = st.tabs(["📂 Master Akun", "📜 System Logs", "⚠️ Factory Reset"])


    with t_acc:
        col_form, col_view = st.columns([1, 2])
        
    
        with col_form:
            st.write("##### ➕ Input Akun")
            with st.form("add_acc_form"):
                kd = st.text_input("Kode", placeholder="Contoh: 1-11")
                nm = st.text_input("Nama Akun", placeholder="Contoh: Kas Kecil")
                tp = st.selectbox("Tipe", ["Aset", "Kewajiban", "Modal", "Pendapatan", "Beban"])
                
                if st.form_submit_button("Simpan", type="primary"):
                    if kd and nm:
                        try:
                            db.run_query("INSERT INTO akun (kode_akun, nama_akun, tipe_akun) VALUES (?,?,?)", (kd, nm, tp))
                            st.success(f"Berhasil!")
                            time.sleep(0.5)
                            st.rerun()
                        except:
                            st.error("Kode/Nama sudah ada!")
                    else:
                        st.warning("Wajib diisi.")

        with col_view:
            st.write("##### 📋 Daftar Akun")
            
            df_acc = db.get_df("SELECT kode_akun, nama_akun, tipe_akun FROM akun ORDER BY kode_akun")
            
            if not df_acc.empty:
                st.dataframe(
                    df_acc,
                    column_config={
                        "kode_akun": "Kode",
                        "nama_akun": "Nama Akun",
                        "tipe_akun": st.column_config.SelectboxColumn(
                            "Kategori",
                            width="medium",
                            options=["Aset", "Kewajiban", "Modal", "Pendapatan", "Beban"],
                            disabled=True
                        )
                    },
                    use_container_width=True,
                    hide_index=True,
                    height=500
                )
                
                st.markdown("---")
                with st.expander("🗑️ Hapus Akun"):
                    del_opt = df_acc['kode_akun'] + " - " + df_acc['nama_akun']
                    sel_del = st.selectbox("Pilih akun:", del_opt)
                    if st.button("Hapus Permanen", type="secondary"):
                        code_del = sel_del.split(" - ")[0]
                        db.run_query("DELETE FROM akun WHERE kode_akun=?", (code_del,))
                        st.warning("Dihapus."); time.sleep(0.5); st.rerun()
            else:
                st.info("Data kosong.")

    with t_reset:
        st.error("⚠️ **ZONA BAHAYA**")
        st.write("Menghapus SEMUA transaksi (Jurnal & Stok). Data Master aman.")
        if st.button("🔥 RESET DATA TRANSAKSI", type="primary"):
            db.run_query("DELETE FROM jurnal")
            db.run_query("DELETE FROM stock_log")
            db.run_query("UPDATE inventory SET stok_saat_ini = 0")
            st.success("Reset Berhasil!"); time.sleep(1); st.rerun()

def login_page():

    inject_login_css()

   

    if 'auth_mode' not in st.session_state:

        st.session_state['auth_mode'] = 'login'



    def toggle_mode():

        if st.session_state['auth_mode'] == 'login':

            st.session_state['auth_mode'] = 'register'

        else:

            st.session_state['auth_mode'] = 'login'



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

        if st.session_state['auth_mode'] == 'login':

            with st.form("login_form"):

                st.markdown("<h3 style='text-align:center; color:#333; margin:0 0 20px 0;'>Login</h3>", unsafe_allow_html=True)

                u = st.text_input("Username", placeholder="Masukkan username")

                p = st.text_input("Password", type="password", placeholder="Masukkan password")

                st.markdown("<br>", unsafe_allow_html=True)

        

                if st.form_submit_button("MASUK", type="primary"):

                    user = db.get_one("SELECT * FROM users WHERE username=? AND password=?", (u, make_hash(p)))

                    if user:

                        st.session_state['logged_in'] = True

                        st.session_state['username'] = user['username']

                        st.session_state['role'] = user['role']

                        st.rerun()

                    else:

                        st.error("Username atau Password Salah")

        

            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

            if st.button("Belum punya akun? Daftar sekarang", use_container_width=True):

                toggle_mode()

                st.rerun()


        else:

            with st.form("register_form"):

                st.markdown("<h3 style='text-align:center; color:#333; margin:0 0 20px 0;'>Daftar Akun Baru</h3>", unsafe_allow_html=True)

                new_u = st.text_input("Username Baru")

                new_p1 = st.text_input("Password", type="password")

                new_p2 = st.text_input("Ulangi Password", type="password")

                st.markdown("<br>", unsafe_allow_html=True)

                if st.form_submit_button("DAFTAR", type="primary"):

                    if not new_u or not new_p1:

                        st.error("Username dan Password wajib diisi!")

                    elif new_p1 != new_p2:

                        st.error("Password tidak sama!")

                    else:

                        cek_user = db.get_one("SELECT username FROM users WHERE username=?", (new_u,))

                        if cek_user:

                            st.error("Username sudah terpakai!")

                        else:

                            try:

                                db.run_query("INSERT INTO users (username, password, role) VALUES (?,?,?)", (new_u, make_hash(new_p1), 'Manager'))

                                st.success("Akun berhasil dibuat! Silakan login.")

                                time.sleep(1.5)

                                toggle_mode()

                                st.rerun()

                            except Exception as e:

                                st.error(f"Gagal membuat akun: {e}")



            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

            if st.button("Sudah punya akun? Login", use_container_width=True):

                toggle_mode()

                st.rerun()



        st.markdown("<p style='text-align:center; font-size:12px; color:#fff; margin-top:20px; text-shadow: 0 1px 2px rgba(0,0,0,0.8);'>© 2025 Hasna Farm Enterprise</p>", unsafe_allow_html=True)

def main_app():
    inject_main_css()
    
    st.markdown("""
    <style>
        /* Definisi Animasi Muncul Perlahan (Fade In) */
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Styling Hero Section (Header Atas) */
        .hero-title { font-size: 22px; font-weight: 800; color: #768209; margin-bottom: 5px; }
        .hero-text { font-size: 14px; line-height: 1.5; color: #4b5563; text-align: justify; }
        .hero-list { margin-bottom: 0; padding-left: 15px; font-size: 13px; color: #4b5563;}
        
        .hero-container {
            background-color: transparent !important; 
            padding: 0px; margin-bottom: 15px;
            /* Tambahkan Animasi di sini */
            animation: fadeIn 1s ease-out;
            transition: transform 0.3s ease, filter 0.3s ease;
        }

        /* Efek saat mouse diarahkan ke Header (Hover) */
        .hero-container:hover {
            transform: scale(1.01); /* Membesar sedikit */
        }
        
        /* Efek Hover untuk Kartu Metric (Angka-angka di Dashboard) */
        div[data-testid="stMetric"] {
            transition: all 0.3s ease;
        }
        div[data-testid="stMetric"]:hover {
            transform: translateY(-5px); /* Naik sedikit */
            box-shadow: 0 10px 20px rgba(118, 130, 9, 0.2); /* Bayangan hijau halus */
            border-color: #768209;
        }
    </style>
    """, unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="hero-container">', unsafe_allow_html=True)
        col_img, col_txt = st.columns([1.5, 3], gap="large")
        
        with col_img:
            # GANTI NAMA FILE DISINI
            nama_file_gambar = "banner.jpg" 
            try:
                st.image(nama_file_gambar, use_container_width=True)
            except:
                st.warning(f"⚠️ File '{nama_file_gambar}' belum ada.")
        
        with col_txt:
            st.markdown('<div class="hero-title">Why Hasna Farm ERP?</div>', unsafe_allow_html=True)
            st.markdown("""
            <div class="hero-text">
                <p>
                    Hasna Farm merupakan nama peternakan puyuh, lalu sistem ini dibuat untuk memudahkan.
                    Sistem ini dirancang khusus untuk memodernisasi pengelolaan <b>Hasna Farm</b>. 
                    Membantu pemilik beralih dari pencatatan manual yang rawan kesalahan ke sistem digital yang terintegrasi.
                    Peternakan puyuh ini berlokasi di Pagersari RT 02/RW 03, Bergas, Kabupaten Semarang, Jawa Tengah.
                </p>
                <ul class="hero-list">
                    <li>✅ <b>Kontrol Stok Akurat:</b> Mencegah selisih pakan dan hasil panen.</li>
                    <li>✅ <b>Keuangan Transparan:</b> Laporan laba rugi otomatis dan real-time.</li>
                    <li>✅ <b>Data Driven:</b> Keputusan bisnis berdasarkan data nyata, bukan asumsi.</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
 
    role = st.session_state['role']
    if role == "Manager":
        opts = ["Launchpad", "Inventory", "Journal", "General Ledger", "Reports", "Master Data", "Logout"]
        icns = ["grid-fill", "box-seam-fill", "receipt", "book-half", "file-earmark-bar-graph", "database-fill-gear", "power"]
    else:
        opts = ["Inventory", "Journal", "General Ledger", "Logout"] 
        icns = ["box-seam-fill", "receipt", "book-half", "power"]
    
    c_logo, c_menu = st.columns([1.5, 10.5], gap="medium", vertical_alignment="center")
    
    with c_logo:
        try:
            st.image("logo.png", use_container_width=True)
        except:
            st.caption("Hasna Farm")
    
    with c_menu:
        selected = option_menu(menu_title=None, options=opts, icons=icns, default_index=0, orientation="horizontal",
            styles={"container": {"padding": "5px!important", "background-color": "#768209", "border-radius": "10px", "box-shadow": "0 4px 6px rgba(0,0,0,0.1)"},
                    "icon": {"color": "white", "font-size": "16px"}, "nav-link": {"font-size": "14px", "text-align": "center", "margin": "0px 5px", "color": "white", "font-weight": "500"},
                    "nav-link-hover": {"background-color": "#5a6307"}, "nav-link-selected": {"background-color": "#3B2417", "font-weight": "700", "border-radius": "8px"}})
    
    if selected != "Logout":
        st.markdown(f"""
        <div style='text-align: right; padding-top: 5px; padding-bottom: 15px; font-size: 0.85rem; color: #666; animation: fadeIn 1.5s ease-out;'>
            Login sebagai: <b>{st.session_state['username']}</b> 
            <span style='background:#768209; color:white; padding:2px 8px; border-radius:10px; font-size:0.75rem; margin-left:5px;'>{role}</span>
        </div>
        """, unsafe_allow_html=True)

    placeholder = st.empty()
    
    with placeholder.container():
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


