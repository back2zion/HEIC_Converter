#!/usr/bin/env python3
"""
HEIC 변환 웹 서비스 - FastAPI
오늘 하루 만에 완성하는 MVP
"""

import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import List
import zipfile
import asyncio
from datetime import datetime

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
import uvicorn

# HEIC 변환 관련
from PIL import Image
from pillow_heif import register_heif_opener

# HEIC 지원 등록
register_heif_opener()

app = FastAPI(title="HEIC Converter API", version="1.0.0")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 임시 파일 저장 디렉토리
TEMP_DIR = Path("temp_files")
TEMP_DIR.mkdir(exist_ok=True)

# 변환 작업 상태 저장
conversion_status = {}

class HEICConverter:
    def __init__(self):
        self.supported_formats = ['jpeg', 'png', 'bmp', 'webp']
    
    def convert_file(self, input_path: Path, output_format: str = 'jpeg', quality: int = 90) -> Path:
        """단일 HEIC 파일 변환"""
        try:
            output_path = input_path.with_suffix(f'.{output_format}')
            
            with Image.open(input_path) as img:
                # JPEG의 경우 RGBA를 RGB로 변환
                if output_format.lower() in ['jpeg', 'jpg'] and img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                
                # 저장 옵션
                save_kwargs = {}
                if output_format.lower() in ['jpeg', 'jpg']:
                    save_kwargs = {'quality': quality, 'optimize': True}
                elif output_format.lower() == 'png':
                    save_kwargs = {'optimize': True}
                
                img.save(output_path, format=output_format.upper(), **save_kwargs)
                
            return output_path
            
        except Exception as e:
            raise Exception(f"변환 실패: {str(e)}")

converter = HEICConverter()

@app.get("/api")
async def root():
    return {"message": "HEIC Converter API is running!", "version": "1.0.0"}

