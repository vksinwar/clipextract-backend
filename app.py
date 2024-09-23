# File: app.py

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl, validator
import yt_dlp
import os
import tempfile
import shutil
import re
import unicodedata
from typing import Generator

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DownloadRequest(BaseModel):
    url: HttpUrl

    @validator('url')
    def validate_url(cls, v):
        allowed_domains = [
            'instagram.com', 'youtube.com', 'youtu.be', 'facebook.com', 'fb.watch',
            'tiktok.com', 'twitter.com', 'vimeo.com', 'dailymotion.com', 'twitch.tv',
            'linkedin.com'
        ]
        if not any(domain in str(v).lower() for domain in allowed_domains):
            raise ValueError('URL must be from a supported platform')
        return v

def sanitize_filename(filename: str) -> str:
    filename = unicodedata.normalize('NFKD', filename).encode('ASCII', 'ignore').decode()
    filename = re.sub(r'[^\w\-.]', '_', filename)
    return filename if filename else 'video'

def generate_file(filename: str) -> Generator[bytes, None, None]:
    with open(filename, 'rb') as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            yield chunk

def cleanup(temp_dir: str):
    shutil.rmtree(temp_dir, ignore_errors=True)

@app.post("/download")
async def download_video(request: DownloadRequest, background_tasks: BackgroundTasks):
    temp_dir = tempfile.mkdtemp()
    try:
        ydl_opts = {
            'format': 'best',
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(str(request.url), download=True)
            video_title = sanitize_filename(info['title'])
            filename = ydl.prepare_filename(info)
            if not filename.endswith('.mp4'):
                new_filename = os.path.splitext(filename)[0] + '.mp4'
                os.rename(filename, new_filename)
                filename = new_filename
        
        background_tasks.add_task(cleanup, temp_dir)
        
        return StreamingResponse(
            generate_file(filename),
            media_type="video/mp4",
            headers={
                "Content-Disposition": f"attachment; filename={video_title}.mp4"
            }
        )
    except Exception as e:
        cleanup(temp_dir)
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)