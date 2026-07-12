# Final-Project: Intelliguard AI-Powered PPE Compliance Monitoring System 

## Overview
This project focuses on monitoring **Personal Protective Equipment (PPE)** compliance in manufacturing environments using Computer Vision and Artificial Intelligence. The system detects whether workers are wearing the required safety equipment such as helmets, gloves, safety vests, and masks while identifying safety violations in real time.

A **YOLOv8** object detection model is used to detect both PPE compliance and non-compliance from uploaded images. The detected violations are securely stored in **AWS RDS**, while **AWS S3** is used to store uploaded media files. An interactive **Streamlit** web application provides face-recognition-based login, real-time detection, violation monitoring, automated reporting, and an AI-powered chatbot for querying workplace safety data using natural language.

## Technologies Used
- **Python**: Core programming language for application development.
- **YOLOv8**: Real-time PPE object detection.
- **OpenCV**: Image and video processing.
- **Face Recognition**: Secure user authentication.
- **Streamlit**: Interactive web application development.
- **AWS RDS (MySQL)**: Stores PPE violation logs and metadata.
- **AWS S3**: Secure storage for uploaded images and videos.
- **SQLAlchemy & PyMySQL**: Database connectivity and operations.
- **Pandas & NumPy**: Data processing and analysis.
- **LangChain**: AI-powered chatbot with SQL Agent.
- **SMTP**: Automated email notifications.
- **Matplotlib**: Visualization of detection results.

## Steps Involved

### 1. Dataset Preparation
- Collected a PPE object detection dataset containing workers with and without safety equipment.
- Verified image quality and annotation files.
- Organized the dataset into training, validation, and testing sets.
- Ensured all annotations followed the YOLO format.

### 2. Data Preprocessing
- Resized images to the required YOLO input size.
- Cleaned and verified annotation labels.
- Applied image augmentation techniques such as flipping, scaling, and rotation.
- Prepared the dataset for efficient model training.

### 3. YOLO Model Development
- Trained a YOLOv8 object detection model on the PPE dataset.
- Learned to detect multiple PPE categories simultaneously.
- Identified both compliant workers and safety violations.
- Saved the trained model for deployment.

### 4. Model Evaluation
- Evaluated the model using Precision, Recall, and Mean Average Precision (mAP).
- Tested the model on unseen images and videos.
- Verified the detection accuracy for PPE compliance and violations.

### 5. Streamlit Application Development
- Built a secure Streamlit web application.
- Implemented face-recognition-based login authentication.
- Allowed users to upload images for PPE detection.
- Displayed detection results with bounding boxes and confidence scores.
- Stored uploaded files in AWS S3.
- Logged detected violations into AWS RDS.
- Generated downloadable CSV reports.
- Sent automated email alerts for detected violations.
- Integrated a LangChain SQL chatbot to answer workplace safety queries.
