# Enterprise Features Implementation Plan

## Overview
Current Score: 6.5/10 (B)
Target Score: 9/10 (A)

---

## 1. API Authentication Enforcement

### Current State
- `api_key` setting exists in `config/settings.py`
- Not enforced on any endpoints
- Anyone can access the API

### Implementation Plan

#### Step 1: Create Auth Middleware
**File:** `pinterest_automation/api/auth.py` (new)

```python
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from pinterest_automation.config.settings import settings

class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip auth if no API key configured
        if not settings.api_key:
            return await call_next(request)
        
        # Skip auth for health check
        if request.url.path == "/health":
            return await call_next(request)
        
        # Check API key in header
        api_key = request.headers.get("X-API-Key")
        if api_key != settings.api_key:
            raise HTTPException(
                status_code=401,
                detail="Invalid or missing API key"
            )
        
        return await call_next(request)
```

#### Step 2: Register Middleware
**File:** `pinterest_automation/dashboard/app.py`

```python
from pinterest_automation.api.auth import APIKeyAuthMiddleware

app.add_middleware(APIKeyAuthMiddleware)
```

#### Step 3: Update Frontend to Send API Key
**File:** `pinterest-web/src/lib/api.ts`

```typescript
const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? ""

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      "X-API-Key": API_KEY,
      ...init?.headers,
    },
  })
  // ... rest of function
}
```

#### Step 4: Update .env Files
**File:** `.env.example`
```
API_KEY=your-secure-api-key-here
NEXT_PUBLIC_API_KEY=your-secure-api-key-here
```

### Testing
- [ ] Test with valid API key → 200 OK
- [ ] Test with invalid API key → 401 Unauthorized
- [ ] Test with no API key → 401 Unauthorized
- [ ] Test health endpoint without key → 200 OK

---

## 2. Rate Limiting

### Current State
- No rate limiting on any endpoints
- Vulnerable to abuse

### Implementation Plan

#### Step 1: Install slowapi
```bash
pip install slowapi
```

#### Step 2: Create Rate Limiter
**File:** `pinterest_automation/api/ratelimit.py` (new)

```python
from slowapi import Limiter
from slowapi.util import get_remote_address
from pinterest_automation.config.settings import settings

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],
    storage_uri="memory://",
)

# Custom limits per endpoint
UPLOAD_LIMIT = "10/minute"
PIPELINE_LIMIT = "2/minute"
READ_LIMIT = "200/minute"
```

#### Step 3: Apply to Endpoints
**File:** `pinterest_automation/api/rest.py`

```python
from pinterest_automation.api.ratelimit import limiter, UPLOAD_LIMIT, PIPELINE_LIMIT

@router.post("/uploads", status_code=201)
@limiter.limit(UPLOAD_LIMIT)
async def upload_images(request: Request, files: list[UploadFile] = File(...)):
    # ... existing code

@router.post("/pipeline/run")
@limiter.limit(PIPELINE_LIMIT)
def run_pipeline(request: Request):
    # ... existing code
```

#### Step 4: Add to FastAPI App
**File:** `pinterest_automation/dashboard/app.py`

