#!/bin/bash

# Knowledge Assistant Deployment Script
set -e

echo "🚀 Knowledge Assistant Deployment Script"
echo "========================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    print_status "Docker and Docker Compose are installed ✓"
}

# Check if required files exist
check_files() {
    required_files=("docker-compose.yml" "api/Dockerfile" "api/requirements.txt")
    
    for file in "${required_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            print_error "Required file $file not found!"
            exit 1
        fi
    done
    
    print_status "All required files found ✓"
}

# Set up environment file
setup_env() {
    if [[ ! -f ".env" ]]; then
        if [[ -f ".env.example" ]]; then
            cp .env.example .env
            print_status "Created .env from .env.example"
            print_warning "Please review and update .env file with your settings"
        else
            print_warning "No .env or .env.example file found. Using default settings."
        fi
    else
        print_status "Using existing .env file"
    fi
}

# Build and start services
deploy() {
    print_status "Building Docker images..."
    docker-compose build
    
    print_status "Starting services..."
    docker-compose up -d
    
    # Wait for services to be ready
    print_status "Waiting for services to start..."
    sleep 10
    
    # Check if services are running
    if docker-compose ps | grep -q "Up"; then
        print_status "Services started successfully ✓"
    else
        print_error "Some services failed to start"
        docker-compose logs
        exit 1
    fi
}

# Test deployment
test_deployment() {
    print_status "Testing deployment..."
    
    # Wait a bit more for the API to be ready
    sleep 5
    
    # Test if API is responding
    if curl -f -s http://localhost:8000 > /dev/null; then
        print_status "API is responding ✓"
        echo ""
        echo "🎉 Deployment successful!"
        echo "📱 Access the application at: http://localhost:8000"
    else
        print_warning "API might not be ready yet. Check logs with: docker-compose logs api"
    fi
}

# Show status
show_status() {
    echo ""
    echo "📊 Service Status:"
    docker-compose ps
    
    echo ""
    echo "📋 Useful Commands:"
    echo "  View logs:           docker-compose logs -f api"
    echo "  Stop services:       docker-compose down"
    echo "  Restart services:    docker-compose restart"
    echo "  Update application:  docker-compose up -d --build"
}

# Main deployment process
main() {
    echo "Starting deployment process..."
    echo ""
    
    check_docker
    check_files
    setup_env
    deploy
    test_deployment
    show_status
    
    echo ""
    print_status "Deployment completed!"
}

# Handle script arguments
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "stop")
        print_status "Stopping services..."
        docker-compose down
        print_status "Services stopped ✓"
        ;;
    "restart")
        print_status "Restarting services..."
        docker-compose restart
        print_status "Services restarted ✓"
        ;;
    "logs")
        docker-compose logs -f api
        ;;
    "status")
        docker-compose ps
        ;;
    "update")
        print_status "Updating application..."
        docker-compose down
        docker-compose build --no-cache
        docker-compose up -d
        print_status "Application updated ✓"
        ;;
    *)
        echo "Usage: $0 {deploy|stop|restart|logs|status|update}"
        echo ""
        echo "Commands:"
        echo "  deploy   - Deploy the application (default)"
        echo "  stop     - Stop all services"
        echo "  restart  - Restart all services"
        echo "  logs     - Show API logs"
        echo "  status   - Show service status"
        echo "  update   - Update and rebuild application"
        exit 1
        ;;
esac