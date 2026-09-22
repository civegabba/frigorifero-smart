import streamlit as st
import json
import os
import io
import base64
import smtplib
from email.mime.text import MIMEText
import requests
import pandas as pd
from datetime import date, datetime, timedelta
from openai import OpenAI
from PIL import Image

try:
    from pyzbar.pyzbar import decode as decodifica_barcode_immagine
    PYZBAR_DISPONIBILE = True
except ImportError:
    PYZBAR_DISPONIBILE = False

# =====================================================
# CONFIGURAZIONE PAGINA E STILE
# =====================================================
st.set_page_config(page_title="Frigorifero Smart", page_icon="🥶", layout="centered")

# Mostra un eventuale toast rimasto "in coda" da un'azione precedente
# (vedi accoda_toast per il perché di questo meccanismo).
if "_toast_in_coda" in st.session_state:
    _messaggio_toast, _icona_toast = st.session_state.pop("_toast_in_coda")
    st.toast(_messaggio_toast, icon=_icona_toast)

st.markdown(
    """
    <style>
    :root, .stApp {
        --background-color: #ffffff;
        --secondary-background-color: #f3f8fa;
        --text-color: #1a2b30;
        --primary-color: #00b4c6;
    }
    .stApp {
        background: linear-gradient(180deg, #f3fbfc 0%, #ffffff 250px) !important;
        color: #1a2b30 !important;
    }
    .stApp, .stApp p, .stApp span, .stApp label,
    .stApp h1, .stApp h2, .stApp h3, .stApp h4,
    .stApp div[data-testid="stMarkdownContainer"] {
        color: #1a2b30 !important;
    }
    .main-title {
        font-size: 2.6rem;
        font-weight: 800;
        background: linear-gradient(90deg, #00b4c6 0%, #00f2c3 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0;
    }
    .subtitle {
        color: #8a9a9e;
        margin-top: 0;
        margin-bottom: 1.5rem;
        font-size: 1.05rem;
    }
    .badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 999px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-bottom: 0.3rem;
    }
    .badge-scaduto { background: #ffe0e0; color: #c62828; }
    .badge-oggi { background: #ffe9d6; color: #e65100; }
    .badge-presto { background: #fff9d6; color: #a68b00; }
    .badge-ok { background: #dff7ec; color: #1b7a4d; }
    .food-row {
        padding: 0.7rem 1rem;
        border-radius: 14px;
        background: #fafdfd;
        color: #1a2b30 !important;
        margin-bottom: 0.5rem;
        border: 1px solid #eaf2f2;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        transition: box-shadow 0.15s ease-in-out, transform 0.15s ease-in-out;
    }
    .food-row b { color: #1a2b30 !important; }
    .food-row:hover {
        box-shadow: 0 4px 14px rgba(0,180,198,0.15);
        transform: translateY(-1px);
    }
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #f3f8fa 0%, #e8f6f7 100%);
        border-radius: 14px;
        padding: 0.9rem 0.5rem;
        border: 1px solid #d9edef;
        box-shadow: 0 1px 4px rgba(0,0,0,0.03);
    }
    div[data-testid="stMetric"] label,
    div[data-testid="stMetricLabel"],
    div[data-testid="stMetricLabel"] p {
        color: #4a5a5e !important;
    }
    div[data-testid="stMetricValue"] {
        color: #00838f !important;
        font-weight: 800 !important;
    }
    .stButton > button {
        border-radius: 10px !important;
        font-weight: 600 !important;
        transition: transform 0.12s ease-in-out, box-shadow 0.12s ease-in-out !important;
        border: 1px solid #d9edef !important;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,180,198,0.25);
        border-color: #00b4c6 !important;
        color: #00838f !important;
    }
    button[kind="primary"] {
        background: linear-gradient(90deg, #00b4c6 0%, #00d4b8 100%) !important;
        border: none !important;
        color: white !important;
    }
    button[kind="primary"]:hover {
        box-shadow: 0 4px 14px rgba(0,180,198,0.45) !important;
        color: white !important;
    }
    div[data-baseweb="tab-list"] {
        gap: 6px;
        border-bottom: 2px solid #eaf2f2;
    }
    button[data-baseweb="tab"] {
        border-radius: 10px 10px 0 0 !important;
        padding: 8px 18px !important;
        font-weight: 600 !important;
        background: #f3f8fa !important;
    }
    button[aria-selected="true"] {
        background: linear-gradient(90deg, #00b4c6 0%, #00d4b8 100%) !important;
        color: white !important;
    }
    .stTextInput input, .stNumberInput input, .stDateInput input {
        border-radius: 10px !important;
    }
    div[data-baseweb="select"] > div {
        border-radius: 10px !important;
    }
    hr { border-color: #eaf2f2 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# =====================================================
# CONFIGURAZIONE PERCORSI E COSTANTI
# =====================================================
CARTELLA_DATI = os.path.dirname(os.path.abspath(__file__))
PERCORSO = os.path.join(CARTELLA_DATI, "frigorifero.json")
SPESA_PATH = os.path.join(CARTELLA_DATI, "spesa.json")
SPRECHI_PATH = os.path.join(CARTELLA_DATI, "sprechi.json")
IMPOSTAZIONI_PATH = os.path.join(CARTELLA_DATI, "impostazioni.json")

GIORNI_SOGLIA_SCADENZA_DEFAULT = 3
GIORNI_SOGLIA_SCADENZA = GIORNI_SOGLIA_SCADENZA_DEFAULT  # aggiornata dopo il caricamento impostazioni
SOGLIA_SCORTA_BASSA = 1
FINESTRA_FRESCHEZZA_GIORNI = 10

ICONE_ALIMENTI = {
    "mela": "🍎", "banana": "🍌", "arancia": "🍊", "limone": "🍋",
    "uva": "🍇", "fragol": "🍓", "pesca": "🍑", "anguria": "🍉",
    "pomodor": "🍅", "carota": "🥕", "insalata": "🥬", "lattuga": "🥬",
    "patata": "🥔", "cipolla": "🧅", "aglio": "🧄", "peperone": "🫑",
    "funghi": "🍄", "broccol": "🥦",
    "latte": "🥛", "yogurt": "🥣", "formaggio": "🧀", "burro": "🧈",
    "uov": "🥚",
    "pollo": "🍗", "carne": "🥩", "manzo": "🥩", "salsiccia": "🌭",
    "pesce": "🐟", "salmone": "🐟", "tonno": "🐟", "gambero": "🦐",
    "pane": "🍞", "pasta": "🍝", "riso": "🍚", "pizza": "🍕",
    "vino": "🍷", "birra": "🍺", "acqua": "💧", "succo": "🧃",
    "cioccolat": "🍫", "biscott": "🍪", "gelato": "🍨",
    "sale": "🧂", "olio": "🫒",
}

CATEGORIE_ALIMENTI = {
    "Frutta": ["mela", "banana", "arancia", "limone", "uva", "fragol", "pesca", "anguria"],
    "Verdura": ["pomodor", "carota", "insalata", "lattuga", "patata", "cipolla", "aglio", "peperone", "funghi", "broccol"],
    "Latticini": ["latte", "yogurt", "formaggio", "burro", "uov"],
    "Carne e pesce": ["pollo", "carne", "manzo", "salsiccia", "pesce", "salmone", "tonno", "gambero"],
    "Cereali e pane": ["pane", "pasta", "riso", "pizza"],
    "Bevande": ["vino", "birra", "acqua", "succo"],
    "Dolci": ["cioccolat", "biscott", "gelato"],
    "Condimenti": ["sale", "olio"],
}


def icona_per(alimento):
    alimento_lower = alimento.lower()
    for parola_chiave, emoji in ICONE_ALIMENTI.items():
        if parola_chiave in alimento_lower:
            return emoji
    return "🍽️"


def accoda_toast(messaggio, icona="✅"):
    """
    Salva un messaggio toast da mostrare DOPO il prossimo rerun.
    Necessario perché st.toast() chiamato subito prima di st.rerun()
    non fa in tempo a comparire: il rerun lo interrompe.
    """
    st.session_state["_toast_in_coda"] = (messaggio, icona)


def categoria_per(alimento):
    alimento_lower = alimento.lower()
    for categoria, parole_chiave in CATEGORIE_ALIMENTI.items():
        if any(parola in alimento_lower for parola in parole_chiave):
            return categoria
    return "Altro"


# =====================================================
# FUNZIONI DI SUPPORTO — STORAGE (locale + cloud)
# =====================================================
def carica_json(percorso, default):
    try:
        with open(percorso, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return default


def salva_json(percorso, dati):
    with open(percorso, "w", encoding="utf-8") as file:
        json.dump(dati, file, ensure_ascii=False, indent=4)


def usa_storage_cloud():
    return bool(os.environ.get("JSONBIN_API_KEY"))


def carica_dati(percorso_locale, nome_variabile_bin_id, default):
    bin_id = os.environ.get(nome_variabile_bin_id)
    if usa_storage_cloud() and bin_id:
        url = f"https://api.jsonbin.io/v3/b/{bin_id}/latest"
        headers = {"X-Master-Key": os.environ["JSONBIN_API_KEY"]}
        try:
            risposta = requests.get(url, headers=headers, timeout=8)
            risposta.raise_for_status()
            return risposta.json().get("record", default)
        except (requests.exceptions.RequestException, ValueError):
            st.warning("Impossibile leggere dallo storage cloud, uso dati vuoti temporanei.")
            return default
    return carica_json(percorso_locale, default)


def salva_dati(percorso_locale, nome_variabile_bin_id, dati):
    bin_id = os.environ.get(nome_variabile_bin_id)
    if usa_storage_cloud() and bin_id:
        url = f"https://api.jsonbin.io/v3/b/{bin_id}"
        headers = {
            "X-Master-Key": os.environ["JSONBIN_API_KEY"],
            "Content-Type": "application/json",
        }
        try:
            requests.put(url, headers=headers, json=dati, timeout=8)
        except requests.exceptions.RequestException:
            st.warning("Impossibile salvare sullo storage cloud, i dati potrebbero non persistere.")
    else:
        salva_json(percorso_locale, dati)


def migra_formato_vecchio(frigorifero):
    cambiato = False
    for alimento, valore in list(frigorifero.items()):
        if isinstance(valore, (int, float)):
            frigorifero[alimento] = {"quantita": valore, "scadenza": None, "foto": None}
            cambiato = True
    return frigorifero, cambiato


# =====================================================
# FUNZIONI DI SUPPORTO — FOTO
# =====================================================
def immagine_a_base64(immagine_bytes, larghezza_max=300, qualita=70):
    """Comprime un'immagine e la converte in stringa base64, per poterla salvare nel JSON."""
    immagine = Image.open(io.BytesIO(immagine_bytes)).convert("RGB")
    if immagine.width > larghezza_max:
        rapporto = larghezza_max / immagine.width
        immagine = immagine.resize((larghezza_max, int(immagine.height * rapporto)))
    buffer = io.BytesIO()
    immagine.save(buffer, format="JPEG", quality=qualita)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def base64_a_bytes(stringa_base64):
    return base64.b64decode(stringa_base64)


# =====================================================
# FUNZIONI DI SUPPORTO — DOMINIO
# =====================================================
def giorni_alla_scadenza(scadenza_str):
    if not scadenza_str:
        return None
    scadenza = datetime.strptime(scadenza_str, "%Y-%m-%d").date()
    return (scadenza - date.today()).days


def aggiungi_alimento(frigorifero, alimento, quantita, scadenza_str, foto_base64=None):
    if alimento in frigorifero:
        frigorifero[alimento]["quantita"] += quantita
        scadenza_esistente = frigorifero[alimento].get("scadenza")
        if not scadenza_esistente or scadenza_str < scadenza_esistente:
            frigorifero[alimento]["scadenza"] = scadenza_str
        if foto_base64:
            frigorifero[alimento]["foto"] = foto_base64
    else:
        frigorifero[alimento] = {
            "quantita": quantita,
            "scadenza": scadenza_str,
            "foto": foto_base64,
        }
    return frigorifero


def rimuovi_uno(frigorifero, alimento):
    if alimento not in frigorifero:
        return frigorifero
    frigorifero[alimento]["quantita"] -= 1
    if frigorifero[alimento]["quantita"] <= 0:
        del frigorifero[alimento]
    return frigorifero


def rimuovi_completamente(frigorifero, alimento):
    if alimento in frigorifero:
        del frigorifero[alimento]
    return frigorifero


def trova_in_scadenza(frigorifero, soglia_giorni=GIORNI_SOGLIA_SCADENZA_DEFAULT):
    risultato = []
    for alimento, dati in frigorifero.items():
        giorni = giorni_alla_scadenza(dati.get("scadenza"))
        if giorni is not None and giorni <= soglia_giorni:
            risultato.append((alimento, giorni))
    risultato.sort(key=lambda coppia: coppia[1])
    return risultato


def trova_scorte_basse(frigorifero, soglia=SOGLIA_SCORTA_BASSA):
    return [a for a, dati in frigorifero.items() if dati["quantita"] <= soglia]


def ordina_per_scadenza(frigorifero):
    def chiave_ordinamento(coppia):
        _, dati = coppia
        giorni = giorni_alla_scadenza(dati.get("scadenza"))
        return (giorni is None, giorni if giorni is not None else 0)
    return sorted(frigorifero.items(), key=chiave_ordinamento)


def aggiungi_a_lista_spesa(lista_spesa, alimenti):
    esistenti_lower = {p.lower() for p in lista_spesa}
    for alimento in alimenti:
        if alimento.lower() not in esistenti_lower:
            lista_spesa.append(alimento)
            esistenti_lower.add(alimento.lower())
    return lista_spesa


def badge_scadenza(giorni):
    if giorni is None:
        return ""
    if giorni < 0:
        return f'<span class="badge badge-scaduto">Scaduto da {abs(giorni)}g</span>'
    if giorni == 0:
        return '<span class="badge badge-oggi">Scade oggi</span>'
    if giorni <= GIORNI_SOGLIA_SCADENZA:
        return f'<span class="badge badge-presto">Scade tra {giorni}g</span>'
    return f'<span class="badge badge-ok">Scade tra {giorni}g</span>'


def livello_freschezza(giorni):
    if giorni is None:
        return 1.0
    if giorni <= 0:
        return 0.0
    return min(giorni / FINESTRA_FRESCHEZZA_GIORNI, 1.0)


def registra_spreco(cronologia_sprechi, alimento, quantita):
    """Aggiunge una voce alla cronologia degli sprechi, con data odierna."""
    cronologia_sprechi.append({
        "alimento": alimento,
        "quantita": quantita,
        "data": date.today().strftime("%Y-%m-%d"),
    })
    return cronologia_sprechi


def aggrega_sprechi_per_mese(cronologia_sprechi):
    """Ritorna un DataFrame con il totale di unità sprecate per mese (colonna 'mese', 'quantita')."""
    if not cronologia_sprechi:
        return pd.DataFrame(columns=["mese", "quantita"])
    df = pd.DataFrame(cronologia_sprechi)
    df["mese"] = df["data"].str.slice(0, 7)
    aggregato = df.groupby("mese")["quantita"].sum().reset_index()
    return aggregato


# =====================================================
# FUNZIONI DI SUPPORTO — BARCODE
# =====================================================
def estrai_codici_da_immagine(immagine_bytes):
    if not PYZBAR_DISPONIBILE:
        return []
    immagine_originale = Image.open(io.BytesIO(immagine_bytes))
    tentativi = [
        immagine_originale,
        immagine_originale.convert("L"),
        immagine_originale.convert("L").resize(
            (immagine_originale.width * 2, immagine_originale.height * 2)
        ),
    ]
    for immagine_tentativo in tentativi:
        risultati = decodifica_barcode_immagine(immagine_tentativo)
        if risultati:
            return [r.data.decode("utf-8") for r in risultati]
    return []


def cerca_prodotto_da_barcode(codice):
    url = f"https://world.openfoodfacts.org/api/v0/product/{codice}.json"
    # Open Food Facts richiede un User-Agent identificativo nelle richieste,
    # altrimenti alcune richieste vengono rifiutate o bloccate.
    headers = {"User-Agent": "FrigoriferoSmart/1.0 (app personale Streamlit)"}
    try:
        risposta = requests.get(url, headers=headers, timeout=10)
        risposta.raise_for_status()
        dati = risposta.json()
    except requests.exceptions.RequestException as errore_rete:
        return None, f"Impossibile contattare il database prodotti: {errore_rete}"
    except ValueError:
        return None, "Risposta non valida dal database prodotti. Riprova più tardi."

    if dati.get("status") == 1:
        prodotto = dati.get("product", {})
        nome = prodotto.get("product_name_it") or prodotto.get("product_name") or None
        if nome:
            return nome, None
        return None, "Prodotto trovato ma senza nome disponibile."
    return None, "Codice a barre non trovato nel database Open Food Facts."


# =====================================================
# FUNZIONI DI SUPPORTO — AI
# =====================================================
def genera_prompt_ricette(frigorifero):
    righe = []
    for alimento, dati in frigorifero.items():
        giorni = giorni_alla_scadenza(dati.get("scadenza"))
        nota_scadenza = f", scade tra {giorni} giorni" if giorni is not None else ""
        righe.append(f"{alimento}: {dati['quantita']}{nota_scadenza}")
    contenuto = "; ".join(righe)

    return f"""
Sei l'assistente di un frigorifero intelligente.

Questi sono gli alimenti disponibili (con eventuale scadenza):
{contenuto}

Proponimi 3 ricette che posso preparare.

Regole:
- Dai priorità agli alimenti che scadono prima.
- Usa principalmente gli alimenti che ho già.
- Per ogni ricetta indica gli ingredienti che ho.
- Indica chiaramente eventuali ingredienti che mi mancano.
- Dai un procedimento semplice e breve.
- Non inventare alimenti che non sono nella lista come se li avessi.
- Scegli ricette semplici e realistiche.

Per ogni ricetta usa questo formato:

🍽️ NOME DEL PIATTO

Hai:
- ...

Ti manca:
- ...

Procedimento:
1. ...
2. ...
3. ...
"""


def genera_prompt_piano_settimanale(frigorifero):
    righe = []
    for alimento, dati in frigorifero.items():
        giorni = giorni_alla_scadenza(dati.get("scadenza"))
        nota_scadenza = f", scade tra {giorni} giorni" if giorni is not None else ""
        righe.append(f"{alimento}: {dati['quantita']}{nota_scadenza}")
    contenuto = "; ".join(righe)

    return f"""
Sei l'assistente di un frigorifero intelligente.

Questi sono gli alimenti disponibili (con eventuale scadenza):
{contenuto}

Crea un piano pasti per 7 giorni (pranzo e cena), dando priorità agli
alimenti che scadono prima.

Regole:
- Usa principalmente gli alimenti che ho già, specialmente quelli in scadenza.
- Ricette semplici e realistiche, non elaborate.
- Non inventare alimenti che non sono nella lista come se li avessi.

Rispondi in questo formato:

📅 GIORNO 1
Pranzo: ...
Cena: ...

📅 GIORNO 2
Pranzo: ...
Cena: ...

(continua fino al giorno 7)

Alla fine, in una sezione separata intitolata "🛒 DA COMPRARE", elenca
tutti gli ingredienti mancanti per completare il piano, senza duplicati.
"""


def chiave_api_presente():
    return bool(os.environ.get("OPENAI_API_KEY"))


def chiedi_ricette(frigorifero):
    if not chiave_api_presente():
        return None, (
            "Manca la chiave API di OpenAI. Impostala come variabile d'ambiente "
            "OPENAI_API_KEY prima di avviare l'app."
        )
    try:
        client = OpenAI()
        risposta = client.responses.create(
            # "gpt-5.6-luna" è il nome mostrato nell'app ChatGPT, non necessariamente
            # la stringa che l'API si aspetta. Verifica su platform.openai.com > Models
            # quale stringa usare davvero, poi aggiorna qui se serve.
            model="gpt-5-mini",
            input=genera_prompt_ricette(frigorifero),
        )
        return risposta.output_text, None
    except Exception as errore:
        return None, f"Errore durante la chiamata all'AI: {errore}"


def chiedi_piano_settimanale(frigorifero):
    if not chiave_api_presente():
        return None, (
            "Manca la chiave API di OpenAI. Impostala come variabile d'ambiente "
            "OPENAI_API_KEY prima di avviare l'app."
        )
    try:
        client = OpenAI()
        risposta = client.responses.create(
            model="gpt-5-mini",
            input=genera_prompt_piano_settimanale(frigorifero),
        )
        return risposta.output_text, None
    except Exception as errore:
        return None, f"Errore durante la chiamata all'AI: {errore}"


# =====================================================
# FUNZIONI DI SUPPORTO — EMAIL
# =====================================================
def credenziali_email_presenti():
    return bool(os.environ.get("EMAIL_MITTENTE") and os.environ.get("EMAIL_PASSWORD"))


def invia_email(oggetto, corpo):
    """
    Invia un'email usando un account Gmail (richiede una 'App Password',
    non la password normale dell'account). Ritorna (successo, errore).
    """
    if not credenziali_email_presenti():
        return False, "Credenziali email non configurate (EMAIL_MITTENTE, EMAIL_PASSWORD)."

    mittente = os.environ["EMAIL_MITTENTE"]
    password = os.environ["EMAIL_PASSWORD"]
    destinatario = os.environ.get("EMAIL_DESTINATARIO", mittente)

    try:
        messaggio = MIMEText(corpo)
        messaggio["Subject"] = oggetto
        messaggio["From"] = mittente
        messaggio["To"] = destinatario

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(mittente, password)
            server.sendmail(mittente, [destinatario], messaggio.as_string())
        return True, None
    except Exception as errore:
        return False, f"Errore durante l'invio dell'email: {errore}"


def genera_corpo_email_scadenze(in_scadenza):
    righe = []
    for alimento, giorni in in_scadenza:
        if giorni < 0:
            righe.append(f"- {alimento}: scaduto da {abs(giorni)} giorni")
        elif giorni == 0:
            righe.append(f"- {alimento}: scade oggi")
        else:
            righe.append(f"- {alimento}: scade tra {giorni} giorni")
    return "Alimenti in scadenza nel tuo frigorifero:\n\n" + "\n".join(righe)


# =====================================================
# GATE PASSWORD (attivo solo se APP_PASSWORD è configurata)
# =====================================================
def richiede_password():
    return bool(os.environ.get("APP_PASSWORD"))


if richiede_password():
    if "autenticato" not in st.session_state:
        st.session_state["autenticato"] = False

    if not st.session_state["autenticato"]:
        st.markdown('<p class="main-title">🔒 Accesso protetto</p>', unsafe_allow_html=True)
        password_inserita = st.text_input("Password", type="password", key="input_password")
        if st.button("Entra", type="primary"):
            if password_inserita == os.environ["APP_PASSWORD"]:
                st.session_state["autenticato"] = True
                st.rerun()
            else:
                st.error("Password errata.")
        st.stop()


# =====================================================
# CARICAMENTO DATI
# =====================================================
frigorifero = carica_dati(PERCORSO, "JSONBIN_FRIGORIFERO_ID", {})
frigorifero, migrato = migra_formato_vecchio(frigorifero)
if migrato:
    salva_dati(PERCORSO, "JSONBIN_FRIGORIFERO_ID", frigorifero)

lista_spesa = carica_dati(SPESA_PATH, "JSONBIN_SPESA_ID", [])
cronologia_sprechi = carica_dati(SPRECHI_PATH, "JSONBIN_SPRECHI_ID", [])
impostazioni = carica_dati(
    IMPOSTAZIONI_PATH,
    "JSONBIN_IMPOSTAZIONI_ID",
    {"soglia_giorni": GIORNI_SOGLIA_SCADENZA_DEFAULT, "ultima_notifica": None},
)

GIORNI_SOGLIA_SCADENZA = impostazioni.get("soglia_giorni", GIORNI_SOGLIA_SCADENZA_DEFAULT)

in_scadenza_dashboard = trova_in_scadenza(frigorifero, GIORNI_SOGLIA_SCADENZA)
scorte_basse_dashboard = trova_scorte_basse(frigorifero)

# -------- Notifica email automatica (una volta al giorno) --------
oggi_str = date.today().strftime("%Y-%m-%d")
if (
    credenziali_email_presenti()
    and in_scadenza_dashboard
    and impostazioni.get("ultima_notifica") != oggi_str
):
    corpo_email = genera_corpo_email_scadenze(in_scadenza_dashboard)
    inviata, errore_invio_auto = invia_email("🥶 Alimenti in scadenza", corpo_email)
    if inviata:
        impostazioni["ultima_notifica"] = oggi_str
        salva_dati(IMPOSTAZIONI_PATH, "JSONBIN_IMPOSTAZIONI_ID", impostazioni)


# =====================================================
# TITOLO
# =====================================================
st.markdown('<p class="main-title">🥶 Frigorifero Smart</p>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Il tuo frigorifero intelligente</p>', unsafe_allow_html=True)


# =====================================================
# SIDEBAR — filtri, impostazioni, account, notifiche
# =====================================================
with st.sidebar:
    st.header("⚙️ Menu")

    if richiede_password():
        st.caption("Sei connesso.")
        if st.button("🚪 Esci"):
            st.session_state["autenticato"] = False
            accoda_toast("Disconnesso", icon="👋")
            st.rerun()
        st.divider()

    st.subheader("🔍 Filtra il frigorifero")
    ricerca_sidebar = st.text_input("Cerca alimento", key="ricerca_sidebar")
    categorie_disponibili = sorted({categoria_per(a) for a in frigorifero.keys()})
    categorie_scelte = st.multiselect("Categoria", categorie_disponibili, key="filtro_categoria")

    st.divider()
    st.subheader("⏰ Impostazioni scadenza")
    nuova_soglia = st.number_input(
        "Giorni soglia 'in scadenza'",
        min_value=1,
        max_value=30,
        value=int(impostazioni.get("soglia_giorni", GIORNI_SOGLIA_SCADENZA_DEFAULT)),
        key="input_soglia",
    )
    if nuova_soglia != impostazioni.get("soglia_giorni"):
        impostazioni["soglia_giorni"] = nuova_soglia
        salva_dati(IMPOSTAZIONI_PATH, "JSONBIN_IMPOSTAZIONI_ID", impostazioni)
        st.rerun()

    st.divider()
    st.subheader("📧 Notifiche")
    if credenziali_email_presenti():
        if st.button("Invia notifica scadenze ora"):
            corpo_manuale = (
                genera_corpo_email_scadenze(in_scadenza_dashboard)
                if in_scadenza_dashboard
                else "Nessun alimento in scadenza al momento."
            )
            inviata_manuale, errore_manuale_email = invia_email(
                "🥶 Alimenti in scadenza", corpo_manuale
            )
            if inviata_manuale:
                st.success("Email inviata!")
            else:
                st.error(errore_manuale_email)
    else:
        st.caption(
            "Configura EMAIL_MITTENTE, EMAIL_PASSWORD (e opzionalmente "
            "EMAIL_DESTINATARIO) per abilitare le notifiche via email."
        )


# =====================================================
# DASHBOARD
# =====================================================
col_a, col_b, col_c = st.columns(3)
col_a.metric("📦 Alimenti totali", len(frigorifero))
col_b.metric("⏰ In scadenza", len(in_scadenza_dashboard))
col_c.metric("⚠️ Scorte basse", len(scorte_basse_dashboard))

st.divider()


# =====================================================
# NAVIGAZIONE A SCHEDE
# =====================================================
tab_frigo, tab_scansiona, tab_aggiungi, tab_ricette, tab_piano, tab_statistiche, tab_spesa = st.tabs(
    [
        "🧊 Frigorifero",
        "📷 Scansiona",
        "➕ Aggiungi",
        "🍳 Ricette AI",
        "🗓️ Piano settimanale",
        "📊 Statistiche",
        "🛒 Lista spesa",
    ]
)

# -----------------------------------------------------
# SCHEDA: FRIGORIFERO
# -----------------------------------------------------
with tab_frigo:
    if not frigorifero:
        st.info("Il frigorifero è vuoto. Vai alla scheda ➕ Aggiungi per iniziare.")
    else:
        almeno_uno_mostrato = False
        for alimento, dati in ordina_per_scadenza(frigorifero):
            if ricerca_sidebar and ricerca_sidebar.lower() not in alimento.lower():
                continue
            if categorie_scelte and categoria_per(alimento) not in categorie_scelte:
                continue

            almeno_uno_mostrato = True
            giorni = giorni_alla_scadenza(dati.get("scadenza"))

            with st.container():
                col_foto, col_info, col_azioni = st.columns([1, 3, 2])
                with col_foto:
                    if dati.get("foto"):
                        st.image(base64_a_bytes(dati["foto"]), width=60)
                    else:
                        st.markdown(
                            f'<div style="font-size:2.3rem; text-align:center;">{icona_per(alimento)}</div>',
                            unsafe_allow_html=True,
                        )
                with col_info:
                    st.markdown(
                        f"""
                        <div class="food-row">
                        <b>{alimento}</b> — quantità: {dati['quantita']}<br>
                        {badge_scadenza(giorni) if giorni is not None else '<span style="color:#999">senza scadenza impostata</span>'}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    if giorni is not None:
                        st.progress(livello_freschezza(giorni))
                with col_azioni:
                    sub_r1, sub_r2, sub_r3 = st.columns(3)
                    with sub_r1:
                        if st.button("➖", key=f"meno_{alimento}", help="Rimuovi 1"):
                            frigorifero = rimuovi_uno(frigorifero, alimento)
                            salva_dati(PERCORSO, "JSONBIN_FRIGORIFERO_ID", frigorifero)
                            accoda_toast(f"{icona_per(alimento)} {alimento} aggiornato", icon="✅")
                            st.rerun()
                    with sub_r2:
                        if st.button("🗑️", key=f"elimina_{alimento}", help="Elimina (consumato)"):
                            frigorifero = rimuovi_completamente(frigorifero, alimento)
                            salva_dati(PERCORSO, "JSONBIN_FRIGORIFERO_ID", frigorifero)
                            accoda_toast(f"{icona_per(alimento)} {alimento} eliminato", icon="🗑️")
                            st.rerun()
                    with sub_r3:
                        if st.button("🚮", key=f"spreco_{alimento}", help="Segna come sprecato/buttato"):
                            cronologia_sprechi = registra_spreco(
                                cronologia_sprechi, alimento, dati["quantita"]
                            )
                            salva_dati(SPRECHI_PATH, "JSONBIN_SPRECHI_ID", cronologia_sprechi)
                            frigorifero = rimuovi_completamente(frigorifero, alimento)
                            salva_dati(PERCORSO, "JSONBIN_FRIGORIFERO_ID", frigorifero)
                            accoda_toast(f"{alimento} segnato come sprecato", icon="🚮")
                            st.rerun()

        if not almeno_uno_mostrato:
            st.info("Nessun alimento corrisponde ai filtri selezionati.")

        st.divider()

        if scorte_basse_dashboard:
            st.subheader("⚠️ Da ricomprare")
            for alimento_sb in scorte_basse_dashboard:
                st.write(f"{icona_per(alimento_sb)} {alimento_sb}")
            if st.button("🛒 Aggiungi tutti alla lista della spesa", type="primary"):
                lista_spesa = aggiungi_a_lista_spesa(lista_spesa, scorte_basse_dashboard)
                salva_dati(SPESA_PATH, "JSONBIN_SPESA_ID", lista_spesa)
                st.success("Aggiunti alla lista della spesa!")
                st.rerun()

# -----------------------------------------------------
# SCHEDA: SCANSIONA BARCODE
# -----------------------------------------------------
with tab_scansiona:
    st.subheader("📷 Scansiona un codice a barre")

    if not PYZBAR_DISPONIBILE:
        st.error(
            "Manca la libreria 'pyzbar'. Installala con: pip install pyzbar\n\n"
            "Su Windows potrebbe servire anche installare il pacchetto "
            "Visual C++ Redistributable se vedi un errore all'avvio."
        )
    else:
        st.caption("Inquadra il codice a barre del prodotto e scatta.")
        foto = st.camera_input("Scatta una foto del codice a barre", key="foto_barcode")

        if foto is not None:
            st.image(foto, caption="Foto scattata", width=300)
            codici_trovati = estrai_codici_da_immagine(foto.getvalue())

            if not codici_trovati:
                st.warning(
                    "Nessun codice a barre riconosciuto. Guarda la foto qui sopra: "
                    "il codice deve essere nitido, ben illuminato, senza riflessi, "
                    "e occupare una porzione ampia dell'inquadratura (non troppo lontano). "
                    "In alternativa, inserisci il codice a mano qui sotto."
                )
            else:
                codice = codici_trovati[0]
                st.success(f"Codice rilevato: {codice}")

                with st.spinner("Cerco il prodotto..."):
                    nome_prodotto, errore = cerca_prodotto_da_barcode(codice)

                if errore:
                    st.warning(errore)
                    nome_prodotto = ""

                st.write("Controlla e conferma i dati prima di aggiungere:")
                nome_confermato = st.text_input(
                    "Nome prodotto", value=nome_prodotto or "", key="nome_da_barcode"
                )
                quantita_confermata = st.number_input(
                    "Quantità", min_value=1, step=1, key="quantita_da_barcode"
                )
                scadenza_confermata = st.date_input(
                    "Scadenza", value=date.today() + timedelta(days=7), key="scadenza_da_barcode"
                )

                if st.button("✅ Aggiungi al frigorifero", key="conferma_barcode", type="primary"):
                    if nome_confermato:
                        foto_base64 = immagine_a_base64(foto.getvalue())
                        frigorifero = aggiungi_alimento(
                            frigorifero,
                            nome_confermato.strip(),
                            quantita_confermata,
                            scadenza_confermata.strftime("%Y-%m-%d"),
                            foto_base64=foto_base64,
                        )
                        salva_dati(PERCORSO, "JSONBIN_FRIGORIFERO_ID", frigorifero)
                        st.success(f"{icona_per(nome_confermato)} {nome_confermato} aggiunto!")
                        st.rerun()
                    else:
                        st.warning("Inserisci un nome prodotto prima di aggiungerlo.")

        st.divider()
        st.caption("Il codice non viene riconosciuto? Inseriscilo manualmente:")
        codice_manuale = st.text_input("Codice a barre manuale", key="codice_manuale")
        if codice_manuale and st.button("Cerca questo codice", key="cerca_manuale"):
            with st.spinner("Cerco il prodotto..."):
                nome_manuale, errore_manuale = cerca_prodotto_da_barcode(codice_manuale.strip())
            if errore_manuale:
                st.warning(errore_manuale)
            else:
                st.success(f"Trovato: {nome_manuale}")
                st.session_state["nome_da_barcode"] = nome_manuale

# -----------------------------------------------------
# SCHEDA: AGGIUNGI ALIMENTO
# -----------------------------------------------------
with tab_aggiungi:
    st.subheader("➕ Aggiungi un alimento")

    alimento_input = st.text_input("Nome alimento", key="input_alimento")
    quantita_input = st.number_input("Quantità", min_value=1, step=1, key="input_quantita")
    scadenza_input = st.date_input(
        "Data di scadenza", value=date.today() + timedelta(days=7), key="input_scadenza"
    )

    if alimento_input:
        st.caption(f"Anteprima: {icona_per(alimento_input)} {alimento_input} · Categoria: {categoria_per(alimento_input)}")

    foto_input = st.file_uploader(
        "Foto (opzionale)", type=["jpg", "jpeg", "png"], key="foto_input_manuale"
    )
    usa_camera = st.checkbox("...oppure scatta una foto ora", key="usa_camera_manuale")
    if usa_camera:
        foto_camera = st.camera_input("Scatta foto alimento", key="camera_input_manuale")
        if foto_camera is not None:
            foto_input = foto_camera

    if st.button("Aggiungi al frigorifero", type="primary"):
        if alimento_input:
            foto_base64 = immagine_a_base64(foto_input.getvalue()) if foto_input else None
            frigorifero = aggiungi_alimento(
                frigorifero,
                alimento_input.strip(),
                quantita_input,
                scadenza_input.strftime("%Y-%m-%d"),
                foto_base64=foto_base64,
            )
            salva_dati(PERCORSO, "JSONBIN_FRIGORIFERO_ID", frigorifero)
            st.success(f"{icona_per(alimento_input)} {alimento_input} aggiunto!")
            st.rerun()
        else:
            st.warning("Scrivi il nome di un alimento prima di aggiungerlo.")

# -----------------------------------------------------
# SCHEDA: RICETTE AI
# -----------------------------------------------------
with tab_ricette:
    st.subheader("🍳 Cosa posso cucinare?")
    st.caption("L'AI userà gli alimenti che hai, dando priorità a quelli in scadenza.")

    if st.button("Chiedi ricette all'AI", type="primary"):
        if not frigorifero:
            st.warning("Il frigorifero è vuoto, aggiungi prima qualche alimento.")
        else:
            with st.spinner("Sto pensando a qualche ricetta..."):
                risposta, errore = chiedi_ricette(frigorifero)
            if errore:
                st.error(errore)
            else:
                st.markdown(risposta)

# -----------------------------------------------------
# SCHEDA: PIANO SETTIMANALE
# -----------------------------------------------------
with tab_piano:
    st.subheader("🗓️ Piano pasti settimanale")
    st.caption("Genera un piano di 7 giorni basato su cosa hai, con la lista di ciò che manca.")

    if st.button("Genera piano settimanale", type="primary"):
        if not frigorifero:
            st.warning("Il frigorifero è vuoto, aggiungi prima qualche alimento.")
        else:
            with st.spinner("Sto organizzando la settimana..."):
                piano, errore_piano = chiedi_piano_settimanale(frigorifero)
            if errore_piano:
                st.error(errore_piano)
            else:
                st.markdown(piano)
                st.caption(
                    "Copia manualmente gli ingredienti della sezione '🛒 DA COMPRARE' "
                    "nella scheda Lista Spesa, se vuoi tenerne traccia lì."
                )

# -----------------------------------------------------
# SCHEDA: STATISTICHE SPRECO
# -----------------------------------------------------
with tab_statistiche:
    st.subheader("📊 Statistiche spreco")

    if not cronologia_sprechi:
        st.info(
            "Nessun alimento segnato come sprecato finora. "
            "Usa il pulsante 🚮 nella scheda Frigorifero quando butti via qualcosa "
            "(diverso da 🗑️, che indica 'consumato')."
        )
    else:
        aggregato = aggrega_sprechi_per_mese(cronologia_sprechi)
        st.bar_chart(aggregato.set_index("mese"))

        totale_unita = sum(voce["quantita"] for voce in cronologia_sprechi)
        st.metric("Totale unità sprecate registrate", totale_unita)

        with st.expander("Vedi cronologia dettagliata"):
            for voce in reversed(cronologia_sprechi):
                st.write(f"{voce['data']} — {icona_per(voce['alimento'])} {voce['alimento']} (x{voce['quantita']})")

# -----------------------------------------------------
# SCHEDA: LISTA DELLA SPESA
# -----------------------------------------------------
with tab_spesa:
    st.subheader("🛒 Lista della spesa")

    prodotto = st.text_input("Cosa devi comprare?", key="input_spesa")
    if st.button("Aggiungi alla lista", key="btn_spesa", type="primary"):
        if prodotto:
            lista_spesa = aggiungi_a_lista_spesa(lista_spesa, [prodotto.strip()])
            salva_dati(SPESA_PATH, "JSONBIN_SPESA_ID", lista_spesa)
            accoda_toast(f"{icona_per(prodotto)} {prodotto} aggiunto alla lista", icon="✅")
            st.rerun()
        else:
            st.warning("Scrivi cosa devi comprare prima di aggiungerlo.")

    if lista_spesa:
        for i, prodotto_ls in enumerate(lista_spesa):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"{icona_per(prodotto_ls)} {prodotto_ls}")
            with col2:
                if st.button("✓", key=f"comprato_{i}"):
                    lista_spesa.pop(i)
                    salva_dati(SPESA_PATH, "JSONBIN_SPESA_ID", lista_spesa)
                    accoda_toast(f"{icona_per(prodotto_ls)} {prodotto_ls} comprato!", icon="🎉")
                    st.rerun()
    else:
        st.info("La lista della spesa è vuota.")
