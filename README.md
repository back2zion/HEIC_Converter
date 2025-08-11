# 🖼️ HEIC Converter

Fast and secure web service for converting iPhone HEIC photos to universal formats (JPEG, PNG, BMP, WebP).

## ✨ Features

- **Fast Conversion**: GPU-accelerated processing with RTX 3090
- **Batch Processing**: Convert multiple files simultaneously  
- **Universal Formats**: JPEG, PNG, BMP, WebP support
- **Secure & Private**: Files auto-deleted after conversion
- **No File Size Limits**: Handle large photo collections
- **Drag & Drop Interface**: Simple and intuitive web UI

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/back2zion/HEIC_Converter.git
cd HEIC_Converter

# Install dependencies
pip install fastapi uvicorn python-multipart pillow pillow-heif

# Run the service
python app.py
```

### Usage

1. Open your browser and go to `http://localhost:8000`
2. Drag and drop your HEIC files or click to select
3. Choose output format (JPEG, PNG, BMP, WebP)
4. Adjust quality settings if needed
5. Click "Convert Files" and download results

## 📋 Requirements

- Python 3.9+
- FastAPI
- Pillow (PIL)
- pillow-heif
- uvicorn

## 🔧 API Endpoints

- `GET /` - Web interface
- `POST /convert/single` - Convert single file
- `POST /convert/batch` - Convert multiple files
- `GET /status/{job_id}` - Check conversion status
- `GET /download/{job_id}` - Download converted files
- `GET /health` - Service health check

## 🌐 Production Deployment

### Port Forwarding Setup
1. Configure router port forwarding for port 8000
2. Set up dynamic DNS (DuckDNS recommended)
3. Run server with `host="0.0.0.0"`

### Example Production Command
```bash
python app.py
# Access via: http://yourdomain.duckdns.org:8000
```

## 🔒 Security Features

- Rate limiting (20 conversions per IP daily)
- File type validation
- Automatic file cleanup
- Upload size limits (50MB per file)

## 🎯 Target Use Case

Perfect for iPhone users who need to organize photos on Windows computers or share images that require universal compatibility.

## 📊 Performance

- **Processing Speed**: ~2-10 seconds per file
- **Concurrent Files**: Up to 50 files per batch
- **Daily Capacity**: 10,000+ files
- **Supported Sizes**: Up to 50MB per file

## 🌏 Supported Languages

- English (Primary)
- Korean (한국어)

## 📝 License

MIT License - Feel free to use for personal and commercial projects.

## 🤝 Contributing

Contributions welcome! Please feel free to submit pull requests.

## ⚡ Hardware Requirements

- **Recommended**: RTX 3090 or similar GPU for optimal performance
- **Minimum**: Any system capable of running Python and PIL

## 📞 Support

For issues and questions, please create an issue in this repository.

---

**Made with ❤️ for iPhone users everywhere**
