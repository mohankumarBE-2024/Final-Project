import os
import streamlit as st
import psycopg2
from dotenv import load_dotenv
from ultralytics import YOLO
from PIL import Image
import cv2
import smtplib
import io
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from langchain_community.utilities import SQLDatabase
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langchain_community.agent_toolkits import SQLDatabaseToolkit

# --- PAGE CONFIG: must be the very first Streamlit command ---
st.set_page_config(
    page_title="Intelliguard: AI-Powered PPE Compliance",
    page_icon="🦺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- GLOBAL THEME / CSS ---
st.markdown("""
<style>
[data-testid="stAppViewContainer"] {
    background: linear-gradient(180deg, #1a1408 0%, #0E1117 45%) !important;
}
[data-testid="stHeader"] {
    background: rgba(0,0,0,0) !important;
}
[data-testid="stFileUploader"], [data-testid="stMetric"], [data-testid="stChatMessage"] {
    background-color: #1C1F26;
    border: 1px solid #FF6B3533;
    border-radius: 12px;
    padding: 1rem;
}
div[data-baseweb="notification"] {
    border-radius: 10px;
}
.hero-title {
    text-align: center;
    padding: 0.5rem 0 0.2rem 0;
}
.hero-subtitle {
    text-align: center;
    color: #9AA0A6;
    padding-bottom: 1rem;
}
</style>
""", unsafe_allow_html=True)

# Load environment variables securely
load_dotenv()

# --- SECURE AUTHENTICATION LAYER ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown(
        "<h1 class='hero-title'>🦺 Intelliguard</h1>"
        "<p class='hero-subtitle'>AI-Powered PPE Compliance Monitoring System</p>",
        unsafe_allow_html=True
    )
    _, center_col, _ = st.columns([1, 1.2, 1])
    with center_col:
        st.markdown("### 🔐 Secure Access")
        st.write("Please authenticate to access the compliance dashboard.")

        pin_input = st.text_input("Enter Admin PIN", type="password")

        if st.button("Login", use_container_width=True):
            if pin_input == os.getenv("ADMIN_PIN"):
                st.session_state.authenticated = True
                st.success("Authentication successful! Loading dashboard...")
                st.rerun()
            else:
                st.error("Invalid PIN. Access denied.")

    st.stop()

# ==========================================
# IF AUTHENTICATED, THE REST OF THE APP RUNS
# ==========================================

VIOLATION_LABELS = {
    "no-suit":     "Missing Suit",
    "no_glove":    "Missing Gloves",
    "no_goggles":  "Missing Goggles",
    "no_helmet":   "Missing Helmet",
    "no_mask":     "Missing Mask",
    "no_shoes":    "Missing Shoes",
}


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT"),
        sslmode="require"
    )


def log_to_rds(filename, violations_list):
    conn = get_db_connection()
    cursor = conn.cursor()

    is_anomaly = len(violations_list) > 0

    cursor.execute(
        "INSERT INTO detection_logs (image_filename, is_anomaly) VALUES (%s, %s) RETURNING log_id;",
        (filename, is_anomaly)
    )
    log_id = cursor.fetchone()[0]

    for violation, conf in violations_list:
        cursor.execute(
            "INSERT INTO violation_details (log_id, violation_type, confidence_score) VALUES (%s, %s, %s);",
            (log_id, violation, conf)
        )

    conn.commit()
    cursor.close()
    conn.close()


def send_csv_report_email():
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")
    receiver_email = os.getenv("RECEIVER_EMAIL")

    try:
        conn = get_db_connection()
        query = """
        SELECT d.log_id, d.timestamp, d.image_filename, d.is_anomaly, 
               v.violation_type, v.confidence_score
        FROM detection_logs d
        LEFT JOIN violation_details v ON d.log_id = v.log_id
        WHERE d.is_anomaly = TRUE
        ORDER BY d.timestamp DESC;
        """
        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            print("No anomalies found in the database. Email skipped.")
            return "NO_ANOMALIES"

        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_bytes = csv_buffer.getvalue().encode()

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = "⚠️ Intelliguard: Anomaly Compliance CSV Report"

        body = f"Please find attached the compilation of recorded PPE violations.\nTotal anomalies reported: {len(df)}"
        msg.attach(MIMEText(body, 'plain'))

        part = MIMEApplication(csv_bytes, Name="intelliguard_anomalies_report.csv")
        part['Content-Disposition'] = 'attachment; filename="intelliguard_anomalies_report.csv"'
        msg.attach(part)

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return "SUCCESS"

    except Exception as e:
        print(f"Error generating or sending anomaly report: {e}")
        return "ERROR"


