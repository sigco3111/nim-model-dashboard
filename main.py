from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import httpx
import asyncio
import time
from datetime import datetime
from typing import List, Optional
import os

app = FastAPI()

# Templates and Static Files
templates = Jinja2Templates(directory="templates")

# In-memory storage (Note: In production, use Redis or DB)
# Vercel Serverless: State is reset on each cold start, but persists during warm duration
global_state = {
    "api_key": None,
    "models_data": None,
    "last_check": None,
    "is_checking": False
}

class APIKeyRequest(BaseModel):
    api_key: str

class HealthCheckRequest(BaseModel):
    api_key: str

class ModelResult(BaseModel):
    model: str
    status: str
    response_time: float
    tokens_per_sec: float
    last_check: str
    error: str = ""

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/set-key")
async def set_api_key(data: APIKeyRequest):
    global global_state
    global_state["api_key"] = data.api_key
    return {"message": "API Key saved"}

@app.post("/api/clear-key")
async def clear_api_key():
    global global_state
    global_state["api_key"] = None
    return {"message": "API Key cleared"}

@app.get("/api/key-status")
async def get_key_status():
    global global_state
    return {"has_key": global_state["api_key"] is not None}

@app.get("/api/status")
async def get_status():
    global global_state
    return {
        "models_data": global_state["models_data"],
        "last_check": global_state["last_check"],
        "is_checking": global_state["is_checking"]
    }

@app.post("/api/check-models")
async def check_models(data: HealthCheckRequest):
    global global_state
    
    if global_state["is_checking"]:
        raise HTTPException(status_code=400, detail="Check already in progress")
    
    global_state["api_key"] = data.api_key
    global_state["is_checking"] = True
    global_state["models_data"] = None
    
    try:
        headers = {
            "Authorization": f"Bearer {data.api_key}",
            "Content-Type": "application/json"
        }
        
        # Step 1: Fetch model list
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.get("https://api.nvcf.nvidia.com/v2/nvcf/functions", headers=headers)
                if resp.status_code != 200:
                    raise HTTPException(status_code=400, detail=f"Failed to fetch models: {resp.text}")
                
                models_list = resp.json().get("functions", [])
                # Filter for NIM models (heuristic)
                nim_models = [m for m in models_list if "nvcf" in m.get("id", "").lower() or "nim" in m.get("name", "").lower()]
                if not nim_models:
                    nim_models = models_list
                
                total = len(nim_models)
                results = []
                
                # Step 2: Health check with limited concurrency
                semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests
                
                async def check_single_model(model):
                    async with semaphore:
                        model_id = model.get("id", "unknown")
                        model_name = model.get("name", model_id)
                        
                        try:
                            start = time.time()
                            payload = {
                                "model": model_id,
                                "messages": [{"role": "user", "content": "Hi"}],
                                "max_tokens": 1
                            }
                            
                            async with client.post(
                                f"https://api.nvcf.nvidia.com/v2/nvcf/pexec/functions/{model_id}",
                                headers=headers,
                                json=payload,
                                timeout=30
                            ) as model_resp:
                                duration = (time.time() - start) * 1000
                                
                                if model_resp.status_code == 200:
                                    resp_data = model_resp.json()
                                    content = resp_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                                    tokens = len(content.split()) if content else 0
                                    tokens_sec = tokens / (duration / 1000) if duration > 0 else 0
                                    
                                    return {
                                        "model": model_name,
                                        "status": "✅",
                                        "response_time": round(duration, 2),
                                        "tokens_per_sec": round(tokens_sec, 2),
                                        "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                        "error": ""
                                    }
                                else:
                                    return {
                                        "model": model_name,
                                        "status": "❌",
                                        "response_time": 0,
                                        "tokens_per_sec": 0,
                                        "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                        "error": f"HTTP {model_resp.status_code}"
                                    }
                        except Exception as e:
                            return {
                                "model": model_name,
                                "status": "❌",
                                "response_time": 0,
                                "tokens_per_sec": 0,
                                "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "error": str(e)
                            }
                
                # Run all checks
                tasks = [check_single_model(m) for m in nim_models]
                results = await asyncio.gather(*tasks)
                
                global_state["models_data"] = results
                global_state["last_check"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                global_state["is_checking"] = False
                
                return {"message": "Check completed", "count": len(results)}
                
            except httpx.TimeoutException:
                raise HTTPException(status_code=504, detail="Request timeout")
            except Exception as e:
                global_state["is_checking"] = False
                raise HTTPException(status_code=500, detail=str(e))
                
    except Exception as e:
        global_state["is_checking"] = False
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
