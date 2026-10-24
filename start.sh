#!/bin/bash
# FinancePilot AI - Quick Start Script

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "🚀 FinancePilot AI - Starting up..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies if needed
if [ ! -f "venv/.installed" ]; then
    echo "📦 Installing Python dependencies..."
    pip install -r requirements.txt
    touch venv/.installed
fi

# Check for .env file
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Copying from .env.example..."
    cp .env.example .env
    echo "📝 Please edit .env and add your GEMINI_API_KEY"
    echo "   Then run this script again."
    exit 1
fi

# Check for Gemini API key
if grep -q "GEMINI_API_KEY=your_gemini_api_key_here" .env; then
    echo "⚠️  Please set your GEMINI_API_KEY in .env file"
    exit 1
fi

# Install frontend dependencies if needed
if [ ! -d "frontend/node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    cd frontend && npm install && cd ..
fi

echo "✅ Setup complete!"
echo ""
echo "To start the application:"
echo "  Terminal 1: make run-backend    (starts API on http://localhost:8000)"
echo "  Terminal 2: make run-frontend   (starts UI on http://localhost:5173)"
echo ""
echo "For full multi-agent mode (4 additional terminals):"
echo "  make run-orchestrator"
echo "  make run-quant-screener"
echo "  make run-risk-manager"
echo "  make run-deep-researcher"
echo ""
echo "Run tests: make test"
echo "View docs: open docs/architecture.md"