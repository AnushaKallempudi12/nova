import os
import re
from datetime import date, datetime
from typing import Optional
import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import String, Integer, Date, Text, JSON, func
from sqlalchemy.orm import Mapped, mapped_column
from .main import Base, SessionLocal

router=APIRouter(prefix="/api/v2",tags=["account workspace"])

class UserProfile(Base):
    __tablename__="user_profiles"
    user_id:Mapped[str]=mapped_column(String(128),primary_key=True)
    email:Mapped[Optional[str]]=mapped_column(String(320),nullable=True)
    data:Mapped[dict]=mapped_column(JSON,default=dict)
    updated_at:Mapped[datetime]=mapped_column(server_default=func.now(),onupdate=func.now())

class UserResume(Base):
    __tablename__="user_resumes"
    user_id:Mapped[str]=mapped_column(String(128),primary_key=True)
    file_name:Mapped[str]=mapped_column(String(255))
    extracted_text:Mapped[str]=mapped_column(Text)
    skills:Mapped[list]=mapped_column(JSON,default=list)
    updated_at:Mapped[datetime]=mapped_column(server_default=func.now(),onupdate=func.now())

class UserApplication(Base):
    __tablename__="user_applications"
    id:Mapped[int]=mapped_column(Integer,primary_key=True,index=True)
    user_id:Mapped[str]=mapped_column(String(128),index=True)
    company:Mapped[str]=mapped_column(String(200))
    role:Mapped[str]=mapped_column(String(300))
    status:Mapped[str]=mapped_column(String(30),default="Pending")
    platform:Mapped[str]=mapped_column(String(100),default="Manual")
    job_url:Mapped[Optional[str]]=mapped_column(String(2000),nullable=True)
    applied_date:Mapped[Optional[date]]=mapped_column(Date,nullable=True)
    follow_up_date:Mapped[Optional[date]]=mapped_column(Date,nullable=True)
    interview_date:Mapped[Optional[date]]=mapped_column(Date,nullable=True)
    notes:Mapped[str]=mapped_column(Text,default="")
    created_at:Mapped[datetime]=mapped_column(server_default=func.now())

class SavedCoverLetter(Base):
    __tablename__="saved_cover_letters"
    id:Mapped[int]=mapped_column(Integer,primary_key=True,index=True)
    user_id:Mapped[str]=mapped_column(String(128),index=True)
    title:Mapped[str]=mapped_column(String(300))
    company:Mapped[str]=mapped_column(String(200),default="")
    role:Mapped[str]=mapped_column(String(300),default="")
    content:Mapped[str]=mapped_column(Text)
    created_at:Mapped[datetime]=mapped_column(server_default=func.now())

async def current_user(authorization:Optional[str]=Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401,detail="Please sign in to continue.")
    base=os.getenv("SUPABASE_URL","").rstrip("/")
    key=os.getenv("SUPABASE_ANON_KEY","")
    if not base or not key:
        raise HTTPException(status_code=503,detail="Authentication is not configured. Set SUPABASE_URL and SUPABASE_ANON_KEY.")
    token=authorization.split(" ",1)[1].strip()
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response=await client.get(f"{base}/auth/v1/user",headers={"apikey":key,"Authorization":f"Bearer {token}"})
        if response.status_code!=200:
            raise HTTPException(status_code=401,detail="Your session expired. Please sign in again.")
        user=response.json()
        if not user.get("id"): raise HTTPException(status_code=401,detail="Invalid account session.")
        return {"id":user["id"],"email":user.get("email",""),"metadata":user.get("user_metadata",{})}
    except httpx.HTTPError:
        raise HTTPException(status_code=503,detail="Could not validate your account session.")

class ProfileInput(BaseModel):
    data:dict=Field(default_factory=dict)
class ResumeInput(BaseModel):
    file_name:str=Field(min_length=1,max_length=255)
    extracted_text:str=Field(min_length=40,max_length=30000)
    skills:list[str]=Field(default_factory=list,max_length=100)
class ApplicationInput(BaseModel):
    company:str=Field(min_length=1,max_length=200)
    role:str=Field(min_length=1,max_length=300)
    status:str=Field(default="Pending",max_length=30)
    platform:str=Field(default="Manual",max_length=100)
    job_url:Optional[str]=Field(default=None,max_length=2000)
    applied_date:Optional[date]=None
    follow_up_date:Optional[date]=None
    interview_date:Optional[date]=None
    notes:str=Field(default="",max_length=5000)
class CoverLetterInput(BaseModel):
    company:str=Field(default="",max_length=200)
    role:str=Field(min_length=1,max_length=300)
    job_description:str=Field(min_length=80,max_length=12000)
class CoverLetterEdit(BaseModel):
    content:str=Field(min_length=20,max_length=20000)

