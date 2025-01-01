# FLAC Downloader Wiki

## Pages Overview

### 1. Login Page (`/login`)
- **Purpose**: User authentication
- **Features**:
  - Username/password login form
  - Error message display
  - Redirect to home on success
- **Security**:
  - Session-based authentication
  - Bcrypt password hashing
  - Failed login attempt logging

### 2. Home Page (`/`)
- **Purpose**: Main download interface
- **Features**:
  - URL input form
  - Support for YouTube and Spotify URLs
  - Clear error/success messages
  - Mobile-responsive design
- **Notes**:
  - Validates URLs before processing
  - Redirects to status page after starting download

### 3. Status Page (`/status`)
- **Purpose**: Track download progress
- **Features**:
  - Real-time download status
  - Download history (7-day retention)
  - Error messages for failed downloads
  - Links to original URLs
- **Status Types**:
  - In Progress
  - Completed
  - Failed (with error details)

### 4. Profile Page (`/profile`)
- **Purpose**: User account management
- **Features**:
  - Change username
  - Change password
  - View account details
  - Admin panel access (for admin users)
- **Security**:
  - Current password verification
  - Username uniqueness check
  - Safe directory renaming

### 5. Admin Users Page (`/admin/users`)
- **Purpose**: User management for admins
- **Features**:
  - Create new users
  - Delete existing users
  - View all users
  - Cannot delete admin user
- **Access**: Admin only

## Common Elements

### Navigation Bar
- Present on all pages when logged in
- Links to:
  - Home
  - Status
  - Profile
  - Admin (if admin user)
  - Logout

### Flash Messages
- Success messages (green)
- Error messages (red)
- Temporary notifications
- Auto-dismiss after 5 seconds

### Dark Theme
- Modern dark color scheme
- High contrast text
- Mobile-responsive design
- Consistent across all pages

## Technical Details

### Download Process
1. URL submission
2. Title extraction
3. Format selection (FLAC with MP3 fallback)
4. Metadata embedding:
   - Title
   - Artist
   - Thumbnail/cover art
   - Lyrics (Spotify)
5. Status updates
6. User-specific storage

### File Management
- User-specific download folders
- Automatic folder management on username change
- 7-day retention for completed downloads
- Safe file naming

### Security Features
- Session-based authentication
- Bcrypt password hashing
- User isolation
- Admin privileges
- Safe file paths
- XSS protection

## API Endpoints

### Public Endpoints
- `GET /login` - Login page
- `POST /login` - Login submission

### Authenticated Endpoints
- `GET /` - Home page
- `GET /status` - Status page
- `POST /download` - Start download
- `GET /profile` - Profile page
- `POST /change_password` - Update password
- `POST /profile/update_username` - Update username

### Admin Endpoints
- `GET /admin/users` - User management
- `POST /admin/users/create` - Create user
- `POST /admin/users/delete/<username>` - Delete user
- `POST /admin/update_admin` - Update admin password (CLI only)

## Error Handling
- Invalid credentials
- Failed downloads
- File system errors
- Network issues
- Invalid URLs
- Permission issues 