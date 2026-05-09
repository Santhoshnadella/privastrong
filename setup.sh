#!/bin/bash
# Quick Setup Script for Image Provenance Tracking System
# This script automates the complete setup process

set -e  # Exit on error

echo "============================================================"
echo "Image Provenance Tracking System - Quick Setup"
echo "============================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check prerequisites
echo "Checking prerequisites..."

check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}✗ $1 is not installed${NC}"
        return 1
    else
        echo -e "${GREEN}✓ $1 is installed${NC}"
        return 0
    fi
}

MISSING_DEPS=0

check_command "docker" || MISSING_DEPS=1
check_command "docker-compose" || MISSING_DEPS=1
check_command "python3" || MISSING_DEPS=1

if [ $MISSING_DEPS -eq 1 ]; then
    echo -e "\n${RED}Missing required dependencies. Please install them first.${NC}"
    exit 1
fi

echo -e "\n${GREEN}All prerequisites met!${NC}\n"

# Create directory structure
echo "Creating directory structure..."
mkdir -p storage/{images,derivatives}
mkdir -p models
mkdir -p logs
mkdir -p ssl
echo -e "${GREEN}✓ Directories created${NC}"

# Setup environment
if [ ! -f .env ]; then
    echo -e "\n${YELLOW}Creating .env file from template...${NC}"
    cp .env.example .env
    
    # Generate random secrets
    SECRET_KEY=$(openssl rand -hex 32)
    JWT_SECRET=$(openssl rand -hex 32)
    DB_PASSWORD=$(openssl rand -hex 16)
    
    # Update .env with generated secrets
    sed -i "s/your_password_here/$DB_PASSWORD/g" .env
    sed -i "s/your-secret-key-here-change-in-production/$SECRET_KEY/g" .env
    sed -i "s/your-jwt-secret-here/$JWT_SECRET/g" .env
    
    echo -e "${GREEN}✓ Environment file created with random secrets${NC}"
    echo -e "${YELLOW}  Please review .env and update as needed${NC}"
else
    echo -e "${YELLOW}⚠ .env file already exists, skipping...${NC}"
fi

# Setup choice
echo -e "\nChoose setup method:"
echo "1) Docker (recommended - includes all services)"
echo "2) Manual (requires PostgreSQL and Redis installed)"
read -p "Enter choice [1-2]: " SETUP_CHOICE

if [ "$SETUP_CHOICE" == "1" ]; then
    echo -e "\n${GREEN}Setting up with Docker...${NC}"
    
    # Pull images
    echo "Pulling Docker images..."
    docker-compose pull
    
    # Start services
    echo "Starting services..."
    docker-compose up -d
    
    # Wait for database
    echo "Waiting for database to be ready..."
    sleep 10
    
    # Check health
    echo "Checking service health..."
    docker-compose ps
    
    echo -e "\n${GREEN}✓ Docker setup complete!${NC}"
    echo -e "\nServices available at:"
    echo "  API: http://localhost:8000"
    echo "  API Docs: http://localhost:8000/docs"
    echo "  Dashboard: http://localhost:8000/dashboard.html"
    echo "  Grafana: http://localhost:3000"
    echo "  Prometheus: http://localhost:9090"
    
elif [ "$SETUP_CHOICE" == "2" ]; then
    echo -e "\n${GREEN}Setting up manually...${NC}"
    
    # Check PostgreSQL
    if ! command -v psql &> /dev/null; then
        echo -e "${RED}✗ PostgreSQL is not installed${NC}"
        exit 1
    fi
    
    # Install Python dependencies
    echo "Installing Python dependencies..."
    pip install -r requirements.txt --break-system-packages
    
    # Setup database
    read -p "PostgreSQL database URL [postgresql://localhost/image_provenance]: " DB_URL
    DB_URL=${DB_URL:-postgresql://localhost/image_provenance}
    
    echo "Creating database..."
    createdb image_provenance 2>/dev/null || echo "Database already exists"
    
    echo "Loading schema..."
    psql $DB_URL < schema.sql
    
    # Update .env with database URL
    sed -i "s|DATABASE_URL=.*|DATABASE_URL=$DB_URL|g" .env
    
    echo -e "\n${GREEN}✓ Manual setup complete!${NC}"
    echo -e "\nTo start the API:"
    echo "  uvicorn api:app --reload"
    echo -e "\nTo start the worker:"
    echo "  python worker.py"
    
else
    echo -e "${RED}Invalid choice${NC}"
    exit 1
fi

# Run tests
echo -e "\n${YELLOW}Would you like to run tests? (y/n)${NC}"
read -p "> " RUN_TESTS

if [ "$RUN_TESTS" == "y" ]; then
    echo "Running test suite..."
    python test_system.py
fi

# Final instructions
echo -e "\n============================================================"
echo -e "${GREEN}Setup Complete!${NC}"
echo "============================================================"
echo ""
echo "Next steps:"
echo "1. Review and update .env file"
echo "2. Access API docs at http://localhost:8000/docs"
echo "3. Try the CLI: python cli.py --help"
echo "4. See README.md for detailed usage"
echo ""
echo "Quick test:"
echo "  python cli.py health"
echo ""
echo "To stop services:"
echo "  docker-compose down"
echo ""
echo "============================================================"
