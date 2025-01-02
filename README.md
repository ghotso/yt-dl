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

## 🙏 Credits

This application is built upon and depends on these amazing open source projects:

- [**spotDL**](https://github.com/spotDL/spotify-downloader) - Download Spotify songs with metadata
- [**yt-dlp**](https://github.com/yt-dlp/yt-dlp) - Download YouTube videos and extract audio
- [**PlexAPI**](https://github.com/pkkid/python-plexapi) - Python bindings for the Plex API

We are grateful to the maintainers and contributors of these projects for making high-quality audio downloading possible.

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

### 🎨 Plex Integration
- 🎧 Add downloads directly to Plex playlists
- 📚 User-specific music library settings
- 🔄 Automatic library scanning
- ✅ Library validation

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

2. Create a `.env` file:
```bash
cp .env.example .env
```

3. Configure your environment:
```env
# Flask Configuration
SECRET_KEY=your-secret-key-here
DOWNLOAD_DIR=downloads

# Plex Configuration (optional)
PLEX_URL=http://your-plex-server:32400
PLEX_TOKEN=your-plex-token-here
```

4. Run with Docker:
```bash
docker pull ghcr.io/ghotso/ytdl-spotdl-manager:latest

docker run -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/downloads:/app/downloads \
  --env-file .env \
  ghcr.io/ghotso/ytdl-spotdl-manager:latest
```

5. Access at `http://localhost:5000`

6. Login with default credentials:
- 👤 Username: `admin`
- 🔑 Password: `admin`

## 🛠️ Configuration

### Environment Variables
| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask session key | `your-secret-key-here` |
| `DOWNLOAD_DIR` | Download location | `downloads` |
| `PLEX_URL` | Plex server URL | `None` |
| `PLEX_TOKEN` | Plex authentication token | `None` |

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

## 🤝 Plex Integration

1. Get your Plex token:
   - Sign in to Plex
   - View your account page
   - Copy the `X-Plex-Token` from any of the URLs

2. Configure Plex in `.env`:
   ```env
   PLEX_URL=http://your-plex-server:32400
   PLEX_TOKEN=your-plex-token
   ```

3. Each user can:
   - Set their preferred music library
   - Choose playlists for downloads
   - Validate library settings
   - Auto-add songs to playlists

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

### Plex integration not working
- ✅ Verify your Plex token is correct
- 🔍 Check if the music library name matches exactly
- 📝 Ensure Plex server is accessible from the container

## 📜 License

MIT License - See [LICENSE](LICENSE) file for details

---

<div align="center">
Made with ❤️ by contributors worldwide
</div> 
