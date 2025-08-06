# Claude Code Development Notes

## Environment Setup

### Virtual Environment
This project uses a Python virtual environment. Always activate it before running:
```bash
source venv/bin/activate
```

### Running the Application
```bash
source venv/bin/activate && python src/main.py
```

### Dependencies
All required dependencies are already installed in the virtual environment:
- feedparser
- requests
- tkinter (system package)

### Testing
To run tests, ensure virtual environment is active:
```bash
source venv/bin/activate
pytest tests/
```

### Linting
```bash
source venv/bin/activate
# Add appropriate linting command here
```

## Project Structure
- `src/` - Main application code
- `tests/` - Test files
- `venv/` - Virtual environment (do not modify)

## Important Notes
- This is a GUI application requiring a display environment ($DISPLAY)
- Always use the virtual environment to avoid dependency issues