def extract_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts) if parts else str(content)
    return str(content)


def query_database_with_ai(user_question):
    db_uri = os.getenv("DATABASE_URL")
    db = SQLDatabase.from_uri(db_uri, include_tables=["detection_logs", "violation_details"])

    llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite", google_api_key=os.getenv("GOOGLE_API_KEY"), temperature=0)

    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    tools = toolkit.get_tools()

    system_message = (
        "You are an agent designed to interact with a SQL database. "
        "Given a question, create a syntactically correct SQL query, "
        "look at the results, and return the answer. "
        "Always look at the tables in the database first using the list tables tool "
        "before writing any query. Only use tables and columns that actually exist."
    )

    agent_executor = create_react_agent(llm, tools, prompt=system_message)

    try:
        response = agent_executor.invoke({"messages": [("human", user_question)]})
        final_message = response["messages"][-1]
        return extract_text(final_message.content)
    except Exception as e:
        if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
            return "I've hit my daily question limit for now — please try again later, or ask an admin to check the usage quota."
        return f"I encountered an error while analyzing the data: {e}"


# --- HERO HEADER ---
st.markdown(
    "<h1 class='hero-title'>🦺 Intelliguard</h1>"
    "<p class='hero-subtitle'>AI-Powered PPE Compliance Monitoring System</p>",
    unsafe_allow_html=True
)

model = YOLO('intelliguard_best_v1.pt')

tab_detect, tab_chat = st.tabs(["🔍 PPE Detection", "📊 AI Compliance Auditor"])

# ================= DETECTION TAB =================
with tab_detect:
    uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"])

    if uploaded_file is not None:
        image = Image.open(uploaded_file)

        results = model.predict(source=image, conf=0.25)

        detected_violations = []
        for box in results[0].boxes:
            class_id = int(box.cls[0])
            class_name = model.names[class_id]
            confidence = float(box.conf[0])
            if class_name in VIOLATION_LABELS:
                detected_violations.append((class_name, confidence))

        result_image_rgb = cv2.cvtColor(results[0].plot(), cv2.COLOR_BGR2RGB)

        col1, col2 = st.columns(2)
        with col1:
            st.image(image, caption="Uploaded Image", use_container_width=True)
        with col2:
            st.image(result_image_rgb, caption="Detected PPE", use_container_width=True)

        st.divider()

        if detected_violations:
            st.error(f"⚠️ {len(detected_violations)} Violation(s) Detected")
            v_cols = st.columns(len(detected_violations))
            for i, (v_type, conf) in enumerate(detected_violations):
                with v_cols[i]:
                    st.metric(VIOLATION_LABELS.get(v_type, v_type), f"{conf*100:.0f}%")
        else:
            st.success("✅ Fully Compliant — No Violations Detected")

        if st.button("💾 Save Log to Database", use_container_width=True):
            try:
                log_to_rds(uploaded_file.name, detected_violations)
                if detected_violations:
                    st.warning(f"Logged {len(detected_violations)} violation(s) to RDS.")
                else:
                    st.success("Logged clean compliance check to RDS.")
            except Exception as e:
                st.error(f"Database error: {e}")

# ================= CHATBOT TAB =================
with tab_chat:
    st.write("Ask questions about workplace safety logs in plain English.")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("E.g., How many missing helmet violations were logged today?"):
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            with st.spinner("Analyzing database..."):
                ai_response = query_database_with_ai(prompt)
                st.markdown(ai_response)
        st.session_state.messages.append({"role": "assistant", "content": ai_response})

# --- ADMIN SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Admin Tools")
    st.write("Export and email recorded anomalies as a CSV.")

    if st.button("📧 Mail Anomaly CSV Report", use_container_width=True):
        with st.spinner("Filtering AWS RDS for anomalies..."):
            result = send_csv_report_email()

            if result == "SUCCESS":
                st.success("✅ Anomaly report emailed successfully!")
            elif result == "NO_ANOMALIES":
                st.info("ℹ️ No anomalies found in the logs. No report needed.")
            else:
                st.error("❌ Failed to send report. Check terminal logs.")
