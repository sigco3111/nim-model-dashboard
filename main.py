from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
import httpx
import asyncio
import time
from datetime import datetime
from typing import List, Optional
import os

app = FastAPI()

# In-memory storage
global_state = {
    "api_key": None,
    "models_data": None,
    "last_check": None,
    "is_checking": False
}

# Read HTML file directly
def get_html_content():
    try:
        with open("templates/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"<html><body><h1>Error loading page: {e}</h1></body></html>"

@app.get("/", response_class=HTMLResponse)
async def read_root():
    return HTMLResponse(content=get_html_content())

@app.post("/api/set-key")
async def set_api_key(data: dict):
    global global_state
    api_key = data.get("api_key", "")
    global_state["api_key"] = api_key
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
async def check_models(data: dict):
    global global_state
    
    api_key = data.get("api_key", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key is required")
    
    if global_state["is_checking"]:
        raise HTTPException(status_code=400, detail="Check already in progress")
    
    global_state["api_key"] = api_key
    global_state["is_checking"] = True
    global_state["models_data"] = None
    
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Fetch model list
                resp = await client.get("https://api.nvcf.nvidia.com/v2/nvcf/functions", headers=headers)
                if resp.status_code != 200:
                    raise HTTPException(status_code=400, detail=f"Failed to fetch models: {resp.text}")
                
                models_list = resp.json().get("functions", [])
                
                # 모든 모델을 체크 (필터링 제거)
                # 필요시 특정 모델만 필터링: nim_models = [m for m in models_list if "llama" in m.get("id", "").lower()]
                nim_models = models_list
                
                total = len(nim_models)
                
                # Health check with limited concurrency
                semaphore = asyncio.Semaphore(3)  # 동시성 3 개로 줄임 (타임아웃 방지)
                
                async def check_single_model(model, client):
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
                                timeout=15
                            ) as model_resp:
                                duration = (time.time() - start) * 1000
                                
                                if model_resp.status_code == 200:
                                    resp_data = model_resp.json()  # await 제거 (httpx Response.json() is sync)
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
                        except asyncio.TimeoutError:
                            return {
                                "model": model_name,
                                "status": "❌",
                                "response_time": 0,
                                "tokens_per_sec": 0,
                                "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "error": "Timeout"
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
                
                # Run all checks with client passed as argument
                tasks = [check_single_model(m, client) for m in nim_models]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 에러 발생 시 예외 처리
                final_results = []
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        final_results.append({
                            "model": nim_models[i].get("name", nim_models[i].get("id", "unknown")),
                            "status": "❌",
                            "response_time": 0,
                            "tokens_per_sec": 0,
                            "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "error": f"Exception: {str(result)}"
                        })
                    else:
                        final_results.append(result)
                results = final_results
                
                global_state["models_data"] = results
                global_state["last_check"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                global_state["is_checking"] = False
                
                return {
                    "message": "Check completed", 
                    "count": len(results),
                    "models_data": results  # 결과를 바로 반환
                }
                
            except httpx.TimeoutException:
                raise HTTPException(status_code=504, detail="Request timeout")
            except Exception as e:
                global_state["is_checking"] = False
                raise HTTPException(status_code=500, detail=str(e))
                
    except Exception as e:
        global_state["is_checking"] = False
        raise HTTPException(status_code=500, detail=str(e))
