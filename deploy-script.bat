@echo off
setlocal enabledelayedexpansion

echo 🚀 Knowledge Assistant Deployment Script
echo ========================================

REM Check if Docker is installed
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not installed. Please install Docker Desktop first.
    pause
    exit /b 1
)

docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Compose is not installed. Please install Docker Compose first.
    pause
    exit /b 1
)

echo [INFO] Docker and Docker Compose are installed ✓

REM Check if required files exist
if not exist "docker-compose.yml" (
    echo [ERROR] docker-compose.yml not found!
    pause
    exit /b 1
)

if not exist "api\Dockerfile" (
    echo [ERROR] api\Dockerfile not found!
    pause
    exit /b 1
)

if not exist "api\requirements.txt" (
    echo [ERROR] api\requirements.txt not found!
    pause
    exit /b 1
)

echo [INFO] All required files found ✓

REM Set up environment file
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo [INFO] Created .env from .env.example
        echo [WARNING] Please review and update .env file with your settings
    ) else (
        echo [WARNING] No .env or .env.example file found. Using default settings.
    )
) else (
    echo [INFO] Using existing .env file
)

REM Handle command line arguments
set "command=%~1"
if "%command%"=="" set "command=deploy"

if "%command%"=="deploy" goto :deploy
if "%command%"=="stop" goto :stop
if "%command%"=="restart" goto :restart
if "%command%"=="logs" goto :logs
if "%command%"=="status" goto :status
if "%command%"=="update" goto :update

echo Usage: %0 {deploy^|stop^|restart^|logs^|status^|update}
echo.
echo Commands:
echo   deploy   - Deploy the application (default)
echo   stop     - Stop all services
echo   restart  - Restart all services
echo   logs     - Show API logs
echo   status   - Show service status
echo   update   - Update and rebuild application
pause
exit /b 1

:deploy
echo [INFO] Building Docker images...
docker-compose build
if errorlevel 1 (
    echo [ERROR] Failed to build images
    pause
    exit /b 1
)

echo [INFO] Starting services...
docker-compose up -d
if errorlevel 1 (
    echo [ERROR] Failed to start services
    pause
    exit /b 1
)

echo [INFO] Waiting for services to start...
timeout /t 10 /nobreak >nul

echo [INFO] Testing deployment...
timeout /t 5 /nobreak >nul

REM Test if API is responding (simple check)
curl -f -s http://localhost:8000 >nul 2>&1
if errorlevel 1 (
    echo [WARNING] API might not be ready yet. Check logs with: docker-compose logs api
) else (
    echo [INFO] API is responding ✓
    echo.
    echo 🎉 Deployment successful!
    echo 📱 Access the application at: http://localhost:8000
)

goto :show_status

:stop
echo [INFO] Stopping services...
docker-compose down
echo [INFO] Services stopped ✓
goto :end

:restart
echo [INFO] Restarting services...
docker-compose restart
echo [INFO] Services restarted ✓
goto :end

:logs
docker-compose logs -f api
goto :end

:status
docker-compose ps
goto :end

:update
echo [INFO] Updating application...
docker-compose down
docker-compose build --no-cache
docker-compose up -d
echo [INFO] Application updated ✓
goto :end

:show_status
echo.
echo 📊 Service Status:
docker-compose ps

echo.
echo 📋 Useful Commands:
echo   View logs:           docker-compose logs -f api
echo   Stop services:       docker-compose down
echo   Restart services:    docker-compose restart
echo   Update application:  docker-compose up -d --build

:end
echo.
echo [INFO] Operation completed!
pause