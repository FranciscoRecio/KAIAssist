# KAI Assist

KAI Assist is an AI-powered call center assistant that handles customer inquiries using natural language processing and integrates with existing support systems.

## Features

- Automated call handling with natural language understanding
- Integration with Twilio for voice calls
- Integration with Kayako for ticket management
- Speech-to-text and text-to-speech capabilities
- Multi-agent architecture for complex task handling

## Prerequisites

- Python 3.8+
- Twilio account and phone number
- OpenAI API access
- Kayako account and API access

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/kai-assist.git
cd kai-assist
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Unix or MacOS:
source venv/bin/activate
```

3. Install the package in development mode:
```bash
# Install dependencies
pip install -r requirements.txt
# Install the package in development mode
pip install -e .
```

4. Create a `.env` file in the root directory with your configuration:
```env
# Twilio settings
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=your_phone_number

# OpenAI settings
OPENAI_API_KEY=your_api_key

# Kayako settings
KAYAKO_API_KEY=your_api_key
KAYAKO_BASE_URL=your_base_url

# Application settings
DEBUG=True
ENVIRONMENT=development
```

## Running the Application

1. Make sure your virtual environment is activated:
```bash
# On Windows:
venv\Scripts\activate
# On Unix or MacOS:
source venv/bin/activate
```

2. Start the FastAPI server:
```bash
uvicorn src.main:app --reload
```

3. Set up ngrok for local development:
```bash
ngrok http 8000
```

4. Configure your Twilio webhook URL to point to your ngrok URL + `/api/twilio/webhook`

## Project Structure

```
kai_assist/
├── .env                  # Environment variables (not in version control)
├── .gitignore           # Git ignore file
├── requirements.txt     # Project dependencies
├── setup.py            # Package setup file
├── README.md           # This file
├── src/                # Source code
│   ├── main.py        # FastAPI application
│   ├── config/        # Configuration
│   ├── agents/        # AI agents
│   ├── api/           # API endpoints
│   ├── services/      # External services
│   └── utils/         # Utilities
└── tests/             # Test files
```

## Development

- The project follows a modular architecture with separate agents for different responsibilities
- Use the provided base agent class for creating new agents
- Follow the existing code style and patterns
- Add tests for new functionality

## Testing

Run the test suite:
```bash
pytest
```

## License

[MIT License](LICENSE)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request 