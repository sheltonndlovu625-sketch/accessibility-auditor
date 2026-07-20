# Video Accessibility Compliance Auditor

Automated WCAG 2.2 video compliance checking API.

## What It Checks

| WCAG Criterion | Level | Check |
|---|---|---|
| 1.2.2 Captions | A | Detect missing / out-of-sync captions |
| 2.3.1 Three Flashes | A | Detect seizure-risk flashing content |
| 1.2.5 Audio Description | AA | Detect missing audio description tracks |
| 1.4.3 Contrast | AA | Check text-overlay contrast ratios |
| 1.2.6 Sign Language | AAA | Detect sign language interpreter presence |

## Project Structure

```
.
├── src/
│   ├── flash_detector.py      # Seizure-risk flash detection
│   ├── caption_checker.py     # Caption compliance engine
│   ├── audit_engine.py        # Orchestrates all checks
│   └── api.py                 # FastAPI application
├── tests/
│   ├── test_flash_detector.py
│   └── test_caption_checker.py
├── .github/workflows/
│   └── ci.yml                 # GitHub Actions CI/CD
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Setup (No Terminal Needed)

All files are editable directly on GitHub web or mobile app.

### Step 1: Create Repo on GitHub
1. Go to github.com → New Repository
2. Name it `accessibility-auditor`
3. Check "Add a README file"
4. Create repository

### Step 2: Add All Files
For each file below, click "Add file" → "Create new file" and copy-paste the content.

### Step 3: Run CI
Push any change → GitHub Actions automatically runs tests.

## API Usage (Once Deployed)

```bash
POST /api/v1/audit
Content-Type: multipart/form-data

video: <file>
checks: ["captions", "flashing"]
```

Response:
```json
{
  "job_id": "uuid",
  "status": "completed",
  "results": {
    "1.2.2_captions": { "status": "FAIL", "score": 0.0 },
    "2.3.1_flashing": { "status": "PASS", "score": 1.0 }
  }
}
```

## License
MIT — ready for acquisition.