```python
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from pinterest_automation.api.ratelimit import limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

### Rate Limits

| Endpoint | Limit | Purpose |
|----------|-------|---------|
| `/api/uploads` | 10/min | Prevent upload spam |
| `/api/pipeline/run` | 2/min | Prevent pipeline abuse |
| `/api/pins/*` (GET) | 200/min | Allow normal reads |
| `/api/pins/*` (POST/PATCH/DELETE) | 50/min | Allow normal writes |
| `/api/stats` | 100/min | Dashboard polling |
| `/api/analytics` | 30/min | Analytics refresh |

### Testing
- [ ] Test normal usage → 200 OK
- [ ] Test exceeding limit → 429 Too Many Requests
- [ ] Test retry-after header present
- [ ] Test different limits per endpoint

---

## 3. Health Check Endpoint

### Current State
- No health check endpoint
- No way to verify service status

### Implementation Plan

#### Step 1: Create Health Check Endpoint
**File:** `pinterest_automation/api/rest.py`

```python
@router.get("/health")
def health_check():
    """Health check endpoint for load balancers and monitoring."""
    health = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "checks": {}
    }
    
    # Check database
    try:
        with dbmod.get_session_factory()() as db:
            db.execute(text("SELECT 1"))
        health["checks"]["database"] = "ok"
    except Exception as e:
        health["status"] = "degraded"
        health["checks"]["database"] = f"error: {str(e)}"
    
    # Check Pinterest API token
    if settings.pinterest_access_token:
        health["checks"]["pinterest_api"] = "configured"
    else:
        health["checks"]["pinterest_api"] = "not_configured"
    
    # Check LLM providers
    if settings.llm_providers or settings.openrouter_api_key:
        health["checks"]["llm_providers"] = "configured"
    else:
        health["checks"]["llm_providers"] = "not_configured"
    
    return health
```

#### Step 2: Add Deep Health Check
**File:** `pinterest_automation/api/rest.py`

```python
@router.get("/health/ready")
def readiness_check():
    """Readiness probe - is the service ready to accept traffic?"""
    checks = {
        "database": False,
        "pinterest_api": bool(settings.pinterest_access_token),
        "llm_providers": bool(settings.llm_providers or settings.openrouter_api_key),
    }
    
    # Check database connectivity
    try:
        with dbmod.get_session_factory()() as db:
            db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        pass
    
    ready = all(checks.values())
    return {
        "ready": ready,
        "checks": checks,
    }
```

### Health Check Response
```json
{
  "status": "healthy",
  "timestamp": "2026-08-27T12:00:00Z",
  "version": "1.0.0",
  "checks": {
    "database": "ok",
    "pinterest_api": "configured",
    "llm_providers": "configured"
  }
}
```

### Testing
- [ ] Test `/api/health` returns 200
- [ ] Test `/api/health/ready` returns correct readiness
- [ ] Test with database down → status: "degraded"
- [ ] Test with missing API keys → checks show "not_configured"

---

## 4. React Error Boundaries

### Current State
- No error boundaries
- Unhandled errors crash the entire app

### Implementation Plan

#### Step 1: Create Error Boundary Component
**File:** `pinterest-web/src/components/error-boundary.tsx` (new)

```tsx
"use client"

import { Component, type ReactNode } from "react"

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("Error caught by boundary:", error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div className="flex min-h-[200px] flex-col items-center justify-center rounded-lg border border-destructive/20 bg-destructive/5 p-8 text-center">
          <svg
            className="h-12 w-12 text-destructive"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={1.5}
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
            />
          </svg>
          <h3 className="mt-4 text-lg font-semibold">Something went wrong</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            {this.state.error?.message || "An unexpected error occurred"}
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="mt-4 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            Try again
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
```

#### Step 2: Wrap Layout with Error Boundary
**File:** `pinterest-web/src/app/layout.tsx`

```tsx
import { ErrorBoundary } from "@/components/error-boundary"

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={...}>
      <body className="min-h-full flex flex-col">
        <ThemeProvider>
          <ErrorBoundary>
            <Nav />
            <main className="flex-1">{children}</main>
          </ErrorBoundary>
        </ThemeProvider>
      </body>
    </html>
  )
}
```

#### Step 3: Add Error Boundaries to Key Components
**File:** `pinterest-web/src/components/stat-cards.tsx`

```tsx
import { ErrorBoundary } from "@/components/error-boundary"

export function StatCards() {
  return (
    <ErrorBoundary>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {/* ... cards */}
      </div>
    </ErrorBoundary>
  )
}
```

#### Step 4: Add Error Page
**File:** `pinterest-web/src/app/error.tsx` (new)

```tsx
"use client"

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center px-6 text-center">
      <h2 className="text-2xl font-bold">Something went wrong</h2>
      <p className="mt-2 text-muted-foreground">{error.message}</p>
      <button
        onClick={reset}
        className="mt-6 rounded-lg bg-primary px-6 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
      >
        Try again
      </button>
    </div>
  )
}
```

### Error Boundary Coverage

| Component | Error Boundary | Priority |
|-----------|----------------|----------|
| Root Layout | ✅ | High |
| Dashboard Page | ✅ | High |
| Stat Cards | ✅ | Medium |
| Charts | ✅ | Medium |
| Activity Feed | ✅ | Medium |
| Pin Editor | ✅ | Medium |
| Upload Zone | ✅ | High |

### Testing
- [ ] Test component throws error → boundary catches it
- [ ] Test "Try again" button resets state
- [ ] Test fallback UI renders correctly
- [ ] Test error logged to console

---

## Implementation Order

| Phase | Feature | Effort | Impact |
|-------|---------|--------|--------|
| 1 | Health Check Endpoint | 1 hour | High |
| 2 | Rate Limiting | 2 hours | High |
| 3 | API Authentication | 2 hours | High |
| 4 | React Error Boundaries | 2 hours | Medium |

**Total Estimated Time:** 7 hours

---

## Priority Matrix

```
                    HIGH IMPACT
                         │
    ┌────────────────────┼────────────────────┐
    │                    │                    │
    │   Rate Limiting    │   API Auth         │
    │   Health Check     │                    │
    │                    │                    │
LOW ├────────────────────┼────────────────────┤ HIGH
EFFORT│                    │                    │ EFFORT
    │                    │                    │
    │                    │   Error Boundaries │
    │                    │                    │
    │                    │                    │
    └────────────────────┼────────────────────┘
                         │
                    LOW IMPACT
```

---

## Success Criteria

| Feature | Metric | Target |
|---------|--------|--------|
| API Auth | Unauthorized requests blocked | 100% |
| Rate Limiting | Requests over limit rejected | 100% |
| Health Check | Response time < 100ms | 99.9% |
| Error Boundaries | App crashes prevented | 100% |
| Overall Score | Enterprise grade | 9/10 |
