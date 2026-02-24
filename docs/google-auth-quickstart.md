# Google Auth Quickstart

## Backend setup
1. Set environment variable:
   - `GOOGLE_CLIENT_ID=your-google-oauth-client-id.apps.googleusercontent.com`
2. Apply migration:
   - `/Users/kaushha/Documents/careerops-1/infra/migrations/003_google_auth_users.sql`
3. Install dependencies from:
   - `/Users/kaushha/Documents/careerops-1/backend/requirements.txt`

## Endpoint
- `POST /api/v1/auth/google`

Request body:
```json
{
  "id_token": "google-id-token-from-frontend"
}
```

Response:
```json
{
  "access_token": "jwt",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "full_name": "User Name",
    "auth_provider": "google",
    "created_at": "timestamp"
  }
}
```

## Frontend integration flow
1. Use Google Identity Services in the browser to obtain `id_token`.
2. Send token to `POST /api/v1/auth/google`.
3. Store returned app JWT and include it as:
   - `Authorization: Bearer <jwt>`
4. Call `/api/v1/auth/me` to hydrate session state.
