# CareerOps Frontend (Zero-Dependency MVP)

This UI is a single static page used to test scoring and recommendations.

## Run
From `/Users/kaushha/Documents/careerops-1/frontend`:

```bash
python3 -m http.server 3000
```

Open:
- `http://localhost:3000`

## Backend expectation
The page calls:
- `POST /api/v1/matches/compute`

Default API base URL is:
- `http://localhost:8000`

You can change API base URL from the top input field in the UI.
