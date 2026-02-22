#!/bin/bash

echo "🚀 Setting up Pathway Smart Parking System..."

# Create virtual environment
echo "📦 Creating virtual environment..."
python -m venv venv

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Create logs directory
echo "📁 Creating logs directory..."
mkdir -p logs

# Copy environment file
if [ ! -f .env ]; then
    echo "📝 Creating .env file from .env.example..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your API keys and configuration"
else
    echo "✅ .env file already exists"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your Roboflow API key and configuration"
echo "2. Activate virtual environment: source venv/bin/activate"
echo "3. Run the application: python main.py"
echo ""
