"""
FastAPI Application — Video Accessibility Compliance Auditor API
"""

import os
import uuid
import shutil
from typing import List, Optional
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .audit_engine import AuditEngine

app = FastAPI(
    title="Video Accessibility Compliance Auditor",
    description="Automated WCAG 2.2 video compliance checking API",
    version="0.1.0"
)

# In-memory job store (replace with Redis/DB in production)
jobs = {}
engine = AuditEngine()

UPLOAD_DIR = Path("./uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


class AuditRequest(BaseModel):
    checks: Optional[List[str]] = None
    webhook_url: Optional[str] = None


class AuditResponse(BaseModel):
    job_id: str
    status: str
    message: str


@app.get("/")
async def root():
    return {
        "service": "Video Accessibility Compliance Auditor",
        "version": "0.1.0",
        "wcag_version": "2.2",
        "available_checks": list(AuditEngine.AVAILABLE_CHECKS.keys())
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/api/v1/audit", response_model=AuditResponse)
async def create_audit(
    video: UploadFile = File(...),
    captions: Optional[UploadFile] = File(None),
    checks: Optional[str] = Form(None),
    webhook_url: Optional[str] = Form(None)
):
    """
    Submit a video for accessibility audit.
    
    - **video**: Video file to analyze
    - **captions**: Optional caption file (.srt or .vtt)
    - **checks**: Comma-separated list of checks (default: all)
    - **webhook_url**: Optional URL to notify when complete
    """
    job_id = str(uuid.uuid4())
    
    # Validate video
    allowed_video = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
    video_ext = Path(video.filename).suffix.lower()
    if video_ext not in allowed_video:
        raise HTTPException(400, f"Unsupported video format: {video_ext}")
    
    # Save video
    video_path = UPLOAD_DIR / f"{job_id}_video{video_ext}"
    with open(video_path, "wb") as f:
        shutil.copyfileobj(video.file, f)
    
    # Save captions if provided
    caption_path = None
    if captions:
        cap_ext = Path(captions.filename).suffix.lower()
        if cap_ext not in {'.srt', '.vtt'}:
            raise HTTPException(400, f"Unsupported caption format: {cap_ext}")
        caption_path = UPLOAD_DIR / f"{job_id}_captions{cap_ext}"
        with open(caption_path, "wb") as f:
            shutil.copyfileobj(captions.file, f)
    
    # Parse checks
    check_list = None
    if checks:
        check_list = [c.strip() for c in checks.split(",")]
        invalid = [c for c in check_list if c not in AuditEngine.AVAILABLE_CHECKS]
        if invalid:
            raise HTTPException(400, f"Invalid checks: {invalid}")
    
    # Run audit synchronously (for MVP — add Celery later for async)
    try:
        report = engine.audit(str(video_path), check_list, str(caption_path) if caption_path else None)
        
        jobs[job_id] = {
            "status": "completed",
            "progress": 100,
            "report": report.to_dict(),
            "webhook_url": webhook_url
        }
        
        return AuditResponse(
            job_id=job_id,
            status="completed",
            message="Audit completed successfully"
        )
        
    except Exception as e:
        jobs[job_id] = {
            "status": "failed",
            "progress": 0,
            "error": str(e)
        }
        raise HTTPException(500, f"Audit failed: {str(e)}")


@app.get("/api/v1/audit/{job_id}")
async def get_audit_status(job_id: str):
    """Get audit status and results."""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    
    job = jobs[job_id]
    return {
        "job_id": job_id,
        "status": job["status"],
        "progress": job.get("progress", 0),
        "results": job.get("report") if job["status"] == "completed" else None,
        "error": job.get("error")
    }


@app.get("/api/v1/audit/{job_id}/report")
async def get_audit_report(job_id: str):
    """Get full audit report."""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    
    job = jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(400, f"Audit not completed. Status: {job['status']}")
    
    return JSONResponse(content=job["report"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
