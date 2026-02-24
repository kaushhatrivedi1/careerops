# CareerOps Frontend (Zero-Dependency MVP)

This UI is a single static page used to test scoring and recommendations.
It now accepts:
- resume file upload (`.pdf`, `.docx`, `.txt`)
- job URL input

## Run
From `/Users/kaushha/Documents/careerops-1/frontend`:

```bash
python3 -m http.server 3000
```

Open:
- `http://localhost:3000`
- `http://localhost:3000/history.html` (request history page)

## Backend expectation
The page calls:
- `POST /api/v1/matches/compute-from-file-url`

Default API base URL is:
- `http://localhost:8000`

You can change API base URL from the top input field in the UI.
