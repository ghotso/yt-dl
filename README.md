# yt-dlp FLAC Downloader

A web-based application that enables authenticated users to download audio from YouTube videos in FLAC format. Built with Flask and modern UI components, featuring user-specific storage and download tracking.

## Features

- User authentication with session management
- Download YouTube audio in FLAC format
- Per-user download tracking and history
- User-specific download folders
- Mobile-friendly, responsive UI
- Detailed logging and error handling
- Docker container deployment
- GitHub Actions CI/CD integration

## Prerequisites

- Docker
- Docker Compose (optional, for development)

## Quick Start

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd flac-downloader
   ```

2. Build and run with Docker:
   ```bash
   docker build -t flac-downloader .
   docker run -p 5000:5000 -v $(pwd)/downloads:/app/downloads flac-downloader
   ```

3. Access the application at `http://localhost:5000`

4. Login with default credentials:
   - Username: `admin`
   - Password: `admin`

## Development Setup

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the development server:
   ```bash
   python app.py
   ```

## Environment Variables

- `SECRET_KEY`: Flask session secret key (default: 'your-secret-key-here')
- `DOWNLOAD_DIR`: Directory for storing downloads (default: 'downloads')

## Project Structure

```
.
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── Dockerfile         # Docker configuration
├── users.json         # User credentials store
├── downloads/         # Download directory
└── templates/         # HTML templates
    ├── base.html     # Base template
    ├── index.html    # Home page
    ├── login.html    # Login page
    └── status.html   # Download status page
```

## Adding Users

To add new users, modify the `users.json` file. Passwords should be hashed using bcrypt. You can use the Python REPL to generate password hashes:

```python
import bcrypt
password = "your_password".encode('utf-8')
hashed = bcrypt.hashpw(password, bcrypt.gensalt())
print(hashed.decode('utf-8'))
```

## Security Notes

- All passwords are hashed using bcrypt
- Session-based authentication
- User-specific download folders
- HTTPS recommended for production deployment

## License

MIT License - See LICENSE file for details 