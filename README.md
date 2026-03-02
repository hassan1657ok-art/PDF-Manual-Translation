# 📄 PDF Manual Translation System

> A production-ready, containerized application for translating PDF documents while preserving their original formatting, layout, and styling.

[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://www.docker.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-Frontend-61DAFB?logo=react)](https://reactjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6?logo=typescript)](https://www.typescriptlang.org/)

---

## ✨ Features

- **📑 Format Preservation**: Maintains original PDF layout, fonts, colors, and styling during translation
- **🔄 Full-Page Translation**: Translates entire PDF pages rather than just extracting text
- **🎯 Visual Fidelity**: Produces translated PDFs that visually match the originals
- **🌐 Multi-Language Support**: Extensible architecture supports any language pair
- **🐳 Containerized Deployment**: Docker Compose setup for easy local and cloud deployment
- **⚡ Real-Time Progress Tracking**: WebSocket-based workflow status updates
- **📤 Drag & Drop Upload**: Intuitive interface for uploading PDF documents
- **🔍 Page-by-Page Preview**: Review individual pages before downloading
- **⚙️ Configurable**: Environment-based configuration for flexible deployment

---

## 🏗️ Architecture

This application follows a microservices architecture with three main components:

```
┌─────────────────────────────────────────────────────────────┐
│                      Client (Browser)                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │  Upload         │  │  Progress       │  │  Preview    │ │
│  │  Dashboard      │  │  Tracker        │  │  & Download │ │
│  └────────┬────────┘  └─────────────────┘  └─────────────┘ │
└───────────┼─────────────────────────────────────────────────┘
            │ HTTP/WebSocket
┌───────────▼─────────────────────────────────────────────────┐
│                   Nginx (Reverse Proxy)                     │
└───────────┬───────────────────────┬─────────────────────────┘
            │                       │
┌───────────▼──────────┐  ┌────────▼─────────┐
│   React Frontend     │  │   FastAPI        │
│   (Port 80/5173)     │  │   Backend        │
│                      │  │   (Port 8000)    │
│ • Vite + React 18    │  │                  │
│ • TypeScript         │  │ • PDF Upload     │
│ • Tailwind CSS       │  │ • Text Extraction│
│ • WebSocket Client   │  │ • Translation    │
│                      │  │ • PDF Rebuild    │
└──────────────────────┘  └────────┬─────────┘
                                   │
                          ┌────────▼─────────┐
                          │  Orchestrator    │
                          │  Service         │
                          └────────┬─────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
       ┌──────▼──────┐    ┌───────▼────────┐   ┌──────▼──────┐
       │  Extractor  │    │   Rebuilder    │   │   Gemini    │
       │  Service    │    │   Service      │   │   AI API    │
       └─────────────┘    └────────────────┘   └─────────────┘
```

### Backend Services

| Service | Description | Key Technologies |
|---------|-------------|------------------|
| **API Gateway** ([`main.py`](backend/main.py)) | FastAPI entry point, handles uploads/downloads | FastAPI, WebSockets |
| **Orchestrator** ([`orchestrator.py`](backend/orchestrator.py)) | Workflow coordination and progress tracking | Python asyncio |
| **Extractor** ([`extractor.py`](backend/extractor.py)) | PDF text and layout extraction | PyMuPDF, pdf2image |
| **Reconstructor** ([`reconstructor.py`](backend/reconstructor.py)) | PDF rebuilding with translated text | ReportLab, Pillow |

### Frontend Components

| Component | Purpose |
|-----------|---------|
| **UploadDashboard** ([`UploadDashboard.tsx`](frontend/src/components/UploadDashboard.tsx)) | PDF upload with drag & drop |
| **WorkflowTracker** ([`WorkflowTracker.tsx`](frontend/src/components/WorkflowTracker.tsx)) | Real-time progress visualization |
| **PagePreview** ([`PagePreview.tsx`](frontend/src/components/PagePreview.tsx)) | Individual page preview |
| **OutputViewer** ([`OutputViewer.tsx`](frontend/src/components/OutputViewer.tsx)) | Final output display and download |

---

## 🚀 Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (20.10+)
- [Docker Compose](https://docs.docker.com/compose/install/) (2.0+)
- [Git](https://git-scm.com/downloads)

### Running with Docker Compose

```bash
# Clone the repository
git clone https://github.com/hassan1657ok-art/PDF-Manual-Translation.git
cd PDF-Manual-Translation

# Start all services
docker-compose up --build

# Access the application
# Frontend: http://localhost:80
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Development Setup

#### Backend (Local)

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn main:app --reload --port 8000
```

#### Frontend (Local)

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Access at http://localhost:5173
```

---

## 📖 Usage Guide

### 1. Upload a PDF

- Navigate to the upload page
- Drag and drop your PDF file or click to browse
- Supported: PDF documents with embedded text or scanned images

### 2. Monitor Progress

Watch the real-time workflow tracker as the system:
1. **Extracts** text and layout from your PDF
2. **Translates** content using AI (Gemini API)
3. **Reconstructs** the PDF with translated text
4. **Finalizes** the output document

### 3. Preview & Download

- Review individual page previews
- Download the translated PDF
- Original formatting is preserved

---

## 🔧 Configuration

### Environment Variables

#### Backend ([`.env`](backend/.env))

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Google Gemini API key for translation | *(required)* |
| `UPLOAD_DIR` | Directory for uploaded files | `/tmp/uploads` |
| `OUTPUT_DIR` | Directory for translated outputs | `/tmp/output` |
| `MAX_FILE_SIZE` | Maximum upload file size (bytes) | `10485760` (10MB) |

#### Frontend ([`.env`](.env))

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_BASE_URL` | Backend API URL | `http://localhost:8000` |
| `VITE_WS_URL` | WebSocket URL for progress | `ws://localhost:8000` |

---

## 📁 Project Structure

```
PDF-Manual-Translation/
├── 📁 backend/                 # FastAPI backend service
│   ├── main.py                 # API entry point & routes
│   ├── orchestrator.py         # Workflow orchestration
│   ├── extractor.py            # PDF text/layout extraction
│   ├── reconstructor.py        # PDF rebuilding
│   ├── requirements.txt        # Python dependencies
│   ├── Dockerfile              # Backend container config
│   └── .env                    # Backend environment vars
│
├── 📁 frontend/                # React frontend application
│   ├── src/
│   │   ├── components/         # React components
│   │   │   ├── UploadDashboard.tsx
│   │   │   ├── WorkflowTracker.tsx
│   │   │   ├── PagePreview.tsx
│   │   │   └── OutputViewer.tsx
│   │   ├── App.tsx             # Main application
│   │   ├── api.ts              # API client
│   │   └── main.tsx            # Entry point
│   ├── package.json            # Node dependencies
│   ├── Dockerfile              # Frontend container config
│   └── nginx.conf              # Nginx reverse proxy config
│
├── docker-compose.yml          # Multi-service orchestration
├── .env                        # Global environment variables
└── README.md                   # This file
```

---

## 🛠️ Technology Stack

### Backend
- **FastAPI** - Modern, fast web framework for building APIs
- **Uvicorn** - ASGI server for running the application
- **PyMuPDF (fitz)** - PDF text and layout extraction
- **pdf2image** - Convert PDF pages to images
- **ReportLab** - PDF generation and manipulation
- **Pillow** - Image processing
- **WebSockets** - Real-time progress updates

### Frontend
- **React 18** - Component-based UI library
- **TypeScript** - Type-safe JavaScript
- **Vite** - Fast build tooling and dev server
- **Tailwind CSS** - Utility-first CSS framework
- **Axios** - HTTP client for API requests

### Infrastructure
- **Docker** - Containerization
- **Docker Compose** - Multi-container orchestration
- **Nginx** - Reverse proxy and static file serving

---

## 📝 API Documentation

When running locally, visit: http://localhost:8000/docs

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/upload` | Upload PDF file for translation |
| `GET` | `/api/v1/status/{job_id}` | Get translation job status |
| `GET` | `/api/v1/download/{job_id}` | Download translated PDF |
| `WS` | `/ws/{job_id}` | WebSocket for real-time progress |

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Built with ❤️ using [FastAPI](https://fastapi.tiangolo.com/) and [React](https://reactjs.org/)
- PDF processing powered by [PyMuPDF](https://pymupdf.readthedocs.io/) and [ReportLab](https://www.reportlab.com/)
- Translation powered by [Google Gemini AI](https://deepmind.google/technologies/gemini/)

---

## 💬 Support

If you encounter any issues or have questions:

1. Check the [Issues](https://github.com/hassan1657ok-art/PDF-Manual-Translation/issues) page
2. Create a new issue with detailed information
3. Include error messages, steps to reproduce, and your environment details

---

<p align="center">
  <sub>Built with care for translating documents across languages while preserving their soul.</sub>
</p>