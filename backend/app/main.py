import os
import re
from pathlib import Path
from datetime import date, datetime
from typing import Optional
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import create_engine, String, Integer, Date, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .providers import GREENHOUSE_BOARDS, LEVER_SITES, ASHBY_BOARDS, search_public_company_boards, _is_us_location
from .career_discovery import COMPANY_CAREER_SITES, configured_smartrecruiters_companies
from .verification import verify_job_listing

app=FastAPI(title="Nova Career Intelligence API",version="0.6.0")
DATABASE_URL=os.getenv("DATABASE_URL","sqlite:///./nova.db")
if DATABASE_URL.startswith("postgres://"): DATABASE_URL=DATABASE_URL.replace("postgres://","postgresql+psycopg://",1)
elif DATABASE_URL.startswith("postgresql://") and "+psycopg" not in DATABASE_URL: DATABASE_URL=DATABASE_URL.replace("postgresql://","postgresql+psycopg://",1)
engine=create_engine(DATABASE_URL,connect_args={"check_same_thread":False} if DATABASE_URL.startswith("sqlite") else {},pool_pre_ping=True)
SessionLocal=sessionmaker(bind=engine,autoflush=False,autocommit=False)
class Base(DeclarativeBase): pass
class Application(Base):
    __tablename__="applications"
    id:Mapped[int]=mapped_column(Integer,primary_key=True,index=True)
    workspace_id:Mapped[str]=mapped_column(String(80),index=True)
    company:Mapped[str]=mapped_column(String(200))
    role:Mapped[str]=mapped_column(String(300))
    status:Mapped[str]=mapped_column(String(30),default="Applied")
    platform:Mapped[str]=mapped_column(String(100),default="Manual")
    job_url:Mapped[Optional[str]]=mapped_column(String(2000),nullable=True)
    applied_date:Mapped[Optional[date]]=mapped_column(Date,nullable=True)
    follow_up_date:Mapped[Optional[date]]=mapped_column(Date,nullable=True)
    interview_date:Mapped[Optional[date]]=mapped_column(Date,nullable=True)
    notes:Mapped[str]=mapped_column(Text,default="")
    created_at:Mapped[datetime]=mapped_column(server_default=func.now())
Base.metadata.create_all(bind=engine)
STATUSES={"Saved","In Progress","Ready for Review","Awaiting Submission","Submitted","Applied","Pending","Responded","Interview","Rejected","Offer","Withdrawn"}
class ApplicationInput(BaseModel):
    company:str=Field(min_length=1,max_length=200)
    role:str=Field(min_length=1,max_length=300)
    status:str=Field(default="Applied",max_length=30)
    platform:str=Field(default="Manual",max_length=100)
    job_url:Optional[str]=Field(default=None,max_length=2000)
    applied_date:Optional[date]=None
    follow_up_date:Optional[date]=None
    interview_date:Optional[date]=None
    notes:str=Field(default="",max_length=5000)
    @field_validator("status")
    @classmethod
    def valid_status(cls,v):
        if v not in STATUSES: raise ValueError("Unsupported application status.")
        return v
class JobSearchRequest(BaseModel):
    query:str=Field(default="",max_length=300)
    location:str=Field(default="United States",max_length=120)
    limit:int=Field(default=50,ge=1,le=100)
    selected_platforms:list[str]=Field(default_factory=lambda:["greenhouse","lever","ashby","smartrecruiters","career"],max_length=20)
    skills:list[str]=Field(default_factory=list,max_length=100)
    company:str=Field(default="",max_length=200)
    @field_validator("location")
    @classmethod
    def normalize_location(cls,v):
        cleaned=v.strip()
        if cleaned.lower() in {"united states","usa","us"}: return "United States"
        if not cleaned: raise ValueError("Enter a country or location, such as United States, India, or Dallas, TX.")
        return cleaned
class JobVerificationRequest(BaseModel):
    job_id:str=Field(min_length=1,max_length=300)
    url:str=Field(min_length=8,max_length=2000)
    title:str=Field(min_length=1,max_length=300)
    company:str=Field(min_length=1,max_length=200)
def valid_workspace(v):
    if not v or not 20<=len(v)<=80: raise HTTPException(status_code=400,detail="A valid workspace ID is required.")
    return v