def app_json(r):
    return {"id":r.id,"company":r.company,"role":r.role,"status":r.status,"platform":r.platform,"job_url":r.job_url,
      "applied_date":r.applied_date.isoformat() if r.applied_date else None,
      "follow_up_date":r.follow_up_date.isoformat() if r.follow_up_date else None,
      "interview_date":r.interview_date.isoformat() if r.interview_date else None,"notes":r.notes,
      "created_at":r.created_at.isoformat() if r.created_at else None}

@router.get("/me")
def get_me(user=Depends(current_user)):
    with SessionLocal() as db:
        p=db.get(UserProfile,user["id"]);r=db.get(UserResume,user["id"])
        return {"user":{"id":user["id"],"email":user["email"]},"profile":p.data if p else {},
          "resume":{"file_name":r.file_name,"extracted_text":r.extracted_text,"skills":r.skills} if r else None}

@router.put("/profile")
def save_profile(payload:ProfileInput,user=Depends(current_user)):
    with SessionLocal() as db:
        p=db.get(UserProfile,user["id"])
        if p is None: p=UserProfile(user_id=user["id"],email=user["email"],data=payload.data);db.add(p)
        else: p.email=user["email"];p.data=payload.data
        db.commit()
        return {"saved":True,"profile":p.data}

@router.put("/resume")
def save_resume(payload:ResumeInput,user=Depends(current_user)):
    with SessionLocal() as db:
        r=db.get(UserResume,user["id"])
        if r is None: r=UserResume(user_id=user["id"],**payload.model_dump());db.add(r)
        else: r.file_name=payload.file_name;r.extracted_text=payload.extracted_text;r.skills=payload.skills
        db.commit()
        return {"saved":True,"file_name":r.file_name,"skills":r.skills,"extracted_text":r.extracted_text}

@router.get("/applications")
def list_apps(user=Depends(current_user)):
    with SessionLocal() as db:
        rows=db.query(UserApplication).filter_by(user_id=user["id"]).order_by(UserApplication.created_at.desc()).all()
        return {"applications":[app_json(r) for r in rows]}

@router.post("/applications")
def create_app(payload:ApplicationInput,user=Depends(current_user)):
    if payload.status not in {"Saved","Applied","Pending","Responded","Interview","Rejected","Offer","Withdrawn"}:
        raise HTTPException(status_code=422,detail="Unsupported application status.")
    with SessionLocal() as db:
        r=UserApplication(user_id=user["id"],**payload.model_dump());db.add(r);db.commit();db.refresh(r)
        return app_json(r)

@router.put("/applications/{app_id}")
def update_app(app_id:int,payload:ApplicationInput,user=Depends(current_user)):
    if payload.status not in {"Saved","Applied","Pending","Responded","Interview","Rejected","Offer","Withdrawn"}:
        raise HTTPException(status_code=422,detail="Unsupported application status.")
    with SessionLocal() as db:
        r=db.query(UserApplication).filter_by(id=app_id,user_id=user["id"]).first()
        if not r: raise HTTPException(status_code=404,detail="Application not found.")
        for k,v in payload.model_dump().items(): setattr(r,k,v)
        db.commit();db.refresh(r)
        return app_json(r)

@router.delete("/applications/{app_id}")
def delete_app(app_id:int,user=Depends(current_user)):
    with SessionLocal() as db:
        r=db.query(UserApplication).filter_by(id=app_id,user_id=user["id"]).first()
        if not r: raise HTTPException(status_code=404,detail="Application not found.")
        db.delete(r);db.commit()
        return {"deleted":True}

def _resume_experience_evidence(resume_text: str, job_terms: list[str]) -> list[str]:
    """Select real experience bullets from the user's resume; never invent outcomes."""
    lines=[re.sub(r"^\\s*[•●▪*-]+\\s*","",line).strip() for line in resume_text.splitlines()]
    start_idx=None
    end_markers=re.compile(r"^(education|academic background|technical skills|skills|projects|certifications|summary|professional summary)\\b",re.I)
    for i,line in enumerate(lines):
        if re.match(r"^(professional experience|work experience|experience|employment history|work history)\\b",line,re.I):
            start_idx=i+1
            break
    if start_idx is None:
        return []
    section=[]
    for line in lines[start_idx:]:
        if end_markers.match(line):
            break
        if 45 <= len(line) <= 260 and not re.match(r"^(20\\d{2}|19\\d{2})\\s*[-–—]",line):
            section.append(line)
    action=re.compile(r"\\b(develop|built|designed|implemented|automated|tested|maintained|created|improved|optimized|integrated|deployed|supported|analyzed|delivered|led|collaborated|resolved|reduced|increased)\\b",re.I)
    candidates=[line for line in section if action.search(line)]
    if job_terms:
        matching=[line for line in candidates if any(term in line.lower() for term in job_terms)]
        if matching:
            candidates=matching
    # Keep concise, source-grounded evidence and avoid duplicate bullets.
    unique=[]
    for line in candidates:
        normalized=line.lower()
        if normalized not in {x.lower() for x in unique}:
            unique.append(line)
        if len(unique)==3:
            break
    return unique


