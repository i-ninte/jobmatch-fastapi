from fastapi import FastAPI, HTTPException, Depends, File, UploadFile, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import JWTError, jwt
from typing import Optional
from datetime import datetime, timedelta
from docx import Document  
import os
import PyPDF2 as pdf
import google.generativeai as genai
from dotenv import load_dotenv
import json
import re

# Load environment variables
load_dotenv()

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "fallback_secret_key_if_not_set")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# FastAPI app
app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Welcome to the Resume Matcher API!"}

# In-memory "database"
users_db = {}

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Configure the Generative AI API
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Models
class User(BaseModel):
    username: str
    full_name: str
    email: EmailStr
    hashed_password: str

class UserInDB(User):
    hashed_password: str

class UserCreate(BaseModel):
    username: str
    full_name: str
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

# Helper functions for authentication
def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)

# Function to get the response from Gemini API
def get_gemini_response(input_text):
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(input_text)
        return response.text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching response from Gemini API: {e}")

# Function to extract text from uploaded PDF
def input_pdf_text(file):
    try:
        reader = pdf.PdfReader(file)
        text = ""
        for page_num in range(len(reader.pages)):
            page = reader.pages[page_num]
            text += page.extract_text() or ""
        return text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading PDF file: {e}")

# Function to extract text from DOC/DOCX files
def input_doc_text(file):
    try:
        doc = Document(file)
        text = "\n".join([para.text for para in doc.paragraphs])
        return text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading DOC/DOCX file: {e}")

# Function to clean and parse AI response
def clean_and_parse_response(response):
    cleaned_response = re.sub(r'```json|```', '', response).strip()
    try:
        return json.loads(cleaned_response)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Failed to parse AI response.")

# User Registration Route
@app.post("/register", response_model=Token)
def register(user: UserCreate):
    if user.username in users_db:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = get_password_hash(user.password)
    user_in_db = UserInDB(
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        hashed_password=hashed_password
    )
    users_db[user.username] = user_in_db.dict()

    # Create token
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# Login Route
@app.post("/token", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user(users_db, form_data.username)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid username or password")
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid username or password")
    
    # Create token
    access_token = create_access_token(data={"sub": form_data.username})
    return {"access_token": access_token, "token_type": "bearer"}

# PDF, TXT, DOC/DOCX Upload and Processing Route
@app.post("/upload_resume/")
async def upload_resume(
    resume_file: UploadFile = File(None),  
    resume_text: Optional[str] = Form(None),  # Optional form input for pasted resume text
    token: str = Depends(oauth2_scheme)
):
    try:
        # Check if resume is provided as a file
        if resume_file:
            if resume_file.content_type == "application/pdf":
                # Extract text from PDF resume
                resume_text = input_pdf_text(resume_file.file)
            elif resume_file.content_type == "text/plain":
                # Read text from .txt file
                resume_text = await resume_file.read()
                resume_text = resume_text.decode("utf-8")
            elif resume_file.content_type in [
                "application/msword",  # .doc
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"  # .docx
            ]:
                # Extract text from DOC or DOCX resume
                resume_text = input_doc_text(resume_file.file)
            else:
                raise HTTPException(status_code=400, detail="Unsupported file type. Please upload a .pdf, .txt, or .doc/.docx file.")
        
        # Check if resume text is provided
        if not resume_text:
            raise HTTPException(status_code=400, detail="Resume is required either as text or a file.")
        
        return {"resume_text": resume_text}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {e}")

# Resume and Job Description Matching Route
@app.post("/match_resume/")
async def match_resume(
    resume_text: str = Form(...), 
    job_description: str = Form(...), 
    token: str = Depends(oauth2_scheme)
):
    input_prompt = f"""
    Act as a skilled ATS (Applicant Tracking System) with deep understanding of tech fields, software engineering,
    data science, data analysis, AI/ML, and big data engineering.
    Evaluate the resume based on the given job description. Consider the job market very competitive and provide
    the best assistance for improving the resume.
    Assign the percentage Matching based on the job description and identify missing keywords with high accuracy.
    Also suggest only one best fit alternative job type the candidate might be suitable for.

    Resume: {resume_text}
    Job Description: {job_description}

    Respond with a JSON string structured as follows:
    {{
        "JD Match": "%",
        "MissingKeywords": [],
        "ProfileSummary": "",
        "Advice": [],
        "AlternativeJob": ""
    }}
    """
    
    # Get AI response
    response = get_gemini_response(input_prompt)
    
    # Clean and parse the response
    result = clean_and_parse_response(response)
    
    return result
