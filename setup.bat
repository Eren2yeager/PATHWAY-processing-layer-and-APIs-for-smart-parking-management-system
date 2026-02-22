@echo off
echo 🚀 Setting up Pathway Smart Parking System...

REM Create virtual environment
echo 📦 Creating virtual environment...
python -m venv venv

REM Activate virtual environment
echo 🔌 Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo ⬆️  Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo 📥 Installing dependencies...
pip install -r requirements.txt

REM Create logs directory
echo 📁 Creating logs directory...
if not exist logs mkdir logs

REM Copy environment file
if not exist .env (
    echo 📝 Creating .env file from .env.example...
    copy .env.example .env
    echo ⚠️  Please edit .env file with your API keys and configuration
) else (
    echo ✅ .env file already exists
)

echo.
echo ✅ Setup complete!
echo.
echo Next steps:
echo 1. Edit .env file with your Roboflow API key and configuration
echo 2. Activate virtual environment: venv\Scripts\activate
echo 3. Run the application: python main.py
echo.
pause
