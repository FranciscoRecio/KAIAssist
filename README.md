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
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the root directory with your configuration:
```
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=your_phone_number
OPENAI_API_KEY=your_api_key
KAYAKO_API_KEY=your_api_key
KAYAKO_BASE_URL=your_base_url
DEBUG=True
ENVIRONMENT=development
```

## Running the Application

1. Start the FastAPI server:
```bash
uvicorn src.main:app --reload
```

2. Set up ngrok for local development:
```bash
ngrok http 8000
```

3. Configure your Twilio webhook URL to point to your ngrok URL + `/api/twilio/webhook`

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