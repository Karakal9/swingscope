from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import logging
from pathlib import Path
from typing import Optional

# Setup directories
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Ensure templates directory exists
TEMPLATES_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

# Initialize FastAPI
app = FastAPI(title="SwingScope Analyzer")

# We will use Jinja2 for our HTML rendering
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

from fastapi.responses import PlainTextResponse
import traceback

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return PlainTextResponse(str(traceback.format_exc()), status_code=500)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the main landing page with the search bar."""
    return templates.TemplateResponse("index.html", {"request": request, "initial_ticker": ""})


@app.get("/report/{ticker}", response_class=HTMLResponse)
async def report_page(request: Request, ticker: str):
    """Serve the main landing page with a pre-filled ticker to analyze instantly."""
    return templates.TemplateResponse("index.html", {"request": request, "initial_ticker": ticker.upper()})


@app.post("/analyze", response_class=HTMLResponse)
async def analyze_api(request: Request, ticker: str = Form(...)):
    """Accept the ticker, run the pipeline, and return the generated HTML report."""
    from analyze import analyze_ticker
    import config as cfg

    ticker = ticker.upper().strip()
    
    # We will output the report to a temporary location to pass to the frontend
    output_dir = BASE_DIR / "reports" / "web"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Run the full pipeline!
        result = analyze_ticker(ticker, account_size=cfg.ACCOUNT_SIZE, output_dir=output_dir)
        
        if result is None:
             return HTMLResponse(content=f"<div class='error'>Error: Insufficient data or unable to fetch {ticker}.</div>", status_code=400)
             
        # The renderer in analyze.py creates an HTML file. We need to read it and send it back.
        report_path = Path(result["report"])
        if report_path.exists():
            with open(report_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            return HTMLResponse(content=html_content)
        else:
            return HTMLResponse(content="<div class='error'>Error: Report generation failed.</div>", status_code=500)
            
    except Exception as e:
        logging.exception(f"Error analyzing {ticker}")
        return HTMLResponse(content=f"<div class='error'>Error processing {ticker}: {str(e)}</div>", status_code=500)