def serialize(row):
    return {"id":row.id,"company":row.company,"role":row.role,"status":row.status,"platform":row.platform,"job_url":row.job_url,
    "applied_date":row.applied_date.isoformat() if row.applied_date else None,
    "follow_up_date":row.follow_up_date.isoformat() if row.follow_up_date else None,
    "interview_date":row.interview_date.isoformat() if row.interview_date else None,"notes":row.notes,
    "created_at":row.created_at.isoformat() if row.created_at else None}
origins=[v.strip() for v in os.getenv("NOVA_ALLOWED_ORIGINS","http://localhost:5173").split(",") if v.strip()]
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=True,allow_methods=["GET","POST","PUT","DELETE"],allow_headers=["*"])
PLATFORMS=[
{"id":"linkedin","name":"LinkedIn","search":"Official external search","application":"Manual"},
{"id":"indeed","name":"Indeed","search":"Official external search","application":"Manual"},
{"id":"dice","name":"Dice","search":"Official external search","application":"Manual"},
{"id":"wellfound","name":"Wellfound","search":"Official external search","application":"Manual"},
{"id":"builtin","name":"Built In","search":"Official external search","application":"Manual"},
{"id":"ziprecruiter","name":"ZipRecruiter","search":"Official external search","application":"Manual"},
{"id":"glassdoor","name":"Glassdoor","search":"Official external search","application":"Manual"},
{"id":"monster","name":"Monster","search":"Official external search","application":"Manual"},
{"id":"handshake","name":"Handshake","search":"Official external search","application":"Manual"},
{"id":"usajobs","name":"USAJOBS","search":"Official external search","application":"Manual"},
{"id":"flexjobs","name":"FlexJobs","search":"Official external search","application":"Manual"},
{"id":"weworkremotely","name":"We Work Remotely","search":"Official external search","application":"Manual"},
{"id":"naukri","name":"Naukri","search":"Official external search","application":"Manual"},
{"id":"foundit","name":"Foundit","search":"Official external search","application":"Manual"},
{"id":"instahyre","name":"Instahyre","search":"Official external search","application":"Manual"},
{"id":"cutshort","name":"Cutshort","search":"Official external search","application":"Manual"},
{"id":"hirist","name":"Hirist","search":"Official external search","application":"Manual"},
{"id":"iimjobs","name":"IIMJobs","search":"Official external search","application":"Manual"},
{"id":"shine","name":"Shine","search":"Official external search","application":"Manual"},
{"id":"timesjobs","name":"TimesJobs","search":"Official external search","application":"Manual"},
{"id":"freshersworld","name":"Freshersworld","search":"Official external search","application":"Manual"},
{"id":"apna","name":"Apna","search":"Official external search","application":"Manual"},
{"id":"greenhouse","name":"Greenhouse career pages","search":"Public boards when configured","application":"Employer website"},
{"id":"lever","name":"Lever career pages","search":"Public boards when configured","application":"Employer website"},
{"id":"ashby","name":"Ashby career pages","search":"Public boards when configured","application":"Employer website"},
{"id":"smartrecruiters","name":"SmartRecruiters career pages","search":"Public company postings when configured","application":"Employer website"},
{"id":"career","name":"All company career websites","search":"Public career pages and structured job listings","application":"Employer website"}]
FRONTEND_DIST=Path(__file__).resolve().parents[2]/"frontend"/"dist"
@app.get("/")
def root():
    if FRONTEND_DIST.joinpath("index.html").is_file(): return FileResponse(FRONTEND_DIST/"index.html")
    return {"name":"Nova Career Intelligence","status":"api-ready","version":"0.6.0"}
@app.get("/health")
def health():
    try:
        with engine.connect() as c: c.exec_driver_sql("SELECT 1")
        return {"status":"ok","database":"connected"}
    except Exception: raise HTTPException(status_code=503,detail="Database health check failed.")
@app.get("/api/v1/platforms")
def get_platforms(): return {"platforms":PLATFORMS,"configured_public_boards":len(GREENHOUSE_BOARDS)+len(LEVER_SITES)+len(ASHBY_BOARDS)+len(configured_smartrecruiters_companies()),"configured_career_sites":len(COMPANY_CAREER_SITES)}
@app.get("/api/v1/config")
def get_config():
    n=len(GREENHOUSE_BOARDS)+len(LEVER_SITES)+len(ASHBY_BOARDS)+len(configured_smartrecruiters_companies())
    return {"resume_upload_enabled":True,"resume_parsing_enabled":True,"application_tracking_enabled":True,"application_storage":"database",
    "live_job_search_enabled":True,"job_verification_enabled":True,"guided_application_enabled":True,
    "application_preparation_enabled":False,"application_submission_enabled":False,"provider_integrations_configured":n>0,"configured_public_boards":n,
    "configured_career_sites":len(COMPANY_CAREER_SITES),
    "company_site_search_api_configured":bool(os.getenv("TAVILY_API_KEY")),"tavily_fallback_configured":bool(os.getenv("TAVILY_API_KEY")),
    "message":"Nova searches selected public ATS feeds and registered employer career pages first. Tavily is used only as a fallback when direct results are limited; application submission remains user-controlled."}
