from setuptools import setup, find_packages

setup(
    name="kai_assist",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi",
        "uvicorn",
        "twilio",
        "python-dotenv",
        "pydantic",
        "websockets",
    ],
    python_requires=">=3.8",
) 