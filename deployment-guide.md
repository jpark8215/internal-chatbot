# Knowledge Assistant Deployment Guide

## 🎯 What You Need
- Docker Desktop installed ([download here](https://www.docker.com/products/docker-desktop/))
- The deployment package (ZIP file)

---

## 🚀 Quick Deploy (Most Users)

### 1. Extract the Package
- Unzip `knowledge-assistant-deploy.zip`
- Open terminal/command prompt in the extracted folder

### 2. Run the Deployment Script
**Windows:**
```cmd
deploy-script.bat
```

**Linux/macOS:**
```bash
chmod +x deploy-script.sh
./deploy-script.sh
```

### 3. Access Your Application
- Open browser: http://localhost:8000
- Done! 🎉

---

## 📋 Daily Commands

| What You Want | Windows | Linux/macOS |
|---------------|---------|-------------|
| **Start** | `deploy-script.bat` | `./deploy-script.sh` |
| **Stop** | `deploy-script.bat stop` | `./deploy-script.sh stop` |
| **Restart** | `deploy-script.bat restart` | `./deploy-script.sh restart` |
| **View Logs** | `deploy-script.bat logs` | `./deploy-script.sh logs` |
| **Update** | `deploy-script.bat update` | `./deploy-script.sh update` |

---

## 🔧 If Something Goes Wrong

### Application Won't Start
```bash
# Check what's wrong
docker-compose logs

# Try rebuilding everything
docker-compose down
docker-compose up -d --build
```

### Port Already in Use
1. Open `docker-compose.yml`
2. Change `"8000:8000"` to `"8080:8000"`
3. Access at http://localhost:8080 instead

### Out of Disk Space
```bash
# Clean up Docker
docker system prune -a
```

### Permission Errors (Linux/macOS)
```bash
# Fix script permissions
chmod +x deploy-script.sh

# Fix Docker permissions
sudo usermod -aG docker $USER
# Then logout and login again
```

---

## 📦 Creating Deployment Packages

### For Package Creators (IT/DevOps)

#### Windows:
```powershell
# Automated (recommended)
.\create-deployment-package.ps1

# Manual
Compress-Archive -Path * -DestinationPath knowledge-assistant-deploy.zip -Force
```

#### Linux/macOS:
```bash
zip -r knowledge-assistant-deploy.zip . -x "*.git*" "*__pycache__*" "*.venv*"
```

#### What Gets Packaged:
- ✅ Application code (`api/`)
- ✅ Docker configuration (`docker-compose.yml`)
- ✅ Deployment scripts (`deploy-script.*`)
- ✅ Database setup (`db/`)
- ✅ Documentation
- ❌ Git history, cache files, logs

---

## 🏢 Advanced Deployment

### Manual Docker Commands
If scripts don't work, use these commands directly:

```bash
# Setup
cp .env.example .env

# Deploy
docker-compose up -d --build

# Check status
docker-compose ps

# View logs
docker-compose logs -f api

# Stop
docker-compose down
```

### Multiple Machines
1. **Small team**: Share ZIP file via email/network drive
2. **Large organization**: Use Git repository or network deployment
3. **Enterprise**: Use Docker registry or configuration management tools

### Production Setup
- Change default passwords in `.env`
- Set up SSL/HTTPS with reverse proxy
- Configure backups
- Set up monitoring
- Use external database for high availability

---

## 📁 File Structure
```
knowledge-assistant/
├── docker-compose.yml          # Main configuration
├── deploy-script.bat           # Windows deployment
├── deploy-script.sh            # Linux/macOS deployment
├── .env.example               # Settings template
├── api/                       # Application
│   ├── Dockerfile
│   ├── app.py
│   └── static/
└── db/                        # Database setup
    └── init_db.sql
```

---

## 🆘 Emergency Commands

```bash
# Stop everything now
docker-compose down

# Nuclear reset (deletes all data!)
docker-compose down -v

# Start fresh
docker-compose up -d --build

# Check what's running
docker-compose ps

# See live logs
docker-compose logs -f api
```

---

## 🌐 Access Points
- **Main App**: http://localhost:8000
- **Database**: localhost:5432 (postgres/postgres)
- **Health Check**: http://localhost:8000/health

---

## 💡 Tips
- Keep the deployment package in a safe place for re-deployment
- The database data persists between restarts
- Use `docker-compose logs api` to see application errors
- The application starts automatically when Docker starts

---

*Need help? Check the logs first: `docker-compose logs api`*