@app.get("/api/v1/applications")
def list_applications(workspace_id:str):
    with SessionLocal() as db:
        rows=db.query(Application).filter(Application.workspace_id==valid_workspace(workspace_id)).order_by(Application.applied_date.desc(),Application.id.desc()).all()
        return {"applications":[serialize(r) for r in rows]}
@app.post("/api/v1/applications")
def create_application(payload:ApplicationInput,workspace_id:str):
    with SessionLocal() as db:
        row=Application(workspace_id=valid_workspace(workspace_id),**payload.model_dump());db.add(row);db.commit();db.refresh(row);return serialize(row)
@app.put("/api/v1/applications/{application_id}")
def update_application(application_id:int,payload:ApplicationInput,workspace_id:str):
    with SessionLocal() as db:
        row=db.query(Application).filter(Application.id==application_id,Application.workspace_id==valid_workspace(workspace_id)).first()
        if not row: raise HTTPException(status_code=404,detail="Application not found.")
        for k,v in payload.model_dump().items(): setattr(row,k,v)
        db.commit();db.refresh(row);return serialize(row)
@app.delete("/api/v1/applications/{application_id}")
def delete_application(application_id:int,workspace_id:str):
    with SessionLocal() as db:
        row=db.query(Application).filter(Application.id==application_id,Application.workspace_id==valid_workspace(workspace_id)).first()
        if not row: raise HTTPException(status_code=404,detail="Application not found.")
        db.delete(row);db.commit();return {"deleted":True}
@app.get("/api/v1/analytics")
def analytics(workspace_id:str):
    with SessionLocal() as db:
        rows=db.query(Application).filter(Application.workspace_id==valid_workspace(workspace_id)).all()
        counts={s:sum(1 for r in rows if r.status==s) for s in sorted(STATUSES)}
        return {"total":len(rows),"counts":counts,"response_rate":round((counts.get("Responded",0)+counts.get("Interview",0)+counts.get("Offer",0))/len(rows)*100) if rows else 0}
