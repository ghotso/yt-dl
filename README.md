# YouTube & Spotify FLAC Downloader

A web-based application that enables authenticated users to download audio from YouTube videos and Spotify tracks in FLAC format. Built with Flask and modern UI components, featuring user-specific storage and download tracking.

## Features

- Download from multiple sources:
  - YouTube videos to FLAC
  - Spotify tracks to FLAC
- User Management:
  - Multi-user support with authentication
  - User-specific download folders
  - Profile management (change username/password)
  - Admin interface for user management
- Modern Features:
  - Dark mode UI
  - Mobile-friendly responsive design
  - Real-time download status tracking
  - Download history with 7-day retention
- Security:
  - Session-based authentication
  - Bcrypt password hashing
  - User isolation

## Quick Start

1. Create data and downloads directories:
   ```bash
   mkdir -p data downloads
   ```

2. Run with Docker:
   ```bash
   docker pull ghcr.io/ghotso/ytdl-spotdl-flac:latest
   
   docker run -p 5000:5000 \
     -v $(pwd)/data:/app/data \
     -v $(pwd)/downloads:/app/downloads \
     ghcr.io/ghotso/ytdl-spotdl-flac:latest
   ```

3. Access the application at `http://localhost:5000`

4. Login with default credentials:
   - Username: `admin`
   - Password: `admin`

## Environment Variables

- `SECRET_KEY`: Flask session secret key (default: 'your-secret-key-here')
- `DOWNLOAD_DIR`: Directory for storing downloads (default: 'downloads')

## Security Notes

- Change the admin password immediately after first login
- Use HTTPS in production
- Keep your data directory secure
- Regular backups of the data directory are recommended

## Directory Structure

```
.
├── data/                # Persistent data
│   ├── users.json      # User credentials
│   └── download_status.json  # Download history
└── downloads/          # Downloaded files
    ├── user1/         # User-specific folders
    └── user2/
```

## User Management

### As Admin
- Access user management via the profile page
- Create new users
- Delete existing users
- Change admin password via UI or CLI

### As User
- Change username and password via profile page
- View personal download history
- Access user-specific download folder

## API Notes

For admin password updates via CLI:
```bash
curl -X POST http://localhost:5000/admin/update_admin \
  -H "Content-Type: application/json" \
  -d '{"password": "new_password"}'
```

## License

MIT License - See LICENSE file for details 