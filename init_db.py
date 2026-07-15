import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def create_tables():
    print("Connecting to AWS RDS...")
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            port=os.getenv("DB_PORT")
        )
        cursor = conn.cursor()

        create_schema_sql = """
        -- Table 1: Metadata + Anomaly Status
        CREATE TABLE detection_logs (
            log_id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            image_filename VARCHAR(255),
            is_anomaly BOOLEAN NOT NULL
        );

        -- Table 2: Violation-level details
        CREATE TABLE violation_details (
            violation_id SERIAL PRIMARY KEY,
            log_id INTEGER REFERENCES detection_logs(log_id),
            violation_type VARCHAR(50) NOT NULL,
            confidence_score DECIMAL(5, 4)
        );
        """

        print("Executing SQL script...")
        cursor.execute(create_schema_sql)
        
        conn.commit()
        print("Success! Tables created successfully.")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    create_tables()
