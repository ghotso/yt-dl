# 🎵 YouTube & Spotify FLAC Downloader

<div align="center">

[![GitHub license](https://img.shields.io/github/license/ghotso/ytdl-spotdl-manager)](https://github.com/ghotso/ytdl-spotdl-manager/blob/main/LICENSE)
[![Docker Image](https://img.shields.io/badge/docker-ghcr.io-blue?logo=docker)](https://github.com/ghotso/ytdl-spotdl-manager/pkgs/container/ytdl-spotdl-manager)
[![Container Version](https://img.shields.io/badge/version-latest-brightgreen)](https://github.com/ghotso/ytdl-spotdl-manager/pkgs/container/ytdl-spotdl-manager)
[![GitHub issues](https://img.shields.io/github/issues/ghotso/ytdl-spotdl-manager)](https://github.com/ghotso/ytdl-spotdl-manager/issues)
[![GitHub stars](https://img.shields.io/github/stars/ghotso/ytdl-spotdl-manager)](https://github.com/ghotso/ytdl-spotdl-manager/stargazers)

🎧 A beautiful web interface for downloading high-quality FLAC audio from YouTube and Spotify

<img src="docs/screenshot.png" alt="Screenshot" width="600"/>

</div>

## ✨ Features

### 🎵 Audio Downloads
- 🎼 FLAC format with automatic MP3 fallback
- 🎧 CD-quality audio (up to 1411kbps)
- 🎹 Embedded metadata and album art
- 🎸 Lyrics support for Spotify tracks

### 📥 Download Management
- 🔄 Queue system with priorities
- ⏸️ Pause/Resume downloads
- 🚄 Configurable speed limits
- 📊 Real-time progress tracking

### 👥 User Management
- 🔐 Multi-user support with authentication
- 📁 User-specific download folders
- 👤 Profile management
- 🛡️ Admin controls

### 🎨 Modern UI
- 🌙 Dark mode interface
- 📱 Mobile-friendly design
- 🔍 Track preview before download
- 📑 Batch upload support

## 🚀 Quick Start

1. Create data and downloads directories:
```bash
mkdir -p data downloads
```

2. Run with Docker:
```bash
docker pull ghcr.io/ghotso/ytdl-spotdl-manager:latest

docker run -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/downloads:/app/downloads \
  ghcr.io/ghotso/ytdl-spotdl-manager:latest
```

3. Access at `http://localhost:5000`

4. Login with default credentials:
- 👤 Username: `admin`
- 🔑 Password: `admin`

## 🛠️ Configuration

### Environment Variables
| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask session key | `your-secret-key-here` |
| `DOWNLOAD_DIR` | Download location | `downloads` |

### 📁 Directory Structure
```
.
├── data/                # Persistent data
│   ├── users.json      # User credentials
│   └── download_status.json  # Download history
└── downloads/          # Downloaded files
    ├── user1/         # User-specific folders
    └── user2/
```

## 🔒 Security Features

- 🔐 Session-based authentication
- 🔑 Bcrypt password hashing
- 📁 User isolation
- 🛡️ XSS protection
- 🔒 Safe file paths

## 🤝 Contributing

We love your input! Check out our:
- 🐛 [Bug Report Template](.github/ISSUE_TEMPLATE/bug_report.md)
- 💡 [Feature Request Template](.github/ISSUE_TEMPLATE/feature_request.md)
- 📚 [Contributing Guidelines](CONTRIBUTING.md)

## 📝 Common Issues

### Download fails with "Format not available"
- ✅ Solution: The app will automatically fall back to MP3 format
- 🔍 Check the status page for detailed error messages

### Speed limit not working
- ✅ Make sure to use numbers with decimals (e.g., 1.5)
- 🔄 Restart any active downloads after changing the limit

### Login issues
- ✅ Default credentials: admin/admin
- 🔑 Change password immediately after first login
- 📝 Check logs for authentication errors

## 📜 License

MIT License - See [LICENSE](LICENSE) file for details

---

<div align="center">
Made with ❤️ by contributors worldwide
</div> 