@app.post("/api/v1/resumes/parse")
async def parse_resume(file:UploadFile=File(...)):
    filename=file.filename or "resume";suffix=Path(filename).suffix.lower()
    if suffix not in {".pdf",".docx",".doc"}: raise HTTPException(status_code=415,detail="Upload a PDF, DOCX or DOC file.")
    content=await file.read(10*1024*1024+1)
    if len(content)>10*1024*1024: raise HTTPException(status_code=413,detail="Resume must be smaller than 10 MB.")
    try:
        import io
        if suffix==".pdf":
            from pypdf import PdfReader
            text="\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(content)).pages)
        elif suffix==".docx":
            from docx import Document
            doc=Document(io.BytesIO(content));text="\n".join(p.text for p in doc.paragraphs)
            for table in doc.tables:
                for row in table.rows: text+="\n"+" | ".join(cell.text for cell in row.cells)
        else: raise HTTPException(status_code=415,detail="Legacy DOC files are not supported yet. Save as DOCX or PDF.")
    except HTTPException: raise
    except Exception as exc: raise HTTPException(status_code=422,detail="Could not read this document. Try a text-based PDF or DOCX. "+str(exc)[:100])
    clean=re.sub(r"[ \t]+"," ",text);clean=re.sub(r"\n{3,}","\n\n",clean).strip()
    if len(clean)<40: raise HTTPException(status_code=422,detail="Very little text was extracted. Scanned-image OCR is not enabled yet.")
    skills_catalog=["Java","Python","JavaScript","TypeScript","SQL","Spring Boot","React","FastAPI","REST API","REST Assured","Selenium","Cucumber","TestNG","Maven","Docker","Kubernetes","AWS","Azure","Git","GitHub","Jenkins","CI/CD","PostgreSQL","MySQL","MongoDB","Power BI","Tableau","Machine Learning","Deep Learning","Pandas","NumPy","PyTorch","TensorFlow","Jira","Dynatrace","Agile","HTML","CSS"]
    lower=clean.lower();skills=[s for s in skills_catalog if re.search(r"(?<![a-z0-9])"+re.escape(s.lower())+r"(?![a-z0-9])",lower)]
    email=re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",clean,re.I)
    phone=re.search(r"(?<!\w)(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}(?!\w)",clean)
    references=[]
    for label,patterns in [("Professional experience",[r"\bexperience\b",r"\bemployment\b",r"\bwork history\b"]),("Education",[r"\beducation\b",r"\buniversity\b",r"\bcollege\b"]),("Projects",[r"\bprojects?\b",r"\bportfolio\b"]),("Certifications",[r"\bcertifications?\b",r"\blicenses?\b"]),("Technical skills",[r"\bskills\b",r"\btechnologies\b"])]:
        if any(re.search(p,lower) for p in patterns): references.append(label)
    def capture(pattern):
        match=re.search(pattern,clean,re.I|re.M)
        return match.group(1).strip(" \t|,;") if match else ""
    lines=[line.strip() for line in clean.splitlines() if line.strip()]
    linkedin_match=re.search(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[A-Za-z0-9_%./-]+",clean,re.I)
    github_match=re.search(r"(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9_-]+",clean,re.I)
    name=""
    for line in lines[:8]:
        candidate=re.sub(r"[^A-Za-z .'-]","",line).strip()
        if 2<=len(candidate.split())<=4 and not re.search(r"resume|curriculum|engineer|developer|linkedin|github",candidate,re.I):
            name=candidate;break
    name_parts=name.split()
    education_section=re.search(r"(?is)(?:education|academic background)(.*?)(?:\n\s*(?:experience|work history|skills|projects|certifications)\b|$)",clean)
    education_text=education_section.group(1).strip() if education_section else ""
    institution=""
    if education_text:
        for line in education_text.splitlines():
            if re.search(r"university|college|institute|school",line,re.I):
                institution=line.strip(" |,");break
    degree_match=re.search(r"(?i)\b(Bachelor(?:'s)?|Master(?:'s)?|B\.S\.|M\.S\.|B\.Tech|M\.Tech|Associate|Ph\.D\.)[^\n|]*",education_text or clean)
    year_match=re.search(r"(?i)(?:20\d{2}|19\d{2})(?:\s*[-–—]\s*(?:20\d{2}|present))?",education_text or clean)
    parsed_profile={
      "first_name":name_parts[0] if name_parts else "",
      "last_name":" ".join(name_parts[1:]) if len(name_parts)>1 else "",
      "email":email.group(0) if email else "",
      "phone":phone.group(0) if phone else "",
      "linkedin_url":("https://" if linkedin_match and not linkedin_match.group(0).lower().startswith("http") else "")+linkedin_match.group(0) if linkedin_match else "",
      "github_url":("https://" if github_match and not github_match.group(0).lower().startswith("http") else "")+github_match.group(0) if github_match else "",
      "institution_name":institution,
      "degree":degree_match.group(0).strip() if degree_match else "",
      "graduation_year":year_match.group(0) if year_match else "",
      "technical_skills":", ".join(skills),
      "experience_summary":""
    }
    return {"file_name":filename,"word_count":len(clean.split()),"skills":skills,"email":email.group(0) if email else None,
    "phone":phone.group(0) if phone else None,"references":references,"profile":parsed_profile,"extracted_text":clean[:30000],
    "message":"Resume text extracted. Contact, education and profile fields are best-effort suggestions; review and correct them before use."}
@app.post("/api/v1/search")
async def search_jobs(request:JobSearchRequest):
    return await search_public_company_boards(query=request.query,location=request.location,limit=request.limit,selected_platforms=request.selected_platforms,user_skills=request.skills,company=request.company)
@app.post("/api/v1/verify-job")
async def verify_job(request:JobVerificationRequest):
    return await verify_job_listing(job_id=request.job_id,submitted_url=request.url,submitted_title=request.title,submitted_company=request.company)
if FRONTEND_DIST.exists():
    app.mount("/assets",StaticFiles(directory=str(FRONTEND_DIST/"assets")),name="frontend-assets")
    @app.get("/{full_path:path}")
    def frontend_fallback(full_path:str):
        candidate=FRONTEND_DIST/full_path
        if candidate.is_file() and FRONTEND_DIST in candidate.resolve().parents: return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST/"index.html")


from .auth_api import router as account_router
app.include_router(account_router)
Base.metadata.create_all(bind=engine)
