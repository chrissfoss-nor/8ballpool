from setuptools import setup, find_packages

setup(
    name="8ballpool-backend",
    version="0.1.0",
    description="AI Backend for 8 Ball Pool Game",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    install_requires=[
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        "python-multipart>=0.0.6",
        "pydantic>=2.5.0",
        "numpy>=1.26.0",
        "websockets>=12.0",
    ],
)