@app.post("/convert/single")
async def convert_single_file(
    file: UploadFile = File(...),
    format: str = "jpeg",
    quality: int = 90
):
    """단일 파일 변환"""
    
    # 파일 형식 검증
    if not file.filename.lower().endswith(('.heic', '.heif')):
        raise HTTPException(status_code=400, detail="HEIC/HEIF 파일만 지원됩니다")
    
    if format not in converter.supported_formats:
        raise HTTPException(status_code=400, detail=f"지원되는 형식: {converter.supported_formats}")
    
    # 임시 파일 생성
    job_id = str(uuid.uuid4())
    temp_input = TEMP_DIR / f"{job_id}_input.heic"
    
    try:
        # 파일 저장
        with open(temp_input, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 변환 실행
        output_path = converter.convert_file(temp_input, format, quality)
        
        # 결과 반환
        return FileResponse(
            path=output_path,
            filename=f"{Path(file.filename).stem}.{format}",
            media_type=f"image/{format}"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # 임시 파일 정리
        if temp_input.exists():
            temp_input.unlink()

@app.post("/convert/batch")
async def convert_batch_files(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    format: str = "jpeg",
    quality: int = 90
):
    """배치 파일 변환"""
    
    if len(files) > 50:  # 한 번에 최대 50개 파일
        raise HTTPException(status_code=400, detail="최대 50개 파일까지 처리 가능합니다")
    
    job_id = str(uuid.uuid4())
    conversion_status[job_id] = {
        "status": "processing",
        "total": len(files),
        "completed": 0,
        "failed": 0,
        "start_time": datetime.now(),
        "result_file": None
    }
    
    # 백그라운드에서 변환 실행
    background_tasks.add_task(process_batch_conversion, job_id, files, format, quality)
    
    return {"job_id": job_id, "message": "배치 변환이 시작되었습니다"}

async def process_batch_conversion(job_id: str, files: List[UploadFile], format: str, quality: int):
    """배치 변환 백그라운드 작업"""
    
    job_dir = TEMP_DIR / job_id
    job_dir.mkdir(exist_ok=True)
    
    try:
        converted_files = []
        
        for i, file in enumerate(files):
            try:
                # 입력 파일 저장
                input_path = job_dir / f"input_{i}_{file.filename}"
                with open(input_path, "wb") as buffer:
                    content = await file.read()
                    buffer.write(content)
                
                # 변환 실행
                output_path = converter.convert_file(input_path, format, quality)
                converted_files.append(output_path)
                
                # 상태 업데이트
                conversion_status[job_id]["completed"] += 1
                
            except Exception as e:
                conversion_status[job_id]["failed"] += 1
                print(f"파일 변환 실패 {file.filename}: {e}")
        
        # ZIP 파일 생성
        if converted_files:
            zip_path = job_dir / f"converted_{job_id}.zip"
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for file_path in converted_files:
                    zipf.write(file_path, file_path.name)
            
            conversion_status[job_id]["status"] = "completed"
            conversion_status[job_id]["result_file"] = str(zip_path)
        else:
            conversion_status[job_id]["status"] = "failed"
            
    except Exception as e:
        conversion_status[job_id]["status"] = "failed"
        conversion_status[job_id]["error"] = str(e)

@app.get("/status/{job_id}")
async def get_conversion_status(job_id: str):
    """변환 상태 확인"""
    if job_id not in conversion_status:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
    
    return conversion_status[job_id]

@app.get("/download/{job_id}")
async def download_result(job_id: str):
    """변환 결과 다운로드"""
    if job_id not in conversion_status:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
    
    status = conversion_status[job_id]
    if status["status"] != "completed" or not status.get("result_file"):
        raise HTTPException(status_code=400, detail="변환이 완료되지 않았습니다")
    
    result_file = Path(status["result_file"])
    if not result_file.exists():
        raise HTTPException(status_code=404, detail="결과 파일을 찾을 수 없습니다")
    
    return FileResponse(
        path=result_file,
        filename=f"converted_files_{job_id}.zip",
        media_type="application/zip"
    )

@app.get("/health")
async def health_check():
    """서비스 상태 확인"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "temp_files": len(list(TEMP_DIR.glob("*"))),
        "active_jobs": len([j for j in conversion_status.values() if j["status"] == "processing"])
    }

# 홈페이지 라우트 추가
@app.get("/", response_class=HTMLResponse)
async def home():
    return """<!DOCTYPE html>
<html>
<head>
    <title>HEIC Converter</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .upload-area { border: 2px dashed #ccc; padding: 40px; text-align: center; margin: 20px 0; cursor: pointer; }
        .upload-area:hover, .upload-area.dragover { border-color: #007bff; background-color: #f8f9fa; }
        button { background-color: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; }
        button:hover { background-color: #0056b3; }
        button:disabled { background-color: #ccc; cursor: not-allowed; }
        .progress { background-color: #f0f0f0; border-radius: 5px; margin: 10px 0; }
        .progress-bar { background-color: #007bff; height: 20px; border-radius: 5px; width: 0%; transition: width 0.3s; }
        .result { margin: 20px 0; padding: 15px; background-color: #d4edda; border: 1px solid #c3e6cb; border-radius: 5px; }
    </style>
</head>
<body>
    <h1>🖼️ HEIC Converter</h1>
    <p>Convert your iPhone HEIC photos to JPEG, PNG, BMP, or WebP format</p>
    
    <div class="upload-area" id="uploadArea">
        <p>📁 Drag & drop HEIC files here or click to select</p>
        <input type="file" id="fileInput" multiple accept=".heic,.heif" style="display: none;">
        <button type="button" onclick="document.getElementById('fileInput').click()">Choose Files</button>
    </div>
    
    <div>
        <label>Output Format: </label>
        <select id="formatSelect">
            <option value="jpeg">JPEG</option>
            <option value="png">PNG</option>
            <option value="bmp">BMP</option>
            <option value="webp">WebP</option>
        </select>
        
        <label style="margin-left: 20px;">Quality (JPEG only): </label>
        <input type="range" id="qualitySlider" min="10" max="100" value="90">
        <span id="qualityValue">90</span>
    </div>
    
    <button onclick="convertFiles()" id="convertBtn" style="margin: 20px 0;" disabled>Convert Files</button>
    
    <div id="progress" style="display: none;">
        <div class="progress">
            <div class="progress-bar" id="progressBar"></div>
        </div>
        <p id="progressText">Processing...</p>
    </div>
    
    <div id="result" style="display: none;"></div>

    <script>
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');
        const formatSelect = document.getElementById('formatSelect');
        const qualitySlider = document.getElementById('qualitySlider');
        const qualityValue = document.getElementById('qualityValue');
        const convertBtn = document.getElementById('convertBtn');
        const progress = document.getElementById('progress');
        const progressBar = document.getElementById('progressBar');
        const progressText = document.getElementById('progressText');
        const result = document.getElementById('result');
        
        let selectedFiles = [];
        
        qualitySlider.oninput = function() {
            qualityValue.textContent = this.value;
        }
        
        uploadArea.addEventListener('click', () => fileInput.click());
        
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });
        
        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });
        
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            handleFiles(e.dataTransfer.files);
        });
        
        fileInput.addEventListener('change', (e) => {
            handleFiles(e.target.files);
        });
        
        function handleFiles(files) {
            selectedFiles = Array.from(files).filter(file => 
                file.name.toLowerCase().endsWith('.heic') || 
                file.name.toLowerCase().endsWith('.heif')
            );
            
            if (selectedFiles.length > 0) {
                uploadArea.innerHTML = `<p>✅ ${selectedFiles.length} HEIC files selected</p>`;
                convertBtn.disabled = false;
            } else {
                uploadArea.innerHTML = '<p>❌ No valid HEIC files found</p><br><button type="button" onclick="document.getElementById(\\'fileInput\\').click()">Choose Files</button>';
                convertBtn.disabled = true;
            }
        }
        
        async function convertFiles() {
            if (selectedFiles.length === 0) return;
            
            progress.style.display = 'block';
            result.style.display = 'none';
            convertBtn.disabled = true;
            
            try {
                if (selectedFiles.length === 1) {
                    const formData = new FormData();
                    formData.append('file', selectedFiles[0]);
                    formData.append('format', formatSelect.value);
                    formData.append('quality', qualitySlider.value);
                    
                    const response = await fetch('/convert/single', {
                        method: 'POST',
                        body: formData
                    });
                    
                    if (response.ok) {
                        const blob = await response.blob();
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = `converted.${formatSelect.value}`;
                        a.click();
                        window.URL.revokeObjectURL(url);
                        
                        result.innerHTML = '✅ File converted and downloaded!';
                        result.style.display = 'block';
                    } else {
                        throw new Error('Conversion failed');
                    }
                } else {
                    const formData = new FormData();
                    selectedFiles.forEach(file => formData.append('files', file));
                    formData.append('format', formatSelect.value);
                    formData.append('quality', qualitySlider.value);
                    
                    const response = await fetch('/convert/batch', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const data = await response.json();
                    pollStatus(data.job_id);
                }
            } catch (error) {
                result.innerHTML = '❌ Error: ' + error.message;
                result.style.display = 'block';
            }
            
            progress.style.display = 'none';
            convertBtn.disabled = false;
        }
        
        async function pollStatus(jobId) {
            const interval = setInterval(async () => {
                try {
                    const response = await fetch(`/status/${jobId}`);
                    const status = await response.json();
                    
                    const percent = Math.round((status.completed / status.total) * 100);
                    progressBar.style.width = percent + '%';
                    progressText.textContent = `Processing: ${status.completed}/${status.total} files (${percent}%)`;
                    
                    if (status.status === 'completed') {
                        clearInterval(interval);
                        progress.style.display = 'none';
                        
                        const a = document.createElement('a');
                        a.href = `/download/${jobId}`;
                        a.download = 'converted_files.zip';
                        a.click();
                        
                        result.innerHTML = '✅ All files converted and downloaded!';
                        result.style.display = 'block';
                    } else if (status.status === 'failed') {
                        clearInterval(interval);
                        result.innerHTML = '❌ Conversion failed';
                        result.style.display = 'block';
                    }
                } catch (error) {
                    clearInterval(interval);
                    result.innerHTML = '❌ Error checking status';
                    result.style.display = 'block';
                }
            }, 1000);
        }
    </script>
</body>
</html>"""

if __name__ == "__main__":
    print("🚀 HEIC Converter API 시작 중...")
    print("📍 웹 인터페이스: http://localhost:8000")
    print("📍 API 문서: http://localhost:8000/docs")
    print("📍 직접 접속: http://127.0.0.1:8000")
    
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)