@router.post("/cover-letters/generate")
def generate_letter(payload:CoverLetterInput,user=Depends(current_user)):
    with SessionLocal() as db:
        resume=db.get(UserResume,user["id"])
        profile=db.get(UserProfile,user["id"])
        if not resume:
            raise HTTPException(status_code=400,detail="Upload and save your resume before creating a cover letter.")
        p=profile.data if profile else {}
        name=" ".join(str(x).strip() for x in [p.get("first_name",""),p.get("last_name","")] if str(x).strip())
        name=name or str(p.get("full_name") or user.get("metadata",{}).get("full_name") or "").strip() or "Your Name"
        contact=[p.get("email") or user.get("email",""),p.get("phone",""),p.get("linkedin_url",""),p.get("portfolio_url","")]
        contact_line=" | ".join(x.strip() for x in contact if isinstance(x,str) and x.strip())
        location=str(p.get("location") or "").strip()
        resume_text=resume.extracted_text or ""
        resume_skills=resume.skills or []
        jd_text=re.sub(r"\\s+"," ",payload.job_description).strip()
        jd_lower=jd_text.lower()
        matching=[skill for skill in resume_skills if skill.lower() in jd_lower]
        job_terms=[term.lower() for term in matching]
        evidence=_resume_experience_evidence(resume_text,job_terms)
        summary=re.sub(r"\\s+"," ",str(p.get("experience_summary",""))).strip()
        relevant=matching[:5]
        role=payload.role.strip()
        company=payload.company.strip()
        salutation=f"Dear Hiring Manager at {company}," if company else "Dear Hiring Manager,"
        paragraphs=[
            f"I’m writing to apply for the {role} position"+(f" at {company}." if company else ".")
        ]
        if summary:
            paragraphs.append(summary.rstrip(".")+"." )
        elif relevant:
            paragraphs.append("My background includes hands-on work with "+", ".join(relevant)+", which aligns with several of the technical requirements in your posting.")
        else:
            paragraphs.append("My experience and technical background are outlined in the resume included with my application.")
        if evidence:
            paragraphs.append("A few examples from my experience are:")
            paragraphs.extend("• "+item for item in evidence[:3])
        elif summary:
            paragraphs.append("I would welcome the opportunity to discuss how this experience could support the team’s current priorities.")
        else:
            paragraphs.append("I have kept this draft limited to the information available in your saved profile and resume. Add a short experience summary to your Career Profile to make the letter more specific; Nova will not invent projects, responsibilities or results.")
        if relevant:
            paragraphs.append("I was especially interested in the role’s focus on "+", ".join(relevant[:4])+". I would be glad to explain how I have applied these skills and how I could contribute to the team.")
        else:
            paragraphs.append("After reviewing the responsibilities in the posting, I would welcome a conversation about the experience and approach I could bring to the role.")
        paragraphs.append("Thank you for your time and consideration. I look forward to the opportunity to discuss my application.")
        header=[name]
        if location: header.append(location)
        if contact_line: header.append(contact_line)
        content="\\n".join(header)+"\\n\\n"+salutation+"\\n\\n"+"\\n\\n".join(paragraphs)+"\\n\\nSincerely,\\n"+name
        row=SavedCoverLetter(user_id=user["id"],title=f"{role} — {company or 'Cover Letter'}",
                             company=company,role=role,content=content)
        db.add(row);db.commit();db.refresh(row)
        return {"id":row.id,"title":row.title,"content":row.content,
                "notice":"Draft tailored from the job description and evidence found in your saved resume/profile. Review all details before sending."}

@router.get("/cover-letters")
def list_letters(user=Depends(current_user)):
    with SessionLocal() as db:
        rows=db.query(SavedCoverLetter).filter_by(user_id=user["id"]).order_by(SavedCoverLetter.created_at.desc()).all()
        return {"cover_letters":[{"id":r.id,"title":r.title,"company":r.company,"role":r.role,"content":r.content} for r in rows]}

@router.put("/cover-letters/{letter_id}")
def update_letter(letter_id:int,payload:CoverLetterEdit,user=Depends(current_user)):
    with SessionLocal() as db:
        row=db.query(SavedCoverLetter).filter_by(id=letter_id,user_id=user["id"]).first()
        if not row: raise HTTPException(status_code=404,detail="Cover letter not found.")
        row.content=payload.content;db.commit();db.refresh(row)
        return {"saved":True,"id":row.id,"content":row.content}
