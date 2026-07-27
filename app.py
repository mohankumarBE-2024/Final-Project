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
# from langchain_community.utilities import SQLDatabase
# from langchain_ollama import ChatOllama
# from langgraph.prebuilt import create_react_agent
# from langchain_community.agent_toolkits import SQLDatabaseToolkit


# Load environment variables securely
load_dotenv()

# --- SECURE AUTHENTICATION LAYER ---
# Initialize the session state for authentication
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# The Login Screen
if not st.session_state.authenticated:
    st.title("🔐 Intelliguard Secure Access")
    st.write("Please authenticate to access the compliance dashboard.")
    
    pin_input = st.text_input("Enter Admin PIN", type="password")
    
    if st.button("Login"):
        if pin_input == os.getenv("ADMIN_PIN"):
            st.session_state.authenticated = True
            st.success("Authentication successful! Loading dashboard...")
            st.rerun() # Refreshes the app to show the hidden content
        else:
            st.error("Invalid PIN. Access denied.")
            
    # CRITICAL: st.stop() prevents any code below this line from running 
    # until the user is authenticated.
    st.stop() 

# ==========================================
# IF AUTHENTICATED, THE REST OF THE APP RUNS
# ==========================================

# Database Connection Function
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT")
    )

def log_to_rds(filename, violations_list):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if there are any violations to determine anomaly status
    is_anomaly = len(violations_list) > 0
    
    # Insert into Table 1: Metadata
    cursor.execute(
        "INSERT INTO detection_logs (image_filename, is_anomaly) VALUES (%s, %s) RETURNING log_id;",
        (filename, is_anomaly)
    )
    log_id = cursor.fetchone()[0]
    
    # Insert into Table 2: Violation Details
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
        # 1. Fetch ONLY anomaly data from AWS RDS
        conn = get_db_connection()
        query = """
        SELECT d.log_id, d.timestamp, d.image_filename, d.is_anomaly, 
               v.violation_type, v.confidence_score
        FROM detection_logs d
        LEFT JOIN violation_details v ON d.log_id = v.log_id
        WHERE d.is_anomaly = TRUE
        ORDER BY d.timestamp DESC;
        """
        # Pandas runs the filtered query and maps it to the DataFrame
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        # 2. Check if there are actually any anomalies to report
        if df.empty:
            print("No anomalies found in the database. Email skipped.")
            return "NO_ANOMALIES"
        
        # 3. Convert DataFrame to a CSV string in memory
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_bytes = csv_buffer.getvalue().encode()
        
        # 4. Construct the Email
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = "⚠️ Intelliguard: Anomaly Compliance CSV Report"
        
        body = f"Please find attached the compilation of recorded PPE violations.\nTotal anomalies reported: {len(df)}"
        msg.attach(MIMEText(body, 'plain'))
        
        # 5. Attach the CSV file
        part = MIMEApplication(csv_bytes, Name="intelliguard_anomalies_report.csv")
        part['Content-Disposition'] = 'attachment; filename="intelliguard_anomalies_report.csv"'
        msg.attach(part)
        
        # 6. Send the Email
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return "SUCCESS"
        
    except Exception as e:
        print(f"Error generating or sending anomaly report: {e}")
        return "ERROR"

# def query_database_with_ai(user_question):
#     db_uri = os.getenv("DATABASE_URL")
#     db = SQLDatabase.from_uri(db_uri, include_tables=["detection_logs", "violation_details"])

#     llm = ChatOllama(model="qwen2.5", temperature=0)

#     toolkit = SQLDatabaseToolkit(db=db, llm=llm)
#     tools = toolkit.get_tools()

#     system_message = (
#         "You are an agent designed to interact with a SQL database. "
#         "Given a question, create a syntactically correct SQL query, "
#         "look at the results, and return the answer. "
#         "Always look at the tables in the database first using the list tables tool "
#         "before writing any query. Only use tables and columns that actually exist."
#     )

#     agent_executor = create_react_agent(llm, tools, prompt=system_message)

#     try:
#         response = agent_executor.invoke({"messages": [("human", user_question)]})
#         final_message = response["messages"][-1]
#         return final_message.content
#     except Exception as e:
#         return f"I encountered an error while analyzing the data: {e}"

# --- STREAMLIT UI ---
model = YOLO('intelliguard_best_v1.pt')
st.title("Intelliguard: AI-Powered PPE Compliance")

uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(image, caption="Uploaded Image", use_container_width=True)
    
    # Run YOLO inference
    results = model.predict(source=image, conf=0.25)
    
    detected_violations = []
    
    # Extract the detected classes
    for box in results[0].boxes:
        class_id = int(box.cls[0])
        class_name = model.names[class_id]
        confidence = float(box.conf[0])
        
        # Filter for violation classes based on your dataset
        if class_name in ['no-suit', 'no_glove', 'no_goggles', 'no_helmet', 'no_mask', 'no_shoes']:
            detected_violations.append((class_name, confidence))
    
    # Display the drawn image
    result_image_rgb = cv2.cvtColor(results[0].plot(), cv2.COLOR_BGR2RGB)
    st.image(result_image_rgb, caption="Detected PPE", use_container_width=True)
    
    # Log to AWS RDS
    # Log to AWS RDS and Send Email
    # Log to AWS RDS (NO EMAIL HERE ANYMORE)
    if st.button("Save Log to Database"):
        try:
            log_to_rds(uploaded_file.name, detected_violations)
            if detected_violations:
                st.error(f"Logged {len(detected_violations)} violations to RDS.")
            else:
                st.success("Logged clean compliance check to RDS.")
        except Exception as e:
            st.error(f"Database error: {e}")
    

# --- GENERATIVE AI DASHBOARD ---
# st.markdown("---")
# st.header("📊 AI Compliance Auditor")
# st.write("Ask questions about workplace safety logs in plain English.")

# # Initialize chat history in Streamlit session state
# if "messages" not in st.session_state:
#     st.session_state.messages = []

# # Display previous chat messages
# for message in st.session_state.messages:
#     with st.chat_message(message["role"]):
#         st.markdown(message["content"])

# # Handle new user input
# if prompt := st.chat_input("E.g., How many missing helmet violations were logged today?"):
    
#     # 1. Display user message
#     with st.chat_message("user"):
#         st.markdown(prompt)
    
#     # 2. Add to history
#     st.session_state.messages.append({"role": "user", "content": prompt})
    
#     # 3. Generate AI response
#     with st.chat_message("assistant"):
#         with st.spinner("Analyzing database..."):
#             ai_response = query_database_with_ai(prompt)
#             st.markdown(ai_response)
            
#     # 4. Add AI response to history
#     st.session_state.messages.append({"role": "assistant", "content": ai_response})

# --- ADMIN SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Admin Tools")
    st.write("Export and email recorded anomalies as a CSV.")
    
    if st.button("📧 Mail Anomaly CSV Report"):
        with st.spinner("Filtering AWS RDS for anomalies..."):
            result = send_csv_report_email()
            
            if result == "SUCCESS":
                st.success("✅ Anomaly report emailed successfully!")
            elif result == "NO_ANOMALIES":
                st.info("ℹ️ No anomalies found in the logs. No report needed.")
            else:
                st.error("❌ Failed to send report. Check terminal logs.")
